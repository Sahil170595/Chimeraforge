"""Whole-campaign gates preserve the declared slots and native trace decision precedence."""

from __future__ import annotations

import copy
from dataclasses import asdict
from pathlib import Path

from chimeraforge.bench.gate import RegressionGate
from chimeraforge.bench.gate_inputs import MAX_TOTAL_BYTES, fail
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.trace_campaign import TraceCampaign
from chimeraforge.bench.trace_campaign_inputs import MAX_CAMPAIGN_BYTES, load_campaign
from chimeraforge.bench.trace_gate import TraceGatePolicy, _evidence, _pair, policy_from
from chimeraforge.planner.replay import digest


def _projection(campaign: dict) -> dict:
    data = campaign["data"]
    slots = []
    for slot, native in zip(data["replicas"], campaign["replicas"]):
        summary = None
        if native is not None:
            summary = {
                **{
                    key: native[key]
                    for key in (
                        "sha256",
                        "fingerprint",
                        "size_bytes",
                        "evidence_sha256",
                        "execution",
                    )
                },
                "producer": {
                    key: native["data"][key]
                    for key in ("exit_code", "error", "stop_reason", "resource_cleanup")
                },
                "clock_origin_observed": native["data"]["clock"]["origin"] is not None,
            }
        slots.append(
            {
                **{
                    key: slot[key]
                    for key in ("index", "state", "reason", "error", "start_s", "end_s")
                },
                "receipt": summary,
            }
        )
    return {
        **{key: campaign[key] for key in ("sha256", "fingerprint", "size_bytes")},
        "manifest_fingerprint": data["manifest"]["fingerprint"],
        "population": data["manifest"]["population"],
        **{key: data[key] for key in ("execution", "state", "exit_code", "stop_reason")},
        "replicas": slots,
    }


def _workload(campaign: dict) -> dict:
    manifest = campaign["data"]["manifest"]
    return {
        "canonical_workload_sha256": manifest["workload"]["canonical_sha256"],
        "ordered_descriptors": manifest["ordered_descriptors"],
        "requests_per_replicate": manifest["population"]["requests_per_replicate"],
        "controls": {
            key: value
            for key, value in manifest["controls"].items()
            if key not in ("model", "backend", "endpoint")
        },
    }


def gate_trace_campaigns(
    baseline_campaign: TraceCampaign | dict | str | Path,
    candidate_campaign: TraceCampaign | dict | str | Path,
    *,
    policy: TraceGatePolicy | dict | str | Path,
) -> RegressionGate:
    """Compare every declared ordered slot; incomplete evidence always takes precedence."""
    chosen, policy_path = policy_from(policy)
    arms: dict[str, dict] = {}
    held: dict[Path, dict] = {}
    remaining = MAX_TOTAL_BYTES
    for arm, source in (("baseline", baseline_campaign), ("candidate", candidate_campaign)):
        path = Path(source).absolute() if isinstance(source, (str, Path)) else None
        if path is not None and path in held:
            size = held[path]["size_bytes"]
            if size > remaining:
                fail("campaign declared population exceeds total byte limit")
            remaining -= size
            loaded = copy.deepcopy(held[path])
        else:
            if remaining <= 0:
                fail("campaign population exceeds total byte limit")
            loaded = load_campaign(source, limit=min(MAX_CAMPAIGN_BYTES, remaining))
            remaining -= loaded["size_bytes"]
            if path is not None:
                held[path] = loaded
        arms[arm] = loaded
    blockers = []
    for loaded in arms.values():
        data = loaded["data"]
        if data["manifest"]["population"]["replicates"] != chosen.expected_replicates:
            blockers.append("replicate_population")
        if data["exit_code"] != 0:
            blockers.append("campaign_execution_incomplete")
    if digest(_workload(arms["baseline"])) != digest(_workload(arms["candidate"])):
        blockers.append("campaign_workload_or_controls_changed")
    native_rows = [
        native for loaded in arms.values() for native in loaded["replicas"] if native is not None
    ]
    for native in native_rows:
        native["evidence_sha256"] = _evidence(native)
    if len({native["evidence_sha256"] for native in native_rows}) != len(native_rows):
        blockers.append("duplicate_execution_payload")
    pairs: list[dict] = []
    left, right = arms["baseline"]["replicas"], arms["candidate"]["replicas"]
    for index in range(max(len(left), len(right))):
        baseline = left[index] if index < len(left) else None
        candidate = right[index] if index < len(right) else None
        if baseline is None or candidate is None:
            pairs.append(
                {
                    "index": index,
                    "blockers": ["missing_native_replica"],
                    "metrics": {},
                    "native_receipt_present": {
                        "baseline": baseline is not None,
                        "candidate": candidate is not None,
                    },
                }
            )
        else:
            pairs.append(_pair(baseline, candidate, chosen, index))
    blockers.extend(reason for pair in pairs for reason in pair["blockers"])
    known_breaches = [
        {"index": pair["index"], "metric": name}
        for pair in pairs
        for name, metric in pair["metrics"].items()
        if metric["regression_fraction"] is not None
        and metric["regression_fraction"] > metric["max_regression_fraction"]
    ]
    outcome = "inconclusive" if blockers else "regression" if known_breaches else "conditional_pass"
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-campaign-regression-gate",
        "created_at": now_iso(),
        "policy": asdict(chosen),
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "regression": 1, "inconclusive": 3}[outcome],
        "blockers": sorted(set(blockers)),
        "pairs": pairs,
        "known_breaches": known_breaches,
        "inputs": {arm: _projection(loaded) for arm, loaded in arms.items()},
        "assurance": {
            "source_authentication": "unverified",
            "physical_authentication": "unverified",
            "external_preregistration": "unverified",
            "time_authentication": "unverified",
            "independent_executions_verified": False,
            "cold_runs": "unverified",
            "gpu_geometry": "unverified",
            "confidence_interval": "not computed",
            "cache_evidence_required": chosen.require_cache_evidence,
        },
        "limits": (
            "Conditional engineering comparison over complete declared serial populations. "
            "Known breaches retain arithmetic even when incomplete evidence prevents a decision. "
            "Private prompts, wire coverage, weights, hosts, timing, external preregistration "
            "and independence are not authenticated; no survivor selection or averaging."
        ),
    }
    report["fingerprint"] = digest(report)
    protected = tuple(
        path
        for loaded in arms.values()
        for path in (
            ((loaded["path"],) if loaded["path"] is not None else ()) + loaded["protected_paths"]
        )
    )
    if policy_path is not None:
        protected += (policy_path,)
    return RegressionGate(report, protected)
