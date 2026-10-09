"""Scheduled traces retain complete request populations and explicit timing bases."""

from __future__ import annotations

import asyncio
import hashlib
import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.backends import BACKEND_REGISTRY
from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics
from chimeraforge.cli import app


class FakeBackend(Backend):
    name = "ollama"

    def __init__(self, **kwargs):
        self.closed = False
        self.calls = []
        self.first = True
        self.error = None
        self.health = True
        self.gate = None
        self.entered = asyncio.Event()
        self.active = 0
        self.maximum_active = 0

    async def health_check(self):
        return self.health, "PRIVATE PREFLIGHT PAYLOAD"

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "fixture-version"

    async def close(self):
        assert self.active == 0
        self.closed = True

    async def observe_serving(self, model):
        return {"backend": "ollama", "model": model, "device": "cpu", "version": "fixture"}

    async def generate(self, model, prompt, options=None):
        return RunMetrics(3, 100, 500, 520, 500, 30, ttft_basis="server-prefill-duration")

    async def generate_observed(self, model, prompt, options, on_first_output):
        from chimeraforge.bench.backends.base import GenerationObservation

        self.calls.append((model, prompt, options))
        self.active += 1
        self.maximum_active = max(self.active, self.maximum_active)
        try:
            if self.first:
                on_first_output()
            self.entered.set()
            if self.gate is not None:
                await self.gate.wait()
            if self.error is not None:
                raise self.error
            return GenerationObservation(
                {
                    "tokens_generated": 3,
                    "eval_duration_ms": 30,
                    "prompt_eval_duration_ms": 500,
                    "ttft_basis": "server-prefill-duration",
                },
                10,
                "server-decode-duration/output-token-count",
            )
        finally:
            self.active -= 1


@pytest.fixture
def backend(monkeypatch):
    instance = FakeBackend()
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", lambda **kwargs: instance)
    return instance


def requests():
    return [
        api.TraceRequest("first", "PRIVATE PROMPT alpha", 8, 0),
        api.TraceRequest("second", "PRIVATE PROMPT beta", 12, 0),
    ]


@pytest.mark.asyncio
async def test_absolute_arrival_wait_rechecks_early_event_loop_wakeup(monkeypatch):
    import chimeraforge.bench.trace as trace

    clock = [10.0]
    sleeps = []
    monkeypatch.setattr(trace, "_clock", lambda: clock[0])

    async def early_sleep(delay):
        sleeps.append(delay)
        clock[0] += delay / 2 if len(sleeps) == 1 else delay

    monkeypatch.setattr(trace.asyncio, "sleep", early_sleep)
    await trace._sleep_until(10.005)
    assert clock[0] >= 10.005 and len(sleeps) == 2


@pytest.mark.asyncio
async def test_actual_applied_prompts_caps_and_arrivals_are_bound_without_payloads(backend):
    rows = requests()
    report = (
        await api.replay_trace(rows, model="served", slos=api.TraceSLO(latency_ms=10000))
    ).to_dict()
    assert backend.closed and len(backend.calls) == 2 and backend.maximum_active == 1
    assert [row[1] for row in backend.calls] == [row.prompt for row in rows]
    assert [row[2]["num_predict"] for row in backend.calls] == [8, 12]
    assert report["execution"]["planned"] == report["execution"]["attempted"] == 2
    assert report["execution"]["completed"] == 2 and report["exit_code"] == 0
    encoded = json.dumps(report)
    assert "PRIVATE PROMPT" not in encoded and "PRIVATE PREFLIGHT" not in encoded
    assert report["workload"]["canonical_sha256"] and report["workload"]["raw_sha256"] is None
    assert (
        report["requests"][0]["descriptor"]["prompt_sha256"]
        == hashlib.sha256(rows[0].prompt.encode()).hexdigest()
    )
    assert report["requests"][0]["native"]["tokens_generated"] == 3
    assert report["requests"][0]["descriptor"]["max_output_tokens"] == 8


