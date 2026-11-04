"""Actual loopback HTTP policy and cancellation of owned exporter lifetimes."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from chimeraforge import api
from chimeraforge.fleet_exporter import FleetExporter
from test_fleet_exporter_state import Scene, changed, controls
from test_fleet_monitor import native_fleet as native_fleet


@pytest.mark.asyncio
async def test_http_methods_paths_body_and_cached_head(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=10, stale_after_seconds=20)
    async with api.serve_fleet_exporter(
        saved, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        snapshot = await changed(running)
        before = len(scene.calls)
        async with httpx.AsyncClient(trust_env=False) as client:
            head = await client.head(running.metrics_url)
            assert head.status_code == 200 and not head.content
            assert int(head.headers["content-length"]) == len(snapshot.body)
            assert head.headers["x-chimeraforge-snapshot-state"] == "fresh"
            assert float(head.headers["x-chimeraforge-snapshot-age-seconds"]) >= 0
            assert (await client.post(running.metrics_url)).status_code == 405
            assert (await client.get(running.metrics_url + "?private=secret")).status_code == 404
            assert (await client.get(running.metrics_url + "/other")).status_code == 404
            assert (
                await client.request("GET", running.metrics_url, content=b"x")
            ).status_code == 400
            assert (
                await client.get(running.metrics_url, headers={"X-Pad": "x" * 20000})
            ).status_code in {400, 431}
        assert len(scene.calls) == before


@pytest.mark.asyncio
async def test_oversized_path_has_explicit_admission_before_dispatch(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=10, stale_after_seconds=20)
    async with api.serve_fleet_exporter(
        saved, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        await changed(running)
        before = len(scene.calls)
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(running.metrics_url + "/" + "x" * 3000)
        assert response.status_code == 414
        assert len(scene.calls) == before


@pytest.mark.asyncio
async def test_cancelled_startup_entry_joins_poll_and_listener(native_fleet, monkeypatch):
    Scene(monkeypatch)
    saved, indices = native_fleet
    captured = []
    entered = asyncio.Event()
    native = FleetExporter.start

    async def pause(self):
        await native(self)
        captured.append(self)
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(FleetExporter, "start", pause)

    async def operation():
        async with api.serve_fleet_exporter(
            saved,
            controls(),
            config=api.FleetExporterConfig(port=0),
            candidate_index=indices["vllm"],
        ):
            pytest.fail("startup pause bypassed")

    task = asyncio.create_task(operation())
    await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert captured[0].closed and captured[0].worker_joined and captured[0].listener_joined


@pytest.mark.asyncio
async def test_direct_close_cancellation_returns_only_after_owned_join(native_fleet, monkeypatch):
    Scene(monkeypatch)
    saved, indices = native_fleet
    async with api.serve_fleet_exporter(
        saved, controls(), config=api.FleetExporterConfig(port=0), candidate_index=indices["vllm"]
    ) as running:
        close = asyncio.create_task(running.aclose())
        await asyncio.sleep(0)
        close.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close
        assert running.closed and running.worker_joined and running.listener_joined


@pytest.mark.asyncio
async def test_repeated_context_cancellation_does_not_orphan_worker(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    scene.mode = "stall"
    saved, indices = native_fleet
    active = asyncio.Event()
    captured = []

    async def operation():
        async with api.serve_fleet_exporter(
            saved,
            controls(),
            config=api.FleetExporterConfig(port=0),
            candidate_index=indices["vllm"],
        ) as running:
            captured.append(running)
            active.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(operation())
    await asyncio.wait_for(active.wait(), 3)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert captured[0].closed and captured[0].worker_joined and captured[0].listener_joined
    assert all(p.closed == 1 for p in scene.pools)
