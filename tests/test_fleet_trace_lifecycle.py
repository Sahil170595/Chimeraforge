"""Behavioral ownership controls on the complete public fleet operation."""

from __future__ import annotations

import asyncio
import copy

import pytest

from chimeraforge import api
from chimeraforge.planner.replay import digest
from test_fleet_trace import Node, endpoints, routes, scene as scene, workload
from test_fleet_monitor import native_fleet as native_fleet


async def run_fleet(native_fleet, **kwargs):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    return await api.replay_fleet_trace(
        saved, requests, endpoints(), routes(requests), candidate_index=indices["vllm"], **kwargs
    )


@pytest.mark.asyncio
async def test_repeated_caller_cancel_waits_for_every_close(native_fleet, scene, monkeypatch):
    before = set(asyncio.all_tasks())
    scene.gate = asyncio.Event()
    close_entered, release = asyncio.Event(), asyncio.Event()
    original = Node.close

    async def close(node):
        close_entered.set()
        await release.wait()
        await original(node)

    monkeypatch.setattr(Node, "close", close)
    task = asyncio.create_task(run_fleet(native_fleet, concurrency=3))
    try:
        await asyncio.wait_for(scene.entered.wait(), 5)
        assert task.cancel()
        await asyncio.wait_for(close_entered.wait(), 5)
        assert task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not any(node.closed for node in scene.created)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        scene.gate.set()
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert scene.active == 0 and all(node.closed for node in scene.created)
    assert set(asyncio.all_tasks()) == before


@pytest.mark.asyncio
async def test_generation_completion_cannot_expose_success_after_accepted_caller_cancel(
    native_fleet, scene, monkeypatch
):
    original = Node.generate_observed
    consumer = asyncio.current_task()
    accepted = []

    async def completion(node, *args):
        result = await original(node, *args)
        accepted.append(consumer.cancel())
        return result

    monkeypatch.setattr(Node, "generate_observed", completion)
    with pytest.raises(asyncio.CancelledError):
        await run_fleet(native_fleet)
    assert accepted and all(accepted)
    assert scene.active == 0 and all(node.closed for node in scene.created)


@pytest.mark.asyncio
async def test_expired_allowance_still_attempts_all_closes_before_generation_join(
    native_fleet, scene, monkeypatch
):
    release, started = asyncio.Event(), asyncio.Event()
    closes = []

    async def generation(node, *args):
        scene.active += 1
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await release.wait()
            scene.active -= 1

    async def close(node):
        closes.append(node.url)
        release.set()
        node.closed = True

    monkeypatch.setattr(Node, "generate_observed", generation)
    monkeypatch.setattr(Node, "close", close)
    task = asyncio.create_task(run_fleet(native_fleet, trace_timeout=0.02, cleanup_timeout=0.01))
    try:
        await asyncio.wait_for(started.wait(), 5)
        report = (await asyncio.wait_for(asyncio.shield(task), 5)).to_dict()
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert len(closes) == 3 and scene.active == 0
    assert report["cleanup"]["resources_closed"]
    assert report["cleanup"]["allowance_exceeded"]
    assert report["cleanup"]["joined_tasks"] == report["cleanup"]["owned_tasks"]
    assert report["exit_code"] == 1
    assert api.load_fleet_trace(report).to_dict() == report


@pytest.mark.asyncio
async def test_partial_constructor_failure_closes_already_created_members(
    native_fleet, scene, monkeypatch
):
    from chimeraforge.bench import trace

    def factory(*args, **kwargs):
        if len(scene.created) == 2:
            raise ValueError("PRIVATE CONSTRUCTOR CANARY")
        return scene.factory(*args, **kwargs)

    monkeypatch.setattr(trace, "get_backend", factory)
    with pytest.raises(api.PlanError, match="fleet backend configuration is unavailable"):
        await run_fleet(native_fleet)
    assert len(scene.created) == 2 and all(node.closed for node in scene.created)
    assert not any(node.calls for node in scene.created)


@pytest.mark.asyncio
async def test_one_close_error_does_not_skip_other_owners(native_fleet, scene, monkeypatch, caplog):
    original = Node.close

    async def close(node):
        await original(node)
        if node.url == endpoints()[0].url:
            raise RuntimeError("PRIVATE CLOSE CANARY")

    monkeypatch.setattr(Node, "close", close)
    report = (await run_fleet(native_fleet)).to_dict()
    assert all(node.closed for node in scene.created)
    assert report["cleanup"]["close_errors"] == 1 and report["exit_code"] == 1
    assert "PRIVATE" not in caplog.text
    assert api.load_fleet_trace(report).to_dict() == report


