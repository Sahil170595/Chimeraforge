"""Private recorded-profile replay; original wire options and schedule remain unverified."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from chimeraforge.bench.backends.base import error_category
from chimeraforge.bench.gate import _cache, _cache_compatible, _condition_states, _metric, _workload
from chimeraforge.bench.metrics import result_to_dict
from chimeraforge.bench.serving import _ollama_name
from chimeraforge.signed_contribution import SignedContribution, SignedContributionReceipt, verify
from chimeraforge.signed_payload import (
    MAX_PAYLOAD_BYTES,
    METRICS,
    current_view,
    fail,
    hash_json,
    held_json,
    public_native,
    validate_payload,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Conditions:
    fixed_controls: dict[str, Any] = field(default_factory=dict)
    baseline_treatment: dict[str, Any] = field(default_factory=dict)
    candidate_treatment: dict[str, Any] = field(default_factory=dict)


def _counter(value: object, maximum: int) -> int | None:
    return value if type(value) is int and 0 <= value <= maximum else None


def _counts(
    execution: dict[str, Any], requested: int, *, precontact: bool = False
) -> dict[str, Any]:
    if precontact:
        return {
            "requested_count": requested,
            "successful_count": 0,
            "failed_count": 0,
            "attempted_count": 0,
            "not_started_count": requested,
            "count_state": "precontact_not_started",
        }
    success, failed = [
        _counter(execution.get(name), requested) for name in ("successful_count", "failed_count")
    ]
    reported = _counter(execution.get("requested_count"), requested)
    attempted = (
        success + failed
        if reported == requested
        and success is not None
        and failed is not None
        and success + failed == requested
        else None
    )
    return {
        "requested_count": requested,
        "successful_count": success,
        "failed_count": failed,
        "attempted_count": attempted,
        "not_started_count": requested - attempted if attempted is not None else None,
        "count_state": "observed" if attempted is not None else "unavailable",
    }


def _finish(data: dict[str, Any], paths: tuple[Path, ...]) -> SignedContributionReceipt:
    data.pop("fingerprint", None)
    data["fingerprint"] = hash_json(data)
    return SignedContributionReceipt(data, paths)


def _comparison_view(view: dict[str, Any]) -> dict[str, Any]:
    if view["measurement"]["backend"] != "ollama":
        return view
    result = {**view, "execution": dict(view["execution"])}
    for phase in ("serving_before", "serving_after"):
        observed = dict(view["execution"][phase])
        if observed.get("backend") == "ollama" and type(observed.get("model")) is str:
            observed["model"] = _ollama_name(observed["model"])
        result["execution"][phase] = observed
    return result


def _agreement(
    original: dict[str, Any], current: dict[str, Any]
) -> tuple[dict[str, Any], list[str], list[str]]:
    original, current = _comparison_view(original), _comparison_view(current)
    complete = all(view["execution"]["failed_count"] == 0 for view in (original, current))
    expected = {
        "backend": original["measurement"]["backend"],
        "model": original["measurement"]["model"],
        "context_length": original["measurement"]["context_length"],
    }
    if original["measurement"]["backend"] == "ollama":
        expected["model"] = _ollama_name(expected["model"])
    original_version = original["execution"]["serving_after"].get("version")
    if original_version is not None:
        expected["version"] = original_version
    conditions, _, unknown = _condition_states(original, current, _Conditions(expected))
    mismatch = ["condition:" + k for k, v in conditions.items() if v["state"] == "mismatch"]
    unavailable = [
        "condition:" + k
        for k, v in conditions.items()
        if v["required"] and v["state"] == "unavailable"
    ]
    if original_version is None:
        unavailable.append("original_version_unavailable")
    caches = {"original": _cache(original), "current": _cache(current)}
    if any(v["state"] == "mismatch" for v in caches.values()):
        mismatch.append("cache_contradiction")
    if complete and not _cache_compatible(caches["original"], caches["current"]):
        mismatch.append("cache_population_changed")
    if any(v["state"] == "unknown" for v in caches.values()):
        unavailable.append("cache_evidence_unavailable")
    works = []
    for view in (original, current):
        work, blocked = _workload(view)
        works.append(work)
        unavailable.extend(blocked)
        if view["execution"]["failed_count"]:
            unavailable.append("incomplete_native_population")
    if hash_json(works[0]) != hash_json(works[1]):
        comparable_work = [dict(work) for work in works]
        if not complete:
            for work in comparable_work:
                work.pop("actual_lengths_sha256")
        if hash_json(comparable_work[0]) != hash_json(comparable_work[1]):
            mismatch.append("recorded_workload_or_actual_lengths_changed")
    metrics = {}
    for name in METRICS:
        old, ob = _metric(original, name)
        new, nb = _metric(current, name)
        known = complete and old is not None and new is not None and ob == nb
        if not known:
            unavailable.append("metric_basis_or_value_unavailable:" + name)
        metrics[name] = {
            "original": old,
            "current": new,
            "original_basis": ob,
            "current_basis": nb,
            "raw_delta": new - old if known else None,
            "state": "descriptive_current_profile" if known else "unavailable",
        }
    return (
        {
            "conditions": conditions,
            "cache": caches,
            "metrics": metrics,
            "uncontrolled_facts": unknown,
        },
        mismatch,
        unavailable,
    )


async def replay(
    source: SignedContribution | dict | str | Path,
    private_workload: dict | str | Path,
    *,
    trusted_keys: tuple[bytes | str | Path, ...] = (),
    base_url: str | None = None,
) -> SignedContributionReceipt:
    verified = verify(source, trusted_keys=trusted_keys)
    data = verified.to_dict()
    paths = verified._protected_paths
    if isinstance(private_workload, (str, Path)):
        paths += (Path(private_workload).absolute(),)
    payload = data["contribution"]["public_payload"]
    data.update(
        kind="chimeraforge.signed-contribution-replay",
        current=None,
        comparison=None,
        error=None,
        private_binding={"state": "not_checked"},
        execution=_counts(
            {}, payload["request"]["requested_count"] if payload else 0, precontact=True
        ),
        replay_equivalence={
            "state": "current_recorded_profile_only",
            "original_wire_options": "unverified",
            "original_poisson_schedule_seed": "unverified",
            "independent_execution": "unverified",
        },
    )
    if verified.exit_code != 0:
        return _finish(data, paths)
    workload, _, held_paths = held_json(private_workload, MAX_PAYLOAD_BYTES)
    paths += held_paths
    if (
        set(workload) != {"prompt", "options"}
        or type(workload["prompt"]) is not str
        or not workload["prompt"]
        or type(workload["options"]) is not dict
    ):
        fail("private replay workload requires exactly prompt and recorded options")
    request = payload["request"]
    matched = (
        hashlib.sha256(workload["prompt"].encode()).hexdigest() == request["prompt_sha256"]
        and len(workload["prompt"]) == request["prompt_characters"]
        and hash_json(workload["options"]) == request["options_sha256"]
    )
    data["private_binding"]["state"] = "matched" if matched else "mismatch"
    if not matched:
        data.update(exit_code=1, status="private_workload_mismatch")
        return _finish(data, paths)
    if base_url is not None:
        try:
            url = urlsplit(base_url)
            if url.scheme not in ("http", "https") or not url.hostname:
                fail("replay endpoint requires HTTP(S) and a host")
            url.port
        except (ValueError, TypeError):
            fail("replay endpoint requires HTTP(S) and a host")
    original = validate_payload(payload)
    original["execution"]["request"] = {**request, "options": workload["options"]}
    if original["execution"]["failed_count"]:
        data.update(exit_code=3, status="original_population_incomplete")
        return _finish(data, paths)
    from chimeraforge.bench import runner

    expected_current = dict(original)
    expected_current["execution"] = dict(original["execution"])
    expected_options = runner.effective_adapter_options(
        payload["measurement"]["backend"], request["context_length"], workload["options"]
    )
    expected_current["execution"]["request"] = {
        **original["execution"]["request"],
        "options": expected_options,
    }
    data["current_options_expectation"] = {
        "sha256": hash_json(expected_options),
        "scope": "known current runner map preparation; original wire defaults remain unverified",
    }
    execution: dict[str, Any] = {}
    stage = "preflight_or_initialization"
    try:
        native = await runner.run_benchmark(
            model=payload["measurement"]["model"],
            backend_name=payload["measurement"]["backend"],
            quant=None,
            workload=request["workload"],
            runs=request["requested_count"],
            rate=request["arrival_rate"],
            concurrency=request["concurrency"],
            context_length=request["context_length"],
            prompt=workload["prompt"],
            options=workload["options"],
            base_url=base_url,
            _evidence=execution,
        )
        stage = "native_validation"
        measurement = result_to_dict(native)
        current = current_view(measurement, execution)
        data["current"] = public_native(current)
        agreement, mismatch, unavailable = _agreement(expected_current, current)
        data.update(
            comparison=agreement,
            blockers={"mismatch": sorted(set(mismatch)), "unavailable": sorted(set(unavailable))},
            exit_code=1 if mismatch else 3 if unavailable else 0,
            status="known_mismatch"
            if mismatch
            else "unavailable"
            if unavailable
            else "completed_recorded_profile",
        )
    except Exception as exc:
        category = error_category(exc)
        logger.warning("Signed contribution replay %s failed (%s)", stage, category)
        data.update(
            exit_code=3,
            status="replay_unavailable",
            error={"stage": "benchmark" if execution.get("request") else stage, "type": category},
        )
    data["execution"] = _counts(
        execution,
        request["requested_count"],
        precontact=not execution and stage == "preflight_or_initialization",
    )
    return _finish(data, paths)
