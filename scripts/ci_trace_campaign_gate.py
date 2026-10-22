"""Installed whole-campaign protocol oracles; synthetic timings are not measurements."""

from __future__ import annotations

import copy
import json
from pathlib import Path


def seal(data: dict) -> dict:
    from chimeraforge.planner.replay import digest

    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    return data


def protocol_campaign(durations: tuple[float, ...] = (0.12, 0.14)) -> dict:
    """Use the producer manifest and independently stated synthetic native timings."""
    from ci_trace_gate import protocol_receipt
    from chimeraforge.bench.trace_campaign import _prepare
    from chimeraforge.bench.trace_workload import TraceRequest, TraceSLO

    _, manifest, _ = _prepare(
        [
            TraceRequest(f"synthetic-{i}", "Harmless synthetic protocol fixture", 8, 0.0)
            for i in range(2)
        ],
        model="synthetic-protocol",
        backend="ollama",
        base_url=None,
        replicates=len(durations),
        concurrency=2,
        request_timeout=300,
        trace_timeout=600,
        campaign_timeout=1800,
        slos=TraceSLO(latency_ms=2000.0),
        stop_event=None,
    )
    replicas = []
    cursor = 0.0
    for index, duration in enumerate(durations):
        native = protocol_receipt(duration)
        native["workload"] = {**manifest["workload"], "raw_sha256": None}
        native["clock"]["origin"] = 100.0 + cursor + 0.1
        for row, descriptor in zip(native["requests"], manifest["ordered_descriptors"]):
            row["descriptor"] = copy.deepcopy(descriptor)
        seal(native)
        end = cursor + max(0.8, duration + 0.2)
        replicas.append(
            {
                "index": index,
                "manifest_fingerprint": manifest["fingerprint"],
                "workload_ref": manifest["workload"]["canonical_sha256"],
                "start_s": cursor,
                "end_s": end,
                "state": "completed",
                "receipt": native,
                "error": None,
                "reason": None,
            }
        )
        cursor = end + 0.2
    return seal(
        {
            "schema_version": 1,
            "kind": "chimeraforge.trace-campaign",
            "created_at": "synthetic-protocol",
            "manifest": manifest,
            "replicas": replicas,
            "execution": {
                "planned": len(replicas),
                "completed": len(replicas),
                "incomplete": 0,
                "failed": 0,
                "not_started": 0,
            },
            "clock": {
                "basis": "client time.perf_counter monotonic offsets in seconds",
                "origin": 100.0,
                "elapsed_seconds": cursor,
            },
            "stop_reason": None,
            "state": "completed",
            "exit_code": 0,
            "assurance": dict.fromkeys(
                (
                    "external_preregistration",
                    "time_authentication",
                    "independent_cold_executions",
                    "cache_independence",
                    "gpu_geometry",
                    "served_weights",
                    "provider_termination",
                ),
                "unverified",
            ),
            "limits": "Synthetic protocol oracle only; no serving-performance observation",
        }
    )


def failed_campaign() -> dict:
    report = protocol_campaign((0.10, 0.11))
    first, second = report["replicas"]
    first.update(
        state="failed",
        receipt=None,
        error={"stage": "campaign_replay", "type": "ValueError"},
        reason="replay_failed",
    )
    second.update(
        state="not_started",
        receipt=None,
        error=None,
        start_s=None,
        end_s=None,
        reason="first_incomplete_replicate",
    )
    report.update(state="incomplete", exit_code=1, stop_reason="first_incomplete_replicate")
    report["execution"] = {
        "planned": 2,
        "completed": 0,
        "incomplete": 0,
        "failed": 1,
        "not_started": 1,
    }
    return seal(report)


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli

    assert_installed_origin(chimeraforge.__file__, checkout)
    left, right, policy, out = [
        cwd / name
        for name in (
            "campaign-gate-baseline.json",
            "campaign-gate-candidate.json",
            "campaign-gate-policy.json",
            "campaign-gate-decision.json",
        )
    ]
    left.write_text(json.dumps(protocol_campaign()))
    right.write_text(json.dumps(protocol_campaign((0.10, 0.11))))
    policy.write_text(
        json.dumps(
            {
                "rules": {"latency_p95_ms": 0.1},
                "expected_replicates": 2,
                "fixed_controls": {"device": "cpu"},
            }
        )
    )
    argv = [
        "gate",
        "--kind",
        "trace-campaign",
        "--baseline",
        str(left),
        "--candidate",
        str(right),
        "--policy",
        str(policy),
        "--json",
    ]
    passed = json.loads(run_cli([*argv, "--out", str(out)], cwd, env))
    assert passed["kind"] == "chimeraforge.trace-campaign-regression-gate"
    assert passed["outcome"] == "conditional_pass" and passed["exit_code"] == 0
    assert json.loads(out.read_bytes()) == passed and len(passed["pairs"]) == 2
    right.write_text(json.dumps(protocol_campaign((0.10, 0.30))))
    regression = json.loads(run_cli(argv, cwd, env, 1))
    assert regression["known_breaches"] == [{"index": 1, "metric": "latency_p95_ms"}]
    right.write_bytes(left.read_bytes())
    duplicate = json.loads(run_cli(argv, cwd, env, 3))
    assert "duplicate_execution_payload" in duplicate["blockers"]
    right.write_text(json.dumps(failed_campaign()))
    incomplete = json.loads(run_cli(argv, cwd, env, 3))
    slots = incomplete["inputs"]["candidate"]["replicas"]
    assert [slot["state"] for slot in slots] == ["failed", "not_started"]
    assert all(slot["receipt"] is None for slot in slots) and len(incomplete["pairs"]) == 2
    malformed = protocol_campaign((0.10, 0.11))
    malformed["replicas"].pop()
    right.write_text(json.dumps(seal(malformed)))
    assert json.loads(run_cli(argv, cwd, env, 2))["error"]
    right.write_text(json.dumps(protocol_campaign((0.10, 0.11))))
    for source in (left, right, policy):
        original = source.read_bytes()
        assert json.loads(run_cli([*argv, "--out", str(source)], cwd, env, 2))["error"]
        assert source.read_bytes() == original
    assert json.loads(run_cli([*argv, "--baseline", str(left)], cwd, env, 2))["error"]
    return {
        "scope": (
            "Installed synthetic protocol oracles; no actual serving or independent execution claim"
        ),
        "conditional_pass": passed,
        "regression": regression,
        "copied_evidence": duplicate,
        "incomplete_population": incomplete,
        "malformed_and_aliases": "refused",
    }