@pytest.mark.asyncio
async def test_queue_timing_and_goodput_include_all_scheduled_requests(backend, monkeypatch):
    import chimeraforge.bench.trace as trace

    clock = [10.0]
    monkeypatch.setattr(trace, "_clock", lambda: clock[0])
    backend.gate = asyncio.Event()
    task = asyncio.create_task(
        api.replay_trace(requests(), model="served", slos=api.TraceSLO(latency_ms=1500))
    )
    await backend.entered.wait()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    clock[0] = 12.0
    backend.gate.set()
    report = (await task).to_dict()
    first, second = report["requests"]
    assert second["timing"]["client_queue_ms"] == 2000
    assert first["timing"]["latency_ms"] == second["timing"]["latency_ms"] == 2000
    assert first["slo"]["joint"] == second["slo"]["joint"] == "breach"
    assert report["goodput"]["qualified_requests"] == 0
    assert report["goodput"]["horizon_seconds"] == 2
    assert report["goodput"]["requests_per_second"] == 0


@pytest.mark.asyncio
async def test_first_output_is_actual_client_observation_not_server_prefill(backend):
    report = (
        await api.replay_trace(requests(), model="served", slos=api.TraceSLO(first_output_ms=100))
    ).to_dict()
    first = report["requests"][0]
    assert first["timing"]["first_output_ms"] < 100
    assert first["native"]["prompt_eval_duration_ms"] == 500
    assert first["slo"]["joint"] == "pass"
    assert report["timing_bases"]["first_output_ms"] == "scheduled-arrival-to-client-first-output"


@pytest.mark.asyncio
async def test_unknown_first_output_cannot_pass_required_target(backend):
    backend.first = False
    report = (
        await api.replay_trace(requests(), model="served", slos=api.TraceSLO(first_output_ms=1000))
    ).to_dict()
    assert all(row["timing"]["first_output_ms"] is None for row in report["requests"])
    assert all(row["slo"]["joint"] == "unknown" for row in report["requests"])
    assert report["goodput"]["qualified_requests"] == 0


@pytest.mark.asyncio
async def test_no_targets_is_not_a_qualification_pass(backend):
    report = (await api.replay_trace(requests(), model="served")).to_dict()
    assert report["goodput"]["qualification"] == "not_requested"
    assert report["goodput"]["requests_per_second"] is None
    assert all(row["slo"]["joint"] == "not_requested" for row in report["requests"])


@pytest.mark.asyncio
async def test_failed_partial_requests_are_retained_and_exception_payload_is_private(backend):
    backend.error = ValueError("PRIVATE PROMPT alpha PRIVATE COMPLETION token=secret")
    report = (
        await api.replay_trace(requests(), model="served", slos=api.TraceSLO(latency_ms=1000))
    ).to_dict()
    assert report["execution"]["planned"] == report["execution"]["attempted"] == 2
    assert report["execution"]["partial"] == 2 and report["execution"]["completed"] == 0
    assert report["exit_code"] == 1 and backend.closed
    assert all(row["native"]["tokens_generated"] is None for row in report["requests"])
    assert all(row["error"]["type"] == "ValueError" for row in report["requests"])
    assert "PRIVATE" not in json.dumps(report) and "secret" not in json.dumps(report)


@pytest.mark.asyncio
async def test_preflight_failure_keeps_unattempted_population_without_payload(backend):
    backend.health = False
    report = (await api.replay_trace(requests(), model="served")).to_dict()
    assert report["execution"]["planned"] == report["execution"]["not_started"] == 2
    assert report["execution"]["attempted"] == 0 and report["exit_code"] == 1
    assert backend.closed and "PRIVATE" not in json.dumps(report)


