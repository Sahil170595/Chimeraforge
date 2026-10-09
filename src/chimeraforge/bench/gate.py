"""Explicit engineering regression policies over complete observed benchmark pairs."""

from __future__ import annotations

import copy
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from chimeraforge.bench.gate_inputs import (
    MAX_POLICY_BYTES,
    MAX_TOTAL_BYTES,
    WALL_BASIS,
    fail,
    finite,
    held_json,
    load_receipt,
)
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.serving import safe_observation
from chimeraforge.bench.serving_binding import (
    GEOMETRY_FIELDS,
    PHYSICAL_HARDWARE_FIELDS,
    _geometry,
    _physical,
)
from chimeraforge.planner.replay import digest

MAX_REPLICATES = 16
RULES = {
    "completed_token_rate_tps": ("tokens/second", "higher"),
    "decode_tps": ("tokens/second", "higher"),
    "ttft_ms": ("ms", "lower"),
    "request_duration_ms": ("ms", "lower"),
}
INTEGER_FACTS = {
    "context_length",
    "tensor_parallel",
    "pipeline_parallel",
    "replicas",
    "serving_data_parallel_size",
}
FACTS = {
    "backend",
    "version",
    "model",
    "model_digest",
    "quant",
    "device",
    "prefix_cache",
    "configuration_sha256",
    "weight_version_label",
    "execution_engine",
} | INTEGER_FACTS
FACTS |= {f"hardware.{name}" for name in PHYSICAL_HARDWARE_FIELDS}
FACTS |= {f"model_spec.{name}" for name in GEOMETRY_FIELDS}


@dataclass(frozen=True)
class RegressionPolicy:
    """Predeclared rules and observed conditions; ordered pairs are not proven independent."""

    rules: dict[str, float] = field(default_factory=lambda: {"completed_token_rate_tps": 0.05})
    expected_replicates: int = 1
    pairing: str = "ordered"
    fixed_controls: dict = field(default_factory=dict)
    baseline_treatment: dict = field(default_factory=dict)
    candidate_treatment: dict = field(default_factory=dict)
    require_cache_evidence: bool = True


def _fact(observed: dict, name: str) -> object:
    if "." in name:
        root, key = name.split(".")
        projected = (_physical if root == "hardware" else _geometry)(observed.get(root))
        value = projected.get(key) if projected else None
        if value is None:
            return None
        if root == "model_spec":
            if key in ("parallel_hybrid", "recurrent_state_dtype_declared"):
                return value if type(value) is bool else None
            if key == "recurrent_kind":
                return value if type(value) is str else None
            if key in ("params_b", "recurrent_state_bytes_per_seq"):
                return value if finite(value, minimum=0) else None
            return value if type(value) is int and value >= 0 else None
        return value if type(value) in (str, bool) or finite(value, minimum=0) else None
    value = observed.get(name)
    if name == "prefix_cache":
        return value if type(value) is bool else None
    if name in INTEGER_FACTS:
        return value if type(value) is int and value > 0 else None
    return value if type(value) is str and 0 < len(value) <= 512 else None


def policy_from(
    source: RegressionPolicy | dict | str | Path,
) -> tuple[RegressionPolicy, Path | None]:
    raw = asdict(source) if type(source) is RegressionPolicy else source
    data, _, path = held_json(raw, MAX_POLICY_BYTES)
    if not set(data) <= set(RegressionPolicy.__annotations__):
        fail("unknown policy field")
    policy = RegressionPolicy(**data)
    if (
        type(policy.rules) is not dict
        or not policy.rules
        or not set(policy.rules) <= RULES.keys()
        or any(not finite(value, minimum=0) or value >= 1 for value in policy.rules.values())
    ):
        fail("rules need named metrics and finite regression fractions in [0,1)")
    if (
        type(policy.expected_replicates) is not int
        or not 1 <= policy.expected_replicates <= MAX_REPLICATES
    ):
        fail("expected_replicates must be 1-16")
    if policy.pairing != "ordered" or type(policy.require_cache_evidence) is not bool:
        fail("only ordered pairing and a boolean cache policy are supported")
    for mapping in (policy.fixed_controls, policy.baseline_treatment, policy.candidate_treatment):
        if type(mapping) is not dict or not set(mapping) <= FACTS:
            fail("conditions must use supported observed facts")
        for name, value in mapping.items():
            observation = (
                {name: value}
                if "." not in name
                else {name.split(".")[0]: {name.split(".")[1]: value}}
            )
            expected_fact = _fact(observation, name)
            if (
                expected_fact is None
                or expected_fact != value
                or type(expected_fact) is bool
                and type(value) is not bool
            ):
                fail("condition expectation must be a known correctly typed fact")
    if set(policy.baseline_treatment) != set(policy.candidate_treatment) or set(
        policy.fixed_controls
    ) & set(policy.baseline_treatment):
        fail("treatments need both arm expectations and cannot overlap fixed controls")
    return policy, path