@pytest.mark.asyncio
async def test_zero_assigned_member_keeps_unavailable_evidence(native_fleet, scene):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    report = (
        await api.replay_fleet_trace(
            saved,
            requests,
            endpoints(),
            routes(requests, empty_last=True),
            candidate_index=indices["vllm"],
        )
    ).to_dict()
    empty = report["slots"][2]
    assert empty["row_indices"] == [] and empty["state"] == "zero_assigned"
    assert empty["latency_evidence"] == "unavailable" and empty["slo"]["state"] == "unavailable"
    assert all(row["state"] == "unavailable" for row in empty["binding"]["token_lengths"].values())
    assert api.load_fleet_trace(report).to_dict() == report


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["native_extra", "route", "slot", "native_count", "empty_pass"])
async def test_receiving_loader_rederives_population_instead_of_trusting_fingerprint(
    native_fleet, scene, change
):
    report = (await run_fleet(native_fleet)).to_dict()
    bad = copy.deepcopy(report)
    if change == "native_extra":
        bad["native_trace"]["requests"][0]["arbitrary"] = True
    elif change == "route":
        bad["routes"]["rows"][0]["endpoint_id"] = "member-1"
        bad["routes"]["canonical_sha256"] = digest(bad["routes"]["rows"])
    elif change == "slot":
        bad["slots"][0]["row_indices"] = [0, 0, 3]
    elif change == "native_count":
        bad["native_trace"]["execution"]["completed"] = 5
    else:
        bad["slots"][0]["binding"]["token_lengths"]["prompt_tokens"]["state"] = "unavailable"
    bad["native_trace"]["fingerprint"] = digest(
        {key: value for key, value in bad["native_trace"].items() if key != "fingerprint"}
    )
    bad["fingerprint"] = digest({key: value for key, value in bad.items() if key != "fingerprint"})
    with pytest.raises(api.PlanError):
        api.load_fleet_trace(bad)


@pytest.mark.asyncio
async def test_native_pretty_writer_cap_refusal_does_not_clobber(
    native_fleet, scene, monkeypatch, tmp_path
):
    import json
    from chimeraforge.bench import fleet_trace_types as types

    receipt = await run_fleet(native_fleet)
    data = receipt.to_dict()
    reference = tmp_path / "native-sdk.json"
    api.PlanArtifact(data).save(reference)
    native_bytes = reference.read_bytes()
    compact_bytes = json.dumps(data, allow_nan=False).encode("utf-8")
    assert len(compact_bytes) < len(native_bytes)
    target = tmp_path / "receipt.json"
    original = b"ORIGINAL DESTINATION MUST SURVIVE"
    target.write_bytes(original)
    monkeypatch.setattr(types, "MAX_FLEET_RECEIPT_BYTES", len(native_bytes) - 1)
    with pytest.raises(api.PlanError, match="bounded writer"):
        receipt.save(target)
    assert target.read_bytes() == original
    with pytest.raises(api.PlanError):
        api.load_fleet_trace(data)
    # A separate execution has fresh clocks/fingerprints; use the demonstrated
    # compact/pretty gap rather than assuming byte-identical dynamic observations.
    monkeypatch.setattr(types, "MAX_FLEET_RECEIPT_BYTES", len(compact_bytes))
    with pytest.raises(api.PlanError, match="bounded writer"):
        await run_fleet(native_fleet)
    assert all(node.closed for node in scene.created)


@pytest.mark.asyncio
async def test_exact_portable_writer_boundary_saves_and_reloads(
    native_fleet, scene, monkeypatch, tmp_path
):
    from chimeraforge.bench import fleet_trace_types as types

    receipt = await run_fleet(native_fleet)
    reference = tmp_path / "native-sdk.json"
    api.PlanArtifact(receipt.to_dict()).save(reference)
    # Measure actual native output, normalizing only the documented platform newline.
    portable_bytes = reference.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    monkeypatch.setattr(types, "MAX_FLEET_RECEIPT_BYTES", len(portable_bytes))
    target = tmp_path / "receipt.json"
    receipt.save(target)
    assert target.stat().st_size <= types.MAX_FLEET_RECEIPT_BYTES
    assert api.load_fleet_trace(target).to_dict() == receipt.to_dict()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["model", "backend", "targets"])
async def test_receiving_loader_binds_native_headers_to_saved_original(native_fleet, scene, change):
    bad = (await run_fleet(native_fleet)).to_dict()
    native = bad["native_trace"]
    if change == "model":
        native["model"] = "unrelated-model"
    elif change == "backend":
        native["backend"] = "sglang"
    else:
        native["targets"]["latency_ms"] *= 2
    native["fingerprint"] = digest(
        {key: value for key, value in native.items() if key != "fingerprint"}
    )
    bad["fingerprint"] = digest({key: value for key, value in bad.items() if key != "fingerprint"})
    with pytest.raises(api.PlanError):
        api.load_fleet_trace(bad)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["boolean_index", "boolean_concurrency", "boolean_budget", "missing_owners"]
)
async def test_receiving_loader_refuses_equal_but_impossible_derived_facts(
    native_fleet, scene, change
):
    bad = (await run_fleet(native_fleet, cleanup_timeout=1)).to_dict()
    if change == "boolean_index":
        bad["slots"][0]["row_indices"][0] = False
    elif change == "boolean_concurrency":
        bad["controls"]["concurrency"] = True
    elif change == "boolean_budget":
        bad["cleanup"]["budget_seconds"] = True
    else:
        for key in ("owned_backends", "closed_backends", "owned_tasks", "joined_tasks"):
            bad["cleanup"][key] = 0
    bad["fingerprint"] = digest({key: value for key, value in bad.items() if key != "fingerprint"})
    with pytest.raises(api.PlanError):
        api.load_fleet_trace(bad)
