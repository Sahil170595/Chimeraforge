"""Native cleanup failures cannot be hidden by a previously captured PASS."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api, fleet_exporter
from chimeraforge import fleet_monitor
from chimeraforge.cli import app
from chimeraforge.fleet_monitor_types import FleetMonitorError
from test_fleet_monitor import native_fleet as native_fleet
from test_fleet_exporter_state import Scene, controls
from test_fleet_monitor_transport import Transport

NORMAL_CLEANUP_SECONDS = 1.0
SHORT_CLEANUP_SECONDS = 0.1


def native_shutdown(monkeypatch, fault, *, recover=False):
    scene = Scene(monkeypatch)
    native_monitor = fleet_exporter.monitor_fleet
    native_close = Transport.aclose
    native_serve = api.serve_fleet_exporter
    native_boundary = fleet_exporter._await_run_boundary
    polls, reports, handles, boundaries = [0], [], [], []

    async def close(self):
        await native_close(self)
        failing = polls[0] == 1 if recover else polls[0] >= 2
        if failing:
            if fault == "close-error":
                raise RuntimeError("PRIVATE-native-transport-close-error")
            if fault == "allowance":
                await asyncio.sleep(0.2)

    async def monitor(*args, **kwargs):
        if not kwargs["stop_event"].is_set():
            polls[0] += 1
            if polls[0] >= 2 and not recover:
                scene.mode = "stall"
        report = await native_monitor(*args, **kwargs)
        if polls[0]:
            reports.append(report)
        return report

    @asynccontextmanager
    async def serving(*args, **kwargs):
        async with native_serve(*args, **kwargs) as running:
            handles.append(running)
            yield running

    async def boundary(*args):
        value = await native_boundary(*args)
        boundaries.append(value)
        return value

    monkeypatch.setattr(Transport, "aclose", close)
    monkeypatch.setattr(fleet_exporter, "monitor_fleet", monitor)
    monkeypatch.setattr(api, "serve_fleet_exporter", serving)
    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary)
    return scene, reports, handles, boundaries


def assert_native_shutdown(scene, reports, handles, fault):
    running = handles[0]
    tail = reports[-1]
    assert tail.cancelled and tail.exit_code == 4
    assert tail.cleanup["state"] == ("completed" if fault == "completed" else "incomplete"), (
        tail.cleanup
    )
    assert tail.cleanup["close_errors"] == (3 if fault == "close-error" else 0)
    assert tail.cleanup["allowance_exceeded"] is (fault == "allowance")
    assert tail.cleanup["resources_closed"] is (fault != "close-error")
    assert tail.cleanup["owned_pools"] == 6 and tail.cleanup["joined_endpoint_tasks"] == 3
    assert running.closed and running.listener_joined and running.worker_joined
    assert running._socket.fileno() == -1 and not running._thread.is_alive()
    assert running._worker.done() and running._worker.exception() is None
    assert not running._failed
    assert len(scene.pools) == 9 and all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["close-error", "allowance", "completed"])
async def test_real_native_tail_cleanup_is_authoritative_after_captured_pass(
    native_fleet, monkeypatch, fault
):
    scene, reports, handles, boundaries = native_shutdown(monkeypatch, fault)
    saved, indices = native_fleet
    result, error = None, None
    cleanup_seconds = SHORT_CLEANUP_SECONDS if fault == "allowance" else NORMAL_CLEANUP_SECONDS
    try:
        result = await asyncio.wait_for(
            api.run_fleet_exporter(
                saved,
                replace(controls(), cleanup_seconds=cleanup_seconds),
                candidate_index=indices["vllm"],
                config=api.FleetExporterConfig(port=0, poll_seconds=0.01, stale_after_seconds=10),
                policy=api.FleetExporterRunPolicy(0.4, True),
            ),
            5,
        )
    except api.FleetExporterError as caught:
        error = caught
    assert_native_shutdown(scene, reports, handles, fault)
    assert len(boundaries) == 1 and boundaries[0].observation.native_code == 0
    assert boundaries[0].observation.snapshot.state == "fresh"
    after = len(scene.calls)
    await asyncio.sleep(0.03)
    assert len(scene.calls) == after
    if fault == "completed":
        assert error is None and result.exit_code == 0 and handles[0]._clean_close
    else:
        assert result is None and isinstance(error, api.FleetExporterError)
        assert str(error) == "exporter startup or shutdown unavailable"
        assert not handles[0]._clean_close


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("fault", ["close-error", "allowance"])
def test_cli_native_cleanup_failure_preserves_default_and_fails_selected(
    native_fleet, monkeypatch, tmp_path, fault, required
):
    scene, reports, handles, boundaries = native_shutdown(monkeypatch, fault)
    saved, indices = native_fleet
    path = tmp_path / "saved.json"
    saved.save(path)
    cleanup_seconds = SHORT_CLEANUP_SECONDS if fault == "allowance" else NORMAL_CLEANUP_SECONDS
    args = [
        "monitor-fleet-exporter",
        "--from-plan",
        str(path),
        "--candidate-index",
        str(indices["vllm"]),
        "--listen-port",
        "0",
        "--interval",
        "0.01",
        "--observation-seconds",
        "0.5",
        "--cleanup-seconds",
        str(cleanup_seconds),
        "--poll-seconds",
        "0.01",
        "--run-seconds",
        "0.4",
        "--ttft-slo",
        "500",
    ]
    for endpoint in controls().endpoints:
        args += ["--endpoint", f"{endpoint.id}={endpoint.url}"]
    if required:
        args.append("--require-final-observation")
    result = CliRunner().invoke(app, args)
    assert_native_shutdown(scene, reports, handles, fault)
    rows = [json.loads(row) for row in result.stdout.splitlines()]
    assert len(rows) == 2 and rows[0]["process_exit_is_qualification"] is required
    assert rows[1]["kind"] == "chimeraforge.fleet-exporter-closed"
    assert result.exit_code == (1 if required else 0)
    assert bool(boundaries) is required
    if required:
        assert boundaries[0].observation.native_code == 0
        assert result.stderr.strip() == "Error: invalid, unsupported or unavailable fleet exporter"
    else:
        assert not result.stderr


@pytest.mark.asyncio
async def test_native_cleanup_failure_stays_failed_after_a_newer_real_pass(
    native_fleet, monkeypatch
):
    scene, reports, handles, boundaries = native_shutdown(monkeypatch, "close-error", recover=True)
    saved, indices = native_fleet
    with pytest.raises(api.FleetExporterError, match="startup or shutdown"):
        await api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=api.FleetExporterConfig(port=0, poll_seconds=0.1, stale_after_seconds=10),
            policy=api.FleetExporterRunPolicy(0.4, True),
        )
    assert reports[0].cleanup["state"] == "incomplete" and reports[0].exit_code == 4
    assert any(report.exit_code == 0 for report in reports[1:])
    assert boundaries[0].observation.native_code == 0
    running = handles[0]
    assert not running._clean_close and not running._failed
    assert running.closed and running.listener_joined and running.worker_joined
    assert running._socket.fileno() == -1 and not running._thread.is_alive()
    assert running._worker.done() and running._worker.exception() is None
    assert all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)


def native_setup(monkeypatch, fail_close):
    scene = Scene(monkeypatch)
    native_monitor = fleet_exporter.monitor_fleet
    native_backend = fleet_monitor.get_backend
    native_cleanup = fleet_monitor._cleanup
    native_serve = api.serve_fleet_exporter
    native_boundary = fleet_exporter._await_run_boundary
    facts = {
        name: []
        for name in ("created", "closed", "cleanup", "owners", "errors", "handles", "boundaries")
    }
    polls, building = [0], [0]

    def backend(*args, **kwargs):
        if polls[0] == 2 and building[0] == 2:
            raise RuntimeError("PRIVATE-native-setup-error")
        value = native_backend(*args, **kwargs)
        if polls[0] == 2:
            building[0] += 1
            facts["created"].append(value)
            native_close = value.close

            async def close():
                await native_close()
                facts["closed"].append(value)
                if fail_close:
                    raise RuntimeError("PRIVATE-native-backend-close-error")

            value.close = close
        return value

    async def cleanup(tasks, owners, seconds):
        result = await native_cleanup(tasks, owners, seconds)
        if polls[0] == 2:
            facts["owners"].extend(owners)
            facts["cleanup"].append(result)
        return result

    async def monitor(*args, **kwargs):
        if not kwargs["stop_event"].is_set():
            polls[0] += 1
        try:
            return await native_monitor(*args, **kwargs)
        except FleetMonitorError as error:
            facts["errors"].append(error)
            raise

    @asynccontextmanager
    async def serving(*args, **kwargs):
        async with native_serve(*args, **kwargs) as running:
            facts["handles"].append(running)
            yield running

    async def boundary(*args):
        value = await native_boundary(*args)
        facts["boundaries"].append(value)
        return value

    monkeypatch.setattr(fleet_monitor, "get_backend", backend)
    monkeypatch.setattr(fleet_monitor, "_cleanup", cleanup)
    monkeypatch.setattr(fleet_exporter, "monitor_fleet", monitor)
    monkeypatch.setattr(api, "serve_fleet_exporter", serving)
    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary)
    return scene, facts


def assert_setup_cleanup(scene, facts, fail_close):
    cleanup = facts["cleanup"][0]
    assert cleanup["state"] == ("incomplete" if fail_close else "completed")
    assert cleanup["resources_closed"] and not cleanup["allowance_exceeded"]
    assert cleanup["close_errors"] == (2 if fail_close else 0)
    assert cleanup["owned_pools"] == cleanup["closed_pools"] == 6
    assert cleanup["joined_endpoint_tasks"] == 0
    assert len(facts["created"]) == len(facts["closed"]) == 2
    assert len(facts["owners"]) == 3 and all(row.client.is_closed for row in facts["owners"])
    assert (
        sum(row.metrics_pool.requests + row.metadata_pool.requests for row in facts["owners"]) == 0
    )
    error = facts["errors"][0]
    assert type(error) is FleetMonitorError
    assert error.args == ("fleet observation resources could not be initialized or coordinated",)
    assert error._cleanup_failed is fail_close
    running = facts["handles"][0]
    assert running.closed and running.listener_joined and running.worker_joined
    assert not running._thread.is_alive() and running._socket.fileno() == -1
    assert running._worker.done() and running._worker.exception() is None and not running._failed
    assert all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_close", [False, True])
async def test_real_setup_cleanup_error_survives_unavailable_then_newer_pass(
    native_fleet, monkeypatch, fail_close
):
    from test_fleet_exporter_state import changed

    scene, facts = native_setup(monkeypatch, fail_close)
    saved, indices = native_fleet
    result, error = None, None
    task = asyncio.create_task(
        api.run_fleet_exporter(
            saved,
            controls(),
            candidate_index=indices["vllm"],
            config=api.FleetExporterConfig(port=0, poll_seconds=0.1, stale_after_seconds=10),
            policy=api.FleetExporterRunPolicy(0.6, True),
        )
    )
    while not facts["handles"]:
        await asyncio.sleep(0.01)
    unavailable = await changed(facts["handles"][0], state="unavailable")
    assert unavailable.native_exit_code == 4
    recovered = await changed(facts["handles"][0], unavailable.sequence)
    assert recovered.native_exit_code == 0
    try:
        result = await task
    except api.FleetExporterError as caught:
        error = caught
    assert_setup_cleanup(scene, facts, fail_close)
    assert facts["boundaries"][0].observation.native_code == 0
    assert facts["handles"][0]._clean_close is (not fail_close)
    if fail_close:
        assert result is None and isinstance(error, api.FleetExporterError)
        assert str(error) == "exporter startup or shutdown unavailable"
    else:
        assert error is None and result.exit_code == 0


@pytest.mark.parametrize("fail_close", [False, True])
def test_cli_transient_setup_failure_preserves_native_cleanup_ownership(
    native_fleet, monkeypatch, tmp_path, fail_close
):
    scene, facts = native_setup(monkeypatch, fail_close)
    saved, indices = native_fleet
    path = tmp_path / "saved.json"
    saved.save(path)
    args = [
        "monitor-fleet-exporter",
        "--from-plan",
        str(path),
        "--candidate-index",
        str(indices["vllm"]),
        "--listen-port",
        "0",
        "--interval",
        "0.01",
        "--observation-seconds",
        "0.5",
        "--poll-seconds",
        "0.1",
        "--run-seconds",
        "0.6",
        "--ttft-slo",
        "500",
        "--require-final-observation",
    ]
    for endpoint in controls().endpoints:
        args += ["--endpoint", f"{endpoint.id}={endpoint.url}"]
    result = CliRunner().invoke(app, args)
    assert_setup_cleanup(scene, facts, fail_close)
    assert facts["boundaries"][0].observation.native_code == 0
    rows = [json.loads(row) for row in result.stdout.splitlines()]
    assert len(rows) == (2 if fail_close else 3)
    assert rows[1]["kind"] == "chimeraforge.fleet-exporter-closed"
    assert result.exit_code == (1 if fail_close else 0)
    if fail_close:
        assert result.stderr.strip() == "Error: invalid, unsupported or unavailable fleet exporter"
    else:
        assert rows[2]["qualification_met"] is True and not result.stderr


def native_seed(monkeypatch, fail_close):
    scene = Scene(monkeypatch)
    native_monitor = fleet_exporter.monitor_fleet
    native_backend = fleet_monitor.get_backend
    native_cleanup = fleet_monitor._cleanup
    native_serve = api.serve_fleet_exporter
    native_start = fleet_exporter.FleetExporter.start
    native_boundary = fleet_exporter._await_run_boundary
    seeded = [False]
    facts = {
        name: [] for name in ("reports", "closed", "owners", "handles", "starts", "boundaries")
    }

    def backend(*args, **kwargs):
        value = native_backend(*args, **kwargs)
        if seeded[0]:
            native_close = value.close

            async def close():
                await native_close()
                facts["closed"].append(value)
                if fail_close:
                    raise RuntimeError("PRIVATE-native-seed-close-error")

            value.close = close
        return value

    async def cleanup(tasks, owners, seconds):
        result = await native_cleanup(tasks, owners, seconds)
        if seeded[0]:
            facts["owners"].extend(owners)
        return result

    async def monitor(*args, **kwargs):
        seeded[0] = kwargs["stop_event"].is_set()
        seed = seeded[0]
        report = await native_monitor(*args, **kwargs)
        if seed:
            facts["reports"].append(report)
        return report

    @asynccontextmanager
    async def serving(*args, **kwargs):
        async with native_serve(*args, **kwargs) as running:
            facts["handles"].append(running)
            yield running

    async def start(self):
        facts["starts"].append(self._native_cleanup_failed)
        await native_start(self)

    async def boundary(*args):
        value = await native_boundary(*args)
        facts["boundaries"].append(value)
        return value

    monkeypatch.setattr(fleet_monitor, "get_backend", backend)
    monkeypatch.setattr(fleet_monitor, "_cleanup", cleanup)
    monkeypatch.setattr(fleet_exporter, "monitor_fleet", monitor)
    monkeypatch.setattr(api, "serve_fleet_exporter", serving)
    monkeypatch.setattr(fleet_exporter.FleetExporter, "start", start)
    monkeypatch.setattr(fleet_exporter, "_await_run_boundary", boundary)
    return scene, facts


def assert_seed_cleanup(scene, facts, fail_close):
    assert len(facts["reports"]) == 1
    seed = facts["reports"][0]
    assert seed.cancelled and seed.exit_code == 4
    assert seed.cleanup["state"] == ("incomplete" if fail_close else "completed")
    assert seed.cleanup["resources_closed"] and not seed.cleanup["allowance_exceeded"]
    assert seed.cleanup["close_errors"] == (3 if fail_close else 0)
    assert seed.cleanup["owned_pools"] == seed.cleanup["closed_pools"] == 6
    assert seed.cleanup["joined_endpoint_tasks"] == 0
    assert len(facts["closed"]) == len(facts["owners"]) == 3
    assert all(row.client.is_closed for row in facts["owners"])
    assert (
        sum(row.metrics_pool.requests + row.metadata_pool.requests for row in facts["owners"]) == 0
    )
    running = facts["handles"][0]
    assert running.closed and running.listener_joined and running.worker_joined
    assert running._socket.fileno() == -1 and not running._thread.is_alive()
    assert running._worker.done() and running._worker.exception() is None and not running._failed
    assert all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_close", [False, True])
async def test_real_cancelled_seed_cleanup_remains_owned_after_later_pass(
    native_fleet, monkeypatch, fail_close
):
    scene, facts = native_seed(monkeypatch, fail_close)
    saved, indices = native_fleet
    result, error = None, None
    try:
        result = await asyncio.wait_for(
            api.run_fleet_exporter(
                saved,
                controls(),
                candidate_index=indices["vllm"],
                config=api.FleetExporterConfig(port=0, poll_seconds=0.1, stale_after_seconds=10),
                policy=api.FleetExporterRunPolicy(0.4, True),
            ),
            5,
        )
    except api.FleetExporterError as caught:
        error = caught
    assert_seed_cleanup(scene, facts, fail_close)
    assert facts["boundaries"][0].observation.native_code == 0
    after = len(scene.calls)
    await asyncio.sleep(0.03)
    assert len(scene.calls) == after
    if fail_close:
        assert result is None and isinstance(error, api.FleetExporterError)
        assert str(error) == "exporter startup or shutdown unavailable"
    else:
        assert error is None and result.exit_code == 0
    assert facts["starts"] == [fail_close]
    assert facts["handles"][0]._clean_close is (not fail_close)


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("fail_close", [False, True])
def test_cli_seed_cleanup_keeps_startup_and_default_protocol(
    native_fleet, monkeypatch, tmp_path, required, fail_close
):
    scene, facts = native_seed(monkeypatch, fail_close)
    saved, indices = native_fleet
    path = tmp_path / "saved.json"
    saved.save(path)
    args = [
        "monitor-fleet-exporter",
        "--from-plan",
        str(path),
        "--candidate-index",
        str(indices["vllm"]),
        "--listen-port",
        "0",
        "--interval",
        "0.01",
        "--observation-seconds",
        "0.5",
        "--poll-seconds",
        "0.1",
        "--run-seconds",
        "0.4",
        "--ttft-slo",
        "500",
    ]
    for endpoint in controls().endpoints:
        args += ["--endpoint", f"{endpoint.id}={endpoint.url}"]
    if required:
        args.append("--require-final-observation")
    result = CliRunner().invoke(app, args)
    assert_seed_cleanup(scene, facts, fail_close)
    rows = [json.loads(row) for row in result.stdout.splitlines()]
    assert rows[0]["process_exit_is_qualification"] is required
    assert rows[1]["kind"] == "chimeraforge.fleet-exporter-closed"
    assert result.exit_code == (1 if required and fail_close else 0)
    assert facts["starts"] == [fail_close]
    assert len(rows) == (3 if required and not fail_close else 2)
    if required and fail_close:
        assert result.stderr.strip() == "Error: invalid, unsupported or unavailable fleet exporter"
    else:
        assert not result.stderr