def _observations(receipt: dict) -> tuple[dict, dict]:
    execution = receipt["execution"]
    return tuple(safe_observation(execution[key]) for key in ("serving_before", "serving_after"))


def _condition_states(
    left: dict, right: dict, policy: RegressionPolicy
) -> tuple[dict, list[str], list[str]]:
    phases = {"baseline": _observations(left), "candidate": _observations(right)}
    states, blockers, unknown = {}, [], []
    treatment_names = set(policy.baseline_treatment)
    for name in sorted(FACTS):
        values = {arm: [_fact(row, name) for row in rows] for arm, rows in phases.items()}
        required = name in policy.fixed_controls or name in treatment_names
        expected = {
            arm: policy.fixed_controls.get(name)
            if name not in treatment_names
            else getattr(policy, arm + "_treatment")[name]
            for arm in phases
        }
        unavailable = any(value is None for arm_values in values.values() for value in arm_values)
        drift = any(
            all(value is not None for value in arm_values) and arm_values[0] != arm_values[1]
            for arm_values in values.values()
        )
        cross_changed = (
            any(
                left is not None and right is not None and left != right
                for left in values["baseline"]
                for right in values["candidate"]
            )
            and name not in treatment_names
        )
        contradiction = required and any(
            value is not None and value != expected[arm]
            for arm, rows in values.items()
            for value in rows
        )
        state = (
            "mismatch"
            if drift or cross_changed or contradiction
            else "unavailable"
            if unavailable
            else "matched"
        )
        if state == "mismatch" or required and state == "unavailable":
            blockers.append("condition:" + name)
        if state == "unavailable":
            unknown.append(name)
        # Only explicitly supported facts are exposed; raw metadata/warnings never propagate.
        states[name] = {
            "state": state,
            "required": required,
            "treatment": name in treatment_names,
            "observed": values,
            "expected": expected if required else None,
            "scope": "serving engine; not fleet inventory"
            if name == "serving_data_parallel_size"
            else "observed metadata; not source authentication",
        }
    return states, blockers, unknown


def _workload(receipt: dict) -> tuple[dict, list[str]]:
    request = receipt["execution"]["request"]
    options = copy.deepcopy(request["options"])
    caps = [
        options.pop(key)
        for key in ("num_predict", "max_tokens", "max_new_tokens")
        if key in options
    ]
    blockers = []
    if len(caps) != 1 or type(caps[0]) is not int or caps[0] <= 0:
        blockers.append("output_cap_unavailable")
    rows = receipt["samples"]
    lengths = [(row.prompt_tokens, row.tokens_generated) for row in rows]
    if any(prompt is None or prompt <= 0 or output <= 0 for prompt, output in lengths):
        blockers.append("observed_token_lengths_unavailable")
    if caps and type(caps[0]) is int and any(row.tokens_generated > caps[0] for row in rows):
        fail("observed output exceeds the applied output cap")
    signature = {
        "prompt_sha256": request["prompt_sha256"],
        "profile": request["workload"],
        "concurrency": request["concurrency"],
        "arrival_rate": request.get("arrival_rate"),
        "output_cap": caps[0] if len(caps) == 1 else None,
        "options_sha256": digest(options),
        "requested_count": request["requested_count"],
        "actual_lengths_sha256": digest(sorted(lengths, key=lambda pair: (str(pair[0]), pair[1]))),
    }
    return signature, blockers