@pytest.mark.asyncio
async def test_stop_event_cancels_active_queue_and_future_without_dropping_rows(backend):
    backend.gate = asyncio.Event()
    stop = asyncio.Event()
    rows = requests() + [api.TraceRequest("future", "future prompt", 8, 10)]
    task = asyncio.create_task(api.replay_trace(rows, model="served", stop_event=stop))
    await backend.entered.wait()
    await asyncio.sleep(0)
    stop.set()
    report = (await task).to_dict()
    assert report["execution"]["planned"] == 3 and len(report["requests"]) == 3
    assert report["execution"]["attempted"] == 1
    assert report["execution"]["cancelled"] == 2 and report["execution"]["not_started"] == 1
    assert report["goodput"]["horizon_seconds"] >= 10
    assert backend.closed and backend.active == 0 and report["exit_code"] == 1


@pytest.mark.asyncio
async def test_external_cancellation_propagates_after_reaping_and_closing(backend):
    backend.gate = asyncio.Event()
    task = asyncio.create_task(api.replay_trace(requests(), model="served"))
    await backend.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert backend.closed and backend.active == 0


@pytest.mark.asyncio
async def test_whole_trace_deadline_retains_active_and_unstarted_rows(backend):
    backend.gate = asyncio.Event()
    report = (
        await api.replay_trace(requests(), model="served", trace_timeout=0.03, request_timeout=1)
    ).to_dict()
    assert report["stop_reason"] == "trace_deadline"
    assert len(report["requests"]) == 2 and backend.closed and report["exit_code"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"request_id": ""},
        {"prompt": ""},
        {"max_output_tokens": True},
        {"max_output_tokens": 0},
        {"max_output_tokens": 32769},
        {"arrival_offset_s": -1},
        {"arrival_offset_s": float("nan")},
        {"arrival_offset_s": True},
    ],
)
@pytest.mark.asyncio
async def test_invalid_requests_refused_before_backend_construction(backend, changes):
    row = {"request_id": "one", "prompt": "prompt", "max_output_tokens": 8, "arrival_offset_s": 0}
    with pytest.raises(api.PlanError):
        await api.replay_trace([api.TraceRequest(**{**row, **changes})], model="served")
    assert not backend.calls and not backend.closed


@pytest.mark.asyncio
async def test_duplicate_ids_and_unbounded_population_refused(backend):
    for rows in ([requests()[0], requests()[0]], requests() * 513):
        with pytest.raises(api.PlanError):
            await api.replay_trace(rows, model="served")
    assert not backend.calls and not backend.closed


@pytest.mark.asyncio
async def test_json_raw_and_canonical_hashes_and_source_immutability(tmp_path, backend):
    rows = [
        {
            "request_id": "one",
            "prompt": "PRIVATE PROMPT",
            "max_output_tokens": 8,
            "arrival_offset_s": 0,
        }
    ]
    path = tmp_path / "trace.json"
    original = json.dumps(rows).encode()
    path.write_bytes(original)
    report = await api.replay_trace(path, model="served")
    data = report.to_dict()
    assert data["workload"]["raw_sha256"] == hashlib.sha256(original).hexdigest()
    path.write_text(json.dumps(rows, indent=2))
    second = (await api.replay_trace(path, model="served")).to_dict()
    assert data["workload"]["canonical_sha256"] == second["workload"]["canonical_sha256"]
    assert data["workload"]["raw_sha256"] != second["workload"]["raw_sha256"]
    with pytest.raises(api.PlanError, match="replace"):
        report.save(path)


@pytest.mark.parametrize("raw", ["{}", "null", '[{"prompt":"private"}]', "[]"])
def test_cli_malformed_trace_returns_clean_json_exit2(tmp_path, raw):
    path = tmp_path / "trace.json"
    path.write_text(raw)
    result = CliRunner().invoke(app, ["trace", str(path), "--model", "served", "--json"])
    assert result.exit_code == 2 and json.loads(result.output)["error"]


