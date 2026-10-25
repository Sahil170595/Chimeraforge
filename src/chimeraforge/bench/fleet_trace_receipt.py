"""Whole-population fleet receipts and strict receiving admission."""

from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
from pathlib import Path

from chimeraforge.bench import plan_trace, trace
from chimeraforge.bench.fleet_trace_inputs import _PreparedFleetTrace, admit_endpoints, hold_routes
from chimeraforge.bench.fleet_trace_types import (
    _admit_receipt,
    FleetTraceReplay,
    MAX_FLEET_RECEIPT_BYTES,
    TraceRoute,
)
from chimeraforge.bench.gate_inputs import held_json, sha, finite
from chimeraforge.bench.serving import safe_observation
from chimeraforge.bench.trace_gate_inputs import ENVELOPE as NATIVE_ENVELOPE, load_trace
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.bench.trace_workload import MAX_TRACE_REQUESTS
from chimeraforge.fleet_monitor_types import FleetEndpoint, MAX_CLEANUP_SECONDS, MAX_ENDPOINTS
from chimeraforge.plan_check import identity
from chimeraforge.planner.replay import digest

KIND = "chimeraforge.fleet-trace"
# One worker and generation child per row, two phase workers and one closer per
# endpoint, plus two phase controls and the replay stop/deadline controls.
MAX_OWNED_TASKS = 2 * MAX_TRACE_REQUESTS + 3 * MAX_ENDPOINTS + 4
ENVELOPE = {
    "schema_version",
    "kind",
    "created_at",
    "tool",
    "plan",
    "workload",
    "routes",
    "endpoints",
    "controls",
    "native_trace",
    "slots",
    "cleanup",
    "status",
    "configuration_status",
    "slo",
    "exit_code",
    "limits",
    "fingerprint",
}
SLOT_KEYS = {
    "id",
    "url",
    "row_indices",
    "state",
    "error",
    "serving_before",
    "serving_after",
    "binding",
    "slo",
    "execution",
    "goodput",
    "latency_evidence",
}
NATIVE_ROW = {
    "descriptor",
    "state",
    "times",
    "native",
    "error",
    "mean_tpot_ms",
    "mean_tpot_basis",
    "timing",
    "slo",
    "output_cap_state",
}
CLEANUP_KEYS = {
    "state",
    "budget_seconds",
    "allowance_exceeded",
    "resources_closed",
    "close_errors",
    "owned_backends",
    "closed_backends",
    "owned_tasks",
    "joined_tasks",
}
LIMITS = (
    "One declared original fleet and one client schedule; only output caps and client controls "
    "are applied. Metadata, URL declarations and hashes do not authenticate physical members, "
    "weights, source inputs, capacity or deployment readiness. Native stream/metadata limits "
    "are per-path, not a global HTTP-byte limit; deadlines and final cleanup are cooperative."
)


def _fail() -> None:
    from chimeraforge.api import PlanError

    raise PlanError("invalid bounded original-fleet trace receipt")


def native_projection(native: dict) -> dict:
    """Remove exactly the declared extension, never arbitrary unexpected native fields."""
    if (
        type(native) is not dict
        or set(native) != NATIVE_ENVELOPE
        or type(native["requests"]) is not list
    ):
        _fail()
    projected = copy.deepcopy(native)
    for row in projected["requests"]:
        if type(row) is not dict or set(row) != NATIVE_ROW | {"endpoint_id"}:
            _fail()
        del row["endpoint_id"]
    # This compatibility fingerprint is private validation, not origin authentication.
    projected["fingerprint"] = digest({k: v for k, v in projected.items() if k != "fingerprint"})
    return projected


def _member_view(native: dict, indices: list[int], before: dict | None, after: dict | None) -> dict:
    rows = [native["requests"][index] for index in indices]
    view = {
        "requests": rows,
        "serving_before": before,
        "serving_after": after,
        "goodput": {
            "joint_outcomes": {
                state: sum(row["slo"]["joint"] == state for row in rows)
                for state in ("pass", "breach", "unknown", "not_completed", "not_requested")
            }
        },
    }
    return view


