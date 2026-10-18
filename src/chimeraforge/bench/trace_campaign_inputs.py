"""Closed held campaigns, complete populations, and unmodified native child bindings."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from chimeraforge.bench.gate_inputs import MAX_RECEIPT_BYTES, fail, finite, sha
from chimeraforge.bench.trace_campaign import (
    MAX_CAMPAIGN_REQUESTS,
    MAX_REPLICATES,
    TraceCampaign,
)
from chimeraforge.bench.trace_gate_inputs import (
    CLOCK_BASIS,
    TARGETS,
    held_trace_json,
    load_trace,
    trace_count,
    validate_descriptor,
)
from chimeraforge.bench.trace_workload import (
    MAX_CONCURRENCY,
    MAX_TIMEOUT_SECONDS,
    MAX_TRACE_REQUESTS,
)
from chimeraforge.planner.replay import digest

MAX_CAMPAIGN_BYTES = 16 * 1024 * 1024
STATES = ("completed", "incomplete", "failed", "not_started")
STOP_REASONS = ("caller_stop", "campaign_deadline", "first_incomplete_replicate")
ASSURANCES = {
    "external_preregistration",
    "time_authentication",
    "independent_cold_executions",
    "cache_independence",
    "gpu_geometry",
    "served_weights",
    "provider_termination",
}
OUTER_FIELDS = {
    "schema_version",
    "kind",
    "created_at",
    "manifest",
    "replicas",
    "execution",
    "clock",
    "stop_reason",
    "state",
    "exit_code",
    "assurance",
    "limits",
    "fingerprint",
}
MANIFEST_FIELDS = {
    "schema_version",
    "kind",
    "prepared_at",
    "tool",
    "workload",
    "ordered_descriptors",
    "population",
    "controls",
    "policy",
    "scope",
    "fingerprint",
}
REPLICA_FIELDS = {
    "index",
    "manifest_fingerprint",
    "workload_ref",
    "start_s",
    "end_s",
    "state",
    "receipt",
    "error",
    "reason",
}
DEFAULT_ENDPOINTS = {
    "ollama": "http://localhost:11434",
    "vllm": "http://localhost:8000",
    "tgi": "http://localhost:8080",
    "sglang": "http://localhost:30000",
}


def _object(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        fail("unsupported campaign object shape")
    return cast(dict, value)


def _text(value: object, limit: int, *, nonempty: bool = True) -> bool:
    return type(value) is str and len(value) <= limit and (bool(value.strip()) or not nonempty)


def _envelope(data: object, fields: set[str], kind: str) -> dict:
    data = _object(data, fields)
    if (
        type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["kind"] != kind
        or not sha(data["fingerprint"])
        or digest({k: v for k, v in data.items() if k != "fingerprint"}) != data["fingerprint"]
    ):
        fail("unsupported campaign envelope or fingerprint")
    return data


def _manifest(manifest: object) -> None:
    manifest = _envelope(manifest, MANIFEST_FIELDS, "chimeraforge.trace-campaign-manifest")
    if not _text(manifest["prepared_at"], 128) or not _text(manifest["scope"], 4096):
        fail("unsupported campaign preparation metadata")
    tool = manifest["tool"]
    _object(tool, {"name", "version"})
    if tool["name"] != "chimeraforge" or not _text(tool["version"], 128):
        fail("unsupported campaign producer tool")
    workload = manifest["workload"]
    _object(workload, {"canonical_sha256", "raw_sha256"})
    if not sha(workload["canonical_sha256"]) or (
        workload["raw_sha256"] is not None and not sha(workload["raw_sha256"])
    ):
        fail("invalid campaign workload binding")
    descriptors = manifest["ordered_descriptors"]
    if type(descriptors) is not list or not 1 <= len(descriptors) <= MAX_TRACE_REQUESTS:
        fail("campaign descriptors need a complete bounded request population")
    seen: set[str] = set()
    for descriptor in descriptors:
        validate_descriptor(descriptor, seen)
    population = manifest["population"]
    _object(population, {"replicates", "requests_per_replicate", "total_requests"})
    if (
        not trace_count(population["replicates"], MAX_REPLICATES)
        or population["replicates"] < 1
        or not trace_count(population["requests_per_replicate"])
        or population["requests_per_replicate"] != len(descriptors)
        or not trace_count(population["total_requests"], MAX_CAMPAIGN_REQUESTS)
        or population["total_requests"] != population["replicates"] * len(descriptors)
    ):
        fail("campaign population disagrees with declared descriptors")
    controls = manifest["controls"]
    _object(
        controls,
        {
            "model",
            "backend",
            "endpoint",
            "concurrency",
            "request_timeout_seconds",
            "trace_timeout_seconds",
            "campaign_timeout_seconds",
            "targets",
        },
    )
    if any(not _text(controls[name], 512) for name in ("model", "backend")):
        fail("campaign serving identity is missing")
    if controls["endpoint"] is not None and not _text(controls["endpoint"], 4096):
        fail("unsupported campaign endpoint declaration")
    if not trace_count(controls["concurrency"], MAX_CONCURRENCY) or controls["concurrency"] < 1:
        fail("invalid campaign concurrency")
    for name in ("request_timeout_seconds", "trace_timeout_seconds", "campaign_timeout_seconds"):
        if not finite(controls[name], minimum=0) or not 0 < controls[name] <= MAX_TIMEOUT_SECONDS:
            fail("invalid campaign timeout")
    if any(d["arrival_offset_s"] > controls["trace_timeout_seconds"] for d in descriptors):
        fail("campaign schedule exceeds trace timeout")
    _object(controls["targets"], set(TARGETS))
    if any(
        value is not None and (not finite(value, minimum=0) or value <= 0)
        for value in controls["targets"].values()
    ):
        fail("invalid campaign SLO targets")
    policy = manifest["policy"]
    _object(
        policy,
        {"execution", "retries", "warmup_executions", "stop_after_first_incomplete_replicate"},
    )
    if (
        policy["execution"] != "serial"
        or any(
            type(policy[name]) is not int or policy[name] != 0
            for name in ("retries", "warmup_executions")
        )
        or policy["stop_after_first_incomplete_replicate"] is not True
    ):
        fail("unsupported campaign serial execution policy")


def _completed(native: dict) -> bool:
    data = native["data"]
    return (
        data["exit_code"] == 0
        and data["error"] is None
        and data["stop_reason"] is None
        and data["resource_cleanup"].get("state") == "completed"
        and all(row["state"] == "completed" for row in data["requests"])
    )


def _bind_native(native: dict, manifest: dict) -> None:
    data, controls = native["data"], manifest["controls"]
    endpoint = data["endpoint"]
    expected = controls["endpoint"]
    default = DEFAULT_ENDPOINTS.get(controls["backend"])
    if (
        data["workload"]
        != {"canonical_sha256": manifest["workload"]["canonical_sha256"], "raw_sha256": None}
        or digest([row["descriptor"] for row in data["requests"]])
        != digest(manifest["ordered_descriptors"])
        or data["model"] != controls["model"]
        or data["backend"] != controls["backend"]
        or (endpoint != expected if expected is not None else endpoint not in (None, default))
        or any(
            data["execution"][name] != controls[name]
            for name in ("concurrency", "request_timeout_seconds", "trace_timeout_seconds")
        )
        or digest(data["targets"]) != digest(controls["targets"])
    ):
        fail("native campaign child disagrees with frozen manifest")


def _replicas(data: dict) -> list[dict | None]:
    manifest, replicas = data["manifest"], data["replicas"]
    if type(replicas) is not list or len(replicas) != manifest["population"]["replicates"]:
        fail("campaign must retain every declared replica slot")
    natives: list[dict | None] = []
    boundary, prior_end, native_boundary = False, 0.0, False
    for index, replica in enumerate(replicas):
        _object(replica, REPLICA_FIELDS)
        state, start, end = replica["state"], replica["start_s"], replica["end_s"]
        if (
            type(replica["index"]) is not int
            or replica["index"] != index
            or replica["manifest_fingerprint"] != manifest["fingerprint"]
            or replica["workload_ref"] != manifest["workload"]["canonical_sha256"]
            or type(state) is not str
            or state not in STATES
        ):
            fail("campaign replica identity/state is invalid")
        native = None
        if state == "not_started":
            if any(
                replica[name] is not None for name in ("receipt", "error", "start_s", "end_s")
            ) or (
                replica["reason"] not in STOP_REASONS or replica["reason"] != data["stop_reason"]
            ):
                fail("unstarted campaign slot contains execution evidence")
        else:
            if (
                boundary
                or not finite(start, minimum=0)
                or not finite(end, minimum=0)
                or not prior_end <= start <= end <= data["clock"]["elapsed_seconds"]
                or start >= manifest["controls"]["campaign_timeout_seconds"]
            ):
                fail("campaign serial chronology is inconsistent")
            prior_end = end
            if state == "failed":
                error = replica["error"]
                _object(error, {"stage", "type"})
                if (
                    replica["receipt"] is not None
                    or replica["reason"] != "replay_failed"
                    or error["stage"] != "campaign_replay"
                    or type(error["type"]) is not str
                    or error["type"]
                    not in {
                        "TimeoutError",
                        "HTTPError",
                        "ValueError",
                        "RuntimeError",
                        "BackendError",
                    }
                ):
                    fail("failed campaign slot needs only a categorical failure")
            else:
                if type(replica["receipt"]) is not dict or replica["error"] is not None:
                    fail("native campaign replica receipt is missing")
                native = load_trace(replica["receipt"], limit=MAX_RECEIPT_BYTES)
                _bind_native(native, manifest)
                expected_complete = _completed(native)
                if (state == "completed") is not expected_complete or replica["reason"] != (
                    None if expected_complete else "native_incomplete"
                ):
                    fail("campaign replica state contradicts native execution")
            native_boundary = native_boundary or state != "completed"
        boundary = boundary or state != "completed"
        natives.append(native)
    if (
        data["stop_reason"] == "first_incomplete_replicate"
        and not native_boundary
        or boundary
        and data["stop_reason"] is None
    ):
        fail("campaign stopping boundary is unsupported")
    return natives


def load_campaign(
    source: TraceCampaign | dict | str | Path, *, limit: int = MAX_CAMPAIGN_BYTES
) -> dict:
    """Hold a bounded snapshot once; source labels and private workload paths are never reopened."""
    from chimeraforge.api import PlanError

    snapshot: Any = source
    protected = snapshot._protected_paths if type(snapshot) is TraceCampaign else ()
    try:
        data, raw, path = held_trace_json(
            snapshot.to_dict() if type(snapshot) is TraceCampaign else snapshot,
            min(limit, MAX_CAMPAIGN_BYTES),
        )
        _envelope(data, OUTER_FIELDS, "chimeraforge.trace-campaign")
        _manifest(data["manifest"])
        if not _text(data["created_at"], 128) or not _text(data["limits"], 4096):
            fail("unsupported campaign metadata")
        _object(data["assurance"], ASSURANCES)
        if any(value != "unverified" for value in data["assurance"].values()):
            fail("campaign assurances must remain unverified")
        _object(data["clock"], {"basis", "origin", "elapsed_seconds"})
        if (
            data["clock"]["basis"] != CLOCK_BASIS
            or any(
                not finite(data["clock"][name], minimum=0) for name in ("origin", "elapsed_seconds")
            )
            or data["stop_reason"] not in (None, *STOP_REASONS)
        ):
            fail("campaign clock/stop observation is unsupported")
        natives = _replicas(data)
        expected_counts = {
            "planned": len(data["replicas"]),
            **{state: sum(row["state"] == state for row in data["replicas"]) for state in STATES},
        }
        _object(data["execution"], set(expected_counts))
        if any(
            not trace_count(data["execution"][name], MAX_REPLICATES)
            or data["execution"][name] != value
            for name, value in expected_counts.items()
        ):
            fail("campaign counts disagree with complete slot population")
        complete = expected_counts["completed"] == expected_counts["planned"]
        if (
            data["state"] != ("completed" if complete else "incomplete")
            or type(data["exit_code"]) is not int
            or data["exit_code"] != (0 if complete else 1)
            or complete
            and data["stop_reason"] == "first_incomplete_replicate"
        ):
            fail("campaign outcome disagrees with execution population")
        return {
            "data": data,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "fingerprint": data["fingerprint"],
            "path": path,
            "protected_paths": tuple(protected),
            "replicas": natives,
        }
    except (PlanError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise PlanError("invalid trace campaign input: malformed bounded campaign") from None
