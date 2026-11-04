"""Every ordered whole-fleet execution is compared through native eligibility/math."""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Any, cast

from chimeraforge.bench.fleet_campaign import MAX_EXECUTIONS
from chimeraforge.bench.fleet_campaign_receipt import held_campaign, hold_campaign_json
from chimeraforge.bench.fleet_campaign_types import (
    FleetTraceCampaignGate,
    FleetTraceCampaignGatePolicy,
    MAX_CAMPAIGN_BYTES,
    MAX_PAIR_BYTES,
    MAX_POLICY_BYTES,
    canonical_hash,
)
from chimeraforge.bench.fleet_gate_evidence import evidence
from chimeraforge.bench.fleet_gate_inputs import policy_from as fleet_policy_from
from chimeraforge.bench.fleet_trace_gate import _gate_held_fleets
from chimeraforge.bench.gate_inputs import fail, finite
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.trace_workload import MAX_TIMEOUT_SECONDS

KIND = "chimeraforge.fleet-trace-campaign-gate"
ARMS = ("baseline", "candidate")
LOG = logging.getLogger(__name__)
TRACE_POLICY_FIELDS = (
    "rules",
    "expected_replicates",
    "pairing",
    "fixed_controls",
    "baseline_treatment",
    "candidate_treatment",
    "require_cache_evidence",
)


def policy_data(policy: FleetTraceCampaignGatePolicy) -> dict:
    fleet = policy.fleet
    return {
        "schema_version": policy.schema_version,
        "expected_executions": policy.expected_executions,
        "campaign_timeout_seconds": policy.campaign_timeout_seconds,
        "fleet": {
            "trace": {name: getattr(fleet.trace, name) for name in TRACE_POLICY_FIELDS},
            "population": fleet.population,
            "baseline": fleet.baseline,
            "candidate": fleet.candidate,
        },
    }


