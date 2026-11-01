"""Serial executions preserve original-fleet work independently of qualification."""

from __future__ import annotations

import asyncio

import pytest

from chimeraforge import api
from test_fleet_trace import endpoints, routes, workload
import test_fleet_trace as native_fleet_trace

native_fleet = native_fleet_trace.native_fleet
scene = native_fleet_trace.scene


@pytest.mark.asyncio
async def test_secure_map_is_snapshotted_once_and_forwarded_for_each_native_execution(
    native_fleet, scene, monkeypatch
):
    from chimeraforge.bench import trace

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    declared = tuple(
        api.FleetEndpoint(row.id, row.url.replace("http:", "https:")) for row in endpoints()
    )
    mapping = {row.id: api.MonitorConnection(row.url) for row in declared}
    expected = dict(mapping)
    seen = []

    def factory(name, **kwargs):
        endpoint = next(row for row in declared if row.url == kwargs["base_url"])
        seen.append((endpoint.id, kwargs["connection"]))
        mapping.clear()
        return scene.factory(name, **kwargs)

    monkeypatch.setattr(trace, "get_backend", factory)
    result = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        declared,
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
        connections=mapping,
    )
    assert result.state == "completed" and len(seen) == 6 and not mapping
    assert all(connection is expected[member] for member, connection in seen)
    assert all(node.closed for node in scene.created)


@pytest.mark.asyncio
async def test_genuine_native_ollama_selection_refuses_secure_campaign_before_construction(
    monkeypatch,
):
    from chimeraforge.bench import trace

    saved = api.plan(
        api.PlanRequest(
            models=["ci/manual-fleet"],
            overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=1,
            request_rate=1,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index, selected = next(
        (i, row)
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "ollama"
    )
    declared = tuple(
        api.FleetEndpoint(f"r{i}", f"https://127.0.0.1:{8100 + i}")
        for i in range(selected["n_agents"])
    )
    requests = [api.TraceRequest("request", "fixture", selected["decode_tokens_per_req"], 0)]
    called = []

    def construct(*args, **kwargs):
        called.append(True)
        raise AssertionError("unsupported secure provider must be refused before construction")

    monkeypatch.setattr(trace, "get_backend", construct)
    with pytest.raises(api.PlanError, match="secure Ollama"):
        await api.replay_fleet_trace_campaign(
            saved,
            requests,
            declared,
            [api.TraceRoute("request", declared[0].id)],
            candidate_index=index,
            connections={},
        )
    assert not called


@pytest.mark.asyncio
async def test_complete_configuration_mismatch_continues_all_executions(
    native_fleet, scene, monkeypatch
):
    from chimeraforge.bench import trace

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    factory = scene.factory

    def mismatch(name, **kwargs):
        backend = factory(name, **kwargs)
        backend.observed["context_length"] += 1
        return backend

    monkeypatch.setattr(trace, "get_backend", mismatch)
    control = await api.replay_fleet_trace(
        saved, requests, endpoints(), routes(requests), candidate_index=indices["vllm"]
    )
    native = control.to_dict()
    assert native["status"] == "completed" and native["exit_code"] == 1
    assert native["configuration_status"] == "mismatch"
    assert native["native_trace"]["execution"]["completed"] == 6
    assert native["cleanup"]["state"] == "completed" and all(b.closed for b in scene.created)
    scene.created.clear()

    report = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
        concurrency=3,
    )
    data = report.to_dict()
    assert data["manifest"]["population"] == {
        "executions": 2,
        "original_replicas": 3,
        "requests_per_execution": 6,
        "total_requests": 12,
    }
    assert data["state"] == "completed" and data["exit_code"] == 1
    assert data["execution"]["completed"] == 2 and data["stop_reason"] is None
    assert len(data["executions"]) == 2 and len(scene.created) == 6
    assert sum(len(b.calls) for b in scene.created) == 12 and scene.peak <= 3
    assert all(b.closed for b in scene.created)
    for slot in data["executions"]:
        child = slot["receipt"]
        assert slot["state"] == "completed" and slot["execution_complete"] is True
        assert child["exit_code"] == 1 and child["configuration_status"] == "mismatch"
        assert len(child["slots"]) == 3
        assert [row["endpoint_id"] for row in child["native_trace"]["requests"]] == [
            f"member-{i % 3}" for i in range(6)
        ]
    assert data["executions"][1]["start_s"] >= data["executions"][0]["end_s"]


@pytest.mark.asyncio
async def test_native_incomplete_stops_admission_but_keeps_all_k_slots(native_fleet, scene):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    scene.preflight_failure = endpoints()[1].url
    result = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=3,
        candidate_index=indices["vllm"],
    )
    data = result.to_dict()
    assert data["execution"] == {
        "planned": 3,
        "completed": 0,
        "incomplete": 1,
        "failed": 0,
        "not_started": 2,
    }
    assert data["state"] == "incomplete" and data["exit_code"] == 1
    assert data["executions"][0]["receipt"]["native_trace"]["execution"]["not_started"] == 6
    assert len(data["executions"][0]["receipt"]["slots"]) == 3
    assert [slot["state"] for slot in data["executions"]] == [
        "incomplete",
        "not_started",
        "not_started",
    ]
    assert all(slot["receipt"] is None for slot in data["executions"][1:])
    assert len(scene.created) == 3 and all(b.closed and not b.calls for b in scene.created)


@pytest.mark.asyncio
async def test_pre_cancelled_campaign_keeps_all_unstarted_without_contact(native_fleet, scene):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    stopped = asyncio.Event()
    stopped.set()
    report = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
        stop_event=stopped,
    )
    data = report.to_dict()
    assert data["stop_reason"] == "caller_stop" and data["execution"]["not_started"] == 2
    assert len(data["executions"]) == 2 and all(s["receipt"] is None for s in data["executions"])
    assert data["manifest"]["population"]["original_replicas"] == 3
    assert not scene.created


