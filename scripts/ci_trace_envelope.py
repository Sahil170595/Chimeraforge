"""Installed finite-envelope oracles over synthetic whole campaigns; no inference."""

from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

PRIVATE_INPUT = "private-envelope-input-sentinel"
PRIVATE_DIAGNOSTIC = "private-envelope-diagnostic-sentinel"
LOWER_INTERVAL_SECONDS = 1.0
HIGHER_INTERVAL_SECONDS = 0.5


def uniform_campaign(interval: float, *, durations: tuple[float, ...] = (0.12, 0.14)) -> dict:
    """Reschedule an existing native fixture using producer timing/SLO arithmetic only."""
    from ci_trace_campaign_gate import protocol_campaign, seal
    from chimeraforge.bench.trace import _qualify, _timing
    from chimeraforge.bench.trace_workload import TraceRequest, descriptor
    from chimeraforge.planner.replay import digest

    report: dict = protocol_campaign(durations)
    workload = [
        TraceRequest(f"envelope-{i}", PRIVATE_INPUT, 8, float(i) * interval) for i in range(2)
    ]
    manifest = report["manifest"]
    manifest["ordered_descriptors"] = [descriptor(row) for row in workload]
    manifest["workload"] = {
        "canonical_sha256": digest([asdict(row) for row in workload]),
        "raw_sha256": None,
    }
    seal(manifest)
    cursor = 0.0
    for slot, duration in zip(report["replicas"], durations):
        native = slot["receipt"]
        native["workload"] = copy.deepcopy(manifest["workload"])
        for row, declaration in zip(native["requests"], manifest["ordered_descriptors"]):
            row["descriptor"] = copy.deepcopy(declaration)
            arrival = declaration["arrival_offset_s"]
            row["times"] = {
                "scheduled_s": arrival,
                "arrival_s": arrival,
                "start_s": arrival,
                "first_output_s": arrival + 0.02,
                "terminal_s": arrival + duration,
            }
            row["timing"] = _timing(row)
            row["slo"] = _qualify(row, native["targets"])
        elapsed = max(row["times"]["terminal_s"] for row in native["requests"]) + 0.01
        native["execution"]["elapsed_seconds"] = elapsed
        native["clock"]["origin"] = report["clock"]["origin"] + cursor + 0.1
        outcomes = {
            state: sum(row["slo"]["joint"] == state for row in native["requests"])
            for state in ("pass", "breach", "unknown", "not_completed", "not_requested")
        }
        native["goodput"].update(
            horizon_seconds=elapsed,
            planned_horizon_seconds=interval,
            qualified_requests=outcomes["pass"],
            joint_outcomes=outcomes,
            requests_per_second=outcomes["pass"] / elapsed,
        )
        seal(native)
        slot.update(
            manifest_fingerprint=manifest["fingerprint"],
            workload_ref=manifest["workload"]["canonical_sha256"],
            start_s=cursor,
            end_s=cursor + elapsed + 0.2,
        )
        cursor = slot["end_s"] + 0.1
    report["clock"]["elapsed_seconds"] = cursor
    seal(report)
    return report


def fixtures() -> tuple[dict, dict, dict[str, dict]]:
    lower, higher = (
        uniform_campaign(LOWER_INTERVAL_SECONDS),
        uniform_campaign(HIGHER_INTERVAL_SECONDS),
    )
    controls = lower["manifest"]["controls"]
    cases = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-envelope-cases",
        **{
            name: controls[name]
            for name in (
                "model",
                "backend",
                "concurrency",
                "request_timeout_seconds",
                "trace_timeout_seconds",
                "campaign_timeout_seconds",
            )
        },
        "expected_replicates": 2,
        "ordered_descriptors": [
            {key: value for key, value in row.items() if key != "arrival_offset_s"}
            for row in lower["manifest"]["ordered_descriptors"]
        ],
        "cells": [
            {"name": "lower", "arrival_interval_seconds": LOWER_INTERVAL_SECONDS},
            {"name": "higher", "arrival_interval_seconds": HIGHER_INTERVAL_SECONDS},
        ],
    }
    policy = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-envelope-policy",
        "targets": copy.deepcopy(controls["targets"]),
        "fixed_controls": {"device": "cpu"},
        "require_cache_evidence": True,
    }
    return cases, policy, {"lower": lower, "higher": higher}


