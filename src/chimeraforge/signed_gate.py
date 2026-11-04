"""Conditional regressions over authenticated and explicitly trusted signed public native facts."""

from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any

from chimeraforge.bench.gate import (
    RULES,
    RegressionPolicy,
    _cache,
    _cache_compatible,
    _condition_states,
    _metric,
)
from chimeraforge.bench.gate_inputs import finite
from chimeraforge.bench.metrics import now_iso
from chimeraforge import signed_contribution as signed
from chimeraforge.signed_contribution import SignedContribution, SignedContributionReceipt
from chimeraforge.signed_gate_inputs import hold
from chimeraforge.signed_payload import fail, hash_json, json_bytes, validate_payload

logger = logging.getLogger(__name__)


def _real(value: Any) -> Any:
    if type(value) in (int, float):
        numerator, denominator = (value, 1) if type(value) is int else value.as_integer_ratio()
        return {"real": [numerator, denominator]}
    if type(value) is dict:
        return {key: _real(item) for key, item in value.items()}
    if type(value) is list:
        return [_real(item) for item in value]
    return value


def _evidence(payload: dict, view: dict) -> str:
    measurement = {
        key: value
        for key, value in payload["measurement"].items()
        if key not in ("aggregate", "individual_runs")
    }
    samples = sorted((_real(asdict(row)) for row in view["samples"]), key=json_bytes)
    return hash_json(
        {
            "measurement": _real(measurement),
            "samples": samples,
            "execution": _real(payload["execution"]),
            "request": _real(payload["request"]),
            "observed_controls": _real(payload["observed_controls"]),
        }
    )


def _workload(payload: dict, view: dict) -> tuple[dict, list[str]]:
    request = payload["request"]
    lengths = [(row.prompt_tokens, row.tokens_generated) for row in view["samples"]]
    blockers = (
        ["observed_token_lengths_unavailable"]
        if any(prompt is None or prompt <= 0 or output <= 0 for prompt, output in lengths)
        else []
    )
    signature = {
        **{
            key: request[key]
            for key in (
                "prompt_sha256",
                "prompt_characters",
                "options_sha256",
                "workload",
                "concurrency",
                "arrival_rate",
                "requested_count",
                "context_length",
                "output_token_cap",
                "cap_option",
            )
        },
        "measurement_identity": {
            key: payload["measurement"][key] for key in ("model", "backend", "quant")
        },
        "actual_lengths_sha256": hash_json(
            sorted(lengths, key=lambda value: (str(value[0]), value[1]))
        ),
        "options_scope": (
            "full recorded map hash, including cap/context; "
            "stricter than cap-stripped unsigned comparison"
        ),
    }
    return signature, blockers


def _compare(left: dict, right: dict, policy: RegressionPolicy, index: int) -> dict:
    views = {"baseline": left["view"], "candidate": right["view"]}
    blockers = []
    for view in views.values():
        execution = view["execution"]
        if (
            execution["failed_count"]
            or execution["successful_count"] != execution["requested_count"]
        ):
            blockers.append("incomplete_request_population")
    conditions, condition_blocks, unknown = _condition_states(
        views["baseline"], views["candidate"], policy
    )
    blockers.extend(condition_blocks)
    workload = {}
    for arm, entry in (("baseline", left), ("candidate", right)):
        workload[arm], local = _workload(entry["payload"], entry["view"])
        blockers.extend(local)
    if workload["baseline"] != workload["candidate"]:
        blockers.append("workload_or_actual_lengths_changed")
    caches = {arm: _cache(view) for arm, view in views.items()}
    if any(cache["state"] == "mismatch" for cache in caches.values()):
        blockers.append("cache_contradiction")
    if (
        any(cache["state"] == "unknown" for cache in caches.values())
        and policy.require_cache_evidence
    ):
        blockers.append("cache_evidence_unavailable")
    treatment = (
        "prefix_cache" in policy.baseline_treatment
        and policy.baseline_treatment["prefix_cache"] != policy.candidate_treatment["prefix_cache"]
    )
    if not _cache_compatible(caches["baseline"], caches["candidate"]) and not treatment:
        blockers.append("observed_cache_hits_changed")
    metrics = {}
    for name, threshold in policy.rules.items():
        baseline, baseline_basis = _metric(views["baseline"], name)
        candidate, candidate_basis = _metric(views["candidate"], name)
        comparable = (
            baseline is not None and candidate is not None and baseline_basis == candidate_basis
        )
        if not comparable:
            blockers.append("metric_basis_or_value_unavailable:" + name)
        regression = (
            (
                ((baseline - candidate) if RULES[name][1] == "higher" else (candidate - baseline))
                / baseline
            )
            if comparable
            else None
        )
        if regression is not None and not finite(regression):
            regression = None
            blockers.append("derived_regression_unavailable:" + name)
        metrics[name] = {
            "baseline": baseline,
            "candidate": candidate,
            "baseline_basis": baseline_basis,
            "candidate_basis": candidate_basis,
            "unit": RULES[name][0],
            "statistic": "complete token sum / client workload wall"
            if name == "completed_token_rate_tps"
            else "per-replicate arithmetic mean",
            "regression_fraction": regression,
            "max_regression_fraction": threshold,
            "state": "inconclusive"
            if regression is None or blockers
            else "regression"
            if regression > threshold
            else "pass",
        }
    if blockers:
        for metric in metrics.values():
            metric["state"] = "inconclusive"
    return {
        "index": index,
        "blockers": sorted(set(blockers)),
        "metrics": metrics,
        "conditions": conditions,
        "workload": workload,
        "cache": caches,
        "uncontrolled_or_unavailable_facts": unknown,
    }