def make_report(
    prepared: _PreparedFleetTrace, native: dict, resources: list[dict], cleanup: dict
) -> dict:
    plan = prepared.plan
    horizon = native["goodput"]["horizon_seconds"]
    complete = native["exit_code"] == 0 and cleanup["state"] == "completed"
    slots = []
    for endpoint, resource in zip(prepared.endpoints, resources):
        indices = [i for i, row in enumerate(prepared.routes) if row.endpoint_id == endpoint.id]
        view = _member_view(native, indices, resource["before"], resource["after"])
        rows = view["requests"]
        counts = {
            state: sum(row["state"] == state for row in rows)
            for state in ("completed", "failed", "partial", "cancelled", "not_started")
        }
        slot_complete = (
            all(row["state"] == "completed" for row in rows) and resource["error"] is None
        )
        qualified = sum(row["slo"]["joint"] == "pass" for row in rows)
        slots.append(
            {
                "id": endpoint.id,
                "url": endpoint.url,
                "row_indices": indices,
                "state": "error"
                if resource["error"] is not None
                else "zero_assigned"
                if not rows
                else "completed"
                if slot_complete
                else "incomplete",
                "error": resource["error"],
                "serving_before": resource["before"],
                "serving_after": resource["after"],
                "binding": plan_trace._bindings(plan, view, replica_scope="declared_member"),
                "slo": plan_trace._slo(plan, view, slot_complete),
                "execution": {
                    "planned": len(rows),
                    "attempted": sum(row["times"]["start_s"] is not None for row in rows),
                    **counts,
                },
                "goodput": {
                    "qualified_requests": qualified,
                    "horizon_seconds": horizon,
                    "requests_per_second": qualified / horizon
                    if horizon and any(value is not None for value in asdict(plan.slos).values())
                    else None,
                },
                "latency_evidence": "available"
                if any(row["timing"]["latency_ms"] is not None for row in rows)
                else "unavailable",
            }
        )
    mismatch = any(
        row["state"] == "mismatch"
        for slot in slots
        for group in (slot["binding"]["summary"], slot["binding"]["token_lengths"])
        for row in group.values()
    )
    report = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": native["created_at"],
        "tool": native["tool"],
        "plan": {
            "snapshot": copy.deepcopy(plan.data),
            "fingerprint": plan.data["fingerprint"],
            "raw_sha256": plan.plan_raw_sha256,
            "candidate_index": plan.candidate_index,
            "candidate_sha256": digest(plan.candidate),
            "identity": identity(plan.candidate),
            "served_model": plan.served_model,
            "model_override": plan.model_override,
        },
        "workload": copy.deepcopy(plan.workload),
        "routes": {**prepared.route_identity, "rows": [asdict(row) for row in prepared.routes]},
        "endpoints": [asdict(row) for row in prepared.endpoints],
        "controls": {
            "backend": plan.backend,
            "model": plan.served_model,
            "output_cap_tokens": plan.candidate["decode_tokens_per_req"],
            "concurrency": plan.concurrency,
            "request_timeout_seconds": plan.request_timeout,
            "trace_timeout_seconds": plan.trace_timeout,
            "cleanup_timeout_seconds": prepared.cleanup_timeout,
            "targets": asdict(plan.slos),
            "replica_scope": "declared_member",
            "declared_original_replicas": plan.candidate["n_agents"],
            "physical_independence": "unverified",
        },
        "native_trace": native,
        "slots": slots,
        "cleanup": cleanup,
        "status": "completed" if complete else "incomplete",
        "configuration_status": "mismatch" if mismatch else "unverified",
        "slo": plan_trace._slo(plan, native, complete),
        "exit_code": int(not complete or mismatch),
        "limits": LIMITS,
    }
    report["fingerprint"] = digest(report)
    _admit_receipt(report)
    return report


