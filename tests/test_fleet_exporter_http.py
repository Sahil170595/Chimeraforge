"""Actual loopback HTTP policy and cancellation of owned exporter lifetimes."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
import pytest

from chimeraforge import api
from chimeraforge.fleet_exporter import FleetExporter
from test_fleet_exporter_state import Scene, changed, controls
from test_fleet_monitor import native_fleet as native_fleet


@pytest.mark.asyncio
async def test_readyz_uses_native_fresh_snapshot_without_backend_contact(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=10, stale_after_seconds=20)
    async with api.serve_fleet_exporter(
        saved, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        snapshot = await changed(running)
        before = len(scene.calls)
        readiness = running.metrics_url.removesuffix("/metrics") + "/readyz"
        assert running.readiness_url == readiness
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(readiness)
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "schema_version": 1,
                "kind": "chimeraforge.fleet-exporter-readiness",
                "ready": True,
                "state": "fresh",
                "age_seconds": data["age_seconds"],
                "sequence": snapshot.sequence,
                "native_exit_code": 0,
            }
            assert data["age_seconds"] >= 0 and len(response.content) <= 1024
            assert response.headers["cache-control"] == "no-store"
            assert "private" not in response.text
            head = await client.head(readiness)
            assert head.status_code == 200 and not head.content
        assert len(scene.calls) == before
    assert running.closed and running.worker_joined and running.listener_joined


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,code", [("breach", 3), ("missing", 4), ("reset", 4), ("mismatch", 5)]
)
async def test_readyz_fresh_native_nonpass_is_still_ready(native_fleet, monkeypatch, mode, code):
    if mode == "breach":
        from test_monitor_slo import pair

        monkeypatch.setattr("test_fleet_exporter_state.pair", lambda: pair(ttft=0.7))
    scene = Scene(monkeypatch)
    if mode != "breach":
        scene.mode = mode
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=10, stale_after_seconds=20)
    async with api.serve_fleet_exporter(
        saved, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        snapshot = await changed(running)
        assert snapshot.native_exit_code == code
        before = len(scene.calls)
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(running.readiness_url)
        assert response.status_code == 200
        assert response.json()["ready"] is True and response.json()["native_exit_code"] == code
        assert len(scene.calls) == before


@pytest.mark.asyncio
async def test_readyz_initial_and_cached_unavailable_states(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    scene.mode = "stall"
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=60, stale_after_seconds=20)
    async with api.serve_fleet_exporter(
        saved,
        replace(controls(), observation_seconds=5),
        config=config,
        candidate_index=indices["vllm"],
    ) as running:
        for _ in range(200):
            if scene.stalled.is_set() and len(scene.calls) == 3:
                break
            await asyncio.sleep(0.01)
        assert scene.stalled.is_set() and len(scene.calls) == 3
        before = len(scene.calls)
        async with httpx.AsyncClient(trust_env=False) as client:
            initial = await client.get(running.readiness_url)
            assert initial.status_code == 503
            data = initial.json()
            assert data["ready"] is False and data["state"] == "initial"
            assert data["age_seconds"] is None and data["sequence"] == 0
            for state in ("unavailable", "stopped"):
                running._cache.publish(None, state)
                response = await client.get(running.readiness_url)
                snapshot = running.snapshot()
                assert response.status_code == 503
                assert response.json()["state"] == snapshot.state == state
                assert response.json()["sequence"] == snapshot.sequence
                assert response.json()["native_exit_code"] == snapshot.native_exit_code == 4
                assert response.json()["ready"] is False
        assert len(scene.calls) == before
    assert running.closed and running.worker_joined and running.listener_joined


@pytest.mark.asyncio
async def test_readyz_expiry_and_http_admission_are_cache_only(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=60, stale_after_seconds=20)
    async with api.serve_fleet_exporter(
        saved, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        first = await changed(running)
        before = len(scene.calls)
        async with httpx.AsyncClient(trust_env=False) as client:
            assert (await client.post(running.readiness_url)).status_code == 405
            for suffix in ("?private=secret", "/extra"):
                assert (await client.get(running.readiness_url + suffix)).status_code == 404
            assert (
                await client.get(running.readiness_url.replace("/readyz", "/%72eadyz"))
            ).status_code == 404
            assert (
                await client.request("GET", running.readiness_url, content=b"x")
            ).status_code == 400
            assert (
                await client.get(running.readiness_url, headers={"Transfer-Encoding": "chunked"})
            ).status_code == 400
            assert (await client.get(running.readiness_url + "/" + "x" * 3000)).status_code == 414
            assert (
                await client.get(running.readiness_url, headers={"X-Pad": "x" * 20000})
            ).status_code in {400, 431}
            with monkeypatch.context() as scope:
                scope.setattr("chimeraforge.fleet_exporter.MAX_READINESS_BYTES", 1)
                limited = await client.get(running.readiness_url)
                assert limited.status_code == 503 and not limited.content
            with running._cache._lock:
                entry = running._cache._entry
                assert entry.monotonic is not None
                running._cache._entry = replace(entry, monotonic=entry.monotonic - 21)
            stale = await client.get(running.readiness_url)
            assert stale.status_code == 503 and stale.json()["state"] == "stale"
            assert stale.json()["ready"] is False and stale.json()["native_exit_code"] == 4
            assert stale.json()["sequence"] == first.sequence and stale.json()["age_seconds"] >= 20
            head = await client.head(running.readiness_url)
            assert head.status_code == 503 and not head.content
            assert 0 < int(head.headers["content-length"]) <= 1024
            metrics = await client.get(running.metrics_url)
            assert metrics.content == running.snapshot().body
        assert len(scene.calls) == before


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
