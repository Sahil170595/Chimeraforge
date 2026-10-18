"""Receiver-side scorecards over frozen declarations and bounded native evidence."""

from __future__ import annotations

import copy
import hashlib
import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

from chimeraforge.bench.gate import _cache, _evidence_id, _fact, _metric, _workload
from chimeraforge.bench.gate_inputs import (
    MAX_POLICY_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_TOTAL_BYTES,
    finite,
    held_json,
    load_receipt,
    sha,
)
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.plan import PlanBenchmark, binding
from chimeraforge.bench.serving import _ollama_name, safe_observation
from chimeraforge.bench.serving_binding import GEOMETRY_FIELDS, PHYSICAL_HARDWARE_FIELDS
from chimeraforge.plan_bundle import (
    MAX_INPUT_BYTES,
    MAX_MANIFEST_BYTES,
    ROLE_PATHS,
    PlanBundle,
    _manifest_rows,
    _plain_path,
    _read,
)
from chimeraforge.plan_check import IDENTITY_FIELDS, identity
from chimeraforge.planner.replay import digest

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

logger = logging.getLogger(__name__)
MAX_DECLARED_INDICES = 16
MAX_RECEIPTS_PER_INDEX = 16
MAX_RECEIPTS = MAX_DECLARED_INDICES * MAX_RECEIPTS_PER_INDEX
SERVER_DECODE_BASIS = "server-all-output/decode-duration"
Json = dict[str, Any]
LIMITS = (
    "Conditional frozen base-decode comparison of declared capability-shaped metadata; "
    "measurement truth, physical hardware, immutable weights and independent executions "
    "remain unverified. No fleet, queue-inclusive latency, TTFT, SLO, "
    "calibration or refit qualification."
)
UNSCORED = {
    "fleet_tps": "A single-stream receipt does not execute the modeled fleet.",
    "p95_latency_ms": "Adapter durations exclude the modeled queue.",
    "ttft_ms": "Server prefill and client first-content timing do not qualify modeled TTFT.",
    "tpot_ms": "Native decode arithmetic does not establish the modeled per-output latency basis.",
    "slo": "Base decode arithmetic does not qualify deployment or queue-inclusive SLOs.",
    "client_decode_tps": "Client output-minus-first/stream timing is outside this comparator.",
    "completed_token_rate_tps": "Workload wall throughput is outside the initial comparator.",
}


def _fail() -> NoReturn:
    from chimeraforge.api import PlanError

    raise PlanError("invalid prediction score input") from None


@dataclass(frozen=True)
class PredictionScorePolicy:
    """Explicit frozen plan, population and inclusive absolute relative-error band."""

    plan_fingerprint: str
    candidate_indices: list[int]
    expected_receipts_per_index: dict[str, int]
    relative_error_band: float


@dataclass(frozen=True)
class PredictionScorecard:
    """Defensive score receipt with protected source files and atomic persistence."""

    _data: Json = field(repr=False)
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    def to_dict(self) -> Json:
        return copy.deepcopy(self._data)

    @property
    def exit_code(self) -> int:
        return cast(int, self._data["exit_code"])

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact, PlanError
        from chimeraforge.plan_study import protect_output

        try:
            protect_output(path, self._protected_paths)
            PlanArtifact(self.to_dict()).save(path)
        except (PlanError, OSError, ValueError, TypeError):
            logger.warning("prediction score output unavailable")
            raise PlanError("invalid prediction score output") from None