def _cache(receipt: dict) -> dict:
    before, after = _observations(receipt)
    counts = [row.cached_prompt_tokens for row in receipt["samples"]]
    known = all(value is not None for value in counts)
    disabled = before.get("prefix_cache") is False and after.get("prefix_cache") is False
    # A disabled-cache observation cannot make a contradictory positive count disappear.
    contradiction = disabled and any(value is not None and value > 0 for value in counts)
    return {
        "state": "mismatch" if contradiction else "known" if known or disabled else "unknown",
        "counts_sha256": digest(sorted(counts)) if known else None,
        "disabled_observed": disabled,
        "basis": "observed per-request cached tokens"
        if known
        else "observed disabled prefix cache"
        if disabled
        else "unavailable; not assumed cold",
    }


def _metric(receipt: dict, name: str) -> tuple[float | None, str | None]:
    rows, execution = receipt["samples"], receipt["execution"]
    if name == "completed_token_rate_tps":
        elapsed = execution["elapsed_seconds"]
        if (
            elapsed <= 0
            or execution.get("elapsed_seconds_basis") != WALL_BASIS
            or any(row.tokens_generated <= 0 for row in rows)
        ):
            return None, None
        value = sum(row.tokens_generated for row in rows) / elapsed
        return (value, WALL_BASIS) if finite(value, minimum=0) else (None, None)
    before, after = _observations(receipt)
    engine = after.get("backend")
    bases = {row.ttft_basis for row in rows}
    if before.get("backend") != engine or len(bases) != 1:
        return None, None
    basis = next(iter(bases))
    supported = (
        (engine == "ollama" and basis == "server-prefill-duration")
        or engine in ("vllm", "tgi", "sglang")
        and basis == "client-stream-first-content"
    )
    if not supported:
        return None, None
    if name == "decode_tps":
        if any(
            row.eval_duration_ms <= 0 or row.tokens_generated <= (0 if engine == "ollama" else 1)
            for row in rows
        ):
            return None, None
        values = [
            1000 * (row.tokens_generated - (0 if engine == "ollama" else 1)) / row.eval_duration_ms
            for row in rows
        ]
        import math

        if any(
            not math.isclose(value, row.throughput_tps, rel_tol=1e-12, abs_tol=1e-12)
            for value, row in zip(values, rows)
        ):
            fail("stored native decode rate disagrees with counts/duration/basis")
        basis = (
            "server-all-output/decode-duration"
            if engine == "ollama"
            else "client-output-minus-first/stream-decode-interval"
        )
    elif name == "ttft_ms":
        values = [row.ttft_ms for row in rows]
    else:
        values = [row.total_duration_ms for row in rows]
        basis = (
            "server-total-duration"
            if engine == "ollama"
            else "adapter-client-call-duration; client queue excluded"
        )
    if any(value <= 0 for value in values):
        return None, None
    value = statistics.mean(values)
    return (value, basis) if finite(value, minimum=0) else (None, None)


def _pair(left: dict, right: dict, policy: RegressionPolicy, index: int) -> dict:
    blockers = []
    if left["legacy"] or right["legacy"]:
        return {
            "index": index,
            "blockers": ["legacy_evidence_unavailable"],
            "metrics": {},
            "conditions": {},
        }
    for row in (left, right):
        if (
            row["execution"]["failed_count"]
            or row["execution"]["successful_count"] != row["execution"]["requested_count"]
        ):
            blockers.append("incomplete_request_population")
    conditions, condition_blocks, unknown = _condition_states(left, right, policy)
    blockers.extend(condition_blocks)
    left_work, left_blocks = _workload(left)
    right_work, right_blocks = _workload(right)
    blockers.extend(left_blocks + right_blocks)
    if left_work != right_work:
        blockers.append("workload_or_actual_lengths_changed")
    caches = {arm: _cache(row) for arm, row in (("baseline", left), ("candidate", right))}
    if any(row["state"] == "mismatch" for row in caches.values()):
        blockers.append("cache_contradiction")
    if any(row["state"] == "unknown" for row in caches.values()) and policy.require_cache_evidence:
        blockers.append("cache_evidence_unavailable")
    known_counts = [row["counts_sha256"] for row in caches.values()]
    if (
        all(value is not None for value in known_counts)
        and known_counts[0] != known_counts[1]
        and "prefix_cache" not in policy.baseline_treatment
    ):
        blockers.append("observed_cache_hits_changed")
    metrics = {}
    for name, threshold in policy.rules.items():
        baseline, baseline_basis = _metric(left, name)
        candidate, candidate_basis = _metric(right, name)
        comparable = (
            baseline is not None and candidate is not None and baseline_basis == candidate_basis
        )
        if not comparable:
            blockers.append("metric_basis_or_value_unavailable:" + name)
        direction = RULES[name][1]
        regression = (
            (
                (baseline - candidate) / baseline
                if direction == "higher"
                else (candidate - baseline) / baseline
            )
            if comparable
            else None
        )
        if regression is not None and not finite(regression):
            comparable = False
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
            if not comparable
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
        "workload": {"baseline": left_work, "candidate": right_work},
        "cache": caches,
        "uncontrolled_or_unavailable_facts": unknown,
    }


