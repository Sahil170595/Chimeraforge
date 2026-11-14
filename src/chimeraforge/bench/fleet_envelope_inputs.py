"""Closed declarations and bounded native whole-fleet campaign holding."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from chimeraforge.bench import plan_trace
from chimeraforge.bench.fleet_campaign_receipt import held_campaign
from chimeraforge.bench.fleet_campaign_types import MAX_CAMPAIGN_BYTES
from chimeraforge.bench.fleet_gate_inputs import COMMON_CONTROLS, _controls
from chimeraforge.bench.fleet_trace_inputs import admit_endpoints, hold_routes
from chimeraforge.bench.fleet_trace_types import TraceRoute
from chimeraforge.bench.trace_envelope_inputs import (
    CASE_FIELDS,
    POLICY_FIELDS,
    MAX_CASES_BYTES,
    MAX_CAMPAIGN_TOTAL_BYTES,
    HeldEnvelope,
    _held,
    _closed,
    cases_from,
    policy_from,
    source_path,
    fail,
    SCHEDULE_ROUNDOFF_ULPS,
)
from chimeraforge.bench.gate_inputs import MAX_POLICY_BYTES
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.fleet_monitor_types import FleetEndpoint
from chimeraforge.planner.replay import digest
import math

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

CASE_KIND = "chimeraforge.fleet-trace-envelope-cases"
POLICY_KIND = "chimeraforge.fleet-trace-envelope-policy"
FIELDS = (CASE_FIELDS - {"expected_replicates"}) | {
    "expected_executions",
    "original_replicas",
    "endpoints",
    "routes",
    "cleanup_timeout_seconds",
    "model_override",
}


def load_inputs(
    saved: PlanArtifact | str | Path,
    cases: object,
    campaigns: Mapping,
    policy: object,
    candidate_index: int,
) -> tuple[HeldEnvelope, dict]:
    from chimeraforge.api import MAX_PLAN_BYTES, PlanArtifact
    from chimeraforge.bench.fleet_trace_types import _admit_receipt

    declared, case_receipt, case_path = _held(cases, MAX_CASES_BYTES)
    _closed(declared, FIELDS, CASE_KIND)
    serial = {key: declared[key] for key in CASE_FIELDS - {"expected_replicates"}}
    serial.update(
        kind="chimeraforge.trace-envelope-cases",
        expected_replicates=declared["expected_executions"],
    )
    cases_from(serial)
    chosen, policy_receipt, policy_path = _held(policy, MAX_POLICY_BYTES)
    _closed(chosen, POLICY_FIELDS, POLICY_KIND)
    policy_from({**chosen, "kind": "chimeraforge.trace-envelope-policy"})
    if type(candidate_index) is not int or candidate_index < 0:
        fail("invalid original candidate selection")
    if type(saved) is PlanArtifact:
        _admit_receipt(cast("PlanArtifact", saved)._data, MAX_PLAN_BYTES)
    data, raw_sha, plan_paths = plan_trace._source(saved)
    candidate = PlanArtifact(data).candidate(candidate_index)
    selected = data["result"]["candidates"][candidate_index]
    override = declared["model_override"]
    if override is not None and (type(override) is not str or not override.strip()):
        fail("invalid declared model override")
    served = (candidate.model if override is None else override).removeprefix("ollama:")
    if (
        type(declared["original_replicas"]) is not int
        or declared["original_replicas"] != candidate.n_agents
        or declared["backend"]
        != plan_trace.BACKEND_WRAPPERS.get(candidate.backend, candidate.backend)
        or declared["model"] != served
        or digest(chosen["targets"])
        != digest({name: data["inputs"][field] for name, field in plan_trace.SLO_INPUTS.items()})
    ):
        fail("fleet declaration differs from original plan selection or targets")
    count = declared["original_replicas"]
    endpoints = declared["endpoints"]
    if type(endpoints) is not list or len(endpoints) != count:
        fail("every original endpoint is required")
    admitted = admit_endpoints(tuple(FleetEndpoint(**row) for row in endpoints), count)
    requests = tuple(
        TraceRequest(row["request_id"], "unavailable", row["max_output_tokens"], 0)
        for row in declared["ordered_descriptors"]
    )
    if any(row.max_output_tokens != selected["decode_tokens_per_req"] for row in requests):
        fail("declared output caps differ from original candidate")
    if type(declared["routes"]) is not list or len(declared["routes"]) != len(requests):
        fail("every declared request needs one route")
    ordered, _, _ = hold_routes(
        [TraceRoute(**row) for row in declared["routes"]], requests, admitted
    )
    if digest(endpoints) != digest([{"id": row.id, "url": row.url} for row in admitted]) or digest(
        declared["routes"]
    ) != digest(
        [{"request_id": row.request_id, "endpoint_id": row.endpoint_id} for row in ordered]
    ):
        fail("endpoint and routing declarations must be canonical and ordered")
    controls = {
        "output_cap_tokens": selected["decode_tokens_per_req"],
        **{
            key: declared[key]
            for key in (
                "concurrency",
                "request_timeout_seconds",
                "trace_timeout_seconds",
                "cleanup_timeout_seconds",
            )
        },
        "targets": chosen["targets"],
        "replica_scope": "declared_member",
        "declared_original_replicas": count,
        "physical_independence": "unverified",
    }
    _controls(controls, count)
    expected_plan = {
        "fingerprint": data["fingerprint"],
        "raw_sha256": raw_sha,
        "candidate_index": candidate_index,
        "candidate_sha256": digest(selected),
        "served_model": served,
        "model_override": override,
    }
    loaded, cache, protected = {}, {}, list(plan_paths)
    declaration_paths = [path for path in (case_path, policy_path) if path is not None]
    if len(set(declaration_paths)) != len(declaration_paths):
        fail("declaration roles must be distinct")
    protected.extend(declaration_paths)
    if not isinstance(campaigns, Mapping) or len(campaigns) > len(declared["cells"]):
        fail("campaigns must map declared cell names")
    sources = dict(campaigns)
    if not set(sources) <= {cell["name"] for cell in declared["cells"]}:
        fail("undeclared fleet load cell")
    remaining = MAX_CAMPAIGN_TOTAL_BYTES
    for cell in declared["cells"]:
        name = cell["name"]
        if name not in sources:
            continue
        source = sources[name]
        path = source_path(source)
        if path in declaration_paths or path is not None and path in plan_paths:
            fail("campaign aliases another input role")
        if remaining <= 0:
            fail("campaign occurrences exceed aggregate byte limit")
        key = ("path", path) if path is not None else ("object", id(source))
        if key not in cache:
            cache[key] = held_campaign(source, limit=min(MAX_CAMPAIGN_BYTES, remaining))
        item = cache[key]
        if item["size_bytes"] > remaining:
            fail("campaign occurrences exceed aggregate byte limit")
        remaining -= item["size_bytes"]
        manifest = item["data"]["manifest"]
        if (
            digest({key: manifest["plan"][key] for key in expected_plan}) != digest(expected_plan)
            or digest(manifest["plan"]["snapshot"]) != digest(data)
            or digest(manifest["endpoints"]) != digest(endpoints)
            or digest(manifest["routes"]["rows"]) != digest(declared["routes"])
            or manifest["population"]["executions"] != declared["expected_executions"]
            or digest({key: manifest["controls"][key] for key in COMMON_CONTROLS})
            != digest(controls)
            or manifest["controls"]["campaign_timeout_seconds"]
            != declared["campaign_timeout_seconds"]
        ):
            fail("campaign source, population, routes or fixed controls differ from declaration")
        for ordinal, (actual, wanted) in enumerate(
            zip(manifest["ordered_descriptors"], declared["ordered_descriptors"], strict=True)
        ):
            if digest(
                {key: value for key, value in actual.items() if key != "arrival_offset_s"}
            ) != digest(wanted):
                fail("campaign ordered requests differ from declaration")
            expected = ordinal * float(cell["arrival_interval_seconds"])
            actual_time = float(actual["arrival_offset_s"])
            if abs(actual_time - expected) > SCHEDULE_ROUNDOFF_ULPS * max(
                math.ulp(actual_time), math.ulp(expected)
            ):
                fail("campaign differs from declared uniform schedule")
        loaded[name] = item
        protected.extend(item["protected_paths"])
        if item["path"] is not None:
            protected.append(item["path"])
    source = {
        key: expected_plan[key]
        for key in ("fingerprint", "raw_sha256", "candidate_index", "candidate_sha256")
    }
    source["snapshot_sha256"] = digest(data)
    source["source_kind"] = "file_bytes" if raw_sha is not None else "artifact_snapshot"
    return HeldEnvelope(
        declared,
        chosen,
        loaded,
        {
            "cases": case_receipt,
            "policy": policy_receipt,
            "campaigns": {
                str(i): {
                    key: loaded[cell["name"]][key]
                    for key in ("sha256", "size_bytes", "fingerprint")
                }
                for i, cell in enumerate(declared["cells"])
                if cell["name"] in loaded
            },
        },
        {
            "campaign_bytes": MAX_CAMPAIGN_TOTAL_BYTES - remaining,
            "campaign_limit_bytes": MAX_CAMPAIGN_TOTAL_BYTES,
            "per_campaign_limit_bytes": MAX_CAMPAIGN_BYTES,
        },
        tuple(dict.fromkeys(protected)),
    ), source
