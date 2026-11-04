"""Whole-population passive SLO acceptance, never a relative percentile gate."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from chimeraforge.bench.gate_inputs import MAX_POLICY_BYTES, finite, held_json as policy_json, sha
from chimeraforge.bench.trace_gate import _evidence_real
from chimeraforge.fleet_monitor_gate_types import FleetMonitorGate, FleetMonitorGatePolicy
from chimeraforge.fleet_monitor_json import encode_public
from chimeraforge.fleet_monitor_receipt import (
    controls_from,
    fail,
    from_held,
    held_json,
    held_source,
    same,
    select_plan,
)
from chimeraforge.fleet_monitor_types import FleetMonitorReport, MAX_ENDPOINTS, MAX_TOTAL_WINDOWS
from chimeraforge.planner.replay import digest

KIND = "chimeraforge.fleet-monitor-gate"
ARMS = ("baseline", "candidate")
LOG = logging.getLogger(__name__)


def policy_from(source: Any) -> tuple[dict, tuple[Path, ...]]:
    if type(source) is FleetMonitorGatePolicy:
        source = {
            name: getattr(source, name)
            for name in (
                "schema_version",
                "original_replicas",
                "endpoint_ids",
                "windows",
                "metrics",
                "baseline",
                "candidate",
            )
        }
    if type(source) is dict:
        data = json.loads(encode_public(source, limit=MAX_POLICY_BYTES))
        paths: tuple[Path, ...] = ()
    else:
        data, _, path = policy_json(source, MAX_POLICY_BYTES)
        paths = (path,) if path is not None else ()
    if (
        set(data)
        != {
            "schema_version",
            "original_replicas",
            "endpoint_ids",
            "windows",
            "metrics",
            "baseline",
            "candidate",
        }
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
    ):
        fail("policy requires a closed versioned population/arm commitment")
    n, windows, ids = (data[name] for name in ("original_replicas", "windows", "endpoint_ids"))
    if (
        type(n) is not int
        or not 1 <= n <= MAX_ENDPOINTS
        or type(windows) is not int
        or not 1 <= windows <= MAX_TOTAL_WINDOWS // n
        or type(ids) is not list
        or len(ids) != n
        or any(type(value) is not str for value in ids)
        or len(set(ids)) != n
        or type(data["metrics"]) is not dict
        or not data["metrics"]
        or not set(data["metrics"]) <= {"ttft", "tpot"}
    ):
        fail("invalid declared original population/windows/metrics")
    for rule in data["metrics"].values():
        if (
            type(rule) is not dict
            or set(rule) != {"minimum_samples"}
            or type(rule["minimum_samples"]) is not int
            or rule["minimum_samples"] <= 0
            or not finite(rule["minimum_samples"])
        ):
            fail("each native metric needs a positive finite minimum sample count")
    for arm in ARMS:
        declared = data[arm]
        if type(declared) is not dict or set(declared) != {"plan", "controls"}:
            fail("each arm needs exact plan/controls commitments")
        plan = declared["plan"]
        if (
            type(plan) is not dict
            or set(plan) != {"fingerprint", "candidate_index"}
            or not sha(plan["fingerprint"])
            or type(plan["candidate_index"]) is not int
            or plan["candidate_index"] < 0
        ):
            fail("invalid original plan/selection commitment")
        controls = declared["controls"]
        if type(controls) is not dict or type(controls.get("targets")) is not dict:
            fail("missing explicit resolved targets")
        # Policy admission validates its own declared domain. Actual source/receipt
        # agreement is an eligibility check, not an inferred policy from the run.
        inputs = {
            name + "_slo": controls["targets"].get(name + "_ms")
            if controls.get("target_sources", {}).get(name) == "saved_request"
            else None
            for name in ("ttft", "tpot")
        }
        controls_from(
            controls,
            {"inputs": inputs},
            {"n_agents": n, "backend": "vllm", "model": "policy/model"},
        )
        if controls["windows"] != windows or [row["id"] for row in controls["endpoints"]] != ids:
            fail("policy member/window commitments disagree")
        requested = {
            name for name in ("ttft", "tpot") if controls["targets"][name + "_ms"] is not None
        }
        if requested != set(data["metrics"]):
            fail("every requested native target must have a declared metric rule")
    return data, paths


def evidence(report: FleetMonitorReport) -> str:
    """Equivalent window payload detection ignores labels/timestamps, not proof of independence."""
    members = []
    for slot in report.slots:
        windows = []
        for window in slot.windows:
            windows.append(
                {
                    "seconds": _evidence_real(window.seconds),
                    "metrics": {
                        name: {
                            "samples": metric.samples,
                            "lower": _evidence_real(metric.p95_lower_ms)
                            if metric.p95_lower_ms is not None
                            else None,
                            "upper": _evidence_real(metric.p95_upper_ms)
                            if metric.p95_upper_ms is not None
                            else None,
                            "confidence": metric.confidence,
                        }
                        for name, metric in window.metrics.items()
                    },
                }
            )
        members.append({"windows": windows, "state": slot.state, "error": slot.error})
    cleanup = {**report.cleanup, "budget_seconds": _evidence_real(report.cleanup["budget_seconds"])}
    return digest(
        {"members": sorted(members, key=digest), "budget": report.budget, "cleanup": cleanup}
    )


def _bracket(observations: list[dict], index: int, observed_at: str) -> bool:
    if index + 1 >= len(observations):
        return False
    try:
        before, after = (
            datetime.fromisoformat(observations[i]["captured_at"]) for i in (index, index + 1)
        )
        point = datetime.fromisoformat(observed_at)
        return before <= point <= after
    except (ValueError, TypeError, KeyError) as exc:
        LOG.info("fleet metadata bracket unavailable (%s)", type(exc).__name__)
        return False


def projection(report: FleetMonitorReport, held: tuple, basis: str) -> dict:
    """Native gate evidence summary; full observations stay in hashed held receipts."""
    complete = sum(slot.state == "complete" for slot in report.slots)
    return {
        "receipt_sha256": hashlib.sha256(held[1]).hexdigest(),
        "receipt_bytes": len(held[1]),
        "raw_basis": basis,
        "evidence_sha256": evidence(report),
        "plan": report.plan,
        "producer": {
            "schema_version": report.schema_version,
            "monitor_tool_version": report.monitor_tool_version,
            "native_exit_code": report.exit_code,
            "outcome": {0: "pass", 3: "breach", 4: "unknown", 5: "mismatch"}[report.exit_code],
            "declared_coverage": {
                "expected": len(report.slots),
                "complete": complete,
                "state": "complete" if complete == len(report.slots) else "incomplete",
            },
            "cancelled": report.cancelled,
            "budget": report.budget,
            "cleanup": report.cleanup,
            "target_sources": report.target_sources,
            "effective_controls": report.effective_controls,
        },
        "slots": [
            {
                "id": slot.id,
                "url": slot.url,
                "state": slot.state,
                "slo": slot.slo,
                "error": slot.error,
                "windows": slot.windows,
                "observations_retained": len(slot.observations),
                "metadata_brackets": [
                    {
                        "window_index": i,
                        "complete": i + 1 < len(slot.observations),
                        "timestamp_ordered": _bracket(slot.observations, i, window.observed_at),
                    }
                    for i, window in enumerate(slot.windows)
                ],
                "binding": {
                    section: {
                        "state": slot.binding[section]["state"],
                        "fields": {
                            name: row["state"]
                            for name, row in slot.binding[section]["fields"].items()
                        },
                    }
                    for section in ("identity", "configuration")
                },
                "binding_windows": [
                    {
                        "window_index": row["window_index"],
                        "fields": {name: field["state"] for name, field in row["fields"].items()},
                    }
                    for row in slot.binding["windows"]
                ],
            }
            for slot in report.slots
        ],
    }


def _cases(report: FleetMonitorReport, policy: dict, arm: str) -> tuple[list[dict], list[str]]:
    reasons = []
    if report.effective_controls is None:
        reasons.append(arm + ":legacy_requested_controls_unavailable")
    elif not same(report.effective_controls, policy[arm]["controls"]):
        reasons.append(arm + ":requested_controls_mismatch")
    if not same(
        {key: report.plan[key] for key in ("fingerprint", "candidate_index")}, policy[arm]["plan"]
    ):
        reasons.append(arm + ":original_source_selection_mismatch")
    if (
        len(report.slots) != policy["original_replicas"]
        or [slot.id for slot in report.slots] != policy["endpoint_ids"]
    ):
        reasons.append(arm + ":original_population_mismatch")
    if (
        report.cancelled
        or report.budget["termination"] is not None
        or report.cleanup["state"] != "completed"
    ):
        reasons.append(arm + ":observation_or_cleanup_incomplete")
    lookup = {slot.id: slot for slot in report.slots}
    ids = list(dict.fromkeys([*policy["endpoint_ids"], *(slot.id for slot in report.slots)]))
    cases = []
    for member in ids:
        slot = lookup.get(member)
        if slot is None or slot.state != "complete":
            reasons.append(arm + ":member_incomplete")
        if slot is not None and (
            slot.binding["identity"]["state"] != "matched"
            or slot.binding["configuration"]["state"] == "mismatch"
        ):
            reasons.append(arm + ":identity_unavailable_or_known_configuration_mismatch")
        declared = policy["windows"] if member in policy["endpoint_ids"] else 0
        actual = (
            report.effective_controls["windows"]
            if slot is not None and report.effective_controls is not None
            else len(slot.windows)
            if slot is not None
            else 0
        )
        for index in range(max(declared, actual)):
            window = slot.windows[index] if slot is not None and index < len(slot.windows) else None
            if (
                slot is None
                or window is None
                or not _bracket(slot.observations, index, window.observed_at)
            ):
                reasons.append(arm + ":missing_or_stale_window_bracket")
            for name, rule in policy["metrics"].items():
                metric = window.metrics[name] if window is not None else None
                known = (
                    metric is not None
                    and metric.samples is not None
                    and metric.samples >= rule["minimum_samples"]
                    and metric.confidence == "histogram-bound"
                    and metric.outcome in ("pass", "breach")
                )
                if not known:
                    reasons.append(arm + ":required_metric_unavailable_or_underpopulated")
                cases.append(
                    {
                        "arm": arm,
                        "member_id": member,
                        "window_index": index,
                        "metric": name,
                        "native_outcome": metric.outcome if metric is not None else "unavailable",
                        "samples": metric.samples if metric is not None else None,
                        "p95_lower_ms": metric.p95_lower_ms if metric is not None else None,
                        "p95_upper_ms": metric.p95_upper_ms if metric is not None else None,
                        "target_ms": metric.target_ms if metric is not None else None,
                        "native_reason": metric.reason
                        if metric is not None
                        else "requested window unavailable",
                    }
                )
    return cases, reasons


def gate_fleet_monitors(
    baseline: Any,
    candidate: Any,
    *,
    baseline_plan: Any,
    candidate_plan: Any,
    policy: Any,
) -> FleetMonitorGate:
    from chimeraforge.api import PlanError

    try:
        chosen, policy_paths = policy_from(policy)
        reports, inputs, paths, cases, blockers = {}, {}, list(policy_paths), [], []
        receipt_cache: dict[Any, Any] = {}
        source_cache: dict[Any, Any] = {}
        for arm, receipt, saved in (
            ("baseline", baseline, baseline_plan),
            ("candidate", candidate, candidate_plan),
        ):
            key = (
                ("path", str(Path(receipt).absolute()))
                if isinstance(receipt, (str, Path))
                else ("object", id(receipt))
            )
            if key not in receipt_cache:
                receipt_cache[key] = held_json(receipt)
            held = receipt_cache[key]
            index = held[0]["plan"]["candidate_index"]
            key = (
                ("path", str(Path(saved).absolute()))
                if isinstance(saved, (str, Path))
                else ("object", id(saved))
            )
            if key not in source_cache:
                source_cache[key] = held_source(saved)
            report = from_held(held, select_plan(source_cache[key], index), index)
            reports[arm] = report
            paths.extend(report._input_paths)
            basis = (
                "held file bytes"
                if isinstance(receipt, (str, Path))
                else (
                    "validated original held bytes"
                    if type(receipt) is FleetMonitorReport and receipt._held_bytes is not None
                    else "serialized public snapshot bytes"
                )
            )
            inputs[arm] = projection(report, held, basis)
            arm_cases, reasons = _cases(report, chosen, arm)
            cases.extend(arm_cases)
            blockers.extend(reasons)
        if inputs["baseline"]["evidence_sha256"] == inputs["candidate"]["evidence_sha256"]:
            blockers.append("equivalent_observed_window_payload")
        breach = any(
            row["arm"] == "candidate" and row["native_outcome"] == "breach" for row in cases
        )
        code = 3 if blockers else 1 if breach else 0
        for row in cases:
            row["state"] = (
                "inconclusive"
                if blockers
                else ("supporting" if row["arm"] == "baseline" else row["native_outcome"])
            )
        return FleetMonitorGate(
            {
                "schema_version": 1,
                "kind": KIND,
                "policy": chosen,
                "inputs": inputs,
                "cases": cases,
                "blockers": sorted(set(blockers)),
                "exit_code": code,
                "outcome": {0: "conditional_pass", 1: "breach", 3: "inconclusive"}[code],
                "assurance": {
                    "source_authentication": "unverified",
                    "independent_executions_verified": False,
                    "raw_histograms_reverified": False,
                    "physical_identity": "unverified",
                },
                "limits": (
                    "Conditional passive SLO acceptance; baseline is supporting evidence, "
                    "not a relative comparison. Bucket bounds are not confidence intervals. "
                    "No pooled percentiles, causal improvement, physical independence, weights, "
                    "workload/cache distribution or actual closure attestation. "
                    "Receipts retain endpoint URLs and private model/plan intent; "
                    "treat like the original inputs."
                ),
            },
            tuple(dict.fromkeys(paths)),
        )
    except PlanError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        OSError,
        RecursionError,
        OverflowError,
    ) as exc:
        LOG.info("fleet passive gate refused (%s)", type(exc).__name__)
        fail("malformed, unsupported or over-limit gate input")
