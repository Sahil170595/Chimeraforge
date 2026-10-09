"""Plan identity and observed configuration remain separate from native SLO evidence."""

import copy
import json
import threading
from dataclasses import asdict

import pytest

from chimeraforge.api import PlanRequest, plan
from chimeraforge.monitor import MonitorRequest, MonitorError, prometheus_text
from test_monitor_slo import MODEL, pair, metrics_server


@pytest.fixture
def saved():
    artifact = plan(
        PlanRequest(
            models=[MODEL],
            allow_network=False,
            quality_target=0,
            budget=100000000,
            request_rate=0.1,
            ttft_slo=500,
            prompt_tokens=8,
            avg_tokens=4,
            overrides={
                "params_b": 3.21,
                "n_layers": 28,
                "n_kv_heads": 8,
                "d_head": 128,
                "hidden_size": 3072,
            },
        )
    )
    index = next(
        i
        for i, row in enumerate(artifact.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    return artifact, index


def observe_scene(saved):
    artifact, index = saved
    return {
        "backend": "vllm",
        "version": "0.30.0",
        "model": MODEL,
        "quant": artifact.candidate(index).quant,
        "context_length": 2048,
        "tensor_parallel": 1,
        "pipeline_parallel": 1,
        "replicas": None,
        "serving_data_parallel_size": 1,
        "device": "gpu",
        "hardware": None,
        "model_spec": None,
        "model_digest": None,
        "prefix_cache": False,
        "source": "observed server configuration",
    }


def execute(saved, monkeypatch, *, scene=None, ttft=0.05, target=None, stop=None):
    from chimeraforge.api import monitor_plan
    from chimeraforge import monitor
    from chimeraforge.bench import serving

    snapshots = iter(pair(ttft=ttft))
    monkeypatch.setattr(monitor, "_fetch", lambda *a, **k: next(snapshots))
    observed = observe_scene(saved) if scene is None else scene
    calls = []

    async def metadata_only(backend, model):
        calls.append(model)
        return copy.deepcopy(observed)

    monkeypatch.setattr(serving, "observe_backend", metadata_only)
    request = MonitorRequest(
        "vllm", "http://serving", MODEL, ttft_slo=target, interval=0.01, timeout=0.1
    )
    original_request = asdict(request)
    original_saved = saved[0].to_dict()
    report = monitor_plan(saved[0], request, candidate_index=saved[1], stop_event=stop)
    assert asdict(request) == original_request and saved[0].to_dict() == original_saved
    return report, calls


def test_public_default_saved_targets_bind_candidate_without_mutating_request(saved, monkeypatch):
    report, calls = execute(saved, monkeypatch)
    data = report.to_dict()
    binding = data["plan_binding"]
    assert binding["plan"]["fingerprint"] == saved[0].to_dict()["fingerprint"]
    assert binding["plan"]["candidate_index"] == saved[1]
    assert binding["plan"]["identity"]["backend"] == "vllm"
    assert binding["target_sources"]["ttft"] == "saved_request"
    assert data["windows"][0]["metrics"]["ttft"]["target_ms"] == 500
    assert binding["identity"]["state"] == "matched"
    assert binding["configuration"]["state"] == "unverified"
    assert binding["configuration"]["fields"]["hardware"]["state"] == "unavailable"
    assert binding["configuration"]["fields"]["replicas"]["state"] == "unavailable"
    assert data["outcome"] == "pass" and report.exit_code == 0 and len(calls) == 2


def test_explicit_target_override_keeps_accurate_source(saved, monkeypatch):
    report, _ = execute(saved, monkeypatch, target=150)
    data = report.to_dict()
    assert data["plan_binding"]["target_sources"]["ttft"] == "explicit_override"
    assert data["windows"][0]["metrics"]["ttft"]["target_ms"] == 150
    with pytest.raises(MonitorError, match="explicit"):
        MonitorRequest("vllm", "http://serving", MODEL).validate()


def test_unavailable_endpoint_identity_cannot_pass_plan_binding(saved, monkeypatch):
    report, _ = execute(saved, monkeypatch, scene={"source": "metadata unavailable"})
    assert report.outcome == "pass" and report.exit_code == 4
    assert report.to_dict()["plan_binding"]["identity"]["state"] == "unavailable"


def test_observed_quant_mismatch_is_distinct_from_native_slo_pass(saved, monkeypatch):
    scene = observe_scene(saved)
    scene["quant"] = "Q8_0"
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.outcome == "pass" and report.exit_code == 5
    assert report.to_dict()["plan_binding"]["configuration"]["state"] == "mismatch"


def test_native_slo_breach_remains_breach_when_identity_matches(saved, monkeypatch):
    report, _ = execute(saved, monkeypatch, ttft=0.7)
    assert report.outcome == "breach" and report.exit_code == 3
    assert report.windows[0].metrics["ttft"].p95_lower_ms == 500
    assert report.to_dict()["plan_binding"]["identity"]["state"] == "matched"


def test_pre_cancelled_plan_observation_contacts_nothing(saved, monkeypatch):
    stop = threading.Event()
    stop.set()
    report, calls = execute(saved, monkeypatch, stop=stop)
    assert report.cancelled and report.exit_code == 4 and not calls and not report.windows
    assert report.to_dict()["plan_binding"]["plan"]["candidate_index"] == saved[1]


def test_prometheus_separates_binding_and_native_slo_gauges(saved, monkeypatch):
    scene = observe_scene(saved)
    scene["quant"] = "Q8_0"
    report, _ = execute(saved, monkeypatch, scene=scene)
    text = prometheus_text(report)
    assert 'outcome="pass"} 1' in text
    assert "chimeraforge_monitor_plan_configuration" in text
    assert 'state="mismatch"} 1' in text
    assert saved[0].to_dict()["fingerprint"] in text
    assert f'candidate_index="{saved[1]}"' in text


def test_cli_from_plan_binds_candidate_and_keeps_real_histogram_window(
    saved, monkeypatch, tmp_path
):
    from chimeraforge.bench import serving
    from chimeraforge.cli import app
    from typer.testing import CliRunner

    source = tmp_path / "plan.json"
    saved[0].save(source)
    original = source.read_bytes()

    async def observe(*args):
        return observe_scene(saved)

    monkeypatch.setattr(serving, "observe_backend", observe)
    with metrics_server(pair()) as url:
        outcome = CliRunner().invoke(
            app,
            [
                "monitor",
                "--backend",
                "vllm",
                "--url",
                url,
                "--model",
                MODEL,
                "--from-plan",
                str(source),
                "--candidate-index",
                str(saved[1]),
                "--interval",
                "0.01",
                "--json",
            ],
        )
    assert outcome.exit_code == 0, outcome.output
    data = json.loads(outcome.stdout)
    assert data["plan_binding"]["plan"]["fingerprint"] == saved[0].to_dict()["fingerprint"]
    assert data["windows"][0]["metrics"]["ttft"]["samples"] == 20
    assert source.read_bytes() == original


def test_known_configuration_changes_during_window_are_retained(saved, monkeypatch):
    from chimeraforge import monitor
    from chimeraforge.api import monitor_plan
    from chimeraforge.bench import serving

    values = iter(pair())
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(values))
    first = observe_scene(saved)
    second = dict(first, context_length=4096, serving_data_parallel_size=2)
    observations = iter([first, second])

    async def observe(*args):
        return next(observations)

    monkeypatch.setattr(serving, "observe_backend", observe)
    result = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving", MODEL, interval=0.01),
        candidate_index=saved[1],
    )
    assert result.outcome == "pass" and result.exit_code == 5
    fields = result.to_dict()["plan_binding"]["configuration"]["fields"]
    assert fields["serving_stability"]["state"] == "mismatch"
    assert set(fields["serving_stability"]["detail"]["changed_fields"]) == {
        "context_length",
        "serving_data_parallel_size",
    }