def gate_signed_contributions(
    baseline: list[SignedContribution | dict | str | Path],
    candidate: list[SignedContribution | dict | str | Path],
    *,
    trusted_keys: tuple[bytes | str | Path, ...],
    policy: RegressionPolicy | dict | str | Path,
) -> SignedContributionReceipt:
    from chimeraforge.api import PlanError

    try:
        held = hold(baseline, candidate, trusted_keys=trusted_keys, policy=policy)
        try:
            trusted, _ = signed._trusted(held.keys)
        except signed.SigningUnavailable:
            trusted = None
        verified: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
        reports: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
        for arm, entries in held.arms.items():
            for entry in entries:
                envelope = entry["envelope"]
                received = signed._verify_held(envelope, entry["paths"], trusted=trusted).to_dict()
                evidence = None
                prepared = {"exit_code": received["exit_code"]}
                if received["exit_code"] == 0:
                    payload = received["contribution"]["public_payload"]
                    view = validate_payload(payload)
                    evidence = _evidence(payload, view)
                    prepared.update(payload=payload, view=view)
                verified[arm].append(prepared)
                reports[arm].append(
                    {
                        "index": entry["index"],
                        "envelope_sha256": entry["sha256"],
                        "envelope_size_bytes": entry["size_bytes"],
                        "artifact_id": envelope["id"],
                        "payload_sha256": received["contribution"]["payload_sha256"],
                        "public_key_sha256": received["signature"]["public_key_sha256"],
                        "signature_state": received["signature"]["state"],
                        "trust_state": received["trust"]["state"],
                        "verification_status": received["status"],
                        "exit_code": received["exit_code"],
                        "evidence_sha256": evidence,
                    }
                )
        all_reports = reports["baseline"] + reports["candidate"]
        blockers = []
        if any(len(rows) != held.policy.expected_replicates for rows in reports.values()):
            blockers.append("replicate_population")
        codes = [row["exit_code"] for row in all_reports]
        if 1 in codes:
            blockers.append("authentication_failed")
        if 3 in codes:
            blockers.append("authentication_unavailable")
        evidence_ids = [
            row["evidence_sha256"] for row in all_reports if row["evidence_sha256"] is not None
        ]
        if len(evidence_ids) != len(set(evidence_ids)):
            blockers.append("duplicate_execution_payload")
        comparisons = []
        for index, (left, right) in enumerate(zip(verified["baseline"], verified["candidate"])):
            if left["exit_code"] == right["exit_code"] == 0:
                comparison = _compare(left, right, held.policy, index)
            else:
                comparison = {
                    "index": index,
                    "blockers": [
                        "authentication_failed"
                        if 1 in (left["exit_code"], right["exit_code"])
                        else "authentication_unavailable"
                    ],
                    "metrics": {},
                    "conditions": {},
                    "workload": {},
                    "cache": {},
                    "uncontrolled_or_unavailable_facts": [],
                }
            comparisons.append(comparison)
            blockers.extend(comparison["blockers"])
        regression = any(
            metric["state"] == "regression"
            for pair in comparisons
            for metric in pair["metrics"].values()
        )
        status = (
            "authentication_failed"
            if 1 in codes
            else "inconclusive"
            if blockers
            else "regression"
            if regression
            else "conditional_pass"
        )
        report = {
            "schema_version": 1,
            "kind": "chimeraforge.signed-contribution-gate",
            "created_at": now_iso(),
            "status": status,
            "exit_code": {
                "authentication_failed": 1,
                "inconclusive": 3,
                "regression": 1,
                "conditional_pass": 0,
            }[status],
            "policy": asdict(held.policy),
            **reports,
            "comparisons": comparisons,
            "blockers": sorted(set(blockers)),
            "budgets": held.budgets,
            "assurance": {
                "authenticates_producer_keys": all(code == 0 for code in codes),
                "embedded_key_is_trust": False,
                "measurement_truth": "unverified",
                "original_hardware": "unverified",
                "served_weights": "unverified",
                "original_wire_options": "unverified",
                "original_schedule_seed": "unverified",
                "independent_executions_verified": False,
                "confidence_interval": "not computed",
                "cache_evidence_required": held.policy.require_cache_evidence,
            },
            "limits": (
                "Conditional comparisons of signed public native facts and explicit receiver key "
                "trust; no private request/options are reconstructed. Full recorded options-map "
                "hash equality is stricter than cap-stripped unsigned comparison. Signatures "
                "authenticate trusted producer keys, not measurement truth, "
                "original wire defaults, "
                "schedule seeds, hardware, weights, independent runs, GPU accuracy, deployment or "
                "calibration. Semantic hashes ignore signer/source/format and sample order, retain "
                "multiplicities and public commitments, and cannot authenticate independent "
                "execution. Missing crypto leaves SDK-dependent key semantics unavailable."
            ),
        }
        report["fingerprint"] = hash_json(report)
        return SignedContributionReceipt(report, held.paths)
    except (PlanError, ValueError, OSError, TypeError, KeyError, ArithmeticError, RecursionError):
        logger.warning("signed contribution gate input rejected")
        fail("invalid signed contribution gate input")
