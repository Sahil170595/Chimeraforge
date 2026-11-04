from dataclasses import asdict
import asyncio
import json

import pytest

from chimeraforge import api
from chimeraforge.bench.backends.vllm import VLLMBackend
from chimeraforge.bench.gate_inputs import MAX_RECEIPT_BYTES
from chimeraforge.bench.trace_gate_inputs import load_trace
from chimeraforge.bench.trace_workload import load_workload, MAX_TRACE_BYTES
from chimeraforge.bench import trace
from chimeraforge.bench.fleet_trace_types import _admit_receipt
from chimeraforge.cli import app
from typer.testing import CliRunner
from test_fleet_monitor import native_fleet as native_fleet
from test_fleet_trace import endpoints, routes
from test_plan_trace import saved as saved


@pytest.mark.asyncio
@pytest.mark.parametrize("message_count", [1, 128])
async def test_stopped_native_chat_must_publish_receivable_bytes_or_refuse(
    tmp_path, monkeypatch, message_count
):
    rows = [
        api.ChatTraceRequest(str(i), (api.ChatMessage("user", "x"),) * message_count, 1, 0, 0.0)
        for i in range(1024)
    ]
    raw = json.dumps([asdict(row) for row in rows], sort_keys=True, separators=(",", ":")).encode()
    assert len(raw) < MAX_TRACE_BYTES and len(load_workload(rows)[0]) == 1024
    contacts = []

    async def forbidden(*args, **kwargs):
        contacts.append(True)
        pytest.fail("stopped producer contacted backend")

    for name in ("health_check", "check_model", "get_version", "observe_serving", "chat_observed"):
        monkeypatch.setattr(VLLMBackend, name, forbidden)
    stopped = asyncio.Event()
    stopped.set()
    out = tmp_path / "stopped.trace.json"
    try:
        receipt = await api.replay_trace(
            rows, model="controlled-stopped", backend="vllm", stop_event=stopped
        )
        assert len(receipt.to_dict()["requests"]) == 1024
        receipt.save(out)
    except api.PlanError as exc:
        assert message_count == 128 and not out.exists()
        assert any(word in str(exc).lower() for word in ("size", "byte", "bound", "limit"))
    else:
        # The actual native publication must be accepted by its ordinary receiver.
        assert load_trace(out)["data"] == receipt.to_dict()
        assert out.stat().st_size <= MAX_RECEIPT_BYTES
        old_writer = tmp_path / "same-payload-plan-writer.json"
        api.PlanArtifact(receipt.to_dict()).save(old_writer)
        assert out.read_bytes() == old_writer.read_bytes()
    assert contacts == []


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["ordinary", "plan", "campaign", "fleet", "fleet_campaign"])
async def test_chat_expansion_refuses_before_factory_across_native_paths(
    family, saved, native_fleet, monkeypatch
):
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: pytest.fail("backend factory called"))
    fleet, indices = native_fleet
    chosen = fleet.candidate(indices["vllm"]) if family.startswith("fleet") else saved.candidate(0)
    cap = chosen.decode_tokens_per_req
    assert isinstance(cap, int)
    rows = [
        api.ChatTraceRequest(str(i), (api.ChatMessage("user", "x"),) * 128, cap, 0, 0.0)
        for i in range(1024)
    ]
    expected = "invalid trace campaign workload or controls" if family == "campaign" else "byte"
    with pytest.raises(api.PlanError, match=expected):
        if family == "ordinary":
            await api.replay_trace(rows, model="controlled", backend="vllm")
        elif family == "plan":
            await api.replay_plan_trace(saved, rows)
        elif family == "campaign":
            await api.replay_trace_campaign(rows, model="controlled", backend="vllm", replicates=2)
        elif family == "fleet":
            await api.replay_fleet_trace(
                fleet, rows, endpoints(), routes(rows), candidate_index=indices["vllm"]
            )
        else:
            await api.replay_fleet_trace_campaign(
                fleet,
                rows,
                endpoints(),
                routes(rows),
                candidate_index=indices["vllm"],
                executions=2,
            )


def test_existing_native_pretty_writer_exact_byte_boundary_and_no_limit_widening():
    overhead = len((json.dumps({"padding": ""}, indent=2) + "\n").replace("\n", "\r\n").encode())
    value = {"padding": "x" * (MAX_RECEIPT_BYTES - overhead)}
    assert (
        len((json.dumps(value, indent=2) + "\n").replace("\n", "\r\n").encode())
        == MAX_RECEIPT_BYTES
    )
    _admit_receipt(value, MAX_RECEIPT_BYTES)
    value["padding"] += "x"
    with pytest.raises(api.PlanError):
        _admit_receipt(value, MAX_RECEIPT_BYTES)


@pytest.mark.parametrize("write_target", [False, True])
def test_mutated_native_snapshot_size_guard_precedes_copy_and_cli_publication(
    tmp_path, monkeypatch, write_target
):
    stopped = asyncio.Event()
    stopped.set()
    row = api.ChatTraceRequest("one", (api.ChatMessage("user", "x"),), 1, 0)
    receipt = asyncio.run(
        api.replay_trace([row], model="controlled", backend="vllm", stop_event=stopped)
    )
    receipt._data["limits"] = "x" * MAX_RECEIPT_BYTES
    with monkeypatch.context() as scope:
        scope.setattr(
            trace.copy, "deepcopy", lambda *a, **k: pytest.fail("copied oversized snapshot")
        )
        with pytest.raises(api.PlanError):
            receipt.to_dict()
    out = tmp_path / "out.json"
    with pytest.raises(api.PlanError):
        receipt.save(out)
    assert not out.exists()
    sentinel = tmp_path / "existing.json"
    sentinel.write_bytes(b"held sentinel")
    with pytest.raises(api.PlanError):
        receipt.save(sentinel)
    assert sentinel.read_bytes() == b"held sentinel"
    source = tmp_path / "source.json"
    raw = json.dumps([asdict(row)]).encode()
    source.write_bytes(raw)

    async def supplied(*a, **k):
        return receipt

    monkeypatch.setattr(api, "replay_trace", supplied)
    args = ["trace", str(source), "--model", "controlled", "--backend", "vllm", "--json"]
    if write_target:
        args.extend(["--out", str(out)])
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2 and set(json.loads(result.stdout)) == {"error"}
    assert len(result.stdout.encode()) < 512 and not out.exists()
    assert source.read_bytes() == raw