def test_cli_writes_defensive_receipt_without_overwriting_workload(tmp_path, backend):
    path, out = tmp_path / "trace.json", tmp_path / "receipt.json"
    raw = '[{"request_id":"one","prompt":"private","max_output_tokens":8,"arrival_offset_s":0}]'
    path.write_text(raw)
    result = CliRunner().invoke(
        app, ["trace", str(path), "--model", "served", "--json", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == json.loads(out.read_text()) and path.read_text() == raw
    alias = CliRunner().invoke(
        app, ["trace", str(path), "--model", "served", "--json", "--out", str(path)]
    )
    assert alias.exit_code == 2 and path.read_text() == raw


@pytest.mark.asyncio
async def test_real_ollama_first_frame_observed_before_delayed_final_metrics():
    import httpx
    from chimeraforge.bench.backends.ollama import OllamaBackend

    first, finish = asyncio.Event(), asyncio.Event()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"response":"private completion","done":false}\n'
            await finish.wait()
            yield (
                b'{"done":true,"eval_count":2,"eval_duration":20000000,'
                b'"prompt_eval_duration":500000000}\n'
            )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Stream()))
    )
    real = OllamaBackend()
    real._client = client
    task = asyncio.create_task(
        real.generate_observed("served", "private prompt", {"num_predict": 8}, first.set)
    )
    try:
        await asyncio.wait_for(first.wait(), 1)
        assert not task.done()
    finally:
        finish.set()
        result = await task
        await real.close()
    assert result.native["tokens_generated"] == 2
    assert result.native["prompt_eval_duration_ms"] == 500
    assert result.mean_tpot_ms == 10
    assert client.is_closed


@pytest.mark.asyncio
async def test_failed_terminal_client_latency_stays_known(backend):
    backend.error = ValueError("private output")
    report = (await api.replay_trace(requests(), model="served")).to_dict()
    assert all(row["timing"]["latency_ms"] is not None for row in report["requests"])
    assert all(row["state"] == "partial" for row in report["requests"])


@pytest.mark.parametrize(
    "payload",
    [
        b'{"response":"private completion","done":false}\n',
        b'{"response":"private completion","done":false}\nnot json',
    ],
)
@pytest.mark.asyncio
async def test_real_ollama_incomplete_or_invalid_stream_preserves_partial_count_unknown(
    monkeypatch, payload
):
    import httpx
    from chimeraforge.bench.backends.ollama import OllamaBackend

    def handler(request):
        if request.url.path == "/":
            return httpx.Response(200, text="Ollama is running")
        if request.url.path == "/api/show":
            return httpx.Response(200, json={})
        if request.url.path == "/api/generate":
            return httpx.Response(200, content=payload)
        return httpx.Response(200, json={})

    real = OllamaBackend()
    real._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", lambda **kwargs: real)
    report = (await api.replay_trace(requests(), model="served")).to_dict()
    assert report["execution"]["partial"] == 2 and real._client.is_closed
    assert all(row["native"]["tokens_generated"] is None for row in report["requests"])
    assert "private" not in json.dumps(report) and report["exit_code"] == 1


@pytest.mark.asyncio
async def test_request_timeout_is_recorded_with_queue_and_partial_coverage(backend):
    backend.gate = asyncio.Event()
    report = (
        await api.replay_trace(
            requests(),
            model="served",
            request_timeout=0.02,
            trace_timeout=1,
            slos=api.TraceSLO(latency_ms=1000),
        )
    ).to_dict()
    assert report["execution"]["partial"] == 2 and report["execution"]["attempted"] == 2
    assert all(row["error"]["type"] == "TimeoutError" for row in report["requests"])
    assert report["requests"][1]["timing"]["client_queue_ms"] > 0
    assert report["goodput"]["qualified_requests"] == 0 and backend.closed


@pytest.mark.asyncio
async def test_plugin_mean_basis_is_not_upgraded_to_known_builtin_timing(backend, monkeypatch):
    monkeypatch.setitem(BACKEND_REGISTRY, "custom", lambda **kwargs: backend)
    report = (
        await api.replay_trace(
            requests(),
            model="served",
            backend="custom",
            slos=api.TraceSLO(tpot_ms=100),
        )
    ).to_dict()
    assert all(row["mean_tpot_ms"] is None for row in report["requests"])
    assert all(row["slo"]["joint"] == "unknown" for row in report["requests"])