class _Inputs:
    """Charge every declared occurrence, while holding each physical path only once."""

    def __init__(self) -> None:
        self.total = 0
        self.paths: list[Path] = []
        self.cache: dict[Path, bytes] = {}

    def charge(self, size: int) -> None:
        if size <= 0 or self.total + size > MAX_TOTAL_BYTES:
            _fail()
        self.total += size

    def raw(self, path: Path, limit: int) -> bytes:
        path = path.absolute()
        _plain_path(path)
        if path in self.cache:
            raw = self.cache[path]
            if len(raw) > limit:
                _fail()
            self.charge(len(raw))
        else:
            raw = _read(path, min(limit, MAX_TOTAL_BYTES - self.total))
            self.charge(len(raw))
            self.cache[path] = raw
        self.paths.append(path)
        return raw

    def json(self, source: object, limit: int) -> tuple[Json, bytes, Path | None]:
        from chimeraforge.api import PlanArtifact

        if isinstance(source, (PlanArtifact, PlanBenchmark)):
            source = source.to_dict()
        if isinstance(source, (str, Path)):
            path = Path(source).absolute()
            raw = self.raw(path, limit)
            # held_json supplies the shared strict duplicate/nonfinite parser, without I/O.
            from chimeraforge.api import _unique_object
            import json

            data = json.loads(raw, object_pairs_hook=_unique_object)
            data, _, _ = held_json(data, limit)
            return cast(Json, data), raw, path
        data, raw, path = held_json(source, min(limit, MAX_TOTAL_BYTES - self.total))
        self.charge(len(raw))
        return cast(Json, data), raw, path


def _source(saved: PlanArtifact | PlanBundle | str | Path, held: _Inputs) -> tuple[Json, Json]:
    from chimeraforge.api import MAX_PLAN_BYTES, artifact_from_dict

    bundle: PlanBundle | None = None
    if isinstance(saved, PlanBundle):
        bundle = saved
        held.charge(len(bundle._manifest_bytes))
        held.charge(len(bundle._plan_bytes))
        for _, raw in bundle._input_bytes:
            held.charge(len(raw))
    elif isinstance(saved, (str, Path)) and Path(saved).is_dir():
        root = Path(saved).absolute()
        _plain_path(root)
        manifest_raw = held.raw(root / "manifest.json", MAX_MANIFEST_BYTES)
        manifest = _manifest_rows(manifest_raw)
        members: dict[str, bytes] = {}
        for row in manifest["files"]:
            members[row["role"]] = held.raw(
                root / row["path"], MAX_PLAN_BYTES if row["role"] == "plan" else MAX_INPUT_BYTES
            )
        if {entry.name for entry in root.iterdir()} != {
            "manifest.json",
            *(ROLE_PATHS[role] for role in members),
        }:
            _fail()
        bundle = PlanBundle(root, members.pop("plan"), tuple(members.items()), manifest_raw)
    if bundle is not None:
        artifact, _, _ = bundle._prepare()
        manifest = _manifest_rows(bundle._manifest_bytes)
        held.paths.extend([bundle._directory, bundle._directory / "manifest.json"])
        held.paths.extend(bundle._directory / row["path"] for row in manifest["files"])
        data = cast(Json, artifact.to_dict())
        return data, {
            "kind": "verified_bundle",
            "manifest_sha256": hashlib.sha256(bundle._manifest_bytes).hexdigest(),
            "members": [
                {key: row[key] for key in ("role", "sha256", "size_bytes")}
                for row in manifest["files"]
            ],
            "producing_bytes": "verified_content",
        }
    data, raw, _ = held.json(saved, MAX_PLAN_BYTES)
    artifact = artifact_from_dict(data)
    return cast(Json, artifact.to_dict()), {
        "kind": "frozen_declaration",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "producing_bytes": "unverified",
    }


def _policy(
    source: PredictionScorePolicy | Json | str | Path, held: _Inputs, data: Json
) -> PredictionScorePolicy:
    raw = asdict(source) if type(source) is PredictionScorePolicy else source
    values, _, _ = held.json(raw, MAX_POLICY_BYTES)
    if set(values) != set(PredictionScorePolicy.__annotations__):
        _fail()
    chosen = PredictionScorePolicy(**values)
    indices, counts = chosen.candidate_indices, chosen.expected_receipts_per_index
    if (
        not sha(chosen.plan_fingerprint)
        or chosen.plan_fingerprint != data["fingerprint"]
        or type(indices) is not list
        or not 1 <= len(indices) <= MAX_DECLARED_INDICES
        or any(
            type(index) is not int or not 0 <= index < len(data["result"]["candidates"])
            for index in indices
        )
        or len(set(indices)) != len(indices)
        or type(counts) is not dict
        or set(counts) != {str(index) for index in indices}
        or any(
            type(value) is not int or not 1 <= value <= MAX_RECEIPTS_PER_INDEX
            for value in counts.values()
        )
        or not finite(chosen.relative_error_band, minimum=0)
    ):
        _fail()
    return chosen


