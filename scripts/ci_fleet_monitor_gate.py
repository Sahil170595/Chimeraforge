"""Actual native passive producer/receiver/gate on owned CPU HTTPS fixtures."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree as ET

from ci_secure_monitor import certificates, server

TOKEN = "FictionalMonitorGate83"


def _policy(baseline: Any, candidate: Any) -> dict:
    return {
        "schema_version": 1,
        "original_replicas": 3,
        "endpoint_ids": [slot.id for slot in baseline.slots],
        "windows": 1,
        "metrics": {"ttft": {"minimum_samples": 20}},
        **{
            arm: {
                "plan": {name: report.plan[name] for name in ("fingerprint", "candidate_index")},
                "controls": report.effective_controls,
            }
            for arm, report in (("baseline", baseline), ("candidate", candidate))
        },
    }


def accept(cwd: Path, env: dict[str, str], saved: Path, checkout: Path | None = None) -> dict:
    from ci_installed_acceptance import assert_installed_modules
    from chimeraforge import api
    from chimeraforge.fleet_monitor_types import FleetMonitorError

    cwd.mkdir(parents=True, exist_ok=True)
    loaded_before = assert_installed_modules(checkout) if checkout is not None else None
    original = saved.read_bytes()
    data = json.loads(original)
    paths = certificates(cwd / "tls")
    held_tls = {name: path.read_bytes() for name, path in paths.items()}
    controls, aliases = [], []
    for backend in ("vllm", "sglang"):
        index = next(
            i
            for i, row in enumerate(data["result"]["candidates"])
            if (
                row["backend"] == backend
                and row["n_agents"] == 3
                and row["quant"] == "FP16"
                and row["gpus_total"] == 6
            )
        )
        model = data["result"]["candidates"][index]["model"]
        with server(paths, backend=backend, model=model, token=TOKEN, mtls=True) as (url, _):
            endpoints = tuple(
                api.FleetEndpoint(f"r{i}", url + f"/r{i}/metrics") for i in range(1, 4)
            )
            connections = {
                e.id: api.MonitorConnection(
                    e.url,
                    bearer_token=TOKEN,
                    ca_bundle=paths["ca"],
                    client_cert=paths["client"],
                    client_key=paths["client_key"],
                )
                for e in endpoints
            }
            request = api.FleetMonitorRequest(
                endpoints,
                interval=0.01,
                timeout=5,
                observation_seconds=30,
                concurrency=3,
                ttft_slo=100,
            )
            baseline = asyncio.run(
                api.monitor_fleet(saved, request, candidate_index=index, connections=connections)
            )
        assert baseline.exit_code == 0 and baseline.cleanup["state"] == "completed"
        left = cwd / f"{backend}-baseline.json"
        baseline.save(left)
        assert api.load_fleet_monitor(left, saved, candidate_index=index).exit_code == 0
        for role in ("ca", "client", "client_key"):
            try:
                baseline.save(paths[role])
            except FleetMonitorError:
                aliases.append({"backend": backend, "input": role, "refused": True})
            else:
                raise AssertionError("passive TLS input was overwritten")
        for scenario, native_code, gate_code in (
            ("pass", 0, 0),
            ("breach", 3, 1),
            ("partial", 4, 3),
        ):
            right = cwd / f"{backend}-{scenario}.json"
            with server(
                paths,
                backend=backend,
                model=model,
                token=TOKEN,
                mtls=True,
                slow=scenario == "breach",
            ) as (url, _):
                args = [
                    "monitor-fleet",
                    "--from-plan",
                    str(saved),
                    "--candidate-index",
                    str(index),
                    "--interval",
                    ".01",
                    "--timeout",
                    "5",
                    "--observation-seconds",
                    "30",
                    "--concurrency",
                    "3",
                    "--ttft-slo",
                    "100",
                    "--json",
                    "--out",
                    str(right),
                    "--secure",
                ]
                for i in range(1, 4):
                    args += [
                        "--endpoint",
                        f"r{i}={url}/r{i}/metrics",
                        "--bearer-env",
                        f"r{i}=CF_FIXTURE_MONITOR83",
                        "--ca-bundle",
                        f"r{i}={paths['ca']}",
                        "--client-cert",
                        f"r{i}={paths['client']}",
                        "--client-key",
                        f"r{i}={paths['client_key']}",
                    ]
                if scenario == "partial":
                    args += ["--max-requests", "1"]
                child = subprocess.run(
                    [sys.executable, "-I", "-m", "chimeraforge", *args],
                    cwd=cwd,
                    env={**env, "CF_FIXTURE_MONITOR83": TOKEN},
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60,
                )
                assert child.returncode == native_code, "native passive CLI outcome differed"
                raw = right.read_bytes()
                assert raw == child.stdout and len(raw) <= 8 * 1024 * 1024
                assert b"\r\n" not in raw, "native stdout changed admitted LF bytes"
                assert TOKEN.encode() not in raw + child.stderr
            candidate = api.load_fleet_monitor(right, saved, candidate_index=index)
            assert candidate.exit_code == native_code and len(candidate.slots) == 3
            assert candidate.cleanup["state"] == "completed"
            assert candidate.cleanup["closed_pools"] == candidate.cleanup["owned_pools"] == 6
            assert candidate.cleanup["joined_endpoint_tasks"] == 3
            chosen = _policy(baseline, candidate)
            policy = cwd / f"{backend}-{scenario}-policy.json"
            policy.write_text(json.dumps(chosen), encoding="utf-8")
            result = api.gate_fleet_monitors(
                baseline,
                candidate,
                baseline_plan=saved,
                candidate_plan=saved,
                policy=chosen,
            )
            assert result.exit_code == gate_code, result.to_dict()
            out, junit = cwd / f"{backend}-{scenario}-gate.json", cwd / f"{backend}-{scenario}.xml"
            api.write_fleet_monitor_gate(result, out=out, junit=junit)
            suite = ET.fromstring(junit.read_bytes())
            assert suite.attrib["tests"] == "7"
            assert int(suite.attrib["failures"]) == (3 if gate_code == 1 else 0)
            assert int(suite.attrib["errors"]) == (7 if gate_code == 3 else 0)
            gate_args = [
                "gate",
                "--kind",
                "fleet-monitor",
                "--baseline",
                str(left),
                "--candidate",
                str(right),
                "--baseline-plan",
                str(saved),
                "--candidate-plan",
                str(saved),
                "--policy",
                str(policy),
                "--out",
                str(out),
                "--junit",
                str(junit),
                "--json",
            ]
            gate_child = subprocess.run(
                [sys.executable, "-I", "-m", "chimeraforge", *gate_args],
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            assert gate_child.returncode == gate_code
            assert gate_child.stdout == out.read_bytes() and b"\r\n" not in gate_child.stdout
            assert TOKEN.encode() not in gate_child.stdout + gate_child.stderr
            cli = json.loads(gate_child.stdout)
            assert cli["exit_code"] == gate_code and len(cli["cases"]) == 6
            assert all(len(cli["inputs"][arm]["slots"]) == 3 for arm in ("baseline", "candidate"))
            assert TOKEN not in json.dumps(cli) and str(paths["client_key"]) not in json.dumps(cli)
            controls.append(
                {
                    "backend": backend,
                    "scenario": scenario,
                    "producer_cli_exit": native_code,
                    "api_gate_exit": result.exit_code,
                    "cli_gate_exit": cli["exit_code"],
                    "original_slots_per_arm": 3,
                    "junit_cases": 7,
                    "junit_errors": int(suite.attrib["errors"]),
                    "junit_failures": int(suite.attrib["failures"]),
                    "stdout_equals_admitted_file_bytes": True,
                    "admitted_json_bytes": len(raw),
                    "stdout_bytes": len(child.stdout),
                    "gate_stdout_bytes": len(gate_child.stdout),
                    "gate_stdout_equals_admitted_file_bytes": True,
                }
            )
    assert saved.read_bytes() == original
    assert {name: path.read_bytes() for name, path in paths.items()} == held_tls
    return {
        "controls": controls,
        "output_aliases": aliases,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_and_tls_input_bytes_unchanged": True,
        "owned_listeners_handlers_clients_tasks_closed": True,
        "installed_module_provenance": {
            "before": loaded_before,
            "after": assert_installed_modules(checkout),
        }
        if checkout is not None
        else None,
        "scope": (
            "owned CPU HTTPS protocol fixtures; "
            "no engine/GPU/traffic-authentication/performance qualification"
        ),
    }


def main() -> int:
    import argparse
    from datetime import datetime, timezone
    import os
    import tempfile
    from chimeraforge import __version__, api

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-fleet-monitor-gate-") as temporary:
        cwd = Path(temporary)
        saved = cwd / "plan.json"
        api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                latency_slo=10000,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        ).save(saved)
        result = accept(cwd, dict(os.environ), saved)
    root = Path(__file__).resolve().parents[1]
    files = [
        "scripts/ci_fleet_monitor_gate.py",
        "scripts/ci_installed_acceptance.py",
        "src/chimeraforge/fleet_monitor_types.py",
        "src/chimeraforge/fleet_monitor_json.py",
        "src/chimeraforge/fleet_monitor_receipt.py",
        "src/chimeraforge/fleet_monitor_gate_types.py",
        "src/chimeraforge/fleet_monitor_gate.py",
        "src/chimeraforge/fleet_monitor_gate_output.py",
        "src/chimeraforge/fleet_monitor.py",
        "src/chimeraforge/monitor.py",
        "src/chimeraforge/monitor_binding.py",
        "src/chimeraforge/commands/monitor_fleet.py",
        "src/chimeraforge/commands/gate.py",
        "src/chimeraforge/api.py",
    ]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "evidence": (
            "source native API/CLI on owned CPU HTTPS fixtures; not installed/GPU qualification"
        ),
        "result": result,
        "source_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
