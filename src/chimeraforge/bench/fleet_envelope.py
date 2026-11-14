"""Finite observed load points from every original whole-fleet execution."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from chimeraforge.bench.fleet_envelope_inputs import load_inputs
from chimeraforge.bench.fleet_gate_evidence import evidence, member_view, _member_cache
from chimeraforge.bench.fleet_trace_types import _admit_receipt
from chimeraforge.bench.gate import FACTS, RegressionGate, _condition_states, _cache_compatible
from chimeraforge.bench.gate_inputs import MAX_RECEIPT_BYTES
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.serving_binding import observed_model
from chimeraforge.bench.trace import _qualify
from chimeraforge.bench.trace_gate import TraceGatePolicy, _known_fact, _workload
from chimeraforge.planner.replay import digest

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

LOG = logging.getLogger(__name__)
MAX_OUTPUT_BYTES = MAX_RECEIPT_BYTES


def _assess(
    saved: PlanArtifact | str | Path,
    cases: object,
    campaigns: Mapping,
    policy: object,
    candidate_index: int,
) -> RegressionGate:
    held, source = load_inputs(saved, cases, campaigns, policy, candidate_index)
    declared, chosen = held.cases, held.policy
    fixed = dict(chosen["fixed_controls"])
    if "model" in fixed:
        fixed["model"] = observed_model(fixed["model"], declared["model"])
    adapter = TraceGatePolicy(fixed_controls=fixed)
    endpoint_indices = {row["id"]: i for i, row in enumerate(declared["endpoints"])}
    assignments = [endpoint_indices[row["endpoint_id"]] for row in declared["routes"]]
    known_controls: dict[tuple[int, str], list[object]] = {}
    prior_caches: dict[int, list[dict]] = {}
    known_lengths: dict[tuple[int, str], set[int]] = {}
    payloads: list[str] = []
    global_blocks: list[str] = []
    breaches: list[dict] = []
    cells: list[dict] = []
    for cell_index, cell in enumerate(declared["cells"]):
        campaign = held.campaigns.get(cell["name"])
        blocked, executions = [], []
        if campaign is None:
            blocked.append("campaign_missing")
        elif (
            campaign["data"]["state"] != "completed" or campaign["data"]["stop_reason"] is not None
        ):
            blocked.append("campaign_incomplete")
        joint_states = []
        for execution_index in range(declared["expected_executions"]):
            child = None if campaign is None else campaign["children"][execution_index]
            slot = None if campaign is None else campaign["data"]["executions"][execution_index]
            members, rows = [], []
            native = None if child is None else child["data"]
            evidence_sha = None
            if child is None:
                blocked.append("execution_unavailable")
            else:
                assert native is not None
                evidence_sha = evidence(child)
                payloads.append(evidence_sha)
                if (
                    native["status"] != "completed"
                    or native["exit_code"] != 0
                    or native["cleanup"]["state"] != "completed"
                ):
                    blocked.append("execution_or_configuration_incomplete")
                if child["native"]["data"]["clock"]["origin"] is None:
                    blocked.append("clock_origin_unavailable")
                _, reasons = _workload(child["native"])
                blocked.extend(reasons)
            for member_index in range(declared["original_replicas"]):
                indices = [i for i, member in enumerate(assignments) if member == member_index]
                local = []
                member = None if native is None else native["slots"][member_index]
                if not indices:
                    local.append("inactive_member")
                if member is None:
                    local.append("member_unavailable")
                    conditions, cache_state = {}, "unknown"
                else:
                    if member["error"] is not None or member["state"] in ("error", "incomplete"):
                        local.append("member_incomplete")
                    if any(
                        row["state"] == "mismatch"
                        for group in ("summary", "token_lengths")
                        for row in member["binding"][group].values()
                    ):
                        local.append("known_binding_mismatch")
                    assert native is not None
                    view = member_view(native, member)
                    for phase in ("serving_before", "serving_after"):
                        facts = view["execution"][phase]
                        model = observed_model(_known_fact(facts, "model"), declared["model"])
                        if (
                            _known_fact(facts, "backend") != declared["backend"]
                            or model != declared["model"]
                        ):
                            local.append("serving_identity_unavailable_or_mismatched")
                        facts["model"] = model
                    states, reasons, _ = _condition_states(view, view, adapter)
                    local.extend(reasons)
                    for name in FACTS:
                        fact_values = known_controls.setdefault((member_index, name), [])
                        for facts in view["execution"].values():
                            value = _known_fact(facts, name)
                            if value is not None and value not in fact_values:
                                fact_values.append(value)
                        if len(fact_values) > 1:
                            global_blocks.append("member_condition_changed:condition:" + name)
                    conditions = {
                        key: {"state": value["state"], "required": value["required"]}
                        for key, value in states.items()
                    }
                    cache = _member_cache(view)
                    cache_state = cache["state"]
                    if cache_state == "mismatch":
                        global_blocks.append("cache_contradiction")
                    if chosen["require_cache_evidence"] and cache_state == "unknown":
                        local.append("cache_evidence_unavailable")
                    cache_history = prior_caches.setdefault(member_index, [])
                    if any(not _cache_compatible(previous, cache) for previous in cache_history):
                        global_blocks.append("observed_cache_hits_changed")
                    cache_history.append(cache)
                blocked.extend(local)
                members.append(
                    {
                        "index": member_index,
                        "row_indices": indices,
                        "state": "unavailable" if member is None else member["state"],
                        "blockers": sorted(set(local)),
                        "conditions": conditions,
                        "cache_state": cache_state,
                    }
                )
            for row_index, member_index in enumerate(assignments):
                row = None if native is None else native["native_trace"]["requests"][row_index]
                slo_states = None if row is None else _qualify(row, chosen["targets"])
                outcome = "unknown" if slo_states is None else slo_states["joint"]
                joint_states.append(outcome)
                if outcome not in ("pass", "breach"):
                    blocked.append("slo_evidence_unavailable")
                counts = {
                    key: None if row is None else row["native"][key]
                    for key in ("prompt_tokens", "tokens_generated", "cached_prompt_tokens")
                }
                for key, value in counts.items():
                    known = known_lengths.setdefault((row_index, key), set())
                    if value is not None:
                        known.add(value)
                    if len(known) > 1:
                        global_blocks.append("ordered_actual_lengths_or_cache_changed")
                if row is not None:
                    assert slo_states is not None
                    for target, threshold in chosen["targets"].items():
                        if slo_states[target] == "breach":
                            breaches.append(
                                {
                                    "cell_index": cell_index,
                                    "execution_index": execution_index,
                                    "row_index": row_index,
                                    "target": target,
                                    "observed": row["timing"][target],
                                    "threshold": threshold,
                                }
                            )
                rows.append(
                    {
                        "index": row_index,
                        "member_index": member_index,
                        "state": "unavailable" if row is None else row["state"],
                        "outcome": outcome,
                        "tokens": counts,
                        "timing": {
                            target: None if row is None else row["timing"][target]
                            for target in chosen["targets"]
                        },
                        "mean_tpot_basis": None if row is None else row["mean_tpot_basis"],
                    }
                )
            executions.append(
                {
                    "index": execution_index,
                    "state": "missing" if slot is None else slot["state"],
                    "native_present": child is not None,
                    "evidence_sha256": evidence_sha,
                    "embedded_sha256": None if child is None else child["sha256"],
                    "byte_basis": "serialized embedded child representation",
                    "native_exit_code": None if native is None else native["exit_code"],
                    "members": members,
                    "rows": rows,
                }
            )
        local_breaches = any(item["cell_index"] == cell_index for item in breaches)
        cells.append(
            {
                "index": cell_index,
                "arrival_interval_seconds": cell["arrival_interval_seconds"],
                "nominal_rate_rps": 1.0 / float(cell["arrival_interval_seconds"]),
                "original_replicas": declared["original_replicas"],
                "expected_executions": declared["expected_executions"],
                "requests_per_execution": len(assignments),
                "total_requests": len(assignments) * declared["expected_executions"],
                "outcome": "breach"
                if local_breaches
                else "observed_pass"
                if not blocked and joint_states and all(value == "pass" for value in joint_states)
                else "unknown",
                "blockers": sorted(set(blocked)),
                "executions": executions,
            }
        )
    if len(set(payloads)) != len(payloads):
        global_blocks.append("duplicate_execution_payload")
    if chosen["targets"]["tpot_ms"] is not None:
        bases = {
            row["mean_tpot_basis"]
            for cell in cells
            for execution in cell["executions"]
            for row in execution["rows"]
            if row["mean_tpot_basis"] not in (None, "unavailable")
        }
        if len(bases) > 1:
            global_blocks.append("mean_timing_basis_changed")
    blockers = list(global_blocks)
    for cell in cells:
        cell["eligible_for_point"] = (
            cell["outcome"] == "observed_pass" and not cell["blockers"] and not global_blocks
        )
        blockers.extend("cell-" + str(cell["index"]) + ":" + reason for reason in cell["blockers"])
    passing = [cell for cell in cells if cell["eligible_for_point"]]
    highest = max(passing, key=lambda cell: cell["nominal_rate_rps"]) if passing else None
    outcome = "inconclusive" if blockers else "observed_breach" if breaches else "conditional_pass"
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.fleet-trace-envelope-assessment",
        "created_at": now_iso(),
        "source": source,
        "inputs": held.inputs,
        "policy": {
            "targets": chosen["targets"],
            "fixed_control_names": sorted(fixed),
            "require_cache_evidence": chosen["require_cache_evidence"],
        },
        "population": {
            "original_replicas": declared["original_replicas"],
            "expected_executions": declared["expected_executions"],
            "ordered_descriptors_sha256": digest(declared["ordered_descriptors"]),
            "routes_sha256": digest(declared["routes"]),
            "endpoints_sha256": digest(declared["endpoints"]),
        },
        "cells": cells,
        "known_breaches": breaches,
        "blockers": sorted(set(blockers)),
        "highest_observed_passing": None
        if highest is None
        else {
            "cell_index": highest["index"],
            "nominal_rate_rps": highest["nominal_rate_rps"],
            "arrival_interval_seconds": highest["arrival_interval_seconds"],
        },
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "observed_breach": 1, "inconclusive": 3}[outcome],
        "budgets": {**held.budgets, "output_limit_bytes": MAX_OUTPUT_BYTES},
        "limits": "Finite declared global load points only. "
        "All K executions, N members and K*M rows retained. "
        "Source, physical identity, time and execution independence unauthenticated. "
        "Unknown unrequired controls remain uncontrolled. "
        "No interpolation or capacity qualification.",
    }
    report["fingerprint"] = digest(report)
    _admit_receipt(report, MAX_OUTPUT_BYTES)
    return RegressionGate(report, held.protected_paths)


def assess_fleet_trace_envelope(
    saved: PlanArtifact | str | Path,
    cases: object,
    campaigns: Mapping,
    *,
    policy: object,
    candidate_index: int = 0,
) -> RegressionGate:
    from chimeraforge.api import PlanError

    try:
        return _assess(saved, cases, campaigns, policy, candidate_index)
    except (
        PlanError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        LOG.info("Fleet envelope admission refused (%s)", type(exc).__name__)
        raise PlanError("invalid fleet trace envelope input") from None