def _typed_observation(raw: Json) -> Json:
    observation = safe_observation(raw)
    if observation.get("backend") == "ollama" and isinstance(observation.get("model"), str):
        observation["model"] = _ollama_name(observation["model"])
    for root, names in (("hardware", PHYSICAL_HARDWARE_FIELDS), ("model_spec", GEOMETRY_FIELDS)):
        values = {name: _fact(observation, f"{root}.{name}") for name in names}
        # Omit unknown fields: the shared geometry helper normalizes explicit None to absence.
        observation[root] = {name: value for name, value in values.items() if value is not None}
    return cast(Json, observation)


def _semantic_id(receipt: Json) -> str:
    # Real physical/geometry facts admit equivalent integer/float spellings.
    projected = copy.deepcopy(receipt)
    for phase in ("serving_before", "serving_after"):
        observation = _typed_observation(projected["execution"][phase])
        for name in PHYSICAL_HARDWARE_FIELDS:
            value = observation["hardware"].get(name)
            if type(value) in (int, float):
                observation["hardware"][name] = float(value)
        for name in ("params_b", "recurrent_state_bytes_per_seq"):
            value = observation["model_spec"].get(name)
            if type(value) in (int, float):
                observation["model_spec"][name] = float(value)
        projected["execution"][phase] = observation
    return cast(str, _evidence_id(projected))


def _receipt(source: object, held: _Inputs) -> Json:
    envelope, raw, _ = held.json(source, MAX_RECEIPT_BYTES)
    receipt = cast(Json, load_receipt(envelope))
    receipt.update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw), envelope=envelope)
    if not receipt["legacy"]:
        plan = envelope["plan"]
        if (
            type(plan) is not dict
            or set(plan) != {"fingerprint", "candidate_index", "identity", "served_model"}
            or not sha(plan["fingerprint"])
            or type(plan["candidate_index"]) is not int
            or plan["candidate_index"] < 0
            or type(plan["served_model"]) is not str
            or not plan["served_model"]
            or type(plan["identity"]) is not dict
            or set(plan["identity"]) != set(IDENTITY_FIELDS)
        ):
            _fail()
        for name, value in plan["identity"].items():
            if name in ("tensor_parallel", "pipeline_parallel", "n_agents"):
                if type(value) is not int or value < 1:
                    _fail()
            elif type(value) is not str or not value:
                _fail()
        receipt["evidence_sha256"] = _semantic_id(receipt)
    else:
        receipt["evidence_sha256"] = _evidence_id(receipt)
    return receipt


