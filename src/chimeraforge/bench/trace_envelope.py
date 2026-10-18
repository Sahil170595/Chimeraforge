"""Conditional observed points over a finite declared uniform-load envelope."""

from __future__ import annotations

from collections.abc import Mapping
import copy
from itertools import combinations

from chimeraforge.bench.gate import (
    FACTS,
    RegressionGate,
    _cache,
    _cache_compatible,
    _condition_states,
)
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.serving_binding import observed_model
from chimeraforge.bench.trace import _qualify
from chimeraforge.bench.trace_envelope_inputs import HeldEnvelope, load_inputs
from chimeraforge.bench.trace_gate import TraceGatePolicy, _evidence, _known_fact, _view
from chimeraforge.planner.replay import digest


def _cell(cell: dict, held: HeldEnvelope) -> tuple[dict, list[dict], list[dict]]:
    name = cell["name"]
    campaign = held.campaigns.get(name)
    row = {
        "name": name,
        "arrival_interval_seconds": cell["arrival_interval_seconds"],
        "nominal_rate_rps": 1.0 / float(cell["arrival_interval_seconds"]),
        "execution_state": "missing",
        "observed_outcome": "unavailable",
        "eligible_for_point": False,
        "blockers": [],
        "replicas": [],
    }
    if campaign is None:
        row["blockers"].append("campaign_missing")
        if held.policy["require_cache_evidence"]:
            row["blockers"].append("cache_evidence_unavailable")
        row["replicas"] = [
            {
                "index": index,
                "state": "missing",
                "reason": "campaign_not_supplied",
                "error": None,
                "receipt": None,
            }
            for index in range(held.cases["expected_replicates"])
        ]
        return row, [], []
    complete = campaign["data"]["exit_code"] == 0
    row["execution_state"] = "completed" if complete else "incomplete"
    if not complete:
        row["blockers"].append("campaign_execution_incomplete")
    entries, breaches, joint_states = [], [], []
    for slot, native in zip(campaign["data"]["replicas"], campaign["replicas"]):
        projected = {
            key: slot[key] for key in ("index", "state", "reason", "error", "start_s", "end_s")
        }
        projected["receipt"] = None if native is None else copy.deepcopy(native["data"])
        if native is None:
            if held.policy["require_cache_evidence"]:
                row["blockers"].append("cache_evidence_unavailable")
        else:
            if native["data"]["clock"]["origin"] is None:
                row["blockers"].append("clock_origin_unavailable")
            evidence = _evidence(native)
            projected["evidence_sha256"] = evidence
            entries.append(
                {
                    "cell": name,
                    "replica_index": slot["index"],
                    "native": native,
                    "evidence": evidence,
                }
            )
            for request in native["data"]["requests"]:
                states = _qualify(request, held.policy["targets"])
                joint_states.append(states["joint"])
                for target, threshold in held.policy["targets"].items():
                    if states[target] == "breach":
                        breaches.append(
                            {
                                "cell": name,
                                "replica_index": slot["index"],
                                "request_id": request["descriptor"]["request_id"],
                                "target": target,
                                "observed": request["timing"][target],
                                "threshold": threshold,
                            }
                        )
                if any(
                    request["native"][key] is None or request["native"][key] <= 0
                    for key in ("prompt_tokens", "tokens_generated")
                ):
                    row["blockers"].append("observed_token_lengths_unavailable")
                if request["output_cap_state"] == "exceeded":
                    row["blockers"].append("output_cap_exceeded")
        row["replicas"].append(projected)
    if "unknown" in joint_states:
        row["blockers"].append("slo_evidence_unavailable")
    row["observed_outcome"] = (
        "breach"
        if breaches
        else "observed_pass"
        if complete and joint_states and all(state == "pass" for state in joint_states)
        else "unavailable"
    )
    return row, entries, breaches


def _comparison_view(native: dict, model: str) -> dict:
    view: dict = _view(native)
    for phase in ("serving_before", "serving_after"):
        value = view["execution"][phase]["model"]
        if value is not None:
            view["execution"][phase]["model"] = observed_model(value, model)
    return view


def _conditions(
    entries: list[dict], held: HeldEnvelope, cells: dict[str, dict]
) -> tuple[dict, list[str]]:
    fixed = dict(held.policy["fixed_controls"])
    if "model" in fixed:
        fixed["model"] = observed_model(fixed["model"], held.cases["model"])
    adapter = TraceGatePolicy(fixed_controls=fixed)
    views = []
    blockers = []
    for entry in entries:
        view = _comparison_view(entry["native"], held.cases["model"])
        entry["view"] = view
        views.append(view)
        _, local, _ = _condition_states(view, view, adapter)
        cells[entry["cell"]]["blockers"].extend(local)
        for phase in ("serving_before", "serving_after"):
            facts = view["execution"][phase]
            for name, expected in (
                ("backend", held.cases["backend"]),
                ("model", held.cases["model"].removeprefix("ollama:")),
            ):
                actual = _known_fact(facts, name)
                if actual is not None and actual != expected:
                    blockers.append("serving_identity_mismatch:" + name)
    conditions = {}
    for name in sorted(FACTS):
        values = [
            _known_fact(view["execution"][phase], name)
            for view in views
            for phase in ("serving_before", "serving_after")
        ]
        known = []
        for value in values:
            if value is not None and value not in known:
                known.append(value)
        required = name in fixed
        mismatch = len(known) > 1 or required and any(value != fixed[name] for value in known)
        unavailable = not values or any(value is None for value in values)
        state = "mismatch" if mismatch else "unavailable" if unavailable else "matched"
        if mismatch:
            blockers.append("condition:" + name)
        conditions[name] = {
            "state": state,
            "required": required,
            "comparison_known_values": known,
            "unavailable_observations": sum(value is None for value in values),
            "observations": len(values),
            "expected": held.policy["fixed_controls"].get(name),
            "scope": "supported observed metadata; unrequired unknown facts remain uncontrolled",
        }
    return conditions, blockers