def _receipt(raw: bytes) -> dict:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _validate(
    report: dict,
    cases: dict,
    policy: dict,
    case_raw: bytes,
    policy_raw: bytes,
    campaigns: dict[str, bytes],
) -> dict:
    from chimeraforge.bench.trace_gate_inputs import load_trace
    from chimeraforge.planner.replay import digest

    assert report["kind"] == "chimeraforge.trace-envelope-assessment"
    assert report["fingerprint"] == digest(
        {key: value for key, value in report.items() if key != "fingerprint"}
    )
    assert report["cases"] == cases and report["policy"] == policy
    assert report["inputs"]["cases"] == _receipt(case_raw)
    assert report["inputs"]["policy"] == _receipt(policy_raw)
    assert set(report["inputs"]["campaigns"]) == set(campaigns)
    for name, raw in campaigns.items():
        assert report["inputs"]["campaigns"][name] == {
            **_receipt(raw),
            "fingerprint": json.loads(raw)["fingerprint"],
        }
    assert [cell["name"] for cell in report["cells"]] == [cell["name"] for cell in cases["cells"]]
    missing_replicas, native_requests = 0, 0
    for cell in report["cells"]:
        slots = cell["replicas"]
        assert len(slots) == cases["expected_replicates"]
        assert [slot["index"] for slot in slots] == list(range(cases["expected_replicates"]))
        if cell["name"] not in campaigns:
            assert cell["execution_state"] == "missing"
            assert all(slot["state"] == "missing" and slot["receipt"] is None for slot in slots)
            missing_replicas += len(slots)
        else:
            assert cell["execution_state"] == "completed"
            for slot in slots:
                native = load_trace(slot["receipt"])["data"]
                assert native["exit_code"] == 0
                assert native["execution"]["planned"] == len(cases["ordered_descriptors"])
                native_requests += len(native["requests"])
    assert report["assurance"]["independent_executions_verified"] is False
    assert report["assurance"]["capacity_qualification"] == "unverified"
    assert report["assurance"]["interpolation"] == "not performed"
    assert PRIVATE_INPUT not in json.dumps(report) and PRIVATE_DIAGNOSTIC not in json.dumps(report)
    return {
        "declared_cells": len(report["cells"]),
        "completed_cells": sum(cell["execution_state"] == "completed" for cell in report["cells"]),
        "missing_cells": sum(cell["execution_state"] == "missing" for cell in report["cells"]),
        "missing_replicas": missing_replicas,
        "retained_native_requests": native_requests,
        "known_breaches": len(report["known_breaches"]),
    }


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from ci_trace_campaign_gate import seal

    assert_installed_origin(chimeraforge.__file__, checkout)
    cases, policy, campaigns = fixtures()
    paths = {name: cwd / f"envelope-{name}.json" for name in ("cases", "policy", "lower", "higher")}
    original = {
        paths[name]: json.dumps(value).encode()
        for name, value in {"cases": cases, "policy": policy, **campaigns}.items()
    }
    for path, raw in original.items():
        path.write_bytes(raw)

    def arguments(supplied: dict[str, Path], *, case_path: Path = paths["cases"]) -> list[str]:
        argv = [
            "trace-envelope",
            "--cases",
            str(case_path),
            "--policy",
            str(paths["policy"]),
            "--json",
        ]
        for name, path in supplied.items():
            argv.extend(["--campaign", f"{name}={path}"])
        return argv

    def receive(label: str, supplied: dict[str, Path], code: int) -> dict:
        supplied_bytes = {name: path.read_bytes() for name, path in supplied.items()}
        output = cwd / f"envelope-{label}-assessment.json"
        report = json.loads(run_cli([*arguments(supplied), "--out", str(output)], cwd, env, code))
        assert report == json.loads(output.read_bytes())
        counts = _validate(
            report,
            cases,
            policy,
            original[paths["cases"]],
            original[paths["policy"]],
            supplied_bytes,
        )
        assert all(path.read_bytes() == supplied_bytes[name] for name, path in supplied.items())
        assert report["exit_code"] == code
        return {"assessment": report, "counts": counts}

    supplied = {name: paths[name] for name in campaigns}
    full = receive("full", supplied, 0)
    assert full["assessment"]["outcome"] == "conditional_pass"
    assert full["assessment"]["highest_observed_passing"] == {
        "cell": "higher",
        "arrival_interval_seconds": HIGHER_INTERVAL_SECONDS,
        "nominal_rate_rps": 1.0 / HIGHER_INTERVAL_SECONDS,
    }
    missing = receive("missing", {"lower": paths["lower"]}, 3)
    assert missing["assessment"]["outcome"] == "inconclusive"
    assert missing["assessment"]["highest_observed_passing"]["cell"] == "lower"
    assert missing["counts"]["missing_replicas"] == cases["expected_replicates"]
    breached_path = cwd / "envelope-higher-breach.json"
    breached_path.write_bytes(
        json.dumps(uniform_campaign(HIGHER_INTERVAL_SECONDS, durations=(0.12, 3.0))).encode()
    )
    breached = receive("breach", {"lower": paths["lower"], "higher": breached_path}, 1)
    assert breached["assessment"]["outcome"] == "observed_breach"
    assert breached["assessment"]["highest_observed_passing"]["cell"] == "lower"
    assert breached["counts"]["known_breaches"] == 2
    assert breached["assessment"]["cells"][1]["observed_outcome"] == "breach"

    refusals = []

    def refuse(argv: list[str]) -> None:
        result = json.loads(run_cli(argv, cwd, env, 2))
        assert set(result) == {"error"} and result["error"]
        assert PRIVATE_DIAGNOSTIC not in json.dumps(result) and PRIVATE_INPUT not in json.dumps(
            result
        )
        refusals.append(2)

    refuse(arguments({**supplied, PRIVATE_DIAGNOSTIC: paths["lower"]}))
    malformed = cwd / "envelope-malformed-cases.json"
    malformed.write_bytes(json.dumps({**cases, PRIVATE_DIAGNOSTIC: PRIVATE_INPUT}).encode())
    refuse(arguments(supplied, case_path=malformed))
    malformed.write_bytes(
        b'{"private-envelope-diagnostic-sentinel":1,"private-envelope-diagnostic-sentinel":2}'
    )
    refuse(arguments(supplied, case_path=malformed))
    invalid_campaign = copy.deepcopy(campaigns["higher"])
    invalid_campaign["replicas"].pop()
    invalid_path = cwd / "envelope-malformed-campaign.json"
    invalid_path.write_bytes(json.dumps(seal(invalid_campaign)).encode())
    refuse(arguments({"lower": paths["lower"], "higher": invalid_path}))
    for path in original:
        refuse([*arguments(supplied), "--out", str(path)])
    alias = cwd / "envelope-outside-input-alias.json"
    os.link(paths["lower"], alias)
    refuse([*arguments(supplied), "--out", str(alias)])
    assert all(path.read_bytes() == raw for path, raw in original.items())

    def summary(result: dict) -> dict:
        report = result["assessment"]
        return {
            "exit_code": report["exit_code"],
            "outcome": report["outcome"],
            "highest_observed_passing": report["highest_observed_passing"],
            "counts": result["counts"],
        }

    return {
        "scope": (
            "Installed synthetic offline finite-envelope oracles; "
            "no inference, capacity or independent-execution claim"
        ),
        "full_population": summary(full),
        "missing_higher": summary(missing),
        "known_breach": summary(breached),
        "refusal_count": len(refusals),
        "source_inputs_checked": len(original),
        "source_bytes_unchanged": True,
    }