def _row(
    data: Json, receipt: Json, position: int, chosen: PredictionScorePolicy, duplicate: bool
) -> Json:
    plan = receipt["envelope"].get("plan", {}) if not receipt["legacy"] else {}
    index = plan.get("candidate_index")
    candidate = (
        data["result"]["candidates"][index]
        if type(index) is int and 0 <= index < len(data["result"]["candidates"])
        else None
    )
    row: Json = {
        "receipt_index": position,
        "candidate_index": index,
        "candidate_digest": digest(candidate) if candidate is not None else None,
        "metric": "base_decode_tps",
        "predicted": candidate["throughput_tps"] if candidate else None,
        "measured": None,
        "relative_error": None,
        "within_band": None,
        "measurement_basis": None,
        "provenance": None,
        "state": "unavailable",
        "reasons": [],
        "binding_states": {},
    }
    if candidate is not None:
        provenance = candidate["provenance"].get("throughput")
        row["provenance"] = (
            provenance
            if provenance in ("measured", "contributed", "extrapolated", "estimated", "unknown")
            else "unknown"
        )
    if receipt["legacy"]:
        row["reasons"] = ["native_plan_binding_unavailable"] + (
            ["duplicate_semantic_evidence"] if duplicate else []
        )
        if duplicate:
            row["state"] = "duplicate"
        return row
    execution = copy.deepcopy(receipt["execution"])
    for phase in ("serving_before", "serving_after"):
        execution[phase] = _typed_observation(execution[phase])
    native = {**receipt, "execution": execution}
    measured, basis = _metric(native, "decode_tps")
    row.update(measured=measured, measurement_basis=basis)
    mismatch: list[str] = []
    unavailable: list[str] = []
    devices = [execution[phase].get("device") for phase in ("serving_before", "serving_after")]
    if "cpu" in devices:
        mismatch.append("serving_gpu_device")
    elif devices != ["gpu", "gpu"]:
        unavailable.append("serving_gpu_device")
    if plan["fingerprint"] != data["fingerprint"]:
        mismatch.append("plan_fingerprint")
    if candidate is None or index not in chosen.candidate_indices:
        row.update(
            state="duplicate" if duplicate else "extra",
            reasons=[*mismatch, "undeclared_candidate_index"],
        )
        if duplicate:
            row["reasons"].append("duplicate_semantic_evidence")
        return row
    if plan["identity"] != identity(candidate):
        mismatch.append("candidate_identity")
    if receipt["measurement"]["model"] != plan["served_model"]:
        mismatch.append("measurement_model")
    if any(
        execution[phase].get("backend") != receipt["measurement"]["backend"]
        for phase in ("serving_before", "serving_after")
    ):
        mismatch.append("measurement_backend")
    bound = binding(data, candidate, execution, plan["served_model"])
    if candidate["backend"] == "ollama":
        expected_model = _ollama_name(candidate["model"])
        if _ollama_name(plan["served_model"]) != expected_model or any(
            isinstance(execution[phase].get("model"), str)
            and _ollama_name(execution[phase]["model"]) != expected_model
            for phase in ("serving_before", "serving_after")
        ):
            bound["model"]["state"] = "mismatch"
    required = (
        "backend",
        "model",
        "model_geometry",
        "quant",
        "hardware",
        "tensor_parallel",
        "pipeline_parallel",
        "context_length",
        "prompt_tokens",
        "output_tokens",
        "prefix_cache",
        "serving_stability",
    )
    row["binding_states"] = {name: bound[name]["state"] for name in required}
    engines = [
        _fact(execution[phase], "execution_engine") for phase in ("serving_before", "serving_after")
    ]
    known_engines = [engine for engine in engines if engine is not None]
    engine_state = "unavailable"
    if any(engine != candidate["backend"] for engine in known_engines):
        mismatch.append("execution_engine")
        engine_state = "mismatch"
    elif len(known_engines) == 1:
        unavailable.append("execution_engine_presence")
    elif len(known_engines) == 2:
        engine_state = "matched"
    # Optional missing attestation is unverified; supplied contradictions cannot be waived.
    row["binding_states"]["execution_engine"] = engine_state
    for name in required:
        state = bound[name]["state"]
        if state == "mismatch":
            mismatch.append(name)
        elif state != "matched":
            unavailable.append(name)
    cache = _cache(native)
    if cache["state"] == "mismatch":
        mismatch.append("cache_contradiction")
        row["binding_states"]["prefix_cache"] = "mismatch"
    if data["inputs"]["prefix_cache_hit_rate"] != 0 or candidate["prefix_cache_hit_rate"] != 0:
        unavailable.append("planned_prefix_cache")
    request = execution["request"]
    if request["workload"] != "single" or request["concurrency"] != 1:
        unavailable.append("single_stream_required")
    _, workload_reasons = _workload(native)
    unavailable.extend(workload_reasons)
    if candidate["tensor_parallel"] != 1 or candidate["pipeline_parallel"] != 1:
        unavailable.append("base_parallelism_required")
    if candidate["lora_adapters"] != 0 or candidate["offload_fraction"] != 0:
        unavailable.append("scenario_modifiers_unobserved")
    if execution["failed_count"]:
        unavailable.append("partial_native_population")
    if basis != SERVER_DECODE_BASIS or measured is None or measured <= 0:
        unavailable.append("server_decode_basis_unavailable")
    predicted = row["predicted"]
    if not finite(predicted):
        unavailable.append("frozen_prediction_unavailable")
    row["reasons"] = sorted(set(mismatch + unavailable))
    if duplicate:
        row["state"] = "duplicate"
        row["reasons"].append("duplicate_semantic_evidence")
        return row
    if mismatch or unavailable:
        row["state"] = "binding_mismatch" if mismatch else "unavailable"
        return row
    error = (predicted - measured) / measured
    if not finite(error):
        row["reasons"] = ["finite_relative_error_unavailable"]
        return row
    within = abs(error) <= chosen.relative_error_band
    row.update(
        relative_error=error, within_band=within, state="within_band" if within else "breach"
    )
    return row


