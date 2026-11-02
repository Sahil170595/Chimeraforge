"""Controlled native HTTP lifecycle, not GPU/production/physical fleet proof."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
import pytest
from click import unstyle
import typer.rich_utils
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.fleet_monitor_types import FleetEndpoint
from test_fleet_monitor import fleet_server, native_fleet as native_fleet, request


@pytest.mark.asyncio
async def test_existing_finite_native_observer_retains_original_population(native_fleet):
    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        value = replace(request(urls), interval=0.02, observation_seconds=2)
        result = await api.monitor_fleet(saved, value, candidate_index=indices["vllm"])
    assert result.exit_code == 0 and len(result.slots) == 3
    assert result.cleanup["state"] == "completed" and calls


@pytest.mark.asyncio
async def test_native_exporter_cached_scrapes_and_joined_shutdown(native_fleet):
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=10, stale_after_seconds=20)
    with fleet_server() as (urls, calls):
        value = replace(
            request(urls),
            endpoints=tuple(FleetEndpoint(f"private-id-{i}", url) for i, url in enumerate(urls)),
            interval=0.02,
            observation_seconds=2,
        )
        async with api.serve_fleet_exporter(
            saved, value, config=config, candidate_index=indices["vllm"]
        ) as running:
            for _ in range(200):
                if running.snapshot().state == "fresh":
                    break
                await asyncio.sleep(0.01)
            snapshot = running.snapshot()
            assert snapshot.state == "fresh" and snapshot.native_exit_code == 0
            before = len(calls)
            async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
                responses = await asyncio.gather(
                    *(client.get(running.metrics_url) for _ in range(5))
                )
            assert all(row.status_code == 200 and row.content == snapshot.body for row in responses)
            assert len(calls) == before
            for ordinal in range(1, 4):
                assert f'replica="replica-{ordinal}"'.encode() in snapshot.body
            assert b"private-id-" not in snapshot.body and b"ci/manual-fleet" not in snapshot.body
            assert b"127.0.0.1" not in snapshot.body
        assert running.closed and running.worker_joined and running.listener_joined
        after = len(calls)
        await asyncio.sleep(0.03)
        assert len(calls) == after


@pytest.mark.parametrize("force_terminal", [False, True], ids=["plain", "forced-color"])
def test_exporter_cli_has_explicit_continuous_controls(monkeypatch, force_terminal):
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", force_terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    result = CliRunner().invoke(app, ["monitor-fleet-exporter", "--help"], color=force_terminal)
    assert result.exit_code == 0, result.output
    assert ("\x1b[" in result.output) is force_terminal
    output = unstyle(result.output)
    assert "--poll-seconds" in output and "--stale-after-seconds" in output
    assert "--run-seconds" in output
