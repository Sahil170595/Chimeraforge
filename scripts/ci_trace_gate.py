"""Installed trace-gate protocol oracle; synthetic timings are not serving measurements."""

from __future__ import annotations

import copy
import json
from pathlib import Path


def protocol_receipt(duration: float, *, queued: float = 0) -> dict:
    """Complete bounded synthetic protocol population with independently stated arithmetic."""
    from chimeraforge.bench.serving_binding import serving_stability
    from chimeraforge.planner.replay import digest

    observation = {
        "backend": "ollama",
        "version": "synthetic-protocol",
        "model": "synthetic-protocol",
        "device": "cpu",
        "prefix_cache": False,
        "context_length": 2048,
    }
    rows = []
    for index in range(2):
        start = index * queued
        timing = {
            "scheduler_lag_ms": 0.0,
            "client_queue_ms": start * 1000,
            "latency_ms": (start + duration) * 1000,
            "first_output_ms": (start + 0.02) * 1000,
            "tpot_ms": 25.0,
        }
        rows.append(
            {
                "descriptor": {
                    "request_id": f"synthetic-{index}",
                    "prompt_sha256": "b" * 64,
                    "prompt_bytes": 5,
                    "max_output_tokens": 8,
                    "arrival_offset_s": 0.0,
                },
                "state": "completed",
                "times": {
                    "scheduled_s": 0.0,
                    "arrival_s": 0.0,
                    "start_s": start,
                    "first_output_s": start + 0.02,
                    "terminal_s": start + duration,
                },
                "native": {
                    "tokens_generated": 4,
                    "prompt_tokens": 8,
                    "cached_prompt_tokens": 0,
                    "throughput_tps": 40.0,
                    "ttft_ms": 2.0,
                    "total_duration_ms": 102.0,
                    "prompt_eval_duration_ms": 2.0,
                    "eval_duration_ms": 100.0,
                    "ttft_basis": "server-prefill-duration",
                },
                "error": None,
                "mean_tpot_ms": 25.0,
                "mean_tpot_basis": "server-decode-duration/output-token-count",
                "timing": timing,
                "slo": {
                    "latency_ms": "pass",
                    "first_output_ms": "not_requested",
                    "tpot_ms": "not_requested",
                    "joint": "pass",
                },
                "output_cap_state": "within_cap",
            }
        )
    elapsed = queued + duration + 0.01
    data = {
        "schema_version": 1,
        "created_at": "synthetic-protocol",
        "tool": {"name": "chimeraforge", "version": "synthetic-protocol"},
        "model": "synthetic-protocol",
        "backend": "ollama",
        "endpoint": None,
        "workload": {"canonical_sha256": "c" * 64, "raw_sha256": None},
        "requests": rows,
        "targets": {"latency_ms": 2000.0, "first_output_ms": None, "tpot_ms": None},
        "execution": {
            "planned": 2,
            "attempted": 2,
            "completed": 2,
            "failed": 0,
            "partial": 0,
            "cancelled": 0,
            "not_started": 0,
            "concurrency": 2,
            "request_timeout_seconds": 300,
            "trace_timeout_seconds": 600,
            "elapsed_seconds": elapsed,
        },
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": 0.0,
            "resolution_seconds": 1e-7,
        },
        "timing_bases": {
            "latency_ms": "scheduled-arrival-to-client-terminal",
            "first_output_ms": "scheduled-arrival-to-client-first-output",
            "tpot_ms": "per-request explicitly named mean decode basis; not every-token latency",
        },
        "deadline_scope": (
            "scheduled replay only; preflight/metadata separately bounded, cleanup cooperative"
        ),
        "goodput": {
            "qualification": "observed_targets",
            "qualified_requests": 2,
            "horizon_seconds": elapsed,
            "planned_horizon_seconds": 0.0,
            "horizon_basis": "origin to max(last planned arrival, observed terminal/stop)",
            "joint_outcomes": {
                "pass": 2,
                "breach": 0,
                "unknown": 0,
                "not_completed": 0,
                "not_requested": 0,
            },
            "requests_per_second": 2 / elapsed,
        },
        "serving_before": copy.deepcopy(observation),
        "serving_after": copy.deepcopy(observation),
        "serving_stability": serving_stability(observation, observation),
        "resource_cleanup": {"state": "completed"},
        "stop_reason": None,
        "error": None,
        "exit_code": 0,
        "performance": {
            "state": "observed_client_workload",
            "gpu_qualification": "unverified",
            "served_file_authentication": "unverified",
        },
        "limits": "Synthetic protocol only",
    }
    data["fingerprint"] = digest(data)
    return data


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from chimeraforge.planner.replay import digest

    assert_installed_origin(chimeraforge.__file__, checkout)
    left, right, policy, out = [
        cwd / name
        for name in (
            "trace-gate-baseline.json",
            "trace-gate-candidate.json",
            "trace-gate-policy.json",
            "trace-gate-decision.json",
        )
    ]
    left.write_text(json.dumps(protocol_receipt(0.12)))
    right.write_text(json.dumps(protocol_receipt(0.10)))
    policy.write_text(
        json.dumps(
            {
                "rules": {"goodput_rps": 0.05, "latency_p95_ms": 0.1},
                "fixed_controls": {"device": "cpu"},
            }
        )
    )
    argv = [
        "gate",
        "--kind",
        "trace",
        "--baseline",
        str(left),
        "--candidate",
        str(right),
        "--policy",
        str(policy),
        "--json",
    ]
    passed = json.loads(run_cli([*argv, "--out", str(out)], cwd, env))
    assert passed["exit_code"] == 0 and passed["kind"] == "chimeraforge.trace-regression-gate"
    assert json.loads(out.read_bytes()) == passed
    right.write_text(json.dumps(protocol_receipt(0.10, queued=0.4)))
    regression = json.loads(run_cli(argv, cwd, env, 1))
    assert regression["pairs"][0]["metrics"]["latency_p95_ms"]["state"] == "regression"
    right.write_bytes(left.read_bytes())
    inconclusive = json.loads(run_cli(argv, cwd, env, 3))
    assert "duplicate_execution_payload" in inconclusive["blockers"]
    malformed = protocol_receipt(0.10)
    malformed["requests"][0]["timing"]["latency_ms"] = 1
    malformed["fingerprint"] = digest({k: v for k, v in malformed.items() if k != "fingerprint"})
    right.write_text(json.dumps(malformed))
    error = json.loads(run_cli(argv, cwd, env, 2))
    assert error["error"]
    for report in (passed, regression, inconclusive):
        assert report["fingerprint"] == digest(
            {k: v for k, v in report.items() if k != "fingerprint"}
        )
        assert len(report["inputs"]["baseline"]) == len(report["inputs"]["candidate"]) == 1
        assert report["assurance"]["independent_executions_verified"] is False
    return {
        "scope": (
            "explicitly synthetic installed protocol oracle, "
            "no serving-speed or independent-execution claim"
        ),
        "conditional_pass": passed,
        "regression": regression,
        "inconclusive": inconclusive,
        "malformed_exit": 2,
    }
