"""Actual secure CLI protocol and explicit late writer ownership."""

from __future__ import annotations

import asyncio
import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
from test_ci_acceptance import load_script
from test_secure_active import active_plan as active_plan
from test_secure_monitor import certs as certs


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize("mode", ["bench", "trace", "saved-bench", "saved-trace"])
def test_complete_secure_cli_paths(active_plan, certs, tmp_path, backend, mode):
    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    source, workload = tmp_path / "plan.json", tmp_path / "workload.json"
    saved.save(source)
    workload.write_text(
        json.dumps(
            [
                {
                    "request_id": "one",
                    "prompt": "fixture",
                    "max_output_tokens": 4,
                    "arrival_offset_s": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    cap = 256 if mode == "bench" else 4
    token = "FictionalCliToken82"
    with wire.server(certs, backend=backend, cap=cap, token=token, mtls=True) as (url, calls):
        flags = [
            "--base-url",
            url,
            "--secure",
            "--bearer-env",
            "CF_FIXTURE_ACTIVE82",
            "--ca-bundle",
            str(certs["ca"]),
            "--client-cert",
            str(certs["client"]),
            "--client-key",
            str(certs["client_key"]),
            "--model",
            wire.MODEL,
            "--json",
        ]
        if "bench" in mode:
            args = ["bench", "--runs", "1", "--output-dir", str(tmp_path / "results"), *flags]
            args += (
                ["--plan", str(source), "--candidate-index", str(indices[backend])]
                if mode == "saved-bench"
                else ["--backend", backend]
            )
        else:
            args = ["trace", str(workload), "--out", str(tmp_path / "receipt.json"), *flags]
            args += (
                ["--from-plan", str(source), "--candidate-index", str(indices[backend])]
                if mode == "saved-trace"
                else ["--backend", backend]
            )
        result = CliRunner().invoke(app, args, env={"CF_FIXTURE_ACTIVE82": token})
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert any(row["method"] == "POST" for row in calls)
        assert all(row["authorized"] and row["client_certificate"] for row in calls)
        assert token not in json.dumps(report) + result.stderr
    assert api.load_plan(source).to_dict() == saved.to_dict()


def test_explicit_late_benchmark_writer_refuses_tls_hardlink(certs, tmp_path):
    from chimeraforge.bench.runner import run_benchmark, save_results

    wire = load_script("ci_secure_active")
    before = certs["ca"].read_bytes()
    directory = tmp_path / "outputs"
    directory.mkdir()
    with wire.server(certs, backend="vllm") as (url, _):
        connection = MonitorConnection(url, ca_bundle=certs["ca"])
        result = asyncio.run(
            run_benchmark(
                wire.MODEL,
                "vllm",
                runs=1,
                options={"max_tokens": 4},
                base_url=url,
                connection=connection,
            )
        )
    timestamp = result.timestamp.replace(":", "-").replace("+", "_")
    destination = directory / f"bench_{timestamp}.json"
    destination.hardlink_to(certs["ca"])
    with pytest.raises((api.PlanError, MonitorConnectionError)):
        save_results([result], directory, connection=connection)
    assert certs["ca"].read_bytes() == before


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize("sweep", ["quants", "contexts"])
def test_native_quant_context_sweeps_forward_runtime_connection(certs, tmp_path, backend, sweep):
    wire = load_script("ci_secure_active")
    token = "FictionalSweep82"
    with wire.server(certs, backend=backend, cap=256, token=token) as (url, calls):
        result = CliRunner().invoke(
            app,
            [
                "bench",
                "--model",
                wire.MODEL,
                "--backend",
                backend,
                "--base-url",
                url,
                "--secure",
                "--bearer-env",
                "CF_SWEEP82",
                "--ca-bundle",
                str(certs["ca"]),
                *(["--all-quants"] if sweep == "quants" else ["--context", "512,1024"]),
                "--runs",
                "1",
                "--output-dir",
                str(tmp_path / "results"),
                "--json",
            ],
            env={"CF_SWEEP82": token},
        )
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        from chimeraforge.planner.constants import QUANT_LEVELS

        expected = len(QUANT_LEVELS) if sweep == "quants" else 2
        assert len(report) == expected and all(row["aggregate"]["count"] == 1 for row in report)
        assert all(row["authorized"] for row in calls)
        assert sum(row["method"] == "POST" for row in calls) == expected
        assert all(row["warnings"] for row in report), (
            "unsupported context/quant intent stays explicit"
        )
        assert token not in result.stdout + result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize("workload", ["batch", "server"])
async def test_real_secure_native_batch_and_server_workers_close(certs, workload):
    from chimeraforge.bench.runner import run_benchmark

    wire = load_script("ci_secure_active")
    before = asyncio.all_tasks()
    with wire.server(certs, backend="vllm") as (url, calls):
        result = await run_benchmark(
            wire.MODEL,
            "vllm",
            workload=workload,
            runs=2,
            rate=100 if workload == "server" else None,
            concurrency=2,
            base_url=url,
            options={"max_tokens": 4},
            connection=MonitorConnection(url, ca_bundle=certs["ca"]),
        )
        assert result.aggregate.count == 2 and sum(row["method"] == "POST" for row in calls) == 2
    await asyncio.sleep(0)
    assert not (asyncio.all_tasks() - before)
