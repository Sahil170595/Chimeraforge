"""A finite deadline cannot promote stale, foreign, partial or failed lifecycle evidence."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import fields, replace
import json

import httpx
import pytest
from typer.testing import CliRunner

from chimeraforge import api, fleet_exporter
from chimeraforge.cli import app
from chimeraforge.fleet_monitor_types import FleetMonitorReport, FleetSlot
from test_fleet_monitor import fleet_server, native_fleet as native_fleet, request
from test_fleet_exporter_state import Scene, changed, controls
from test_fleet_exporter_run import config


def watch(monkeypatch):
    native = api.serve_fleet_exporter
    handles, ready = [], asyncio.Event()

    @asynccontextmanager
    async def watched(*args, **kwargs):
        async with native(*args, **kwargs) as running:
            handles.append(running)
            ready.set()
            yield running

    monkeypatch.setattr(api, "serve_fleet_exporter", watched)
    return handles, ready


def capture_first_native_zero(monkeypatch):
    native_boundary = fleet_exporter._await_run_boundary
    boundaries = []

    async def boundary(running, seconds, stop):
        # Exercise qualification of the published report regardless of fixture scheduling.
        first = await changed(running)
        assert first.native_exit_code == 0
        result = await native_boundary(running, seconds, stop)
        assert result.deadline_reached and result.observation.in_time
        assert result.observation.snapshot.sequence == first.sequence
        boundaries.append(result)
        return result

    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary)
    return boundaries


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,code", [("mismatch", 5), ("missing", 4)])
async def test_fresh_readiness_does_not_qualify_native_nonpass(
    native_fleet, monkeypatch, mode, code
):
    scene = Scene(monkeypatch)
    scene.mode = mode
    handles, ready = watch(monkeypatch)
    probed = asyncio.Event()
    native_boundary = fleet_exporter._await_run_boundary

    async def boundary_after_probe(running, seconds, stop):
        # Keep the listener open until the observation has actually been read.
        await probed.wait()
        return await native_boundary(running, seconds, stop)

    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary_after_probe)
    saved, indices = native_fleet
    task = asyncio.create_task(
        api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(0.3, True),
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        fresh = await changed(handles[0])
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(handles[0].readiness_url)
        assert response.status_code == 200 and fresh.native_exit_code == code
    finally:
        probed.set()
        result = await asyncio.wait_for(task, timeout=10)
    assert result.exit_code == result.observed_native_exit_code == code
    assert not result.qualification_met and result.population_bound
    assert result.closed and result.worker_joined and result.listener_joined


@pytest.mark.asyncio
async def test_native_slo_breach_keeps_three(native_fleet, monkeypatch):
    native_boundary = fleet_exporter._await_run_boundary

    async def boundary_after_observation(running, seconds, stop):
        # Exercise the breach mapping after a full real observation arrives.
        await changed(running)
        return await native_boundary(running, seconds, stop)

    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary_after_observation)
    saved, indices = native_fleet
    with fleet_server(ttft=0.7) as (urls, _):
        result = await api.run_fleet_exporter(
            saved,
            replace(request(urls), ttft_slo=400),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(1, True),
        )
    assert result.exit_code == result.observed_native_exit_code == 3
    assert result.population_bound and result.qualification_met is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        "empty",
        "partial",
        "extra",
        "reordered",
        "id",
        "url",
        "plan",
        "index",
        "identity",
        "producer-tool",
        "monitor-tool",
        "backend",
        "model",
        "controls",
        "slot-type",
        "report-type",
    ],
)
async def test_native_zero_with_wrong_population_or_binding_is_four(
    native_fleet, monkeypatch, fault
):
    Scene(monkeypatch)
    saved, indices = native_fleet
    native = fleet_exporter.monitor_fleet

    class OtherSlot(FleetSlot):
        pass

    class OtherReport(FleetMonitorReport):
        pass

    async def altered(*args, **kwargs):
        report = await native(*args, **kwargs)
        if kwargs["stop_event"].is_set():
            return replace(report, slots=()) if fault == "empty" else report
        assert report.exit_code == 0
        slots = report.slots
        if fault == "empty":
            report = replace(report, slots=())
        elif fault == "partial":
            report = replace(report, slots=slots[:-1])
        elif fault == "extra":
            report = replace(report, slots=(*slots, replace(slots[0], id="PRIVATE-extra")))
        elif fault == "reordered":
            report = replace(report, slots=tuple(reversed(slots)))
        elif fault in ("id", "url"):
            report = replace(
                report, slots=(replace(slots[0], **{fault: "PRIVATE-foreign"}), *slots[1:])
            )
        elif fault in ("plan", "index", "identity", "producer-tool"):
            plan = dict(report.plan)
            if fault == "plan":
                plan["fingerprint"] = "f" * 64
            elif fault == "index":
                plan["candidate_index"] += 1
            elif fault == "identity":
                plan["identity"] = {**plan["identity"], "n_agents": 2}
            else:
                plan["tool_version"] = "0.0.0"
            report = replace(report, plan=plan)
        elif fault == "monitor-tool":
            report = replace(report, monitor_tool_version="0.0.0")
        elif fault in ("backend", "model"):
            report = replace(report, **{fault: "PRIVATE-foreign"})
        elif fault == "controls":
            report = replace(report, effective_controls={})
        elif fault == "slot-type":
            other = OtherSlot(
                **{field.name: getattr(slots[0], field.name) for field in fields(FleetSlot)}
            )
            report = replace(report, slots=(other, *slots[1:]))
        else:
            report = OtherReport(
                **{field.name: getattr(report, field.name) for field in fields(FleetMonitorReport)}
            )
        assert report.exit_code == 0
        return report

    monkeypatch.setattr(fleet_exporter, "monitor_fleet", altered)
    capture_first_native_zero(monkeypatch)
    result = await api.run_fleet_exporter(
        saved,
        controls(),
        candidate_index=indices["vllm"],
        config=config(),
        policy=api.FleetExporterRunPolicy(0.25, True),
    )
    assert result.exit_code == 4 and result.qualification_met is False
    assert result.expected_replicas == 3 and not result.population_bound
    assert result.observed_native_exit_code == (None if fault == "report-type" else 0)
    assert result.closed and result.listener_joined and result.worker_joined


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["raise", "missing", "mismatch"])
async def test_newer_native_nonpass_replaces_pass_at_boundary(native_fleet, monkeypatch, mode):
    scene = Scene(monkeypatch)
    handles, ready = watch(monkeypatch)
    saved, indices = native_fleet
    observed = asyncio.Event()
    native_boundary = fleet_exporter._await_run_boundary

    async def boundary_after_nonpass(running, seconds, stop):
        # Set the finite deadline after the replacement becomes visible.
        await observed.wait()
        return await native_boundary(running, seconds, stop)

    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary_after_nonpass)
    task = asyncio.create_task(
        api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=replace(config(), poll_seconds=1.0),
            policy=api.FleetExporterRunPolicy(0.2, True),
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        first = await changed(handles[0])
        assert first.native_exit_code == 0
        scene.mode = mode
        later = await changed(handles[0], first.sequence)
        assert later.native_exit_code == (5 if mode == "mismatch" else 4)
    finally:
        observed.set()
        result = await asyncio.wait_for(task, timeout=10)
    assert result.exit_code == (5 if mode == "mismatch" else 4)
    assert result.sequence > first.sequence and not result.qualification_met


@pytest.mark.asyncio
async def test_clean_external_stop_is_four_even_after_pass(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    handles, ready = watch(monkeypatch)
    saved, indices = native_fleet
    stop = asyncio.Event()
    task = asyncio.create_task(
        api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=config(),
            stop_event=stop,
            policy=api.FleetExporterRunPolicy(20, True),
        )
    )
    await ready.wait()
    assert (await changed(handles[0])).native_exit_code == 0
    stop.set()
    result = await task
    assert result.exit_code == 4 and result.boundary == "stopped"
    assert result.observed_native_exit_code == 0 and result.population_bound
    after = len(scene.calls)
    await asyncio.sleep(0.03)
    assert (
        len(scene.calls) == after
        and result.closed
        and result.worker_joined
        and result.listener_joined
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["worker", "listener"])
async def test_real_late_failure_after_pass_overrides_join_flags(native_fleet, monkeypatch, fault):
    Scene(monkeypatch)
    handles, _ = watch(monkeypatch)
    boundaries = capture_first_native_zero(monkeypatch)
    name = "_poll" if fault == "worker" else "_serve"
    native = getattr(fleet_exporter.FleetExporter, name)

    async def failure(self):
        await native(self)
        raise RuntimeError("PRIVATE-late-failure")

    monkeypatch.setattr(fleet_exporter.FleetExporter, name, failure)
    saved, indices = native_fleet
    with pytest.raises(api.FleetExporterError, match="startup or shutdown") as caught:
        await api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(0.25, True),
        )
    assert boundaries and boundaries[0].observation.native_code == 0
    running = handles[0]
    assert running.closed and running.listener_joined and running.worker_joined
    assert not running._clean_close and "PRIVATE-late-failure" not in str(caught.value)
    if fault == "worker":
        assert running._worker.done() and isinstance(running._worker.exception(), RuntimeError)
        running._failed = False
        assert not running._clean_close


@pytest.mark.asyncio
@pytest.mark.parametrize("during_close", [False, True])
async def test_cancellation_waits_for_owned_cleanup(native_fleet, monkeypatch, during_close):
    scene = Scene(monkeypatch)
    handles, ready = watch(monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    if during_close:
        original = fleet_exporter.FleetExporter._close_owned

        async def close(self):
            entered.set()
            await release.wait()
            await original(self)

        monkeypatch.setattr(fleet_exporter.FleetExporter, "_close_owned", close)
    saved, indices = native_fleet
    task = asyncio.create_task(
        api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(0.2 if during_close else 20, True),
        )
    )
    await ready.wait()
    await changed(handles[0])
    if during_close:
        await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert handles[0].closed and handles[0].listener_joined and handles[0].worker_joined
    before = len(scene.calls)
    await asyncio.sleep(0.03)
    assert len(scene.calls) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "seconds", [True, False, 0, -1, 86401, 10**1000, float("nan"), float("inf"), "1"]
)
async def test_invalid_duration_precedes_resource_work(monkeypatch, seconds):
    monkeypatch.setattr(
        api, "serve_fleet_exporter", lambda *a, **k: pytest.fail("resources opened")
    )
    monkeypatch.setattr(fleet_exporter, "_source", lambda *a, **k: pytest.fail("source read"))
    with pytest.raises(api.FleetExporterError):
        await api.run_fleet_exporter(
            "PRIVATE-missing.json", None, policy=api.FleetExporterRunPolicy(seconds, True)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [None, 0, 1, "true", []])
async def test_exact_boolean_precedes_work(monkeypatch, required):
    monkeypatch.setattr(
        api, "serve_fleet_exporter", lambda *a, **k: pytest.fail("resources opened")
    )
    with pytest.raises(api.FleetExporterError):
        await api.run_fleet_exporter(
            "PRIVATE-missing.json", None, policy=api.FleetExporterRunPolicy(1, required)
        )


def test_requirement_without_duration_is_invalid_before_work(monkeypatch):
    monkeypatch.setattr(
        api, "serve_fleet_exporter", lambda *a, **k: pytest.fail("resources opened")
    )
    result = CliRunner().invoke(
        app,
        [
            "monitor-fleet-exporter",
            "--from-plan",
            "PRIVATE-missing.json",
            "--endpoint",
            "private=http://127.0.0.1:1/metrics",
            "--require-final-observation",
        ],
    )
    assert result.exit_code == 1 and "PRIVATE-missing" not in result.output


@pytest.mark.asyncio
async def test_exact_policy_type_and_stop_event_precede_optional_imports(monkeypatch):
    import builtins

    native_import = builtins.__import__

    def imports(name, *args, **kwargs):
        if name.split(".")[0] in ("uvicorn", "starlette"):
            pytest.fail("invalid policy imported optional exporter dependencies")
        return native_import(name, *args, **kwargs)

    class ForeignPolicy(api.FleetExporterRunPolicy):
        pass

    monkeypatch.setattr(builtins, "__import__", imports)
    monkeypatch.setattr(
        api, "serve_fleet_exporter", lambda *a, **k: pytest.fail("resources opened")
    )
    for policy in (None, {}, True, ForeignPolicy(1, True)):
        with pytest.raises(api.FleetExporterError):
            await api.run_fleet_exporter("PRIVATE-missing", None, policy=policy)
    with pytest.raises(api.FleetExporterError, match="stop event"):
        await api.run_fleet_exporter(
            "PRIVATE-missing", None, policy=api.FleetExporterRunPolicy(1, True), stop_event=object()
        )


@pytest.mark.asyncio
async def test_sdk_ungated_native_nonpass_is_not_qualified_zero(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    scene.mode = "mismatch"
    saved, indices = native_fleet
    result = await api.run_fleet_exporter(
        saved,
        controls(),
        candidate_index=indices["vllm"],
        config=config(),
        policy=api.FleetExporterRunPolicy(0.25, False),
    )
    assert result.exit_code == 0 and result.observed_native_exit_code == 5
    assert result.qualification_met is None and not result.qualification_requested
    assert result.to_dict()["process_exit_is_qualification"] is False


@pytest.mark.asyncio
async def test_later_unavailable_replaces_old_pass_without_receipt_replay(
    native_fleet, monkeypatch
):
    Scene(monkeypatch)
    native = fleet_exporter.monitor_fleet
    completed = []

    async def observe(*args, **kwargs):
        if not kwargs["stop_event"].is_set() and completed:
            raise RuntimeError("PRIVATE-poll-unavailable")
        report = await native(*args, **kwargs)
        if not kwargs["stop_event"].is_set():
            completed.append(report.exit_code)
        return report

    monkeypatch.setattr(fleet_exporter, "monitor_fleet", observe)
    saved, indices = native_fleet
    result = await api.run_fleet_exporter(
        saved,
        controls(),
        candidate_index=indices["vllm"],
        config=replace(config(), poll_seconds=0.02),
        policy=api.FleetExporterRunPolicy(0.4, True),
    )
    assert completed == [0] and result.exit_code == 4
    assert result.snapshot_state == "unavailable" and result.observed_native_exit_code is None
    assert result.observed_replicas == 0 and not result.population_bound
    assert "PRIVATE-poll-unavailable" not in json.dumps(result.to_dict())


@pytest.mark.asyncio
async def test_sdk_holds_plan_path_once_without_boundary_reload(
    native_fleet, monkeypatch, tmp_path
):
    from pathlib import Path
    from chimeraforge import deployment_verify

    scene = Scene(monkeypatch)
    handles, ready = watch(monkeypatch)
    saved, indices = native_fleet
    path = tmp_path / "source.json"
    saved.save(path)
    native_source = deployment_verify._source
    path_reads = []

    def source(value):
        if isinstance(value, (str, Path)):
            path_reads.append(Path(value))
        return native_source(value)

    monkeypatch.setattr(deployment_verify, "_source", source)
    task = asyncio.create_task(
        api.run_fleet_exporter(
            path,
            controls(),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(0.3, True),
        )
    )
    await ready.wait()
    await changed(handles[0])
    path.write_bytes(b"changed after startup")
    result = await task
    assert result.exit_code == 0 and path_reads == [path]
    before = len(scene.calls)
    await asyncio.sleep(0.03)
    assert len(scene.calls) == before
