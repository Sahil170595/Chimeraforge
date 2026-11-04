"""Closed fleet commitments and one held bounded receipt per whole execution."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from pathlib import Path

from chimeraforge.bench import trace_gate
from chimeraforge.bench.plan_trace import MAX_NATIVE_IDENTITY_CHARS
from chimeraforge.bench.fleet_trace_inputs import admit_endpoints
from chimeraforge.bench.fleet_trace_receipt import _held_fleet_trace
from chimeraforge.bench.fleet_trace_types import FleetTraceReplay, MAX_FLEET_RECEIPT_BYTES
from chimeraforge.bench.gate_inputs import (
    MAX_POLICY_BYTES,
    MAX_TOTAL_BYTES,
    fail,
    finite,
    held_json,
    sha,
)
from chimeraforge.bench.trace_workload import (
    MAX_CONCURRENCY,
    MAX_OUTPUT_TOKENS,
    MAX_TIMEOUT_SECONDS,
    MAX_TRACE_REQUESTS,
)
from chimeraforge.fleet_monitor_types import FleetEndpoint, MAX_CLEANUP_SECONDS, MAX_ENDPOINTS
from chimeraforge.planner.replay import digest

PLAN_FIELDS = {
    "fingerprint",
    "raw_sha256",
    "candidate_index",
    "candidate_sha256",
    "served_model",
    "model_override",
}
COMMON_CONTROLS = {
    "output_cap_tokens",
    "concurrency",
    "request_timeout_seconds",
    "trace_timeout_seconds",
    "cleanup_timeout_seconds",
    "targets",
    "replica_scope",
    "declared_original_replicas",
    "physical_independence",
}
POPULATION_FIELDS = {
    "original_replicas",
    "endpoint_ids",
    "workload_sha256",
    "ordered_descriptors_sha256",
    "routes_sha256",
    "controls",
    "minimum_requests_per_slot",
}
ARMS = ("baseline", "candidate")


@dataclass(frozen=True)
class FleetTraceGatePolicy:
    """Explicit source, population and native comparison commitments, never inferred eligibility."""

    trace: trace_gate.TraceGatePolicy
    population: dict
    baseline: dict
    candidate: dict


def _controls(value: dict, count: int) -> None:
    if type(value) is not dict or set(value) != COMMON_CONTROLS:
        fail("fleet policy needs exact common controls")
    for name, maximum in (
        ("output_cap_tokens", MAX_OUTPUT_TOKENS),
        ("concurrency", MAX_CONCURRENCY),
    ):
        if type(value[name]) is not int or not 1 <= value[name] <= maximum:
            fail("invalid fleet integer control")
    for name in ("request_timeout_seconds", "trace_timeout_seconds", "cleanup_timeout_seconds"):
        timeout_maximum = (
            MAX_CLEANUP_SECONDS if name == "cleanup_timeout_seconds" else MAX_TIMEOUT_SECONDS
        )
        if not finite(value[name], minimum=0) or not 0 < value[name] <= timeout_maximum:
            fail("invalid fleet timeout control")
    targets = value["targets"]
    if (
        type(targets) is not dict
        or set(targets) != {"latency_ms", "first_output_ms", "tpot_ms"}
        or any(v is not None and (not finite(v, minimum=0) or v <= 0) for v in targets.values())
        or value["replica_scope"] != "declared_member"
        or value["physical_independence"] != "unverified"
        or type(value["declared_original_replicas"]) is not int
        or value["declared_original_replicas"] != count
    ):
        fail("invalid fleet target/scope commitment")


def policy_from(
    source: FleetTraceGatePolicy | dict | str | Path,
) -> tuple[FleetTraceGatePolicy, Path | None]:
    raw = asdict(source) if type(source) is FleetTraceGatePolicy else source
    data, _, path = held_json(raw, MAX_POLICY_BYTES)
    if set(data) != {"trace", "population", "baseline", "candidate"}:
        fail("fleet policy needs exact trace/population/arm commitments")
    if type(data["trace"]) is not dict:
        fail("fleet trace policy must be an embedded closed object")
    chosen, _ = trace_gate.policy_from(data["trace"])
    if chosen.expected_replicates != 1:
        fail("fleet gate compares exactly one whole execution per arm")
    population = data["population"]
    if (
        type(population) is not dict
        or not POPULATION_FIELDS - {"minimum_requests_per_slot"}
        <= set(population)
        <= POPULATION_FIELDS
    ):
        fail("fleet policy needs a complete closed population commitment")
    population.setdefault("minimum_requests_per_slot", 1)
    n = population["original_replicas"]
    if (
        type(n) is not int
        or not 1 <= n <= MAX_ENDPOINTS
        or type(population["endpoint_ids"]) is not list
        or len(population["endpoint_ids"]) != n
        or type(population["minimum_requests_per_slot"]) is not int
        or not 1 <= population["minimum_requests_per_slot"] <= MAX_TRACE_REQUESTS
        or any(
            not sha(population[name])
            for name in ("workload_sha256", "ordered_descriptors_sha256", "routes_sha256")
        )
    ):
        fail("invalid fleet population commitment")
    _controls(population["controls"], n)
    for arm in ARMS:
        declared = data[arm]
        if type(declared) is not dict or set(declared) != {"plan", "backend", "endpoints"}:
            fail("fleet policy needs exact arm source and endpoints")
        plan = declared["plan"]
        if (
            type(plan) is not dict
            or set(plan) != PLAN_FIELDS
            or not sha(plan["fingerprint"])
            or not sha(plan["candidate_sha256"])
            or plan["raw_sha256"] is not None
            and not sha(plan["raw_sha256"])
            or type(plan["candidate_index"]) is not int
            or plan["candidate_index"] < 0
            or type(plan["served_model"]) is not str
            or not 0 < len(plan["served_model"].strip()) <= MAX_NATIVE_IDENTITY_CHARS
            or plan["model_override"] is not None
            and (
                type(plan["model_override"]) is not str
                or not 0 < len(plan["model_override"].strip()) <= MAX_NATIVE_IDENTITY_CHARS
            )
            or type(declared["backend"]) is not str
            or declared["backend"] not in {"ollama", "vllm", "sglang"}
            or type(declared["endpoints"]) is not list
            or len(declared["endpoints"]) != n
        ):
            fail("invalid fleet arm source commitment")
        try:
            endpoints = admit_endpoints(
                tuple(FleetEndpoint(**row) for row in declared["endpoints"]), n
            )
        except (ValueError, TypeError, KeyError):
            fail("invalid fleet endpoint commitment")
        if [row.id for row in endpoints] != population["endpoint_ids"] or digest(
            [asdict(row) for row in endpoints]
        ) != digest(declared["endpoints"]):
            fail("fleet endpoints must be canonical and follow the exact committed ID order")
    return FleetTraceGatePolicy(chosen, population, data["baseline"], data["candidate"]), path


def hold_pair(
    baseline: FleetTraceReplay | dict | str | Path, candidate: FleetTraceReplay | dict | str | Path
) -> dict[str, dict]:
    arms: dict[str, dict] = {}
    held: dict[Path, dict] = {}
    remaining = MAX_TOTAL_BYTES
    for arm, source in zip(ARMS, (baseline, candidate)):
        path = Path(source).absolute() if isinstance(source, (str, Path)) else None
        if path is not None and path in held:
            loaded = copy.deepcopy(held[path])
            if loaded["size_bytes"] > remaining:
                fail("fleet declared receipt pair exceeds 32 MiB")
        else:
            if remaining <= 0:
                fail("fleet declared receipt pair exceeds 32 MiB")
            loaded = _held_fleet_trace(source, limit=min(MAX_FLEET_RECEIPT_BYTES, remaining))
            if path is not None:
                held[path] = loaded
        remaining -= loaded["size_bytes"]
        arms[arm] = loaded
    return arms