def test_known_before_identity_mismatch_cannot_be_erased_by_after_match(saved, monkeypatch):
    from chimeraforge.api import monitor_plan
    from chimeraforge import monitor
    from chimeraforge.bench import serving

    snapshots = iter(pair())
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))
    observations = iter([dict(observe_scene(saved), model="other"), observe_scene(saved)])

    async def observe(*args):
        return next(observations)

    monkeypatch.setattr(serving, "observe_backend", observe)
    report = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving", MODEL, interval=0.01),
        candidate_index=saved[1],
    )
    assert (
        report.exit_code == 5
        and report.to_dict()["plan_binding"]["identity"]["state"] == "mismatch"
    )


def test_saved_multiple_engine_fleet_and_engine_dp1_is_not_a_topology_mismatch(monkeypatch):
    artifact = plan(
        PlanRequest(
            models=[MODEL],
            allow_network=False,
            quality_target=0,
            budget=100000000,
            request_rate=1000,
            ttft_slo=500,
            prompt_tokens=8,
            avg_tokens=4,
            overrides={
                "params_b": 3.21,
                "n_layers": 28,
                "n_kv_heads": 8,
                "d_head": 128,
                "hidden_size": 3072,
            },
        )
    )
    index = next(
        i
        for i, row in enumerate(artifact.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16" and row["n_agents"] >= 2
    )
    report, _ = execute((artifact, index), monkeypatch)
    fields = report.to_dict()["plan_binding"]["configuration"]["fields"]
    assert report.exit_code == 0 and fields["replicas"]["state"] == "unavailable"
    assert fields["replicas"]["expected"] >= 2
    assert fields["serving_data_parallel_size"]["observed"] == 1
    assert "engine" in fields["serving_data_parallel_size"]["scope"]


def test_unknown_native_histogram_is_not_rescued_by_matched_identity(saved, monkeypatch):
    report, _ = execute(saved, monkeypatch, ttft=0.2, target=150)
    assert report.outcome == "unknown" and report.exit_code == 4
    assert report.to_dict()["plan_binding"]["identity"]["state"] == "matched"


def test_invalid_saved_candidate_is_rejected_before_any_contact(saved, monkeypatch):
    from chimeraforge.api import monitor_plan, PlanError
    from chimeraforge import monitor

    monkeypatch.setattr(
        monitor, "_fetch", lambda *args: pytest.fail("invalid input must not contact endpoint")
    )
    with pytest.raises(PlanError, match="index"):
        monitor_plan(
            saved[0], MonitorRequest("vllm", "http://serving", MODEL), candidate_index=999999
        )


def test_metadata_entire_call_timeout_closes_adapter_and_keeps_native_slo(saved, monkeypatch):
    import asyncio
    import time
    from chimeraforge.api import monitor_plan
    from chimeraforge import monitor, plan_monitor
    from chimeraforge.bench import serving

    snapshots = iter(pair())
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))
    closed = []

    class Adapter:
        async def close(self):
            closed.append(True)

    monkeypatch.setattr(plan_monitor, "get_backend", lambda *args, **kwargs: Adapter())

    async def slow(*args):
        await asyncio.sleep(10)

    monkeypatch.setattr(serving, "observe_backend", slow)
    start = time.perf_counter()
    result = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving", MODEL, interval=0.01, timeout=0.03),
        candidate_index=saved[1],
    )
    assert time.perf_counter() - start < 1 and len(closed) == 2
    assert result.outcome == "pass" and result.exit_code == 4
    assert all(
        "timeout" in window[phase]["source"]
        for window in result.to_dict()["plan_binding"]["windows"]
        for phase in ("before", "after")
    )


