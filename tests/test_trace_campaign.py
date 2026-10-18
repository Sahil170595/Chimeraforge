"""Serial source-protocol campaigns retain every declared replica and native row."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from chimeraforge import api
from chimeraforge.bench.backends import BACKEND_REGISTRY
from chimeraforge.bench.backends.base import Backend, GenerationObservation
from chimeraforge.planner.replay import digest


class CampaignBackend(Backend):
    name = "ollama"

    def __init__(self):
        self.closed = False
        self.calls = []
        self.fail = False
        self.fail_on_call = None
        self.cleanup_fail = False
        self.health = True
        self.gate = None
        self.entered = asyncio.Event()
        self.blocked_stage = None
        self.observations = 0

    async def block(self, stage):
        if self.blocked_stage == stage:
            self.entered.set()
            await self.gate.wait()

    async def health_check(self):
        await self.block("preflight")
        return self.health, "PRIVATE PREFLIGHT token=secret"

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "synthetic-protocol"

    async def observe_serving(self, model):
        self.observations += 1
        await self.block("metadata_before" if self.observations == 1 else "metadata_after")
        return {"backend": "ollama", "model": model, "device": "cpu"}

    async def generate(self, model, prompt, options=None):
        raise AssertionError("observed protocol required")

    async def generate_observed(self, model, prompt, options, first):
        self.calls.append((model, prompt, options))
        first()
        if self.blocked_stage in (None, "generation"):
            self.entered.set()
        if self.gate is not None:
            if self.blocked_stage in (None, "generation"):
                await self.gate.wait()
        if self.fail or len(self.calls) == self.fail_on_call:
            raise ValueError("PRIVATE COMPLETION token=secret")
        return GenerationObservation(
            {
                "tokens_generated": 3,
                "prompt_tokens": 5,
                "cached_prompt_tokens": 0,
                "eval_duration_ms": 30,
                "prompt_eval_duration_ms": 2,
                "ttft_basis": "server-prefill-duration",
            },
            10,
            "server-decode-duration/output-token-count",
        )

    async def close(self):
        self.closed = True
        if self.cleanup_fail:
            raise RuntimeError("PRIVATE CLEANUP token=secret")


@pytest.fixture
def backends(monkeypatch):
    instances = []

    def create(**kwargs):
        instance = CampaignBackend()
        instances.append(instance)
        return instance

    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", create)
    return instances


def requests():
    return [
        api.TraceRequest("first", "PRIVATE PROMPT alpha", 8, 0),
        api.TraceRequest("second", "PRIVATE PROMPT beta", 8, 0),
    ]


@pytest.mark.asyncio
async def test_serial_campaign_frozen_manifest_and_unmodified_native_receipts(backends):
    rows = requests()
    result = await api.replay_trace_campaign(rows, model="served", replicates=3)
    data = result.to_dict()
    assert data["exit_code"] == 0 and len(data["replicas"]) == 3
    assert len(backends) == 3 and all(b.closed for b in backends)
    manifest = data["manifest"]
    assert manifest["workload"]["canonical_sha256"] == digest([asdict(row) for row in rows])
    assert manifest["workload"]["raw_sha256"] is None
    assert manifest["population"]["total_requests"] == 6
    for i, replica in enumerate(data["replicas"]):
        assert replica["index"] == i and replica["state"] == "completed"
        assert replica["manifest_fingerprint"] == manifest["fingerprint"]
        assert 0 <= replica["start_s"] <= replica["end_s"]
        native = replica["receipt"]
        assert native["workload"]["raw_sha256"] is None
        assert native["fingerprint"] == digest(
            {k: v for k, v in native.items() if k != "fingerprint"}
        )
        if i:
            assert data["replicas"][i - 1]["end_s"] <= replica["start_s"]
    data["replicas"].clear()
    assert len(result.to_dict()["replicas"]) == 3
    assert "PRIVATE" not in json.dumps(result.to_dict())


@pytest.mark.parametrize(
    "changes",
    [
        {"replicates": 0},
        {"replicates": 17},
        {"replicates": True},
        {"campaign_timeout": float("nan")},
        {"campaign_timeout": True},
        {"campaign_timeout": 0},
        {"campaign_timeout": 3601},
        {"concurrency": True},
        {"request_timeout": -1},
        {"trace_timeout": float("inf")},
    ],
)
@pytest.mark.asyncio
async def test_campaign_invalid_controls_refused_before_contact(backends, changes):
    with pytest.raises(api.PlanError):
        await api.replay_trace_campaign(requests(), model="served", **changes)
    assert backends == []


@pytest.mark.asyncio
async def test_original_workload_is_read_once_then_frozen_between_replicas(
    tmp_path, backends, monkeypatch
):
    import chimeraforge.bench.trace as trace

    path = tmp_path / "private.json"
    original = json.dumps([asdict(row) for row in requests()]).encode()
    path.write_bytes(original)
    replay = trace.replay
    calls = []

    async def changing(source, **kwargs):
        calls.append(source)
        path.write_text("private input replaced after preparation")
        result = await replay(source, **kwargs)
        return result

    monkeypatch.setattr(trace, "replay", changing)
    data = (await api.replay_trace_campaign(path, model="served", replicates=2)).to_dict()
    assert data["exit_code"] == 0
    assert data["manifest"]["workload"]["raw_sha256"] == hashlib.sha256(original).hexdigest()
    assert calls[0][0] is calls[1][0] and calls[0][0].prompt == requests()[0].prompt
    assert all(r["receipt"]["workload"]["raw_sha256"] is None for r in data["replicas"])


@pytest.mark.asyncio
async def test_cleanup_failure_is_explicit_private_incomplete_and_stops_successors(
    backends, monkeypatch, caplog
):
    create = BACKEND_REGISTRY["ollama"]

    def fail_cleanup(**kwargs):
        result = create(**kwargs)
        result.cleanup_fail = True
        return result

    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", fail_cleanup)
    data = (await api.replay_trace_campaign(requests(), model="served")).to_dict()
    assert data["exit_code"] == 1 and len(backends) == 1
    assert [r["state"] for r in data["replicas"]] == ["incomplete", "not_started", "not_started"]
    assert data["replicas"][0]["receipt"]["resource_cleanup"]["state"] == "incomplete"
    assert "PRIVATE" not in json.dumps(data) + caplog.text and "secret" not in caplog.text


@pytest.mark.parametrize("stage", ["preflight", "generation", "metadata_before", "metadata_after"])
@pytest.mark.parametrize("cause", ["caller_stop", "campaign_deadline"])
@pytest.mark.asyncio
async def test_campaign_stop_and_deadline_drain_full_native_population(monkeypatch, stage, cause):
    backend = CampaignBackend()
    backend.blocked_stage = stage
    backend.gate = asyncio.Event()
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", lambda **kwargs: backend)
    stopped = asyncio.Event()
    rows = (
        requests()
        if stage == "metadata_after"
        else requests() + [api.TraceRequest("future", "PRIVATE FUTURE", 8, 10)]
    )
    task = asyncio.create_task(
        api.replay_trace_campaign(
            rows,
            model="served",
            replicates=3,
            stop_event=stopped,
            campaign_timeout=0.04 if cause == "campaign_deadline" else 10,
        )
    )
    await asyncio.wait_for(backend.entered.wait(), 2)
    if cause == "caller_stop":
        stopped.set()
    data = (await asyncio.wait_for(task, 2)).to_dict()
    assert data["stop_reason"] == cause and data["exit_code"] == 1
    assert backend.closed and data["execution"]["not_started"] == 2
    native = data["replicas"][0]["receipt"]
    assert len(native["requests"]) == native["execution"]["planned"] == len(rows)
    assert data["replicas"][0]["state"] == "incomplete"
    assert stopped.is_set() == (cause == "caller_stop")
    assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("trace-campaign-")]


@pytest.mark.asyncio
async def test_simultaneous_native_completion_and_stop_preserves_receipt_no_successor(
    monkeypatch, backends
):
    import chimeraforge.bench.trace as trace

    stopped = asyncio.Event()
    replay = trace.replay

    async def finish_and_stop(source, **kwargs):
        result = await replay(source, **kwargs)
        stopped.set()
        return result

    monkeypatch.setattr(trace, "replay", finish_and_stop)
    data = (
        await api.replay_trace_campaign(
            requests(), model="served", replicates=2, stop_event=stopped
        )
    ).to_dict()
    assert data["exit_code"] == 1 and data["stop_reason"] == "caller_stop"
    assert [r["state"] for r in data["replicas"]] == ["completed", "not_started"]
    assert data["replicas"][0]["receipt"]["exit_code"] == 0 and len(backends) == 1


@pytest.mark.parametrize("replicates", [1, 2])
@pytest.mark.asyncio
async def test_final_completion_and_caller_stop_keeps_completed_population_exit0(
    monkeypatch, backends, replicates
):
    import chimeraforge.bench.trace as trace

    replay = trace.replay
    stopped = asyncio.Event()
    calls = []

    async def last_complete_and_stop(source, **kwargs):
        result = await replay(source, **kwargs)
        calls.append(result)
        if len(calls) == replicates:
            stopped.set()
        return result

    monkeypatch.setattr(trace, "replay", last_complete_and_stop)
    data = (
        await api.replay_trace_campaign(
            requests(), model="served", replicates=replicates, stop_event=stopped
        )
    ).to_dict()
    assert data["execution"]["completed"] == replicates and data["stop_reason"] == "caller_stop"
    assert data["exit_code"] == 0 and data["state"] == "completed"


@pytest.mark.asyncio
async def test_external_campaign_cancel_propagates_after_owned_native_cleanup(monkeypatch):
    backend = CampaignBackend()
    backend.gate = asyncio.Event()
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", lambda **kwargs: backend)
    task = asyncio.create_task(
        api.replay_trace_campaign(requests(), model="served", stop_event=asyncio.Event())
    )
    await asyncio.wait_for(backend.entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert backend.closed
    assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("trace-campaign-")]


@pytest.mark.asyncio
async def test_replay_exception_is_categorical_failed_without_fabricated_native_rows(
    monkeypatch, caplog
):
    import chimeraforge.bench.trace as trace

    async def failed(*args, **kwargs):
        raise OSError("PRIVATE PROVIDER token=secret")

    monkeypatch.setattr(trace, "replay", failed)
    data = (await api.replay_trace_campaign(requests(), model="served")).to_dict()
    assert [r["state"] for r in data["replicas"]] == ["failed", "not_started", "not_started"]
    first = data["replicas"][0]
    assert first["receipt"] is None and first["error"] == {
        "stage": "campaign_replay",
        "type": "BackendError",
    }
    assert "PRIVATE" not in json.dumps(data) + caplog.text
    assert all(r["start_s"] is r["end_s"] is None for r in data["replicas"][1:])


@pytest.mark.asyncio
async def test_native_failed_population_stops_campaign_but_retains_all_rows(monkeypatch):
    backend = CampaignBackend()
    backend.fail_on_call = 2
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", lambda **kwargs: backend)
    data = (await api.replay_trace_campaign(requests(), model="served", replicates=3)).to_dict()
    assert data["replicas"][0]["state"] == "incomplete"
    assert data["replicas"][0]["receipt"]["execution"]["partial"] == 1
    assert data["replicas"][0]["receipt"]["execution"]["completed"] == 1
    assert len(data["replicas"][0]["receipt"]["requests"]) == 2
    assert data["execution"]["not_started"] == 2 and backend.closed


@pytest.mark.asyncio
async def test_slo_breaches_and_unknowns_do_not_turn_full_execution_incomplete(backends):
    data = (
        await api.replay_trace_campaign(
            requests(), model="served", replicates=2, slos=api.TraceSLO(latency_ms=1e-12)
        )
    ).to_dict()
    assert data["exit_code"] == 0 and data["execution"]["completed"] == 2
    assert all(r["receipt"]["goodput"]["qualified_requests"] == 0 for r in data["replicas"])


@pytest.mark.asyncio
async def test_pre_set_caller_stop_admits_no_backend_and_retains_manifest(backends):
    stopped = asyncio.Event()
    stopped.set()
    data = (
        await api.replay_trace_campaign(requests(), model="served", stop_event=stopped)
    ).to_dict()
    assert backends == [] and data["execution"]["not_started"] == 3
    assert data["manifest"]["policy"]["stop_after_first_incomplete_replicate"] is True


@pytest.mark.asyncio
async def test_population_total_limit_before_contact_and_boundary_manifest(backends, monkeypatch):
    import chimeraforge.bench.trace_campaign as campaign

    rows = [api.TraceRequest(str(i), "private", 1, 0) for i in range(257)]
    with pytest.raises(api.PlanError):
        await api.replay_trace_campaign(rows, model="served", replicates=16)
    assert backends == []
    called = []

    async def rejected(rows, manifest, *args):
        called.append(manifest)
        return None, {"stage": "campaign_replay", "type": "RuntimeError"}, "failed", None

    monkeypatch.setattr(campaign, "_replicate", rejected)
    data = (await api.replay_trace_campaign(rows[:256], model="served", replicates=16)).to_dict()
    assert called[0]["population"]["total_requests"] == 4096
    assert len(data["replicas"]) == 16 and data["execution"]["not_started"] == 15


def test_campaign_cli_receipt_json_prose_output_aliases_and_malformed(tmp_path, backends):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    source, out = tmp_path / "source.json", tmp_path / "campaign.json"
    raw = json.dumps([asdict(row) for row in requests()]).encode()
    source.write_bytes(raw)
    args = ["trace-campaign", str(source), "--model", "served", "--replicates", "2"]
    result = CliRunner().invoke(app, [*args, "--json", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == json.loads(out.read_bytes())
    assert source.read_bytes() == raw
    prose = CliRunner().invoke(app, args)
    assert prose.exit_code == 0 and "Completed 2/2 replicas" in prose.output
    before = len(backends)
    alias = CliRunner().invoke(app, [*args, "--out", str(source), "--json"])
    assert alias.exit_code == 2 and source.read_bytes() == raw and len(backends) == before
    invalid = CliRunner().invoke(app, [*args, "--campaign-timeout", "nan", "--json"])
    assert (
        invalid.exit_code == 2 and json.loads(invalid.output)["error"] and len(backends) == before
    )


@pytest.mark.asyncio
async def test_campaign_atomic_failure_and_hardlink_input_protection(
    tmp_path, backends, monkeypatch
):
    import os

    source = tmp_path / "source.json"
    source.write_text(json.dumps([asdict(row) for row in requests()]))
    result = await api.replay_trace_campaign(source, model="served", replicates=1)
    alias = tmp_path / "alias.json"
    os.link(source, alias)
    with pytest.raises(api.PlanError):
        result.save(alias)
    output = tmp_path / "output.json"
    output.write_bytes(b"prior campaign")

    def fail(*args):
        raise OSError("fixture replacement unavailable")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(api.PlanError):
        result.save(output)
    assert output.read_bytes() == b"prior campaign" and not list(tmp_path.glob("*.tmp"))


@pytest.mark.asyncio
async def test_manifest_frozen_before_adapter_and_file_deletion_cannot_change_it(
    tmp_path, monkeypatch
):
    import chimeraforge.bench.trace_campaign as campaign
    import chimeraforge.plan_bundle as bundle

    source = tmp_path / "private.json"
    source.write_text(json.dumps([asdict(row) for row in requests()]))
    prepared = []
    prepare = campaign._prepare
    read = bundle._read
    reads = []

    def captured(*args, **kwargs):
        result = prepare(*args, **kwargs)
        prepared.append(result[1])
        return result

    def read_once(path, limit, **kwargs):
        reads.append(path)
        return read(path, limit, **kwargs)

    def create(**kwargs):
        assert prepared and prepared[0]["fingerprint"] == digest(
            {k: v for k, v in prepared[0].items() if k != "fingerprint"}
        )
        if source.exists():
            source.unlink()
        return CampaignBackend()

    monkeypatch.setattr(campaign, "_prepare", captured)
    monkeypatch.setattr(bundle, "_read", read_once)
    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", create)
    data = (await api.replay_trace_campaign(source, model="served", replicates=2)).to_dict()
    assert data["exit_code"] == 0 and len(reads) == 1 and not source.exists()
    assert data["manifest"] == prepared[0]


@pytest.mark.asyncio
async def test_deadline_cooperative_drain_has_no_claimed_wall_bound(monkeypatch, backends):
    import chimeraforge.bench.trace as trace

    replay = trace.replay
    draining, release = asyncio.Event(), asyncio.Event()

    async def cooperative(source, **kwargs):
        result = await replay(source, **kwargs)
        await kwargs["stop_event"].wait()
        draining.set()
        await release.wait()
        return result

    monkeypatch.setattr(trace, "replay", cooperative)
    task = asyncio.create_task(
        api.replay_trace_campaign(
            requests(),
            model="served",
            replicates=1,
            campaign_timeout=0.02,
            stop_event=asyncio.Event(),
        )
    )
    try:
        await asyncio.wait_for(draining.wait(), 2)
        assert not task.done()
        assert not [t for t in asyncio.all_tasks() if t.get_name() == "trace-campaign-stop"]
    finally:
        release.set()
        data = (await task).to_dict()
    assert data["stop_reason"] == "campaign_deadline"
    assert data["execution"]["completed"] == 1 and data["exit_code"] == 0
    assert "may be unbounded" in data["limits"]


@pytest.mark.asyncio
async def test_cleanup_preserves_original_failure_cancellation_without_private_logs(caplog):
    from chimeraforge.bench.backends.base import backend_lifecycle

    for original in (ValueError("PRIVATE ORIGINAL"), asyncio.CancelledError("PRIVATE CANCEL")):
        backend = CampaignBackend()
        backend.cleanup_fail = True
        cleanup = {}
        with pytest.raises(type(original)) as caught:
            async with backend_lifecycle(backend, _cleanup=cleanup):
                raise original
        assert caught.value is original and cleanup["state"] == "incomplete" and backend.closed
    assert "PRIVATE" not in caplog.text and "secret" not in caplog.text


@pytest.mark.asyncio
async def test_endpoint_credentials_and_duplicate_private_fields_are_not_persisted(
    tmp_path, backends
):
    data = (
        await api.replay_trace_campaign(
            requests(),
            model="served",
            replicates=1,
            base_url="http://user:credential-sentinel@localhost:11434/path?token=query-sentinel",
        )
    ).to_dict()
    assert data["manifest"]["controls"]["endpoint"] == "http://localhost:11434/path"
    assert "credential-sentinel" not in json.dumps(data) and "query-sentinel" not in json.dumps(
        data
    )
    source = tmp_path / "bad.json"
    source.write_text('[{"private-key-sentinel":1,"private-key-sentinel":2}]')
    with pytest.raises(api.PlanError) as caught:
        await api.replay_trace_campaign(source, model="served")
    assert "private-key-sentinel" not in str(caught.value) and caught.value.__suppress_context__


@pytest.mark.asyncio
async def test_crossing_budget_at_actual_admission_keeps_row_unstarted(monkeypatch):
    import chimeraforge.bench.trace_campaign as campaign

    times = iter([0.0, 0.5, 1.1])
    monkeypatch.setattr(campaign, "_clock", lambda: next(times, 1.2))

    async def refused(*args):
        pytest.fail("native child admitted after recorded campaign deadline")

    monkeypatch.setattr(campaign, "_replicate", refused)
    data = (
        await api.replay_trace_campaign(
            requests(), model="served", replicates=1, campaign_timeout=1
        )
    ).to_dict()
    assert data["stop_reason"] == "campaign_deadline" and data["exit_code"] == 1
    assert data["replicas"][0]["state"] == "not_started"
    assert data["replicas"][0]["start_s"] is data["replicas"][0]["end_s"] is None


@pytest.mark.asyncio
async def test_unknown_required_slo_stays_native_unknown_with_complete_campaign(
    backends, monkeypatch
):
    observed = CampaignBackend.generate_observed

    async def no_first(self, model, prompt, options, first):
        return await observed(self, model, prompt, options, lambda: None)

    monkeypatch.setattr(CampaignBackend, "generate_observed", no_first)
    data = (
        await api.replay_trace_campaign(
            requests(), model="served", replicates=2, slos=api.TraceSLO(first_output_ms=1)
        )
    ).to_dict()
    assert data["exit_code"] == 0 and data["execution"]["completed"] == 2
    assert all(
        row["slo"]["joint"] == "unknown"
        for replica in data["replicas"]
        for row in replica["receipt"]["requests"]
    )


def test_campaign_cli_sigint_produces_receipt_and_restores_handler(tmp_path, monkeypatch):
    import signal
    import chimeraforge.commands.trace_campaign as command
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    handlers = []
    previous = signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(command.signal, "signal", lambda sig, handler: handlers.append(handler))
    instances = []

    def create(**kwargs):
        backend = CampaignBackend()
        backend.gate = asyncio.Event()
        instances.append(backend)
        handlers[-1](signal.SIGINT, None)
        return backend

    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", create)
    source = tmp_path / "private.json"
    source.write_text(json.dumps([asdict(row) for row in requests()]))
    result = CliRunner().invoke(app, ["trace-campaign", str(source), "--model", "served", "--json"])
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    assert data["stop_reason"] == "caller_stop" and data["execution"]["not_started"] == 2
    assert len(instances) == 1 and instances[0].closed and handlers[-1] is previous


def test_campaign_cli_cleanup_failure_keeps_private_diagnostics_out(tmp_path, monkeypatch, caplog):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    def create(**kwargs):
        backend = CampaignBackend()
        backend.cleanup_fail = True
        return backend

    monkeypatch.setitem(BACKEND_REGISTRY, "ollama", create)
    source = tmp_path / "private.json"
    source.write_text(json.dumps([asdict(row) for row in requests()]))
    result = CliRunner().invoke(app, ["trace-campaign", str(source), "--model", "served", "--json"])
    assert (
        result.exit_code == 1 and json.loads(result.output)["replicas"][0]["state"] == "incomplete"
    )
    assert (
        "PRIVATE" not in result.output + caplog.text and "secret" not in result.output + caplog.text
    )


@pytest.mark.asyncio
async def test_campaign_metadata_exception_logs_are_categorical(backends, monkeypatch, caplog):
    async def unavailable(self, model):
        raise ValueError("PRIVATE METADATA token=secret")

    monkeypatch.setattr(CampaignBackend, "observe_serving", unavailable)
    data = (await api.replay_trace_campaign(requests(), model="served", replicates=1)).to_dict()
    native = data["replicas"][0]["receipt"]
    assert native["serving_before"]["source"] == "serving metadata capability unavailable"
    assert native["serving_before"]["limitations"] == ["ValueError"]
    assert "PRIVATE" not in json.dumps(data) + caplog.text and "secret" not in caplog.text
