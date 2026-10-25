"""Ordered conditional regression gates over complete queue-inclusive trace populations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
from pathlib import Path
from types import SimpleNamespace

from chimeraforge.bench.gate import (
    FACTS,
    MAX_REPLICATES,
    RegressionGate,
    _cache,
    _cache_compatible,
    _condition_states,
    _fact,
)
from chimeraforge.bench.gate_inputs import (
    MAX_POLICY_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_TOTAL_BYTES,
    fail,
    finite,
)
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.serving_binding import observed_model
from chimeraforge.bench.trace import TraceReplay
from chimeraforge.bench.trace_gate_inputs import held_trace_json, load_trace
from chimeraforge.planner.replay import digest

RULES = {
    "goodput_rps": ("requests/second", "higher"),
    "latency_p95_ms": ("ms", "lower"),
    "first_output_p95_ms": ("ms", "lower"),
    "tpot_p95_ms": ("ms", "lower"),
}
P95_QUANTILE = 0.95


@dataclass(frozen=True)
class TraceGatePolicy:
    """Closed predeclared trace rules and observed conditions; no independence claim."""

    rules: dict[str, float] = field(default_factory=lambda: {"goodput_rps": 0.05})
    expected_replicates: int = 1
    pairing: str = "ordered"
    fixed_controls: dict[str, object] = field(default_factory=dict)
    baseline_treatment: dict[str, object] = field(default_factory=dict)
    candidate_treatment: dict[str, object] = field(default_factory=dict)
    require_cache_evidence: bool = True


def _known_fact(observation: dict, name: str) -> object:
    value = _fact(observation, name)
    return None if type(value) is str and (not value.strip() or "://" in value) else value


def policy_from(source: TraceGatePolicy | dict | str | Path) -> tuple[TraceGatePolicy, Path | None]:
    data, _, path = held_trace_json(
        asdict(source) if type(source) is TraceGatePolicy else source, MAX_POLICY_BYTES
    )
    if not set(data) <= set(TraceGatePolicy.__annotations__):
        fail("unknown trace policy field")
    policy = TraceGatePolicy(**data)
    if (
        type(policy.rules) is not dict
        or not policy.rules
        or not set(policy.rules) <= RULES.keys()
        or any(not finite(value, minimum=0) or value >= 1 for value in policy.rules.values())
    ):
        fail("trace rules need nonempty supported metrics and finite fractions in [0,1)")
    if (
        type(policy.expected_replicates) is not int
        or not 1 <= policy.expected_replicates <= MAX_REPLICATES
        or policy.pairing != "ordered"
        or type(policy.require_cache_evidence) is not bool
    ):
        fail("trace policy requires 1-16 ordered replicates and boolean cache policy")
    for mapping in (policy.fixed_controls, policy.baseline_treatment, policy.candidate_treatment):
        if type(mapping) is not dict or not set(mapping) <= FACTS:
            fail("trace conditions require supported observed facts")
        for name, value in mapping.items():
            observation = (
                {name: value}
                if "." not in name
                else {name.split(".")[0]: {name.split(".")[1]: value}}
            )
            expected = _known_fact(observation, name)
            if expected is None or digest(expected) != digest(value):
                fail("trace condition needs a known correctly typed expectation")
    if set(policy.baseline_treatment) != set(policy.candidate_treatment) or set(
        policy.fixed_controls
    ) & set(policy.baseline_treatment):
        fail("trace treatments require both arms and cannot overlap fixed controls")
    return policy, path


def _view(row: dict) -> dict:
    data = row["data"]
    observations = {}
    for phase in ("before", "after"):
        projected = {}
        for name in FACTS:
            value = _known_fact(data["serving_" + phase] or {}, name)
            if "." in name:
                prefix, key = name.split(".")
                projected.setdefault(prefix, {})[key] = value
            else:
                projected[name] = value
        observations["serving_" + phase] = projected
    return {
        "execution": observations,
        "samples": [
            SimpleNamespace(
                prompt_tokens=r["native"]["prompt_tokens"],
                cached_prompt_tokens=r["native"]["cached_prompt_tokens"],
            )
            for r in data["requests"]
        ],
    }


def _workload(row: dict) -> tuple[dict, list[str]]:
    data = row["data"]
    rows = data["requests"]
    lengths = [(r["native"]["prompt_tokens"], r["native"]["tokens_generated"]) for r in rows]
    blockers = []
    if any(
        prompt is None or prompt <= 0 or output is None or output <= 0 for prompt, output in lengths
    ):
        blockers.append("observed_token_lengths_unavailable")
    if any(r["output_cap_state"] == "exceeded" for r in rows):
        blockers.append("output_cap_exceeded")
    return {
        "canonical_workload_sha256": data["workload"]["canonical_sha256"],
        "ordered_descriptors_sha256": digest([r["descriptor"] for r in rows]),
        "ordered_actual_lengths_sha256": digest(lengths),
        "planned": data["execution"]["planned"],
        "concurrency": data["execution"]["concurrency"],
        "request_timeout_seconds": data["execution"]["request_timeout_seconds"],
        "trace_timeout_seconds": data["execution"]["trace_timeout_seconds"],
        "targets": data["targets"],
    }, blockers


def _evidence_real(value: int | float) -> float:
    """Canonicalize equivalent real spellings, including IEEE signed zero."""
    return 0.0 if value == 0 else float(value)


def _normalize_evidence_facts(observations: dict) -> None:
    # These supported facts accept either numeric representation; integer counters do not.
    real_facts = {
        "hardware": ("vram_gb", "bandwidth_gbps", "fp16_tflops", "tdp_watts", "interconnect_gbps"),
        "model_spec": ("params_b", "recurrent_state_bytes_per_seq"),
    }
    for observation in observations.values():
        for group, names in real_facts.items():
            for name in names:
                value = observation[group][name]
                if value is not None:
                    observation[group][name] = _evidence_real(value)


def _evidence(row: dict) -> str:
    data = row["data"]
    view = _view(row)
    workload, _ = _workload(row)
    workload.pop("canonical_workload_sha256")
    for name in ("request_timeout_seconds", "trace_timeout_seconds"):
        workload[name] = _evidence_real(workload[name])
    workload["targets"] = {
        name: _evidence_real(value) if value is not None else None
        for name, value in workload["targets"].items()
    }
    workload["ordered_descriptors_sha256"] = digest(
        [
            {
                key: _evidence_real(value) if key == "arrival_offset_s" else value
                for key, value in request["descriptor"].items()
                if key != "request_id"
            }
            for request in data["requests"]
        ]
    )
    _normalize_evidence_facts(view["execution"])
    measurements = []
    for r in data["requests"]:
        native = dict(r["native"])
        for name in (
            "throughput_tps",
            "ttft_ms",
            "total_duration_ms",
            "prompt_eval_duration_ms",
            "eval_duration_ms",
        ):
            if native[name] is not None:
                native[name] = _evidence_real(native[name])
        measurements.append(
            {
                "state": r["state"],
                "times": {
                    k: _evidence_real(v) if v is not None else None for k, v in r["times"].items()
                },
                "native": native,
                "mean_tpot_ms": _evidence_real(r["mean_tpot_ms"])
                if r["mean_tpot_ms"] is not None
                else None,
                "mean_tpot_basis": r["mean_tpot_basis"],
                "error": r["error"],
            }
        )
    return digest(
        {
            "measurements": measurements,
            "workload": workload,
            "observed_controls": view["execution"],
            "elapsed": _evidence_real(data["execution"]["elapsed_seconds"])
            if data["execution"]["elapsed_seconds"] is not None
            else None,
            "cleanup": data["resource_cleanup"],
            "error": data["error"],
            "stop_reason": data["stop_reason"],
        }
    )


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * P95_QUANTILE
    lower = int(position)
    fraction = position - lower
    return (
        ordered[lower]
        if lower == len(ordered) - 1
        else ordered[lower] * (1 - fraction) + ordered[lower + 1] * fraction
    )


def _metric(row: dict, name: str) -> tuple[float | None, str | None]:
    data = row["data"]
    rows = data["requests"]
    if any(r["state"] != "completed" for r in rows):
        return None, None
    if name == "goodput_rps":
        value = row["goodput"]["requests_per_second"]
        if row["goodput"]["qualification"] != "observed_targets" or any(
            r["slo"]["joint"] in {"unknown", "not_completed"} for r in rows
        ):
            return None, None
        return value, "qualified complete population / max(drained elapsed,last planned arrival)"
    field = {
        "latency_p95_ms": "latency_ms",
        "first_output_p95_ms": "first_output_ms",
        "tpot_p95_ms": "tpot_ms",
    }[name]
    values = [r["timing"][field] for r in rows]
    if any(v is None for v in values):
        return None, None
    bases = (
        {r["mean_tpot_basis"] for r in rows}
        if field == "tpot_ms"
        else {data["timing_bases"][field]}
    )
    if len(bases) != 1 or "unavailable" in bases:
        return None, None
    return _p95(values), next(iter(bases))


def _compare_metrics(left: dict, right: dict, rules: dict[str, float]) -> tuple[dict, list[str]]:
    """Shared native directions/fractions; eligibility stays with each caller."""
    blockers = []
    metrics = {}
    for name, threshold in rules.items():
        baseline, bb = _metric(left, name)
        candidate, cb = _metric(right, name)
        comparable = baseline is not None and candidate is not None and bb == cb and baseline > 0
        if not comparable:
            blockers.append("zero_baseline_or_metric_basis_unavailable:" + name)
        fraction = (
            (
                (baseline - candidate) / baseline
                if RULES[name][1] == "higher"
                else (candidate - baseline) / baseline
            )
            if comparable
            else None
        )
        if fraction is not None and not finite(fraction):
            comparable = False
            fraction = None
            blockers.append("derived_regression_unavailable:" + name)
        metrics[name] = {
            "baseline": baseline,
            "candidate": candidate,
            "baseline_basis": bb,
            "candidate_basis": cb,
            "unit": RULES[name][0],
            "statistic": "full-population joint goodput"
            if name == "goodput_rps"
            else "linear-interpolated p95 over every request"
            + (" of per-request mean TPOT; not every token" if name == "tpot_p95_ms" else ""),
            "regression_fraction": fraction,
            "max_regression_fraction": threshold,
            "state": "inconclusive"
            if not comparable
            else "regression"
            if fraction > threshold
            else "pass",
        }
    return metrics, blockers


def _pair(left: dict, right: dict, policy: TraceGatePolicy, index: int) -> dict:
    blockers = []
    for receipt in (left, right):
        data = receipt["data"]
        if data["exit_code"] != 0 or data["error"] is not None or data["stop_reason"] is not None:
            blockers.append("producer_execution_incomplete")
        if data["clock"]["origin"] is None:
            blockers.append("clock_origin_unavailable")
        if data["resource_cleanup"].get("state") != "completed":
            blockers.append("resource_cleanup_unverified")
        for phase in ("before", "after"):
            observed = data["serving_" + phase] or {}
            if _known_fact(observed, "backend") != data["backend"] or observed_model(
                _known_fact(observed, "model"), data["model"]
            ) != data["model"].removeprefix("ollama:"):
                blockers.append("serving_identity_unavailable_or_mismatched")
    views = [_view(r) for r in (left, right)]
    conditions, condition_blocks, unknown = _condition_states(*views, policy)
    blockers.extend(condition_blocks)
    works = []
    for r in (left, right):
        work, more = _workload(r)
        works.append(work)
        blockers.extend(more)
    if digest(works[0]) != digest(works[1]):
        blockers.append("workload_or_actual_lengths_changed")
    caches = {arm: _cache(view) for arm, view in zip(("baseline", "candidate"), views)}
    if any(c["state"] == "mismatch" for c in caches.values()):
        blockers.append("cache_contradiction")
    if policy.require_cache_evidence and any(c["state"] == "unknown" for c in caches.values()):
        blockers.append("cache_evidence_unavailable")
    cache_treatment = (
        "prefix_cache" in policy.baseline_treatment
        and policy.baseline_treatment["prefix_cache"] != policy.candidate_treatment["prefix_cache"]
    )
    if not cache_treatment and not _cache_compatible(caches["baseline"], caches["candidate"]):
        blockers.append("observed_cache_hits_changed")
    for arm, receipt in (("baseline", left), ("candidate", right)):
        caches[arm]["ordered_counts"] = [
            r["native"]["cached_prompt_tokens"] for r in receipt["data"]["requests"]
        ]
    if not cache_treatment and any(
        before is not None and after is not None and before != after
        for before, after in zip(
            caches["baseline"]["ordered_counts"], caches["candidate"]["ordered_counts"]
        )
    ):
        blockers.append("ordered_cache_hits_changed")
    mean_consumed = (
        "tpot_p95_ms" in policy.rules
        or "goodput_rps" in policy.rules
        and any(r["data"]["targets"]["tpot_ms"] is not None for r in (left, right))
    )
    if mean_consumed:
        bases = [
            {r["mean_tpot_basis"] for r in receipt["data"]["requests"]} for receipt in (left, right)
        ]
        if bases[0] != bases[1] or len(bases[0]) != 1 or "unavailable" in bases[0]:
            blockers.append("mean_timing_basis_unavailable_or_changed")
    metrics, metric_blocks = _compare_metrics(left, right, policy.rules)
    blockers.extend(metric_blocks)
    if blockers:
        for metric in metrics.values():
            metric["state"] = "inconclusive"
    return {
        "index": index,
        "blockers": sorted(set(blockers)),
        "metrics": metrics,
        "conditions": conditions,
        "workload": dict(zip(("baseline", "candidate"), works)),
        "cache": caches,
        "uncontrolled_or_unavailable_facts": unknown,
    }


def gate_traces(
    baseline_receipts: list[TraceReplay | dict | str | Path],
    candidate_receipts: list[TraceReplay | dict | str | Path],
    *,
    policy: TraceGatePolicy | dict | str | Path,
) -> RegressionGate:
    """Retain every declared receipt; incomplete evidence never yields a favorable pass."""
    chosen, policy_path = policy_from(policy)
    if any(
        type(arm) is not list or not 1 <= len(arm) <= MAX_REPLICATES
        for arm in (baseline_receipts, candidate_receipts)
    ):
        fail("trace gate arms need 1-16 declared receipts")
    arms: dict[str, list[dict]] = {"baseline": [], "candidate": []}
    held_paths: dict[Path, dict] = {}
    remaining = MAX_TOTAL_BYTES
    for arm, sources in zip(arms, (baseline_receipts, candidate_receipts)):
        for source in sources:
            path = Path(source).absolute() if isinstance(source, (str, Path)) else None
            if path is not None and path in held_paths:
                if held_paths[path]["size_bytes"] > remaining:
                    fail("trace declared receipt population exceeds 32 MiB")
                remaining -= held_paths[path]["size_bytes"]
                row = copy.deepcopy(held_paths[path])
            else:
                if remaining <= 0:
                    fail("trace gate total receipts exceed 32 MiB")
                row = load_trace(source, limit=min(MAX_RECEIPT_BYTES, remaining))
                remaining -= row["size_bytes"]
                if path is not None:
                    held_paths[path] = row
            arms[arm].append(row)
    all_rows = [r for rows in arms.values() for r in rows]
    if sum(r["size_bytes"] for r in all_rows) > MAX_TOTAL_BYTES:
        fail("trace gate total receipts exceed 32 MiB")
    for r in all_rows:
        r["evidence_sha256"] = _evidence(r)
    blockers = []
    if any(len(rows) != chosen.expected_replicates for rows in arms.values()):
        blockers.append("replicate_population")
    if len({r["evidence_sha256"] for r in all_rows}) != len(all_rows):
        blockers.append("duplicate_execution_payload")
    pairs = [
        _pair(left, right, chosen, i)
        for i, (left, right) in enumerate(zip(arms["baseline"], arms["candidate"]))
    ]
    blockers.extend(reason for p in pairs for reason in p["blockers"])
    outcome = (
        "inconclusive"
        if blockers
        else "regression"
        if any(m["state"] == "regression" for p in pairs for m in p["metrics"].values())
        else "conditional_pass"
    )
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-regression-gate",
        "created_at": now_iso(),
        "policy": asdict(chosen),
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "regression": 1, "inconclusive": 3}[outcome],
        "blockers": sorted(set(blockers)),
        "pairs": pairs,
        "inputs": {
            arm: [
                {
                    **{
                        k: r[k]
                        for k in (
                            "sha256",
                            "fingerprint",
                            "size_bytes",
                            "evidence_sha256",
                            "execution",
                        )
                    },
                    "producer": {
                        k: r["data"][k]
                        for k in ("exit_code", "error", "stop_reason", "resource_cleanup")
                    },
                    "clock_origin_observed": r["data"]["clock"]["origin"] is not None,
                }
                for r in rows
            ]
            for arm, rows in arms.items()
        },
        "assurance": {
            "source_authentication": "unverified",
            "physical_authentication": "unverified",
            "independent_executions_verified": False,
            "cold_runs": "unverified",
            "gpu_geometry": "unverified",
            "confidence_interval": "not computed",
            "cache_evidence_required": chosen.require_cache_evidence,
            "elapsed_primitive": (
                "fingerprint-bound observed drained value; not physically re-proven"
            ),
            "native_wire_coverage": (
                "original EOS/IDs/arrival coverage/coalescing not re-proven from saved rows"
            ),
            "private_prompts": "SHA-bound descriptors do not re-prove private prompt contents",
        },
        "limits": (
            "Conditional engineering decision over declared queue-inclusive populations/observed "
            "controls; unrequired unknown facts remain uncontrolled. Per-request mean TPOT is not "
            "every-token latency; no independent cold execution, GPU geometry or "
            "source/served-file authentication."
        ),
    }
    report["fingerprint"] = digest(report)
    protected = tuple(
        p
        for r in all_rows
        for p in ((r["path"],) if r["path"] is not None else ()) + r["protected_paths"]
    )
    if policy_path is not None:
        protected += (policy_path,)
    return RegressionGate(report, protected)