@pytest.mark.asyncio
async def test_legacy_generation_capability_has_unknown_first_output(backend, monkeypatch):
    monkeypatch.setattr(backend, "generate_observed", Backend.generate_observed.__get__(backend))
    report = (
        await api.replay_trace(
            requests(),
            model="served",
            slos=api.TraceSLO(first_output_ms=10000),
        )
    ).to_dict()
    assert all(row["native"]["ttft_ms"] == 500 for row in report["requests"])
    assert all(row["timing"]["first_output_ms"] is None for row in report["requests"])
    assert all(row["slo"]["joint"] == "unknown" for row in report["requests"])


@pytest.mark.parametrize(
    "options",
    [
        {"concurrency": True},
        {"concurrency": 65},
        {"request_timeout": 0},
        {"trace_timeout": float("inf")},
        {"base_url": "file:///private"},
        {"base_url": "http://"},
        {"slos": "not typed"},
        {"slos": None, "trace_timeout": -1},
    ],
)
@pytest.mark.asyncio
async def test_invalid_execution_options_fail_before_contact(backend, options):
    with pytest.raises(api.PlanError):
        await api.replay_trace(requests(), model="served", **options)
    assert not backend.calls and not backend.closed


@pytest.mark.asyncio
async def test_receipt_fingerprint_defensive_copy_and_url_credentials(backend):
    from chimeraforge.planner.replay import digest

    receipt = await api.replay_trace(
        requests(), model="served", base_url="http://user:password@localhost:11434/?token=private"
    )
    report = receipt.to_dict()
    assert report["endpoint"] == "http://localhost:11434/"
    fingerprint = report.pop("fingerprint")
    assert digest(report) == fingerprint
    report["execution"]["planned"] = 0
    assert receipt.to_dict()["execution"]["planned"] == 2


@pytest.mark.parametrize(
    "raw",
    [
        '[{"request_id":"a","prompt":"x","prompt":"y","max_output_tokens":8,"arrival_offset_s":0}]',
        '[{"request_id":"a","prompt":"x","max_output_tokens":8,"arrival_offset_s":0,"extra":true}]',
    ],
)
def test_duplicate_or_extra_json_fields_refused(tmp_path, raw):
    path = tmp_path / "trace.json"
    path.write_text(raw)
    result = CliRunner().invoke(app, ["trace", str(path), "--model", "served", "--json"])
    assert result.exit_code == 2 and json.loads(result.output)["error"]