def score_predictions(
    saved_plan: PlanArtifact | PlanBundle | str | Path,
    benchmark_receipts: list[PlanBenchmark | Json | str | Path],
    *,
    policy: PredictionScorePolicy | Json | str | Path,
) -> PredictionScorecard:
    """Score every declared row without planning, inference, corpus replacement or refitting."""
    from chimeraforge.api import PlanError

    try:
        held = _Inputs()
        data, source = _source(saved_plan, held)
        chosen = _policy(policy, held, data)
        if type(benchmark_receipts) is not list or len(benchmark_receipts) > MAX_RECEIPTS:
            _fail()
        receipts = [_receipt(item, held) for item in benchmark_receipts]
        duplicates = Counter(item["evidence_sha256"] for item in receipts)
        rows = [
            _row(data, item, position, chosen, duplicates[item["evidence_sha256"]] > 1)
            for position, item in enumerate(receipts)
        ]
        coverage = []
        for index in chosen.candidate_indices:
            population = [row for row in rows if row["candidate_index"] == index]
            expected = chosen.expected_receipts_per_index[str(index)]
            missing = max(0, expected - len(population))
            comparable = sum(row["relative_error"] is not None for row in population)
            candidate = data["result"]["candidates"][index]
            coverage.append(
                {
                    "candidate_index": index,
                    "expected": expected,
                    "received": len(population),
                    "comparable": comparable,
                    "missing": missing,
                    "extra": max(0, len(population) - expected),
                    "ineligible": len(population) - comparable,
                }
            )
            for _ in range(missing):
                rows.append(
                    {
                        "receipt_index": None,
                        "candidate_index": index,
                        "candidate_digest": digest(candidate),
                        "metric": "base_decode_tps",
                        "predicted": candidate["throughput_tps"],
                        "measured": None,
                        "relative_error": None,
                        "within_band": None,
                        "measurement_basis": None,
                        "provenance": None,
                        "state": "missing",
                        "reasons": ["missing_receipt"],
                        "binding_states": {},
                    }
                )
        breach = any(row["state"] == "breach" for row in rows)
        incomplete = any(row["relative_error"] is None for row in rows) or any(
            row["missing"] or row["extra"] for row in coverage
        )
        outcome = "breach" if breach else "incomplete" if incomplete else "within_band"
        report: Json = {
            "schema_version": 1,
            "kind": "chimeraforge.prediction-scorecard",
            "created_at": now_iso(),
            "plan": {"fingerprint": data["fingerprint"], "corpus_sha256": data["corpus_sha256"]},
            "policy": asdict(chosen),
            "outcome": outcome,
            "exit_code": {"within_band": 0, "breach": 1, "incomplete": 3}[outcome],
            "coverage": coverage,
            "rows": rows,
            "worst_rows": sorted(
                [index for index, row in enumerate(rows) if row["relative_error"] is not None],
                key=lambda index: abs(rows[index]["relative_error"]),
                reverse=True,
            ),
            "inputs": {
                "plan": source,
                "receipts": [
                    {
                        key: item[key]
                        for key in (
                            "sha256",
                            "size_bytes",
                            "fingerprint",
                            "evidence_sha256",
                            "legacy",
                        )
                    }
                    for item in receipts
                ],
                "total_bytes": held.total,
            },
            "unscored_metrics": dict(UNSCORED),
            "assurance": {
                "source_authentication": "unverified",
                "measurement_truth": "unverified",
                "physical_hardware": "unverified",
                "immutable_weights": "unverified",
                "actual_serving_modifiers": "unverified",
                "underlying_engine_authentication": "unverified",
                "independent_executions": "unverified",
                "calibration": "not_performed",
                "candidate_digest_scope": (
                    "receiver commitment to full frozen candidate; not producer-recorded"
                ),
            },
            "limits": LIMITS,
        }
        report["fingerprint"] = digest(report)
        return PredictionScorecard(report, tuple(held.paths))
    except (PlanError, OSError, ValueError, TypeError, KeyError, ArithmeticError, RecursionError):
        logger.warning("prediction score input rejected")
        _fail()