def test_metadata_cancellation_closes_adapter_and_preserves_completed_breach(saved, monkeypatch):
    import asyncio
    from chimeraforge.api import monitor_plan
    from chimeraforge import monitor, plan_monitor
    from chimeraforge.bench import serving

    snapshots = iter(pair(ttft=0.7))
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))
    stop = threading.Event()
    closed = []

    class Adapter:
        async def close(self):
            closed.append(True)

    monkeypatch.setattr(plan_monitor, "get_backend", lambda *args, **kwargs: Adapter())
    calls = []

    async def observe(*args):
        calls.append(True)
        if len(calls) == 2:
            stop.set()
            await asyncio.sleep(10)
        return observe_scene(saved)

    monkeypatch.setattr(serving, "observe_backend", observe)
    callbacks = []
    result = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving", MODEL, interval=0.01),
        candidate_index=saved[1],
        stop_event=stop,
        on_window=callbacks.append,
    )
    assert len(closed) == 2 and result.cancelled and len(result.windows) == 1
    assert result.outcome == "breach" and result.exit_code == 3
    assert callbacks == result.windows


def test_slow_supported_transport_cleanup_has_separate_bounded_receipt(monkeypatch):
    import asyncio
    import time
    import httpx
    from chimeraforge import plan_monitor
    from chimeraforge.bench import serving
    from chimeraforge.bench.backends.vllm import VLLMBackend

    class SlowTransport(httpx.AsyncBaseTransport):
        closed = False

        async def aclose(self):
            await asyncio.sleep(0.12)
            self.closed = True

    transport = SlowTransport()
    backend = VLLMBackend(transport=transport)
    monkeypatch.setattr(plan_monitor, "get_backend", lambda *args, **kwargs: backend)

    async def observe(*args):
        await backend._get_client()
        await asyncio.sleep(1)

    monkeypatch.setattr(serving, "observe_backend", observe)

    async def run():
        start = time.perf_counter()
        result = await plan_monitor._observe(
            MonitorRequest("vllm", "http://serving", MODEL, timeout=0.03), threading.Event()
        )
        assert time.perf_counter() - start < 0.12
        assert result["resource_cleanup"]["state"] == "incomplete"
        assert result["resource_cleanup"]["budget_seconds"] == 0.03
        assert not transport.closed and backend._client.is_closed
        assert len(asyncio.all_tasks()) == 1

    asyncio.run(run())