def _compatibility(
    entries: list[dict], held: HeldEnvelope, cells: dict[str, dict]
) -> tuple[dict, list[str]]:
    conditions, blockers = _conditions(entries, held, cells)
    caches = []
    for entry in entries:
        native = entry["native"]["data"]
        cached = _cache(entry["view"])
        if cached["state"] == "mismatch":
            blockers.append("cache_contradiction")
        if held.policy["require_cache_evidence"] and cached["state"] == "unknown":
            cells[entry["cell"]]["blockers"].append("cache_evidence_unavailable")
        caches.append(
            {
                "cell": entry["cell"],
                "replica_index": entry["replica_index"],
                **cached,
                "ordered_counts": [
                    request["native"]["cached_prompt_tokens"] for request in native["requests"]
                ],
            }
        )
        if any(request["output_cap_state"] == "exceeded" for request in native["requests"]):
            blockers.append("output_cap_exceeded")
    if any(not _cache_compatible(left, right) for left, right in combinations(caches, 2)):
        blockers.append("observed_cache_hits_changed")
    for field_name in ("prompt_tokens", "tokens_generated", "cached_prompt_tokens"):
        for index in range(len(held.cases["ordered_descriptors"])):
            known = []
            for entry in entries:
                value = entry["native"]["data"]["requests"][index]["native"][field_name]
                if value is not None and value not in known:
                    known.append(value)
            if len(known) > 1:
                blockers.append(
                    "ordered_cache_hits_changed"
                    if field_name == "cached_prompt_tokens"
                    else "observed_actual_lengths_changed:" + field_name
                )
    evidence = [entry["evidence"] for entry in entries]
    if len(set(evidence)) != len(evidence):
        blockers.append("duplicate_execution_payload")
    if held.policy["targets"]["tpot_ms"] is not None:
        bases = {
            request["mean_tpot_basis"]
            for entry in entries
            for request in entry["native"]["data"]["requests"]
            if request["mean_tpot_basis"] != "unavailable"
        }
        if len(bases) > 1:
            blockers.append("mean_timing_basis_changed")
    return {"conditions": conditions, "cache": caches}, sorted(set(blockers))


def assess_trace_envelope(cases: object, campaigns: Mapping, *, policy: object) -> RegressionGate:
    """Assess declared uniform schedules, never interpolate or infer serving capacity."""
    held = load_inputs(cases, campaigns, policy)
    rows, entries, breaches = [], [], []
    for cell in held.cases["cells"]:
        row, natives, observed_breaches = _cell(cell, held)
        rows.append(row)
        entries.extend(natives)
        breaches.extend(observed_breaches)
    compatibility, global_blocks = _compatibility(entries, held, {row["name"]: row for row in rows})
    blockers = list(global_blocks)
    for row in rows:
        row["blockers"] = sorted(set(row["blockers"]))
        row["eligible_for_point"] = (
            row["execution_state"] == "completed"
            and row["observed_outcome"] == "observed_pass"
            and not row["blockers"]
            and not global_blocks
        )
        blockers.extend("cell:" + row["name"] + ":" + reason for reason in row["blockers"])
    passing = [row for row in rows if row["eligible_for_point"]]
    highest = max(passing, key=lambda row: row["nominal_rate_rps"]) if passing else None
    point = (
        None
        if highest is None
        else {
            "cell": highest["name"],
            "arrival_interval_seconds": highest["arrival_interval_seconds"],
            "nominal_rate_rps": highest["nominal_rate_rps"],
        }
    )
    outcome = "inconclusive" if blockers else "observed_breach" if breaches else "conditional_pass"
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-envelope-assessment",
        "created_at": now_iso(),
        "cases": held.cases,
        "policy": held.policy,
        "inputs": held.inputs,
        "cells": rows,
        "highest_observed_passing": point,
        "compatibility": compatibility,
        "known_breaches": breaches,
        "blockers": sorted(set(blockers)),
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "observed_breach": 1, "inconclusive": 3}[outcome],
        "budgets": held.budgets,
        "assurance": {
            "source_authentication": "unverified",
            "physical_authentication": "unverified",
            "external_preregistration": "unverified",
            "time_authentication": "unverified",
            "independent_executions_verified": False,
            "cache_evidence_required": held.policy["require_cache_evidence"],
            "capacity_qualification": "unverified",
            "interpolation": "not performed",
        },
        "limits": (
            "Highest observed complete passing declared nominal cadence only, not capacity, "
            "interpolation, deployment qualification or calibration GO. "
            "Every declared request/replica "
            "is retained; unknown unrequired controls remain uncontrolled. Evidence hashes catch "
            "unchanged normalized native payloads despite relabelled IDs/stamps/origins; "
            "schedule and "
            "relative timings are retained, so consistently rescheduled/resealed copies cannot be "
            "authenticated or excluded. Prompts, serving weights, hardware, timing and execution "
            "independence remain unauthenticated. Byte limits charge campaign input occurrences, "
            "with separate case/policy budgets; they are not a total transport/output bound."
        ),
    }
    report["fingerprint"] = digest(report)
    return RegressionGate(report, held.protected_paths)
