"""Finite exporter qualification is separate from readiness and clean process exit."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import subprocess
import sys

import pytest

from chimeraforge import api
from test_fleet_monitor import fleet_server, native_fleet as native_fleet, request


def config():
    return api.FleetExporterConfig(port=0, poll_seconds=10, stale_after_seconds=10)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_real_three_replica_sdk_boundary_pass_is_finalized_after_all_joins(
    native_fleet, backend
):
    saved, indices = native_fleet
    with fleet_server(backend=backend) as (urls, calls):
        result = await api.run_fleet_exporter(
            saved,
            request(urls),
            candidate_index=indices[backend],
            config=config(),
            policy=api.FleetExporterRunPolicy(1.0, require_final_observation=True),
        )
        after = len(calls)
        await asyncio.sleep(0.03)
        assert len(calls) == after and calls
    data = result.to_dict()
    assert data["exit_code"] == 0 and data["qualification_met"] is True
    assert data["qualification_requested"] and data["process_exit_is_qualification"]
    assert data["boundary"] == "deadline" and data["snapshot_state"] == "fresh"
    assert data["observed_native_exit_code"] == 0 and data["population_bound"]
    assert data["expected_replicas"] == data["observed_replicas"] == 3
    assert data["closed"] and data["listener_joined"] and data["worker_joined"]
    assert all(value not in json.dumps(data) for value in (*urls, "ci/manual-fleet", "replica-1"))


@pytest.mark.asyncio
async def test_deadline_before_first_observation_is_unknown_four_and_still_joins(native_fleet):
    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        result = await api.run_fleet_exporter(
            saved,
            replace(request(urls), interval=1),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(0.01, True),
        )
    data = result.to_dict()
    assert data["exit_code"] == 4 and data["qualification_met"] is False
    assert data["sequence"] == 0 and data["observed_replicas"] == 0
    assert data["observed_native_exit_code"] is None
    assert data["closed"] and data["worker_joined"] and data["listener_joined"]


@pytest.mark.asyncio
async def test_sdk_false_clean_close_is_not_a_qualified_pass(native_fleet):
    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        result = await api.run_fleet_exporter(
            saved,
            replace(request(urls), interval=1),
            candidate_index=indices["vllm"],
            config=config(),
            policy=api.FleetExporterRunPolicy(0.01),
        )
    data = result.to_dict()
    assert data["exit_code"] == 0 and data["qualification_met"] is None
    assert not data["qualification_requested"] and not data["process_exit_is_qualification"]
    assert data["closed"] and data["listener_joined"] and data["worker_joined"]


def test_actual_os_cli_selected_path_keeps_ready_closed_then_safe_qualification(
    tmp_path, native_fleet
):
    saved, indices = native_fleet
    source = tmp_path / "source.json"
    saved.save(source)
    original = source.read_bytes()
    with fleet_server() as (urls, calls):
        args = [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "chimeraforge",
            "monitor-fleet-exporter",
            "--from-plan",
            str(source),
            "--candidate-index",
            str(indices["vllm"]),
            "--listen-port",
            "0",
            "--interval",
            "0.01",
            "--timeout",
            "1",
            "--observation-seconds",
            "3",
            "--cleanup-seconds",
            "1",
            "--poll-seconds",
            "10",
            "--run-seconds",
            "1",
            "--require-final-observation",
            "--ttft-slo",
            "500",
        ]
        for index, url in enumerate(urls):
            args += ["--endpoint", f"private-id-{index}={url}"]
        child = subprocess.run(args, cwd=tmp_path, capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr
    rows = [json.loads(row) for row in child.stdout.splitlines()]
    assert len(rows) == 3 and rows[0]["process_exit_is_qualification"] is True
    assert rows[1] == {
        "kind": "chimeraforge.fleet-exporter-closed",
        "listener_joined": True,
        "worker_joined": True,
    }
    assert rows[2]["kind"] == "chimeraforge.fleet-exporter-run" and rows[2]["exit_code"] == 0
    assert rows[2]["qualification_met"] is True and rows[2]["expected_replicas"] == 3
    assert source.read_bytes() == original and calls
    assert not any(
        value in json.dumps(rows[2]) for value in (*urls, "private-id", "ci/manual-fleet")
    )