def _held_fleet_trace(
    source: FleetTraceReplay | dict | str | Path, *, limit: int = MAX_FLEET_RECEIPT_BYTES
) -> dict:
    from chimeraforge import api

    protected = source._protected_paths if isinstance(source, FleetTraceReplay) else ()
    try:
        if type(limit) is not int or not 0 < limit <= MAX_FLEET_RECEIPT_BYTES:
            _fail()
        value = source.to_dict() if isinstance(source, FleetTraceReplay) else source
        data, raw, path = held_json(value, limit)
        if (
            set(data) != ENVELOPE
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1
            or data["kind"] != KIND
            or not sha(data["fingerprint"])
            or data["fingerprint"] != digest({k: v for k, v in data.items() if k != "fingerprint"})
        ):
            _fail()
        plan = data["plan"]
        if type(plan) is not dict or set(plan) != {
            "snapshot",
            "fingerprint",
            "raw_sha256",
            "candidate_index",
            "candidate_sha256",
            "identity",
            "served_model",
            "model_override",
        }:
            _fail()
        artifact = api.artifact_from_dict(plan["snapshot"])
        selected = artifact.candidate(plan["candidate_index"])
        if plan["raw_sha256"] is not None and not sha(plan["raw_sha256"]):
            _fail()
        native = data["native_trace"]
        if native["fingerprint"] != digest({k: v for k, v in native.items() if k != "fingerprint"}):
            _fail()
        native_loaded = load_trace(native_projection(native))
        if (
            native["endpoint"] is not None
            or native["serving_before"] is not None
            or native["serving_after"] is not None
        ):
            _fail()
        controls = data["controls"]
        if type(controls) is not dict or set(controls) != {
            "backend",
            "model",
            "output_cap_tokens",
            "concurrency",
            "request_timeout_seconds",
            "trace_timeout_seconds",
            "cleanup_timeout_seconds",
            "targets",
            "replica_scope",
            "declared_original_replicas",
            "physical_independence",
        }:
            _fail()
        # Native validation admits descriptors without requiring private prompt bytes.
        # Construct only a typed validation carrier, never new traffic or reconstructed prompts.
        descriptors = [row["descriptor"] for row in native["requests"]]
        typed = tuple(
            TraceRequest(
                row["request_id"], "unavailable", row["max_output_tokens"], row["arrival_offset_s"]
            )
            for row in descriptors
        )
        if type(data["endpoints"]) is not list or len(data["endpoints"]) != selected.n_agents:
            _fail()
        endpoints = admit_endpoints(
            tuple(FleetEndpoint(**row) for row in data["endpoints"]), selected.n_agents
        )
        route_data = data["routes"]
        if type(route_data) is not dict or set(route_data) != {
            "rows",
            "canonical_sha256",
            "raw_sha256",
        }:
            _fail()
        if route_data["raw_sha256"] is not None and not sha(route_data["raw_sha256"]):
            _fail()
        if type(route_data["rows"]) is not list or len(route_data["rows"]) != len(descriptors):
            _fail()
        ordered, route_identity, _ = hold_routes(
            [TraceRoute(**row) for row in route_data["rows"]], typed, endpoints
        )
        if (
            route_identity["canonical_sha256"] != route_data["canonical_sha256"]
            or [asdict(row) for row in ordered] != route_data["rows"]
        ):
            _fail()
        if any(
            row["endpoint_id"] != route.endpoint_id
            for row, route in zip(native["requests"], ordered)
        ):
            _fail()
        expected_backend = plan_trace.BACKEND_WRAPPERS.get(selected.backend, selected.backend)
        targets = trace.TraceSLO(
            **{
                key: plan["snapshot"]["inputs"][value]
                for key, value in plan_trace.SLO_INPUTS.items()
            }
        )
        served = (
            selected.model if plan["model_override"] is None else plan["model_override"]
        ).removeprefix("ollama:")
        trace.validate_options(
            list(typed),
            served,
            expected_backend,
            native["execution"]["concurrency"],
            native["execution"]["request_timeout_seconds"],
            native["execution"]["trace_timeout_seconds"],
            targets,
            None,
        )
        if (
            native["model"] != served
            or native["backend"] != expected_backend
            or native["targets"] != asdict(targets)
        ):
            _fail()
        if (
            expected_backend not in {"ollama", "vllm", "sglang"}
            or not 0 < controls["cleanup_timeout_seconds"] <= MAX_CLEANUP_SECONDS
            or not finite(controls["cleanup_timeout_seconds"], minimum=0)
            or any(
                row["max_output_tokens"] != selected.decode_tokens_per_req for row in descriptors
            )
        ):
            _fail()
        prepared_plan = plan_trace._PreparedPlanTrace(
            artifact.to_dict(),
            asdict(selected),
            plan["candidate_index"],
            plan["raw_sha256"],
            typed,
            data["workload"],
            tuple(descriptors),
            served,
            plan["model_override"],
            expected_backend,
            None,
            native["execution"]["concurrency"],
            native["execution"]["request_timeout_seconds"],
            native["execution"]["trace_timeout_seconds"],
            targets,
            None,
            (),
        )
        prepared = _PreparedFleetTrace(
            prepared_plan,
            endpoints,
            ordered,
            {
                "canonical_sha256": route_data["canonical_sha256"],
                "raw_sha256": route_data["raw_sha256"],
            },
            controls["cleanup_timeout_seconds"],
            (),
        )
        cleanup = data["cleanup"]
        if type(cleanup) is not dict or set(cleanup) != CLEANUP_KEYS:
            _fail()
        for name in (
            "close_errors",
            "owned_backends",
            "closed_backends",
            "owned_tasks",
            "joined_tasks",
        ):
            if type(cleanup[name]) is not int or not 0 <= cleanup[name] <= MAX_OWNED_TASKS:
                _fail()
        if (
            cleanup["owned_backends"] > selected.n_agents
            or cleanup["closed_backends"] > cleanup["owned_backends"]
            or cleanup["joined_tasks"] > cleanup["owned_tasks"]
            or type(cleanup["allowance_exceeded"]) is not bool
            or type(cleanup["resources_closed"]) is not bool
            or not finite(cleanup["budget_seconds"], minimum=0)
            or cleanup["budget_seconds"] != prepared.cleanup_timeout
        ):
            _fail()
        if native["clock"]["origin"] is not None:
            minimum_tasks = (
                2 * selected.n_agents + len(descriptors) + native["execution"]["attempted"] + 3
            )
            if (
                cleanup["owned_backends"] != selected.n_agents
                or cleanup["owned_tasks"] < minimum_tasks
            ):
                _fail()
        successful_cleanup = (
            cleanup["resources_closed"]
            and not cleanup["allowance_exceeded"]
            and not cleanup["close_errors"]
            and cleanup["joined_tasks"] == cleanup["owned_tasks"]
        )
        if (
            cleanup["resources_closed"] != (cleanup["closed_backends"] == cleanup["owned_backends"])
            or cleanup["state"] != ("completed" if successful_cleanup else "incomplete")
            or native["resource_cleanup"] != {"state": cleanup["state"]}
        ):
            _fail()
        if type(data["slots"]) is not list or len(data["slots"]) != len(endpoints):
            _fail()
        resources = []
        for slot in data["slots"]:
            if type(slot) is not dict or set(slot) != SLOT_KEYS:
                _fail()
            for key in ("serving_before", "serving_after"):
                if slot[key] is not None and digest(slot[key]) != digest(
                    safe_observation(slot[key])
                ):
                    _fail()
            trace_error = slot["error"]
            if trace_error is not None:
                from chimeraforge.bench.trace_gate_inputs import _error

                _error(trace_error)
            resources.append(
                {
                    "before": slot["serving_before"],
                    "after": slot["serving_after"],
                    "error": trace_error,
                }
            )
        expected = make_report(prepared, native, resources, cleanup)
        if digest(data) != digest(expected) or data["workload"] != native["workload"]:
            _fail()
        return {
            "data": copy.deepcopy(data),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "path": path,
            "protected_paths": tuple(dict.fromkeys((*protected, *((path,) if path else ())))),
            "fingerprint": data["fingerprint"],
            "native": native_loaded,
        }
    except (
        api.PlanError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        _fail()
    raise AssertionError("unreachable")


def load_fleet_trace(source: FleetTraceReplay | dict | str | Path) -> FleetTraceReplay:
    held = _held_fleet_trace(source)
    return FleetTraceReplay(held["data"], held["protected_paths"])