def test_prometheus_output_cannot_overwrite_saved_plan(saved, monkeypatch, tmp_path):
    from chimeraforge import monitor
    from chimeraforge.cli import app
    from typer.testing import CliRunner

    source = tmp_path / "plan.json"
    saved[0].save(source)
    original = source.read_bytes()
    monkeypatch.setattr(
        monitor, "_fetch", lambda *args: pytest.fail("collision must be refused before contact")
    )
    result = CliRunner().invoke(
        app,
        [
            "monitor",
            "--backend",
            "vllm",
            "--url",
            "http://server",
            "--model",
            MODEL,
            "--from-plan",
            str(source),
            "--candidate-index",
            str(saved[1]),
            "--prometheus",
            str(source),
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert "must not overwrite" in json.loads(result.stdout)["error"]
    assert source.read_bytes() == original


def test_custom_metrics_path_has_unavailable_metadata_without_guessing_server_root(
    saved, monkeypatch
):
    from chimeraforge.api import monitor_plan
    from chimeraforge import monitor, plan_monitor

    snapshots = iter(pair())
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))
    monkeypatch.setattr(
        plan_monitor,
        "get_backend",
        lambda *args, **kwargs: pytest.fail("do not guess a custom route's serving root"),
    )
    report = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving/private-stats", MODEL, interval=0.01),
        candidate_index=saved[1],
    )
    assert report.outcome == "pass" and report.exit_code == 4


def test_public_monitor_type_annotations_resolve():
    import typing
    from chimeraforge.api import monitor_plan
    from chimeraforge.monitor import MonitorReport

    assert typing.get_type_hints(monitor_plan)["return"] is MonitorReport


