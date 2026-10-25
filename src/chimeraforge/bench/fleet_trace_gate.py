"""Conditional native regression over two complete original-fleet executions."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from chimeraforge.bench import trace_gate
from chimeraforge.bench.fleet_gate_evidence import compare_members, evidence, projection
from chimeraforge.bench.fleet_gate_inputs import (
    ARMS,
    COMMON_CONTROLS,
    PLAN_FIELDS,
    FleetTraceGatePolicy,
    hold_pair,
    policy_from,
)
from chimeraforge.bench.fleet_trace_types import FleetTraceReplay
from chimeraforge.bench.gate import RegressionGate
from chimeraforge.bench.metrics import now_iso
from chimeraforge.planner.replay import digest

KIND = "chimeraforge.fleet-trace-regression-gate"


def gate_fleet_traces(
    baseline: FleetTraceReplay | dict | str | Path,
    candidate: FleetTraceReplay | dict | str | Path,
    *,
    policy: FleetTraceGatePolicy | dict | str | Path,
) -> RegressionGate:
    chosen, policy_path = policy_from(policy)
    arms = hold_pair(baseline, candidate)
    blockers, populations, works = [], {}, {}
    for arm in ARMS:
        loaded = arms[arm]
        data, declared = loaded["data"], getattr(chosen, arm)
        selected = data["plan"]["snapshot"]["result"]["candidates"][data["plan"]["candidate_index"]]
        source = {
            "plan": {key: data["plan"][key] for key in PLAN_FIELDS},
            "backend": data["controls"]["backend"],
            "endpoints": data["endpoints"],
        }
        population = {
            "original_replicas": selected["n_agents"],
            "endpoint_ids": [row["id"] for row in data["endpoints"]],
            "workload_sha256": data["workload"]["canonical_sha256"],
            "ordered_descriptors_sha256": digest(
                [row["descriptor"] for row in data["native_trace"]["requests"]]
            ),
            "routes_sha256": data["routes"]["canonical_sha256"],
            "controls": {key: data["controls"][key] for key in COMMON_CONTROLS},
        }
        if digest(source) != digest(declared):
            blockers.append(arm + ":source_selection_or_endpoint_commitment")
        if digest(population) != digest(
            {k: v for k, v in chosen.population.items() if k != "minimum_requests_per_slot"}
        ):
            blockers.append(arm + ":population_work_routes_or_controls_commitment")
        populations[arm] = population
        native = loaded["native"]
        if data["exit_code"] != 0 or native["data"]["exit_code"] != 0:
            blockers.append(arm + ":producer_execution_or_configuration_incomplete")
        if native["data"]["clock"]["origin"] is None:
            blockers.append(arm + ":clock_origin_unavailable")
        if data["cleanup"]["state"] != "completed":
            blockers.append(arm + ":resource_cleanup_unverified")
        works[arm], more = trace_gate._workload(native)
        blockers.extend(arm + ":" + reason for reason in more)
        loaded["evidence_sha256"] = evidence(loaded)
    if digest(works["baseline"]) != digest(works["candidate"]):
        blockers.append("workload_or_actual_lengths_changed")
    if arms["baseline"]["evidence_sha256"] == arms["candidate"]["evidence_sha256"]:
        blockers.append("duplicate_execution_payload")
    members, more = compare_members(arms, chosen)
    blockers.extend(more)
    mean_consumed = (
        "tpot_p95_ms" in chosen.trace.rules
        or "goodput_rps" in chosen.trace.rules
        and any(arms[arm]["native"]["data"]["targets"]["tpot_ms"] is not None for arm in ARMS)
    )
    if mean_consumed:
        bases = [
            {row["mean_tpot_basis"] for row in arms[arm]["native"]["data"]["requests"]}
            for arm in ARMS
        ]
        if bases[0] != bases[1] or len(bases[0]) != 1 or "unavailable" in bases[0]:
            blockers.append("mean_timing_basis_unavailable_or_changed")
    metrics, more = trace_gate._compare_metrics(
        arms["baseline"]["native"], arms["candidate"]["native"], chosen.trace.rules
    )
    blockers.extend(more)
    known_breaches = [
        name
        for name, value in metrics.items()
        if value["regression_fraction"] is not None
        and value["regression_fraction"] > value["max_regression_fraction"]
    ]
    outcome = "inconclusive" if blockers else "regression" if known_breaches else "conditional_pass"
    if blockers:
        for value in metrics.values():
            value["state"] = "inconclusive"
    report = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": now_iso(),
        "policy": asdict(chosen),
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "regression": 1, "inconclusive": 3}[outcome],
        "blockers": sorted(set(blockers)),
        "known_breaches": known_breaches,
        "population": populations,
        "members": members,
        "metrics": metrics,
        "workload": works,
        "inputs": {arm: projection(arms[arm]) for arm in ARMS},
        "assurance": {
            "source_authentication": "unverified",
            "physical_authentication": "unverified",
            "external_preregistration": "unverified",
            "independent_executions_verified": False,
            "cold_runs": "unverified",
            "gpu_geometry": "unverified",
            "confidence_interval": "not computed",
            "cache_evidence_required": chosen.trace.require_cache_evidence,
        },
        "limits": (
            "Conditional comparison of two declared complete original-fleet executions. "
            "All original rows and members retained; no survivor selection, slot-percentile "
            "averaging, independent/cold/GPU/capacity qualification or source authentication. "
            "Private plan intent, model identifiers and declared URLs may be present; "
            "treat the decision like its source inputs."
        ),
    }
    report["fingerprint"] = digest(report)
    protected = tuple(path for loaded in arms.values() for path in loaded["protected_paths"])
    if policy_path is not None:
        protected += (policy_path,)
    return RegressionGate(report, tuple(dict.fromkeys(protected)))
