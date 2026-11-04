"""One held complete campaign, with every native child validated after admission."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from chimeraforge.bench import plan_trace
from chimeraforge.bench.fleet_campaign import MAX_EXECUTIONS, STATES, native_complete
from chimeraforge.bench.fleet_campaign_types import (
    FleetTraceCampaign,
    FleetTraceCampaignError,
    KIND,
    MANIFEST_KIND,
    MAX_CAMPAIGN_BYTES,
    CAMPAIGN_LIMITS,
    canonical_hash,
    encoded_data,
)
from chimeraforge.bench.fleet_gate_inputs import COMMON_CONTROLS, _controls
from chimeraforge.bench.fleet_trace_inputs import admit_endpoints, hold_routes
from chimeraforge.bench.fleet_trace_receipt import _fleet_trace_from_held
from chimeraforge.bench.fleet_trace_types import TraceRoute
from chimeraforge.bench.gate_inputs import _finite_float, fail, finite, sha
from chimeraforge.bench.trace_campaign import MAX_CAMPAIGN_REQUESTS
from chimeraforge.bench.trace_campaign_inputs import _bind_clock
from chimeraforge.bench.trace_gate_inputs import validate_descriptor
from chimeraforge.bench.trace_workload import (
    MAX_TIMEOUT_SECONDS,
    MAX_TRACE_REQUESTS,
    TraceRequest,
    TraceSLO,
    validate_options,
)
from chimeraforge.fleet_monitor_types import FleetEndpoint, MAX_ENDPOINTS
from chimeraforge.plan_check import identity

LOG = logging.getLogger(__name__)
OUTER = {
    "schema_version",
    "kind",
    "created_at",
    "tool",
    "manifest",
    "executions",
    "execution",
    "clock",
    "stop_reason",
    "state",
    "configuration_status",
    "exit_code",
    "cleanup",
    "limits",
    "fingerprint",
}
MANIFEST = {
    "schema_version",
    "kind",
    "prepared_at",
    "tool",
    "plan",
    "workload",
    "ordered_descriptors",
    "endpoints",
    "routes",
    "population",
    "controls",
    "policy",
    "scope",
    "fingerprint",
}
SLOT = {
    "index",
    "manifest_fingerprint",
    "state",
    "execution_complete",
    "reason",
    "error",
    "start_s",
    "end_s",
    "receipt",
}
STOP_REASONS = {
    None,
    "caller_stop",
    "campaign_deadline",
    "first_incomplete_execution",
    "native_receipt_unavailable",
}


def _count(value: object, maximum: int, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _time(value: object) -> None:
    if type(value) is not str or not 1 <= len(value) <= 64:
        fail("invalid campaign timestamp")
    assert isinstance(value, str)
    if datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is None:
        fail("campaign timestamps require a timezone")


def _tool(value: object) -> None:
    if (
        type(value) is not dict
        or set(value) != {"name", "version"}
        or value["name"] != "chimeraforge"
        or type(value["version"]) is not str
        or not 0 < len(value["version"]) <= 128
    ):
        fail("invalid campaign producer")


def _fingerprint(data: dict, keys: set[str], kind: str) -> None:
    if (
        type(data) is not dict
        or set(data) != keys
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["kind"] != kind
        or not sha(data["fingerprint"])
        or data["fingerprint"]
        != canonical_hash({k: v for k, v in data.items() if k != "fingerprint"})
    ):
        fail("invalid closed campaign envelope or fingerprint")


def hold_campaign_json(
    source: Any, limit: int | None = None
) -> tuple[dict, bytes, Path | None, tuple[Path, ...]]:
    from chimeraforge.api import PlanError, _unique_object
    from chimeraforge.plan_bundle import _read

    limit = MAX_CAMPAIGN_BYTES if limit is None else limit
    try:
        paths = source._input_paths if type(source) is FleetTraceCampaign else ()
        path = Path(source).absolute() if isinstance(source, (str, Path)) else None
        if path is not None:
            raw = _read(path, limit)
        else:
            value = source._data if type(source) is FleetTraceCampaign else source
            if type(value) is not dict:
                fail("expected a complete campaign object or JSON file")
            raw = encoded_data(value, limit)
        if not 0 < len(raw) <= limit:
            fail("campaign exceeds its held-byte profile")
        data = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_float=_finite_float,
            parse_constant=lambda _: fail("nonfinite campaign JSON"),
        )
        if type(data) is not dict:
            fail("campaign JSON must be an object")
        # New schema1 has no legacy pretty-size exception: raw and canonical fit.
        encoded_data(data, limit)
        return data, raw, path, tuple(dict.fromkeys((*paths, *((path,) if path else ()))))
    except (
        PlanError,
        FleetTraceCampaignError,
        OSError,
        ValueError,
        TypeError,
        UnicodeError,
        RecursionError,
    ) as exc:
        LOG.info("fleet campaign receiving refused (%s)", type(exc).__name__)
        raise PlanError("invalid bounded fleet campaign JSON") from None


def validate_manifest(manifest: dict) -> None:
    from chimeraforge import api

    _fingerprint(manifest, MANIFEST, MANIFEST_KIND)
    _time(manifest["prepared_at"])
    _tool(manifest["tool"])
    plan = manifest["plan"]
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
        fail("invalid campaign plan selection")
    artifact = api.artifact_from_dict(plan["snapshot"])
    if type(plan["candidate_index"]) is not int or plan["candidate_index"] < 0:
        fail("invalid campaign selection index")
    candidate = artifact.candidate(plan["candidate_index"])
    raw_candidate = plan["snapshot"]["result"]["candidates"][plan["candidate_index"]]
    if (
        plan["fingerprint"] != plan["snapshot"]["fingerprint"]
        or plan["raw_sha256"] is not None
        and not sha(plan["raw_sha256"])
        or plan["candidate_sha256"] != canonical_hash(raw_candidate)
        or canonical_hash(plan["identity"]) != canonical_hash(identity(raw_candidate))
    ):
        fail("campaign source identity is inconsistent")
    population = manifest["population"]
    if (
        type(population) is not dict
        or set(population)
        != {"executions", "original_replicas", "requests_per_execution", "total_requests"}
        or not _count(population["executions"], MAX_EXECUTIONS, 1)
        or not _count(population["original_replicas"], MAX_ENDPOINTS, 1)
        or population["original_replicas"] != candidate.n_agents
        or not _count(population["requests_per_execution"], MAX_TRACE_REQUESTS, 1)
        or not _count(population["total_requests"], MAX_CAMPAIGN_REQUESTS, 1)
        or population["total_requests"]
        != population["executions"] * population["requests_per_execution"]
    ):
        fail("invalid whole-fleet campaign population")
    descriptors = manifest["ordered_descriptors"]
    if type(descriptors) is not list or len(descriptors) != population["requests_per_execution"]:
        fail("campaign needs its full ordered descriptor population")
    seen: set[str] = set()
    for row in descriptors:
        validate_descriptor(row, seen)
    if len({row["request_id"] for row in descriptors}) != len(descriptors):
        fail("campaign request identities must be unique")
    work = manifest["workload"]
    if (
        type(work) is not dict
        or set(work) != {"canonical_sha256", "raw_sha256"}
        or not sha(work["canonical_sha256"])
        or work["raw_sha256"] is not None
        and not sha(work["raw_sha256"])
    ):
        fail("invalid campaign workload commitment")
    endpoints = manifest["endpoints"]
    if type(endpoints) is not list or len(endpoints) != candidate.n_agents:
        fail("campaign needs every original endpoint")
    admitted = admit_endpoints(tuple(FleetEndpoint(**row) for row in endpoints), candidate.n_agents)
    if endpoints != [{"id": row.id, "url": row.url} for row in admitted]:
        fail("campaign endpoints must be canonical")
    routing = manifest["routes"]
    if type(routing) is not dict or set(routing) != {"rows", "canonical_sha256", "raw_sha256"}:
        fail("invalid campaign route commitment")
    if type(routing["rows"]) is not list or len(routing["rows"]) != len(descriptors):
        fail("campaign needs its whole ordered route population")
    typed = tuple(
        TraceRequest(
            row["request_id"], "unavailable", row["max_output_tokens"], row["arrival_offset_s"]
        )
        for row in descriptors
    )
    ordered, route_id, _ = hold_routes(
        [TraceRoute(**row) for row in routing["rows"]], typed, admitted
    )
    if (
        routing["canonical_sha256"] != route_id["canonical_sha256"]
        or routing["rows"]
        != [{"request_id": row.request_id, "endpoint_id": row.endpoint_id} for row in ordered]
        or routing["raw_sha256"] is not None
        and not sha(routing["raw_sha256"])
    ):
        fail("campaign routes differ from ordered original work")
    controls = manifest["controls"]
    if type(controls) is not dict or set(controls) != COMMON_CONTROLS | {
        "backend",
        "model",
        "campaign_timeout_seconds",
    }:
        fail("campaign needs effective controls")
    native_controls = {k: controls[k] for k in COMMON_CONTROLS}
    _controls(native_controls, candidate.n_agents)
    timeout = controls["campaign_timeout_seconds"]
    if not finite(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        fail("invalid campaign time budget")
    backend = plan_trace.BACKEND_WRAPPERS.get(candidate.backend, candidate.backend)
    served = candidate.model if plan["model_override"] is None else plan["model_override"]
    if type(served) is not str or not served or len(served) > plan_trace.MAX_NATIVE_IDENTITY_CHARS:
        fail("invalid campaign served model")
    served = served.removeprefix("ollama:")
    if any(row.max_output_tokens != raw_candidate["decode_tokens_per_req"] for row in typed):
        fail("campaign request caps differ from the selected original candidate")
    validate_options(
        list(typed),
        served,
        controls["backend"],
        controls["concurrency"],
        controls["request_timeout_seconds"],
        controls["trace_timeout_seconds"],
        TraceSLO(**controls["targets"]),
        None,
    )
    targets = {
        key: plan["snapshot"]["inputs"][value] for key, value in plan_trace.SLO_INPUTS.items()
    }
    if (
        backend not in {"ollama", "vllm", "sglang"}
        or controls["backend"] != backend
        or controls["model"] != served
        or plan["served_model"] != served
        or controls["output_cap_tokens"] != raw_candidate["decode_tokens_per_req"]
        or canonical_hash(controls["targets"]) != canonical_hash(targets)
    ):
        fail("campaign controls disagree with original source selection")
    if (
        type(manifest["policy"]) is not dict
        or canonical_hash(manifest["policy"])
        != canonical_hash(
            {
                "execution": "serial",
                "retries": 0,
                "warmup_executions": 0,
                "stop_after_first_unavailable_execution": True,
            }
        )
        or manifest["scope"]
        != (
            "Client-recorded intent; external preregistration, traffic "
            "and independence unauthenticated."
        )
    ):
        fail("invalid campaign execution policy")


def _validate_slots(data: dict, path: Path | None) -> list[dict | None]:
    manifest = data["manifest"]
    population = manifest["population"]
    slots = data["executions"]
    if type(slots) is not list or len(slots) != population["executions"]:
        fail("campaign must retain every declared execution slot")
    children: list[dict | None] = []
    previous_end, blocked = 0.0, False
    for index, slot in enumerate(slots):
        if (
            type(slot) is not dict
            or set(slot) != SLOT
            or type(slot["index"]) is not int
            or slot["index"] != index
            or slot["manifest_fingerprint"] != manifest["fingerprint"]
            or slot["state"] not in STATES
        ):
            fail("invalid campaign execution slot")
        state = slot["state"]
        if state == "not_started":
            if (
                any(
                    slot[key] is not None
                    for key in ("start_s", "end_s", "receipt", "error", "execution_complete")
                )
                or slot["reason"] != data["stop_reason"]
                or slot["reason"] is None
            ):
                fail("unstarted executions require unavailable facts and a stop reason")
            blocked = True
            children.append(None)
            continue
        if (
            blocked
            or not finite(slot["start_s"], minimum=0)
            or not finite(slot["end_s"], minimum=0)
            or slot["start_s"] >= manifest["controls"]["campaign_timeout_seconds"]
            or not previous_end
            <= slot["start_s"]
            <= slot["end_s"]
            <= data["clock"]["elapsed_seconds"]
        ):
            fail("campaign executions must be serial within the observed horizon")
        previous_end = slot["end_s"]
        if state == "failed":
            error = slot["error"]
            if (
                slot["receipt"] is not None
                or slot["execution_complete"] is not None
                or slot["reason"] != "native_receipt_unavailable"
                or type(error) is not dict
                or set(error) != {"stage", "type"}
                or error["stage"] != "native_result"
                or type(error["type"]) is not str
                or not error["type"].isidentifier()
                or len(error["type"]) > 128
            ):
                fail("missing native results must keep execution completion unknown")
            blocked = True
            children.append(None)
            continue
        child = slot["receipt"]
        if type(child) is not dict or slot["error"] is not None:
            fail("started native evidence is unavailable")
        # These are embedded serialized bytes, never an alleged original child file.
        loaded = _fleet_trace_from_held(child, encoded_data(child), None)
        if (
            canonical_hash(child["plan"]) != canonical_hash(manifest["plan"])
            or canonical_hash(child["endpoints"]) != canonical_hash(manifest["endpoints"])
            or canonical_hash(child["routes"]) != canonical_hash(manifest["routes"])
            or canonical_hash(child["workload"]) != canonical_hash(manifest["workload"])
            or canonical_hash([row["descriptor"] for row in child["native_trace"]["requests"]])
            != canonical_hash(manifest["ordered_descriptors"])
            or canonical_hash(child["controls"])
            != canonical_hash(
                {k: v for k, v in manifest["controls"].items() if k != "campaign_timeout_seconds"}
            )
        ):
            fail("native child differs from held campaign source/work/routes/controls")
        complete = native_complete(child, population["requests_per_execution"])
        if (
            type(slot["execution_complete"]) is not bool
            or slot["execution_complete"] != complete
            or state != ("completed" if complete else "incomplete")
            or slot["reason"]
            not in (
                {None, "caller_stop", "campaign_deadline"} if complete else {"native_incomplete"}
            )
            or complete
            and slot["reason"] is not None
            and slot["reason"] != data["stop_reason"]
        ):
            fail("campaign state cannot rewrite native execution completeness")
        _bind_clock(loaded["native"], data, slot)
        if not complete or slot["reason"] is not None:
            blocked = True
        children.append(loaded)
    return children


def held_campaign(source: Any, *, limit: int | None = None) -> dict:
    from chimeraforge.api import PlanError

    try:
        data, raw, path, protected = hold_campaign_json(source, limit)
        _fingerprint(data, OUTER, KIND)
        _time(data["created_at"])
        _tool(data["tool"])
        validate_manifest(data["manifest"])
        if canonical_hash(data["tool"]) != canonical_hash(data["manifest"]["tool"]):
            fail("campaign producer differs from its declared preparation")
        clock = data["clock"]
        if (
            type(clock) is not dict
            or set(clock) != {"basis", "origin", "elapsed_seconds"}
            or clock["basis"] != "client time.perf_counter monotonic offsets in seconds"
            or not finite(clock["origin"], minimum=0)
            or not finite(clock["elapsed_seconds"], minimum=0)
        ):
            fail("invalid whole-campaign clock")
        if data["stop_reason"] not in STOP_REASONS:
            fail("invalid campaign stop reason")
        children = _validate_slots(data, path)
        counts = {
            state: sum(slot["state"] == state for slot in data["executions"]) for state in STATES
        }
        expected = {"planned": len(data["executions"]), **counts}
        if (
            type(data["execution"]) is not dict
            or set(data["execution"]) != set(expected)
            or any(
                type(data["execution"][k]) is not int or data["execution"][k] != v
                for k, v in expected.items()
            )
        ):
            fail("invalid campaign execution coverage")
        complete = counts["completed"] == len(data["executions"]) and data["stop_reason"] is None
        if (
            (counts["failed"] or counts["incomplete"] or counts["not_started"])
            and data["stop_reason"] is None
            or counts["failed"]
            and data["stop_reason"]
            not in {"native_receipt_unavailable", "caller_stop", "campaign_deadline"}
            or counts["incomplete"]
            and data["stop_reason"]
            not in {"first_incomplete_execution", "caller_stop", "campaign_deadline"}
            or counts["completed"] == len(data["executions"])
            and data["stop_reason"] in {"native_receipt_unavailable", "first_incomplete_execution"}
            or data["stop_reason"] == "first_incomplete_execution"
            and counts["incomplete"] != 1
            or data["stop_reason"] == "native_receipt_unavailable"
            and counts["failed"] != 1
        ):
            fail("campaign stop reason contradicts retained native coverage")
        mismatch = any(
            child is not None and child["data"]["configuration_status"] == "mismatch"
            for child in children
        )
        if (
            data["state"] != ("completed" if complete else "incomplete")
            or data["configuration_status"] != ("mismatch" if mismatch else "unverified")
            or type(data["exit_code"]) is not int
            or data["exit_code"] != int(not complete or mismatch)
            or data["stop_reason"] is None
            and clock["elapsed_seconds"] >= data["manifest"]["controls"]["campaign_timeout_seconds"]
            or data["stop_reason"] == "campaign_deadline"
            and clock["elapsed_seconds"] < data["manifest"]["controls"]["campaign_timeout_seconds"]
        ):
            fail("campaign outcome disagrees with native coverage or budget")
        cleanup = data["cleanup"]
        started = len(data["executions"]) - counts["not_started"]
        if (
            type(cleanup) is not dict
            or set(cleanup)
            != {"state", "owned_children", "joined_children", "owned_waiters", "joined_waiters"}
            or cleanup["state"] != "completed"
            or any(type(cleanup[name]) is not int for name in cleanup if name != "state")
            or cleanup["owned_children"] != started
            or cleanup["joined_children"] != started
            or cleanup["owned_waiters"] not in {0, started}
            or cleanup["joined_waiters"] != cleanup["owned_waiters"]
        ):
            fail("campaign owned child/waiter coverage is inconsistent")
        if data["limits"] != CAMPAIGN_LIMITS:
            fail("invalid campaign scope statement")
        return {
            "data": data,
            "raw": raw,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "path": path,
            "protected_paths": protected,
            "children": children,
            "fingerprint": data["fingerprint"],
        }
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
        LOG.info("fleet campaign validation refused (%s)", type(exc).__name__)
        raise PlanError("invalid complete fleet campaign receipt") from None


def load_fleet_trace_campaign(source: Any) -> FleetTraceCampaign:
    held = held_campaign(source)
    return FleetTraceCampaign(held["data"], held["protected_paths"])