def test_actual_vllm_http_adapter_monitor_is_passive_and_binds_native_window(saved, tmp_path):
    from contextlib import contextmanager
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit
    from chimeraforge.api import monitor_plan

    paths = []
    scrapes = iter(pair())
    bodies = {
        "/version": {"version": "0.30.0"},
        "/v1/models": {"data": [{"id": MODEL}]},
        "/server_info": {
            "vllm_config": {
                "model_config": {"dtype": "float16", "max_model_len": 2048},
                "parallel_config": {
                    "tensor_parallel_size": 1,
                    "pipeline_parallel_size": 1,
                    "data_parallel_size": 1,
                },
                "cache_config": {"enable_prefix_caching": False},
                "device_config": {"device": "cuda"},
                "private_configuration": "private-server-token",
            }
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            path = urlsplit(self.path).path
            payload = (
                next(scrapes).encode() if path == "/metrics" else json.dumps(bodies[path]).encode()
            )
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            paths.append("POST " + self.path)
            self.send_error(405)

        def log_message(self, *args):
            pass

    @contextmanager
    def server():
        host = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=host.serve_forever)
        worker.start()
        try:
            yield f"http://127.0.0.1:{host.server_port}"
        finally:
            host.shutdown()
            host.server_close()
            worker.join()

    source = tmp_path / "plan.json"
    saved[0].save(source)
    original = source.read_bytes()
    with server() as url:
        report = monitor_plan(
            source, MonitorRequest("vllm", url, MODEL, interval=0.01), candidate_index=saved[1]
        )
    data = report.to_dict()
    assert report.outcome == "pass" and report.exit_code == 0
    assert data["windows"][0]["metrics"]["ttft"]["samples"] == 20
    assert data["plan_binding"]["identity"]["state"] == "matched"
    assert data["plan_binding"]["configuration"]["fields"]["context_length"]["observed"] == 2048
    assert data["plan_binding"]["configuration"]["fields"]["replicas"]["state"] == "unavailable"
    assert paths.count("/metrics") == 2 and paths.count("/version") == 2
    assert all(
        urlsplit(path).path in {"/metrics", "/version", "/v1/models", "/server_info"}
        for path in paths
    )
    assert source.read_bytes() == original
    assert "private-server-token" not in json.dumps(data)
    (tmp_path / "plan-monitor.json").write_text(json.dumps(data), encoding="utf-8")


def test_metadata_diagnostic_urls_are_redacted_and_private_fields_discarded(saved, monkeypatch):
    scene = dict(
        observe_scene(saved),
        source="http://private:password@server/path?token=secret#fragment",
        private="private-secret",
    )
    report, _ = execute(saved, monkeypatch, scene=scene)
    result = json.dumps(report.to_dict())
    assert "password" not in result and "secret" not in result and "fragment" not in result
    assert "http://server/path" in result


def test_reset_remains_unknown_with_known_plan_identity(saved, monkeypatch):
    from chimeraforge import monitor
    from chimeraforge.api import monitor_plan
    from chimeraforge.bench import serving

    first, second = pair()
    values = iter(
        [first + "process_start_time_seconds 100\n", second + "process_start_time_seconds 200\n"]
    )
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(values))

    async def observe(*args):
        return observe_scene(saved)

    monkeypatch.setattr(serving, "observe_backend", observe)
    report = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving", MODEL, interval=0.01),
        candidate_index=saved[1],
    )
    assert report.exit_code == 4 and report.outcome == "unknown"
    assert "restart" in report.windows[0].metrics["ttft"].reason


def test_malformed_scalar_metadata_is_unavailable_and_never_preserves_nested_private_config(
    saved, monkeypatch
):
    scene = dict(observe_scene(saved), quant={"private": "nested-private-token"})
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.exit_code == 0
    data = report.to_dict()
    assert data["plan_binding"]["configuration"]["fields"]["quant"]["state"] == "unavailable"
    assert "nested-private-token" not in json.dumps(data)


def test_partial_geometry_is_unavailable_and_known_partial_disagreement_is_mismatch(
    saved, monkeypatch
):
    scene = dict(observe_scene(saved), model_spec={"n_layers": 28})
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.exit_code == 0
    assert (
        report.to_dict()["plan_binding"]["configuration"]["fields"]["model_geometry"]["state"]
        == "unavailable"
    )
    scene["model_spec"]["n_layers"] = 99
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.exit_code == 5


def test_multiple_windows_share_observation_boundary_and_retain_earlier_mismatch(
    saved, monkeypatch
):
    from chimeraforge import monitor
    from chimeraforge.api import monitor_plan
    from chimeraforge.bench import serving
    from test_monitor_slo import scrape

    snapshots = iter(
        [scrape(ttft=[0.05] * n, tpot=[0.015] * n, itl=[0.08] * n) for n in (100, 120, 140)]
    )
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))
    rows = iter(
        [dict(observe_scene(saved), quant="Q8_0"), observe_scene(saved), observe_scene(saved)]
    )
    calls = []

    async def observe(*args):
        calls.append(True)
        return next(rows)

    monkeypatch.setattr(serving, "observe_backend", observe)
    callbacks = []
    result = monitor_plan(
        saved[0],
        MonitorRequest("vllm", "http://serving", MODEL, interval=0.01, windows=2),
        candidate_index=saved[1],
        on_window=callbacks.append,
    )
    assert len(calls) == 3 and len(result.windows) == 2 and len(callbacks) == 2
    assert result.outcome == "pass" and result.exit_code == 5
    fields = result.to_dict()["plan_binding"]["configuration"]["fields"]
    assert "quant" in fields["serving_stability"]["detail"]["changed_fields"]