def hold_policy(source: Any) -> tuple[FleetTraceCampaignGatePolicy, Path | None]:
    value = policy_data(source) if type(source) is FleetTraceCampaignGatePolicy else source
    data, _, path, _ = hold_campaign_json(value, MAX_POLICY_BYTES)
    if (
        set(data) != {"schema_version", "expected_executions", "campaign_timeout_seconds", "fleet"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or type(data["expected_executions"]) is not int
        or not 1 <= data["expected_executions"] <= MAX_EXECUTIONS
        or not finite(data["campaign_timeout_seconds"])
        or not 0 < data["campaign_timeout_seconds"] <= MAX_TIMEOUT_SECONDS
    ):
        fail("invalid complete fleet campaign policy")
    fleet, _ = fleet_policy_from(data["fleet"])
    return FleetTraceCampaignGatePolicy(
        fleet, data["expected_executions"], data["campaign_timeout_seconds"]
    ), path


def _projection(held: dict) -> dict:
    data = held["data"]
    slots = []
    for slot, child in zip(data["executions"], held["children"]):
        native = None
        if child is not None:
            receipt = child["data"]
            native = {
                "fingerprint": child["fingerprint"],
                "serialized_sha256": child["sha256"],
                "serialized_bytes": child["size_bytes"],
                "hash_basis": (
                    "canonical embedded child representation, not original child file bytes"
                ),
                "exit_code": receipt["exit_code"],
                "status": receipt["status"],
                "configuration_status": receipt["configuration_status"],
                "slo": receipt["slo"],
                "execution": receipt["native_trace"]["execution"],
                "cleanup": receipt["cleanup"],
                "slots": [
                    {
                        **{
                            key: member[key]
                            for key in (
                                "id",
                                "url",
                                "row_indices",
                                "state",
                                "error",
                                "slo",
                                "execution",
                                "goodput",
                                "latency_evidence",
                            )
                        },
                        "binding_states": {
                            group: {
                                name: row["state"] for name, row in member["binding"][group].items()
                            }
                            for group in ("summary", "token_lengths")
                        },
                        "metadata": {
                            key + "_present": member[key] is not None
                            for key in ("serving_before", "serving_after")
                        },
                    }
                    for member in receipt["slots"]
                ],
            }
        slots.append(
            {
                **{
                    key: slot[key]
                    for key in (
                        "index",
                        "state",
                        "execution_complete",
                        "reason",
                        "error",
                        "start_s",
                        "end_s",
                    )
                },
                "receipt": native,
            }
        )
    manifest = data["manifest"]
    return {
        "sha256": held["sha256"],
        "size_bytes": held["size_bytes"],
        "fingerprint": held["fingerprint"],
        "manifest_fingerprint": manifest["fingerprint"],
        "population": manifest["population"],
        "controls": manifest["controls"],
        "source": {k: v for k, v in manifest["plan"].items() if k != "snapshot"},
        "endpoints": manifest["endpoints"],
        "workload": manifest["workload"],
        "ordered_descriptors_sha256": canonical_hash(manifest["ordered_descriptors"]),
        "routes": manifest["routes"],
        **{
            key: data[key]
            for key in (
                "state",
                "exit_code",
                "execution",
                "configuration_status",
                "stop_reason",
                "cleanup",
            )
        },
        "executions": slots,
    }


def _gate_campaigns(baseline: Any, candidate: Any, *, policy: Any) -> FleetTraceCampaignGate:
    chosen, policy_path = hold_policy(policy)
    held, cache, remaining = {}, {}, MAX_PAIR_BYTES
    for arm, source in zip(ARMS, (baseline, candidate)):
        key = (
            ("path", str(Path(source).absolute()))
            if isinstance(source, (str, Path))
            else ("object", id(source))
        )
        if key not in cache:
            cache[key] = held_campaign(source, limit=min(MAX_CAMPAIGN_BYTES, remaining))
        current = cache[key]
        if current["size_bytes"] > remaining:
            fail("logical fleet campaign pair exceeds 32MiB")
        remaining -= current["size_bytes"]
        held[arm] = current
    blockers = []
    payloads = []
    for arm in ARMS:
        data = held[arm]["data"]
        if data["manifest"]["population"]["executions"] != chosen.expected_executions:
            blockers.append(arm + ":execution_population")
        if (
            data["manifest"]["controls"]["campaign_timeout_seconds"]
            != chosen.campaign_timeout_seconds
        ):
            blockers.append(arm + ":campaign_budget_commitment")
        if data["state"] != "completed" or data["stop_reason"] is not None:
            blockers.append(arm + ":campaign_execution_incomplete_or_unavailable")
        for index, child in enumerate(held[arm]["children"]):
            if child is not None:
                payloads.append({"arm": arm, "index": index, "evidence_sha256": evidence(child)})
    if len({item["evidence_sha256"] for item in payloads}) != len(payloads):
        blockers.append("duplicate_execution_payload_across_declared_population")
    pairs = []
    count = max(chosen.expected_executions, *(len(held[arm]["children"]) for arm in ARMS))
    for index in range(count):
        arms = {
            arm: held[arm]["children"][index] if index < len(held[arm]["children"]) else None
            for arm in ARMS
        }
        if all(value is not None for value in arms.values()):
            native = _gate_held_fleets(cast(dict[str, dict], arms), chosen.fleet)._data
            pair = {
                "index": index,
                "blockers": native["blockers"],
                "members": native["members"],
                "metrics": native["metrics"],
                "known_breaches": native["known_breaches"],
                "native_gate_exit_code": native["exit_code"],
                "native_receipt_present": {arm: True for arm in ARMS},
            }
        else:
            pair = {
                "index": index,
                "blockers": ["missing_native_whole_fleet_execution"],
                "members": [],
                "metrics": {
                    name: {
                        "baseline": None,
                        "candidate": None,
                        "regression_fraction": None,
                        "max_regression_fraction": threshold,
                        "state": "inconclusive",
                    }
                    for name, threshold in chosen.fleet.trace.rules.items()
                },
                "known_breaches": [],
                "native_gate_exit_code": 3,
                "native_receipt_present": {arm: arms[arm] is not None for arm in ARMS},
            }
        blockers.extend("execution-" + str(index) + ":" + reason for reason in pair["blockers"])
        pairs.append(pair)
    breaches = [
        {"index": pair["index"], "metric": name}
        for pair in pairs
        for name in pair["known_breaches"]
    ]
    outcome = "inconclusive" if blockers else "regression" if breaches else "conditional_pass"
    if blockers:
        for pair in pairs:
            for metric in pair["metrics"].values():
                metric["state"] = "inconclusive"
    data = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": now_iso(),
        "policy": policy_data(chosen),
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "regression": 1, "inconclusive": 3}[outcome],
        "blockers": sorted(set(blockers)),
        "pairs": pairs,
        "known_breaches": breaches,
        "evidence": payloads,
        "inputs": {arm: _projection(held[arm]) for arm in ARMS},
        "limits": (
            "Conditional native per-execution comparisons; all K/original N retained. "
            "No pooling, averaging, survivor selection, confidence intervals or "
            "independence/source/GPU authentication. Treat original plan intent "
            "and endpoint URLs like source inputs."
        ),
    }
    data["fingerprint"] = canonical_hash(data)
    paths = tuple(dict.fromkeys(path for arm in ARMS for path in held[arm]["protected_paths"]))
    if policy_path is not None:
        paths += (policy_path,)
    return FleetTraceCampaignGate(data, paths)


def gate_fleet_trace_campaigns(
    baseline: Any, candidate: Any, *, policy: Any
) -> FleetTraceCampaignGate:
    from chimeraforge.api import PlanError

    try:
        return _gate_campaigns(baseline, candidate, policy=policy)
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
        LOG.info("fleet campaign comparison refused (%s)", type(exc).__name__)
        raise PlanError("invalid or unavailable complete fleet campaign comparison") from None