@pytest.mark.parametrize("executions", [0, 17, True, 1.0])
@pytest.mark.asyncio
async def test_campaign_population_is_admitted_before_contact(native_fleet, scene, executions):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    with pytest.raises(api.PlanError):
        await api.replay_fleet_trace_campaign(
            saved,
            requests,
            endpoints(),
            routes(requests),
            executions=executions,
            candidate_index=indices["vllm"],
        )
    assert not scene.created


@pytest.mark.asyncio
async def test_native_receipt_guard_refusal_leaves_completion_unknown(
    native_fleet, scene, monkeypatch
):
    from chimeraforge.bench import fleet_trace_types

    # A fictional small native limit exercises its unchanged actual final guard.
    monkeypatch.setattr(fleet_trace_types, "MAX_FLEET_RECEIPT_BYTES", 128)
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    result = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
    )
    data = result.to_dict()
    first, last = data["executions"]
    assert first["state"] == "failed" and first["execution_complete"] is None
    assert first["receipt"] is None and first["reason"] == "native_receipt_unavailable"
    assert first["error"]["stage"] == "native_result"
    assert last["state"] == "not_started" and last["receipt"] is None
    assert data["stop_reason"] == "native_receipt_unavailable"
    assert sum(len(b.calls) for b in scene.created) == 6
    assert all(b.closed for b in scene.created)


@pytest.mark.asyncio
async def test_campaign_clock_includes_synchronous_native_preparation(
    native_fleet, scene, monkeypatch
):
    import time
    from chimeraforge.bench import fleet_campaign

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    original = fleet_campaign.prepare
    calls = []

    def observed(*args, **kwargs):
        calls.append(1)
        result = original(*args, **kwargs)
        time.sleep(0.02)
        return result

    monkeypatch.setattr(fleet_campaign, "prepare", observed)
    result = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        campaign_timeout=0.001,
        candidate_index=indices["vllm"],
    )
    data = result.to_dict()
    assert calls == [1] and not scene.created
    assert data["stop_reason"] == "campaign_deadline"
    assert data["clock"]["elapsed_seconds"] >= 0.02
    assert all(slot["state"] == "not_started" for slot in data["executions"])


@pytest.mark.asyncio
async def test_repeated_cancellation_joins_native_generation_and_all_clients(
    native_fleet, scene, monkeypatch
):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    release, closing = asyncio.Event(), asyncio.Event()
    scene.gate = asyncio.Event()
    original = native_fleet_trace.Node.generate_observed
    held = []

    async def observed(self, *args, **kwargs):
        try:
            return await original(self, *args, **kwargs)
        finally:
            closing.set()
            waiter = asyncio.create_task(release.wait())
            held.append(waiter)
            while not waiter.done():
                try:
                    await asyncio.shield(waiter)
                except asyncio.CancelledError:
                    continue

    monkeypatch.setattr(native_fleet_trace.Node, "generate_observed", observed)
    task = asyncio.create_task(
        api.replay_fleet_trace_campaign(
            saved,
            requests,
            endpoints(),
            routes(requests),
            executions=2,
            candidate_index=indices["vllm"],
            concurrency=1,
        )
    )
    try:
        await asyncio.wait_for(scene.entered.wait(), 5)
        assert task.cancel()
        await asyncio.wait_for(closing.wait(), 5)
        assert task.cancel()
        done, _ = await asyncio.wait({task}, timeout=0.1)
        assert not done, "campaign abandoned a native generation finalizer"
    finally:
        release.set()
        scene.gate.set()
        if not closing.is_set() and not task.done():
            task.cancel()
        await asyncio.gather(task, *held, return_exceptions=True)
    assert task.cancelled()
    assert scene.active == 0 and all(b.closed for b in scene.created)
    assert len(scene.created) == 3 and all(waiter.done() for waiter in held)


def test_closed_family_stream_hash_matches_native_canonical_digest():
    from chimeraforge.bench.fleet_campaign_types import canonical_hash
    from chimeraforge.planner.replay import digest

    values = [
        None,
        True,
        1,
        1.0,
        -0.0,
        1e-30,
        1e30,
        "\u03bb\n$\\",
        [],
        {},
        {"z": [True, None, {"a": "\u65e5\u672c\u8a9e", "x": 1.0}], "a": "\u0001"},
    ]
    assert all(canonical_hash(value) == digest(value) for value in values)


@pytest.mark.asyncio
async def test_completed_child_late_drain_retains_completion_but_expires_campaign(
    native_fleet, scene, monkeypatch
):
    from chimeraforge.bench import fleet_campaign

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    original_execution, original_join = fleet_campaign._execution, fleet_campaign._join_owned
    deadline = []

    async def execution(*args):
        deadline.append(args[3])
        return await original_execution(*args)

    async def join(child, waiter):
        await original_join(child, waiter)
        assert child.result()._data["status"] == "completed"
        assert fleet_campaign._clock() < deadline[0]
        # Deterministic unit boundary after actual native completion/owned join.
        monkeypatch.setattr(fleet_campaign, "_clock", lambda: deadline[0] + 1)

    monkeypatch.setattr(fleet_campaign, "_execution", execution)
    monkeypatch.setattr(fleet_campaign, "_join_owned", join)
    result = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=1,
        campaign_timeout=60,
        candidate_index=indices["vllm"],
    )
    data = result.to_dict()
    assert data["executions"][0]["state"] == "completed"
    assert data["executions"][0]["receipt"]["native_trace"]["execution"]["completed"] == 6
    assert data["stop_reason"] == "campaign_deadline"
    assert data["state"] == "incomplete" and data["exit_code"] == 1
