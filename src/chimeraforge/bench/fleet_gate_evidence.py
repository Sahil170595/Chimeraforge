"""Native full-row evidence with member facts kept separate from global timing."""

from __future__ import annotations

import copy

from chimeraforge.bench import trace_gate
from chimeraforge.bench.fleet_gate_inputs import FleetTraceGatePolicy
from chimeraforge.bench.gate import _cache, _cache_compatible, _condition_states
from chimeraforge.bench.serving_binding import observed_model
from chimeraforge.planner.replay import digest


def member_view(data: dict, slot: dict) -> dict:
    # This is only the existing native fact/sample projection, not a child receipt.
    return trace_gate._view(
        {
            "data": {
                "serving_before": slot["serving_before"],
                "serving_after": slot["serving_after"],
                "requests": [data["native_trace"]["requests"][i] for i in slot["row_indices"]],
            }
        }
    )


def evidence(held: dict) -> str:
    data = held["data"]
    members = []
    for slot in data["slots"]:
        view = member_view(data, slot)
        trace_gate._normalize_evidence_facts(view["execution"])
        members.append(
            {
                "row_indices": slot["row_indices"],
                "observed_controls": view["execution"],
                "state": slot["state"],
                "error": slot["error"],
            }
        )
    return digest(
        {
            "global": trace_gate._evidence(held["native"]),
            "original_replicas": data["controls"]["declared_original_replicas"],
            "members": sorted(members, key=digest),
            "cleanup_timeout_seconds": trace_gate._evidence_real(
                data["controls"]["cleanup_timeout_seconds"]
            ),
        }
    )


def _member_cache(view: dict) -> dict:
    if view["samples"]:
        return _cache(view)
    return {
        "state": "unknown",
        "counts_sha256": None,
        "disabled_observed": False,
        "known_counts": [],
        "unknown_count": 0,
        "unknown_prompt_capacities": [],
        "basis": "unavailable; zero assigned requests",
    }


def compare_members(arms: dict, policy: FleetTraceGatePolicy) -> tuple[list[dict], list[str]]:
    left, right = (arms[name]["data"] for name in ("baseline", "candidate"))
    members: list[dict] = []
    blockers: list[str] = []
    for i, (before, after) in enumerate(zip(left["slots"], right["slots"])):
        local = []
        views = [member_view(data, slot) for data, slot in ((left, before), (right, after))]
        conditions, more, unknown = _condition_states(views[0], views[1], policy.trace)
        local.extend(more)
        for arm, data, slot in (("baseline", left, before), ("candidate", right, after)):
            if len(slot["row_indices"]) < policy.population["minimum_requests_per_slot"]:
                local.append(arm + ":inactive_member")
            if slot["state"] in ("error", "incomplete") or slot["error"] is not None:
                local.append(arm + ":member_execution_incomplete")
            if any(
                row["state"] == "mismatch"
                for section in ("summary", "token_lengths")
                for row in slot["binding"][section].values()
            ):
                local.append(arm + ":known_binding_mismatch")
            for phase in ("before", "after"):
                observed = slot["serving_" + phase] or {}
                if trace_gate._known_fact(observed, "backend") != data["controls"][
                    "backend"
                ] or observed_model(
                    trace_gate._known_fact(observed, "model"), data["controls"]["model"]
                ) != data["controls"]["model"].removeprefix("ollama:"):
                    local.append(arm + ":serving_identity_unavailable_or_mismatched")
        caches = {name: _member_cache(view) for name, view in zip(("baseline", "candidate"), views)}
        if any(value["state"] == "mismatch" for value in caches.values()):
            local.append("cache_contradiction")
        if policy.trace.require_cache_evidence and any(
            value["state"] == "unknown" for value in caches.values()
        ):
            local.append("cache_evidence_unavailable")
        treatment = (
            "prefix_cache" in policy.trace.baseline_treatment
            and policy.trace.baseline_treatment["prefix_cache"]
            != policy.trace.candidate_treatment["prefix_cache"]
        )
        if not treatment and not _cache_compatible(caches["baseline"], caches["candidate"]):
            local.append("observed_cache_hits_changed")
        for arm, data, slot in (("baseline", left, before), ("candidate", right, after)):
            caches[arm]["ordered_counts"] = [
                data["native_trace"]["requests"][j]["native"]["cached_prompt_tokens"]
                for j in slot["row_indices"]
            ]
        if not treatment and any(
            a is not None and b is not None and a != b
            for a, b in zip(
                caches["baseline"]["ordered_counts"], caches["candidate"]["ordered_counts"]
            )
        ):
            local.append("ordered_cache_hits_changed")
        local = sorted(set(local))
        blockers.extend(f"member:{i}:{reason}" for reason in local)
        members.append(
            {
                "index": i,
                "endpoint_id": before["id"],
                "blockers": local,
                "states": {"baseline": before["state"], "candidate": after["state"]},
                "row_indices": {
                    "baseline": before["row_indices"],
                    "candidate": after["row_indices"],
                },
                "binding": {
                    "baseline": copy.deepcopy(before["binding"]),
                    "candidate": copy.deepcopy(after["binding"]),
                },
                "slo": {"baseline": before["slo"], "candidate": after["slo"]},
                "conditions": conditions,
                "cache": caches,
                "uncontrolled_or_unavailable_facts": unknown,
            }
        )
    return members, blockers


def projection(loaded: dict) -> dict:
    data = loaded["data"]
    return {
        "sha256": loaded["sha256"],
        "size_bytes": loaded["size_bytes"],
        "raw_basis": "held file bytes"
        if loaded["path"] is not None
        else "serialized defensive snapshot bytes",
        "fingerprint": loaded["fingerprint"],
        "evidence_sha256": loaded["evidence_sha256"],
        "producer": {
            key: copy.deepcopy(data[key])
            for key in ("status", "exit_code", "configuration_status", "slo", "cleanup")
        },
        "execution": data["native_trace"]["execution"],
        "slots": copy.deepcopy(data["slots"]),
        "rows": [
            {
                "index": i,
                "request_id": row["descriptor"]["request_id"],
                "endpoint_id": row["endpoint_id"],
                "state": row["state"],
                "error": row["error"],
                "output_cap_state": row["output_cap_state"],
                "slo": row["slo"],
                "tokens": {
                    k: row["native"][k]
                    for k in ("prompt_tokens", "tokens_generated", "cached_prompt_tokens")
                },
                "mean_tpot_ms": row["mean_tpot_ms"],
                "mean_tpot_basis": row["mean_tpot_basis"],
            }
            for i, row in enumerate(data["native_trace"]["requests"])
        ],
    }
