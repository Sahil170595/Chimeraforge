"""Private boundary capture binds raw clock and census facts to one immutable entry."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
import math
import threading
from types import SimpleNamespace

import pytest

from chimeraforge import api, fleet_exporter, fleet_exporter_cache
from chimeraforge.fleet_monitor_types import FleetMonitorReport
from test_fleet_monitor import native_fleet as native_fleet
from test_fleet_exporter_state import Scene, controls
from test_fleet_exporter_run import config
from test_fleet_exporter_run_state import watch


async def prepared(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    handles, _ = watch(monkeypatch)
    reports = []
    native = fleet_exporter.monitor_fleet

    async def remember(*args, **kwargs):
        report = await native(*args, **kwargs)
        if not kwargs["stop_event"].is_set():
            reports.append(report)
        return report

    monkeypatch.setattr(fleet_exporter, "monitor_fleet", remember)
    saved, indices = native_fleet
    result = await api.run_fleet_exporter(
        saved,
        controls(),
        candidate_index=indices["vllm"],
        config=config(),
        policy=api.FleetExporterRunPolicy(0.2, True),
    )
    assert result.exit_code == 0 and reports
    return handles[0], reports[0], scene


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "age,code",
    [
        (0.0, 0),
        (9.999, 0),
        (10.0, 4),
        (10.001, 4),
        (-1.0, 4),
        (float("nan"), 4),
        (float("inf"), 4),
        (float("-inf"), 4),
    ],
)
async def test_raw_clock_not_default_clamping_decides_gate(native_fleet, monkeypatch, age, code):
    running, report, scene = await prepared(native_fleet, monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(
        fleet_exporter_cache,
        "time",
        SimpleNamespace(time=lambda: 100.0, monotonic=lambda: clock[0]),
    )
    running._cache.publish(report)
    clock[0] = 10.0 + age
    public = running.snapshot()
    captured = running._cache._capture()
    result = fleet_exporter._finish_run(
        running, fleet_exporter._RunBoundary(True, 0.2, captured), True
    )
    assert result.exit_code == code and result.observed_native_exit_code == 0
    assert result.population_bound and result.sequence == public.sequence
    if age < 0 or not math.isfinite(age):
        assert result.snapshot_state == "invalid_clock" and result.age_seconds is None
    if age == -1.0 or math.isnan(age):
        assert public.state == "fresh" and public.age_seconds == 0
    if age >= 10:
        assert public.state == "stale" and public.native_exit_code == 4
    assert running.closed and scene.calls


@pytest.mark.asyncio
async def test_capture_and_population_fact_are_one_entry_under_publication_race(
    native_fleet, monkeypatch
):
    running, report, _ = await prepared(native_fleet, monkeypatch)
    entered, attempted = threading.Event(), threading.Event()
    active = [False]

    def monotonic():
        if active[0]:
            entered.set()
            assert attempted.wait(1)
        return 10.0

    monkeypatch.setattr(
        fleet_exporter_cache, "time", SimpleNamespace(time=lambda: 100.0, monotonic=monotonic)
    )
    cache = running._cache
    cache.publish(report)
    original_sequence = cache.snapshot().sequence

    def publish():
        assert entered.wait(1)
        attempted.set()
        cache.publish(replace(report, slots=report.slots[:-1]))

    writer = threading.Thread(target=publish, name="exporter-cache-race-proof")
    writer.start()
    try:
        active[0] = True
        captured = cache._capture()
    finally:
        active[0] = False
        writer.join(2)
    assert not writer.is_alive()
    assert captured.snapshot.sequence == original_sequence
    assert captured.native_code == 0 and captured.observation.bound
    assert captured.observation.expected == captured.observation.observed == 3
    later = cache._capture()
    assert later.snapshot.sequence == original_sequence + 1 and not later.observation.bound
    assert later.observation.expected == 3 and later.observation.observed == 2
    with pytest.raises(FrozenInstanceError):
        captured.observation.bound = False
    assert all(type(value) is not FleetMonitorReport for value in vars(cache._entry).values())
    assert {field.name for field in fields(api.FleetExporterSnapshot)} == {
        "body",
        "state",
        "age_seconds",
        "sequence",
        "native_exit_code",
        "original_replicas",
        "published_unix_seconds",
    }


@pytest.mark.asyncio
async def test_unavailable_and_stopped_templates_are_not_real_observations(
    native_fleet, monkeypatch
):
    running, report, _ = await prepared(native_fleet, monkeypatch)
    for state in ("unavailable", "stopped"):
        running._cache.publish(None, state)
        captured = running._cache._capture()
        result = fleet_exporter._finish_run(
            running, fleet_exporter._RunBoundary(True, 0.2, captured), True
        )
        assert captured.observation is None
        assert result.exit_code == 4 and result.observed_native_exit_code is None
        assert result.observed_replicas == 0 and result.expected_replicas == 3
        assert not result.population_bound and report.exit_code == 0