@pytest.mark.asyncio
async def test_installed_trace_consumer_source_protocol_and_adversarial_validator(
    tmp_path, backend, monkeypatch
):
    """Source-only real command wiring with the already imported parent helper patched."""
    import importlib.util
    from pathlib import Path
    from chimeraforge.planner.replay import digest

    path = Path(__file__).resolve().parents[1] / "scripts" / "ci_cpu_trace.py"
    spec = importlib.util.spec_from_file_location("ci_cpu_trace_test", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    workload = [
        {
            "request_id": "one",
            "prompt": "private alpha",
            "max_output_tokens": 8,
            "arrival_offset_s": 0,
        },
        {
            "request_id": "two",
            "prompt": "private beta",
            "max_output_tokens": 12,
            "arrival_offset_s": 0,
        },
    ]
    source = tmp_path / "trace.json"
    raw = json.dumps(workload).encode()
    source.write_bytes(raw)
    report = (await api.replay_trace(source, model="served", slos=api.TraceSLO(1, 1, 1))).to_dict()
    script.validate(report, workload, raw, "served", "fixture")
    for retained in ([], report["requests"][:1]):
        invalid = json.loads(json.dumps(report))
        invalid["requests"] = retained
        qualified = sum(row["slo"]["joint"] == "pass" for row in retained)
        invalid["goodput"]["qualified_requests"] = qualified
        invalid["goodput"]["requests_per_second"] = (
            qualified / invalid["goodput"]["horizon_seconds"]
        )
        invalid["fingerprint"] = digest({k: v for k, v in invalid.items() if k != "fingerprint"})
        with pytest.raises(AssertionError):
            script.validate(invalid, workload, raw, "served", "fixture")
    for key in ("first_output_ms", "client_queue_ms"):
        invalid = json.loads(json.dumps(report))
        invalid["requests"][0]["timing"][key] = 9999
        invalid["fingerprint"] = digest({k: v for k, v in invalid.items() if k != "fingerprint"})
        with pytest.raises(AssertionError):
            script.validate(invalid, workload, raw, "served", "fixture")


def test_installed_trace_consumer_commands_source_protocol(tmp_path, backend, monkeypatch):
    """Source CLI wiring, not an installed distribution or actual CPU server proof."""
    import importlib.util
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    path = Path(__file__).resolve().parents[1] / "scripts" / "ci_cpu_trace.py"
    spec = importlib.util.spec_from_file_location("ci_cpu_trace_protocol", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    def run_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == expected_code, result.output
        return result.output

    monkeypatch.setitem(sys.modules, "ci_installed_acceptance", SimpleNamespace(run_cli=run_cli))
    receipt = script.accept(tmp_path, {}, "served", "http://localhost:11434", "fixture")
    assert receipt["source_bytes_unchanged"] and receipt["output_alias_refused"]


def test_public_trace_type_introspection():
    from typing import get_type_hints

    assert get_type_hints(api.replay_trace)["return"] is api.TraceReplay


@pytest.mark.asyncio
async def test_model_only_generation_failure_preserves_failed_population(backend):
    backend.first = False
    backend.error = RuntimeError("private completion")
    report = (await api.replay_trace(requests(), model="served", slos=api.TraceSLO(1000))).to_dict()
    assert report["execution"]["failed"] == 2 and report["execution"]["partial"] == 0
    assert report["goodput"]["qualified_requests"] == 0
    assert all(row["times"]["terminal_s"] is not None for row in report["requests"])


@pytest.mark.asyncio
async def test_actual_ollama_missing_final_native_counts_remain_unknown(monkeypatch):
    import httpx
    from chimeraforge.bench.backends.ollama import OllamaBackend

    real = OllamaBackend()

    def handler(request):
        if request.url.path == "/":
            return httpx.Response(200, text="Ollama is running")
        if request.url.path == "/api/generate":
            return httpx.Response(
                200, content=b'{"response":"hello","done":false}\n{"done":true}\n'
            )
        return httpx.Response(200, json={})

    real._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", lambda **kwargs: real)
    report = (
        await api.replay_trace(requests(), model="served", slos=api.TraceSLO(tpot_ms=100))
    ).to_dict()
    assert report["execution"]["completed"] == 2
    assert all(row["native"]["tokens_generated"] is None for row in report["requests"])
    assert all(row["slo"]["joint"] == "unknown" for row in report["requests"])
    assert real._client.is_closed


@pytest.mark.parametrize("stopped", [False, True])
@pytest.mark.asyncio
async def test_no_replay_origin_cannot_claim_observed_zero_goodput(backend, stopped):
    backend.health = False
    stop = asyncio.Event()
    if stopped:
        stop.set()
    report = (
        await api.replay_trace(
            [api.TraceRequest("future", "private", 8, 10)],
            model="served",
            slos=api.TraceSLO(latency_ms=100),
            stop_event=stop,
        )
    ).to_dict()
    assert report["clock"]["origin"] is None
    assert report["goodput"]["requests_per_second"] is None
    assert report["goodput"]["horizon_seconds"] is None
    assert report["goodput"]["planned_horizon_seconds"] == 10
    assert report["goodput"]["qualification"] == "unavailable"


@pytest.mark.parametrize("phase", ["health", "model", "metadata_before", "metadata_after"])
@pytest.mark.asyncio
async def test_graceful_stop_cancels_and_drains_setup_and_metadata(backend, phase):
    entered, drained, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    async def blocking():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    async def health():
        calls.append("health")
        if phase == "health":
            await blocking()
        return True, ""

    async def model(_):
        calls.append("model")
        if phase == "model":
            await blocking()
        return True, ""

    async def metadata(_):
        name = "metadata_after" if "metadata_before" in calls else "metadata_before"
        calls.append(name)
        if phase == name:
            await blocking()
        return {"backend": "ollama", "model": "served", "version": "fixture"}

    backend.health_check, backend.check_model, backend.observe_serving = health, model, metadata
    task = asyncio.create_task(api.replay_trace(requests(), model="served", stop_event=stopped))
    await asyncio.wait_for(entered.wait(), 1)
    stopped.set()
    report = (await asyncio.wait_for(task, 0.5)).to_dict()
    assert (
        drained.is_set() and backend.closed and report["resource_cleanup"]["state"] == "completed"
    )
    assert report["stop_reason"] == "cancelled" and report["exit_code"] == 1
    assert calls[-1] == phase
    expected = 2 if phase == "metadata_after" else 0
    assert report["execution"]["completed"] == report["execution"]["attempted"] == expected
    assert report["execution"]["not_started"] == 2 - expected


@pytest.mark.parametrize("metadata", [False, True])
@pytest.mark.asyncio
async def test_setup_probe_timeout_is_operational_with_closed_unstarted_population(
    backend, metadata
):
    drained = asyncio.Event()

    async def hanging(*_):
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    if metadata:
        backend.observe_serving = hanging
    else:
        backend.health_check = hanging
    report = (await api.replay_trace(requests(), model="served", request_timeout=0.02)).to_dict()
    assert report["error"] == {
        "stage": "metadata_before" if metadata else "preflight",
        "type": "TimeoutError",
    }
    assert drained.is_set() and backend.closed and report["clock"]["origin"] is None
    assert report["execution"]["not_started"] == 2 and report["exit_code"] == 1


@pytest.mark.asyncio
async def test_external_setup_cancellation_propagates_after_owned_probe_drained(backend):
    entered, drained = asyncio.Event(), asyncio.Event()

    async def hanging():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    backend.health_check = hanging
    owned_before = set(asyncio.all_tasks())
    task = asyncio.create_task(api.replay_trace(requests(), model="served"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert drained.is_set() and backend.closed
    assert not (set(asyncio.all_tasks()) - owned_before)


@pytest.mark.parametrize("when", ["metadata_after", "after_return", "next_loop_turn"])
@pytest.mark.asyncio
async def test_late_first_output_callback_is_unknown_and_cannot_mutate_receipt(backend, when):
    from chimeraforge.bench.backends.base import GenerationObservation
    from chimeraforge.planner.replay import digest

    callbacks, metadata_calls = [], []

    async def generation(model, prompt, options, on_first_output):
        callbacks.append(on_first_output)
        if when == "next_loop_turn":
            asyncio.get_running_loop().call_soon(on_first_output)
        return GenerationObservation({"tokens_generated": 3})

    async def metadata(_):
        metadata_calls.append(True)
        if len(metadata_calls) == 2 and when == "metadata_after":
            callbacks[0]()
        return {"backend": "ollama", "model": "served", "version": "fixture"}

    backend.generate_observed, backend.observe_serving = generation, metadata
    receipt = await api.replay_trace(
        requests()[:1], model="served", slos=api.TraceSLO(first_output_ms=1000)
    )
    original = receipt.to_dict()
    if when == "after_return":
        callbacks[0]()
    report = receipt.to_dict()
    assert report == original
    assert report["requests"][0]["times"]["first_output_s"] is None
    assert report["requests"][0]["slo"]["joint"] == "unknown"
    assert report["goodput"]["qualified_requests"] == 0
    assert (
        digest({key: value for key, value in report.items() if key != "fingerprint"})
        == report["fingerprint"]
    )