@dataclass(frozen=True)
class RegressionGate:
    """Defensive, atomic engineering decision receipt with protected consumed inputs."""

    _data: dict = field(repr=False)
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact
        from chimeraforge.plan_study import protect_output

        protect_output(path, self._protected_paths)
        PlanArtifact(self.to_dict()).save(path)


def gate_benchmarks(
    baseline_receipts: list,
    candidate_receipts: list,
    *,
    policy: RegressionPolicy | dict | str | Path,
) -> RegressionGate:
    """Compare every declared ordered pair; unknown required evidence refuses a pass."""
    chosen, policy_path = policy_from(policy)
    for arm in (baseline_receipts, candidate_receipts):
        if type(arm) is not list or not 1 <= len(arm) <= MAX_REPLICATES:
            fail("each arm needs 1-16 declared receipts")
    arms = {
        "baseline": [load_receipt(row) for row in baseline_receipts],
        "candidate": [load_receipt(row) for row in candidate_receipts],
    }
    all_rows = [row for rows in arms.values() for row in rows]
    if sum(row["size_bytes"] for row in all_rows) > MAX_TOTAL_BYTES:
        fail("total receipt bytes exceed 32 MiB")
    blockers = []
    if any(len(rows) != chosen.expected_replicates for rows in arms.values()):
        blockers.append("replicate_population")
    evidence_ids = [row["evidence_sha256"] for row in all_rows]
    if len(set(evidence_ids)) != len(evidence_ids):
        blockers.append("duplicate_execution_payload")
    # Unpaired declared receipts are consumed and retained; they cannot quietly disappear.
    pairs = [
        _pair(left, right, chosen, index)
        for index, (left, right) in enumerate(zip(arms["baseline"], arms["candidate"]))
    ]
    blockers.extend(reason for pair in pairs for reason in pair["blockers"])
    if any(row["legacy"] for row in all_rows):
        blockers.append("legacy_evidence_unavailable")
    regression = any(
        metric["state"] == "regression" for pair in pairs for metric in pair["metrics"].values()
    )
    outcome = "inconclusive" if blockers else "regression" if regression else "conditional_pass"
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.regression-gate",
        "created_at": now_iso(),
        "policy": asdict(chosen),
        "outcome": outcome,
        "exit_code": {"conditional_pass": 0, "regression": 1, "inconclusive": 3}[outcome],
        "blockers": sorted(set(blockers)),
        "pairs": pairs,
        "inputs": {
            arm: [
                {
                    key: row[key]
                    for key in ("sha256", "fingerprint", "size_bytes", "evidence_sha256", "legacy")
                }
                for row in rows
            ]
            for arm, rows in arms.items()
        },
        "assurance": {
            "source_authentication": "unverified",
            "independent_executions_verified": False,
            "confidence_interval": "not computed",
            "cold_runs": "unverified",
            "cache_evidence_required": chosen.require_cache_evidence,
        },
        "limits": (
            "Conditional engineering decision for declared observed controls and workload; "
            "unrequired unknown facts remain uncontrolled. No statistical confidence, "
            "independent cold execution, GPU accuracy, served-weight authentication "
            "or queue-inclusive SLO qualification."
        ),
    }
    report["fingerprint"] = digest(report)
    protected = tuple(row["path"] for row in all_rows if row["path"] is not None)
    if policy_path is not None:
        protected += (policy_path,)
    return RegressionGate(report, protected)