def test_actual_sglang_adapter_keeps_scoped_config_and_native_ttft(saved, monkeypatch):
    import httpx
    from chimeraforge.api import monitor_plan
    from chimeraforge import monitor, plan_monitor
    from chimeraforge.bench.backends.sglang import SGLangBackend

    index = next(
        i
        for i, row in enumerate(saved[0].to_dict()["result"]["candidates"])
        if row["backend"] == "sglang" and row["quant"] == "FP16"
    )
    snapshots = iter(pair("sglang"))
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))
    requests = []
    clients = []

    def reply(request):
        requests.append((request.method, request.url.path))
        payload = {
            "version": "0.5.20",
            "dtype": "float16",
            "context_length": 2048,
            "tp_size": 1,
            "pp_size": 1,
            "dp_size": 1,
            "device": "cuda",
            "disable_radix_cache": True,
        }
        if request.url.path == "/model_info":
            payload = {"served_model_name": MODEL, "weight_version": "operator-label"}
        return httpx.Response(200, json=payload)

    def adapter(*args, **kwargs):
        result = SGLangBackend(base_url=kwargs["base_url"], transport=httpx.MockTransport(reply))
        clients.append(result)
        return result

    monkeypatch.setattr(plan_monitor, "get_backend", adapter)
    result = monitor_plan(
        saved[0],
        MonitorRequest("sglang", "http://server", MODEL, interval=0.01),
        candidate_index=index,
    )
    assert result.outcome == "pass" and result.exit_code == 0
    fields = result.to_dict()["plan_binding"]["configuration"]["fields"]
    assert fields["quant"]["state"] == "matched" and fields["replicas"]["state"] == "unavailable"
    assert fields["immutable_weights"]["state"] == "unavailable"
    assert requests == [("GET", "/server_info"), ("GET", "/model_info")] * 2
    assert all(client._client.is_closed for client in clients)


def test_extra_observed_hidden_vocab_does_not_contradict_unknown_saved_geometry(monkeypatch):
    artifact = plan(
        PlanRequest(
            models=["llama3.2-3b"], allow_network=False, quality_target=0, budget=1e8, ttft_slo=500
        )
    )
    index = next(
        i
        for i, row in enumerate(artifact.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    saved = artifact, index
    expected = artifact.to_dict()["result"]["replay_context"]["model_specs"]["llama3.2-3b"]
    assert expected["hidden_size"] is None and expected["vocab_size"] is None
    scene = dict(
        observe_scene(saved),
        model="llama3.2-3b",
        model_spec=dict(expected, hidden_size=3072, vocab_size=128256),
    )
    from chimeraforge import monitor
    from chimeraforge.api import monitor_plan
    from chimeraforge.bench import serving

    snapshots = iter(pair())
    monkeypatch.setattr(monitor, "_fetch", lambda *args: next(snapshots))

    async def observe(*args):
        return scene

    monkeypatch.setattr(serving, "observe_backend", observe)
    # Histograms select this candidate's exact model, without assigning org/model evidence to it.
    first, second = pair()
    snapshots = iter([text.replace(MODEL, "llama3.2-3b") for text in (first, second)])
    report = monitor_plan(
        artifact,
        MonitorRequest("vllm", "http://server", "llama3.2-3b", interval=0.01),
        candidate_index=index,
    )
    assert report.outcome == "pass" and report.exit_code == 0
    assert (
        report.to_dict()["plan_binding"]["configuration"]["fields"]["model_geometry"]["state"]
        == "unavailable"
    )


def test_partial_physical_hardware_agreement_is_unavailable_but_known_contradiction_is_mismatch(
    saved, monkeypatch
):
    expected = saved[0].to_dict()["result"]["replay_context"]["hardware"]["effective"]
    partial = {name: expected[name] for name in ("name", "vram_gb", "bandwidth_gbps")}
    scene = dict(observe_scene(saved), hardware=partial)
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.exit_code == 0
    assert (
        report.to_dict()["plan_binding"]["configuration"]["fields"]["hardware"]["state"]
        == "unavailable"
    )
    partial["vram_gb"] = 1
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.exit_code == 5


def test_hardware_price_and_source_are_not_observed_physical_configuration(saved, monkeypatch):
    hardware = saved[0].to_dict()["result"]["replay_context"]["hardware"]["effective"]
    scene = dict(
        observe_scene(saved),
        hardware=dict(
            hardware,
            cost_per_hour=99,
            captured_at="different date",
            source_url="https://different-source",
        ),
    )
    report, _ = execute(saved, monkeypatch, scene=scene)
    assert report.exit_code == 0
    assert (
        report.to_dict()["plan_binding"]["configuration"]["fields"]["hardware"]["state"]
        == "matched"
    )
