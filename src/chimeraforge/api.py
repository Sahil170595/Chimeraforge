"""Validated public planning API and integrity-checked, credential-free snapshots."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import types
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Callable
from typing import get_args, get_origin, get_type_hints

from chimeraforge.bench.plan import PlanBenchmark
from chimeraforge.contribution_review import ContributionReceipt

from chimeraforge import __version__
from chimeraforge.monitor import MonitorReport, MonitorRequest, MonitorWindow
from chimeraforge.plan_check import PlanCheck
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.hardware import GPU_OVERRIDE_FIELDS
from chimeraforge.planner.resolver import ModelSpec, ResolverError
from chimeraforge.planner.service import PlanResult, run_plan, validate_plan_inputs

SCHEMA_VERSION = 2
MAX_PLAN_BYTES = 8 * 1024 * 1024
MODEL_OVERRIDE_TYPES = {
    "params_b": float,
    "n_layers": int,
    "n_kv_heads": int,
    "d_head": int,
    "hidden_size": int,
}


class PlanError(ValueError):
    """Invalid request, unavailable planning input, or invalid saved plan."""


@dataclass(frozen=True)
class PlanRequest:
    """Typed options for the shared planner; network use is explicit in callers."""

    models: list[str] | None = None
    model_size: str = "3b"
    hardware: str = "RTX 4080 12GB"
    request_rate: float = 1.0
    latency_slo: float | None = None
    quality_target: float = 0.5
    budget: float = 100.0
    avg_tokens: int = 128
    reasoning_tokens: int = 0
    prefix_cache_hit_rate: float = 0.0
    duty_cycle: float = 1.0
    gpu_price_multiplier: float = 1.0
    allow_offload: bool = False
    host_bandwidth_gbps: float | None = None
    ttft_slo: float | None = None
    tpot_slo: float | None = None
    context_length: int = 2048
    prompt_tokens: int = 512
    gpu_overrides: dict | None = None
    platform: str | None = None
    unified_memory_fraction: float | None = None
    quality_from: str | None = None
    max_num_batched_tokens: int | None = None
    safety_target: float | None = None
    workload_cv2: float = 0.0
    electricity_rate: float = 0.12
    kv_quant: str = "fp16"
    tensor_parallel: int | None = 1
    pipeline_parallel: int | None = 1
    lora_adapters: int = 0
    lora_rank: int = 16
    lora_target: str = "qv"
    pareto: bool = False
    grid_region: str | None = None
    carbon_intensity: float | None = None
    mode: str = "online"
    use_contributions: bool = False
    cloud: str | None = None
    think_time_s: float | None = None
    session_turns: int | None = None
    models_path: str | None = None
    ollama_url: str | None = None
    hf_token: str | None = None
    model_revisions: dict[str, str] | None = None
    allow_network: bool = True
    overrides: dict | None = None

    def validate(self) -> None:
        """Reject mistyped, non-finite and impossible inputs before resolution."""
        values = asdict(self)
        for name, annotation in get_type_hints(type(self)).items():
            _check_type(values[name], annotation, name)
        _finite_input(values)
        _validate_overrides(self.overrides, MODEL_OVERRIDE_TYPES, set(MODEL_OVERRIDE_TYPES))
        _validate_overrides(
            self.gpu_overrides,
            {k: float for k in GPU_OVERRIDE_FIELDS},
            {"vram_gb", "bandwidth_gbps"},
        )
        if self.models is not None and any(not model.strip() for model in self.models):
            raise PlanError("model identifiers must be non-empty")
        from chimeraforge.planner.checkpoint import revisions

        try:
            revisions(self.model_revisions, self.models)
        except ValueError as exc:
            raise PlanError(str(exc)) from exc
        names = get_type_hints(validate_plan_inputs)
        validate_plan_inputs(**{k: v for k, v in values.items() if k in names})
        for name in ("budget", "workload_cv2", "lora_adapters", "reasoning_tokens"):
            if values[name] < 0:
                raise PlanError(f"{name} must be non-negative")
        for name in ("quality_target", "safety_target", "unified_memory_fraction"):
            value = values[name]
            if value is not None and not 0 <= value <= 1:
                raise PlanError(f"{name} must be between 0 and 1")
        for name in (
            "tensor_parallel",
            "pipeline_parallel",
            "lora_rank",
            "max_num_batched_tokens",
            "session_turns",
        ):
            value = values[name]
            if value is not None and value <= 0:
                raise PlanError(f"{name} must be positive")
        if self.think_time_s is not None and self.think_time_s < 0:
            raise PlanError("think_time_s must be non-negative")
        if (self.think_time_s is None) != (self.session_turns is None):
            raise PlanError("think_time_s and session_turns must be supplied together")
        if self.platform is not None and self.platform not in ("linux", "windows", "wsl2", "macos"):
            raise PlanError("platform must be linux, windows, wsl2 or macos")


def _validate_overrides(values: dict | None, annotations: dict, positive: set[str]) -> None:
    if values is None:
        return
    unknown = set(values) - set(annotations)
    if unknown:
        raise PlanError(f"unknown override fields: {sorted(unknown, key=str)}")
    for name, value in values.items():
        if value is None:
            continue
        _check_type(value, annotations[name], name)
        if value < 0 or (name in positive and value == 0):
            constraint = "positive" if name in positive else "non-negative"
            raise PlanError(f"override {name} must be {constraint}")


def _check_type(value, annotation, name: str) -> None:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is types.UnionType:
        for option in args:
            try:
                _check_type(value, option, name)
                return
            except PlanError:
                continue
        raise PlanError(f"invalid type for {name}")
    if annotation is type(None):
        valid = value is None
    elif annotation is float:
        valid = type(value) in (int, float)
    else:
        valid = type(value) is (origin or annotation)
    if not valid:
        raise PlanError(f"invalid type for {name}")
    if origin is list:
        for item in value:
            _check_type(item, args[0], name)
    elif origin is dict and args:
        for key, item in value.items():
            _check_type(key, args[0], name)
            _check_type(item, args[1], name)


def _finite_input(value) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise PlanError("planning inputs must be finite")
    if isinstance(value, dict):
        for item in value.values():
            _finite_input(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _finite_input(item)


def _json_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    return value


def _digest(value: dict) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PlanArtifact:
    """Portable record; its fingerprint detects edits, not contributor authenticity."""

    _data: dict

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def candidate(self, index: int = 0) -> Candidate:
        """Read a candidate without replanning or replacing unknown values."""
        rows = self._data["result"]["candidates"]
        if type(index) is not int or not 0 <= index < len(rows):
            raise PlanError("candidate index is out of range; the plan may have no feasible result")
        return Candidate(**copy.deepcopy(rows[index]))

    def spec(self, model: str) -> ModelSpec | None:
        row = self._data["result"]["specs"].get(model)
        return ModelSpec(**copy.deepcopy(row)) if row else None

    def save(self, path: str | Path) -> None:
        """Write UTF-8 JSON atomically in the destination directory."""
        from tempfile import NamedTemporaryFile

        target = Path(path)
        temp = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp"
            ) as stream:
                temp = Path(stream.name)
                json.dump(self._data, stream, indent=2, allow_nan=False)
                stream.write("\n")
            temp.replace(target)
        except OSError as exc:
            raise PlanError(f"cannot save plan to {target}: {exc}") from exc
        finally:
            if temp is not None and temp.exists():
                temp.unlink()


def snapshot(request: PlanRequest, result: PlanResult) -> PlanArtifact:
    """Capture effective options, resolved facts, corpus identity and provenance."""
    request.validate()
    inputs = asdict(request)
    inputs.pop("hf_token")
    # URL userinfo is a credential too. An authenticated endpoint is not portable.
    from urllib.parse import urlsplit, urlunsplit

    if inputs["ollama_url"]:
        url = urlsplit(inputs["ollama_url"])
        inputs["ollama_url"] = urlunsplit((url.scheme, url.netloc.split("@")[-1], url.path, "", ""))
    if not result.corpus_sha256:
        raise PlanError("planning result did not record its consumed corpus")
    result_data = asdict(result)
    schema_version = SCHEMA_VERSION if result.replay_context is not None else 1
    if schema_version == 1:
        result_data.pop("replay_context")
    body = _json_value(
        {
            "schema_version": schema_version,
            "tool": {"name": "chimeraforge", "version": __version__},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "corpus_sha256": result.corpus_sha256,
            "result": result_data,
        }
    )
    body["fingerprint"] = _digest(body)
    return artifact_from_dict(body)


def plan(request: PlanRequest) -> PlanArtifact:
    """Plan with the same search as CLI/MCP, through a strict public boundary."""
    try:
        request.validate()
        return snapshot(request, run_plan(**asdict(request)))
    except (ValueError, OSError, ResolverError, TypeError, OverflowError) as exc:
        raise PlanError(str(exc)) from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PlanError(f"duplicate saved-plan key: {key}")
        result[key] = value
    return result


def load_plan(path: str | Path) -> PlanArtifact:
    """Load a current-schema snapshot; reject malformed or edited input."""
    try:
        target = Path(path)
        if target.stat().st_size > MAX_PLAN_BYTES:
            raise PlanError("saved plan exceeds size limit")
        data = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        return artifact_from_dict(data)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise PlanError(f"invalid saved plan: {exc}") from exc


def artifact_from_dict(data: dict) -> PlanArtifact:
    """Validate an artifact received from a file or another programmatic surface."""
    required = {
        "schema_version",
        "tool",
        "created_at",
        "inputs",
        "corpus_sha256",
        "result",
        "fingerprint",
    }
    if (
        not isinstance(data, dict)
        or set(data) != required
        or type(data["schema_version"]) is not int
        or data["schema_version"] not in (1, SCHEMA_VERSION)
    ):
        raise PlanError("unsupported saved-plan schema or fields")
    body = {k: v for k, v in data.items() if k != "fingerprint"}
    try:
        if _digest(body) != data["fingerprint"]:
            raise PlanError("saved-plan fingerprint mismatch")
        if (
            not isinstance(data["tool"], dict)
            or set(data["tool"]) != {"name", "version"}
            or data["tool"]["name"] != "chimeraforge"
            or not isinstance(data["tool"]["version"], str)
        ):
            raise PlanError("invalid saved-plan tool identity")
        stamp = datetime.fromisoformat(data["created_at"])
        if stamp.tzinfo is None:
            raise PlanError("saved-plan timestamp must include a timezone")
        corpus_hash = data["corpus_sha256"]
        if (
            not isinstance(corpus_hash, str)
            or len(corpus_hash) != 64
            or any(c not in "0123456789abcdef" for c in corpus_hash)
        ):
            raise PlanError("invalid corpus fingerprint")
        expected_inputs = {f.name for f in fields(PlanRequest)} - {"hf_token"}
        if set(data["inputs"]) not in (expected_inputs, expected_inputs - {"model_revisions"}):
            raise PlanError("saved plan must record every noncredential request field")
        request = PlanRequest(**data["inputs"])
        request.validate()
        if "hf_token" in data["inputs"]:
            raise PlanError("saved plans must not contain credentials")
        from urllib.parse import urlsplit

        if request.ollama_url:
            url = urlsplit(request.ollama_url)
            if url.username is not None or url.password is not None or url.query or url.fragment:
                raise PlanError("saved endpoint must omit userinfo, query and fragment")
        result = data["result"]
        result_fields = {f.name for f in fields(PlanResult)}
        if data["schema_version"] == 1:
            result_fields.remove("replay_context")
        if set(result) != result_fields:
            raise PlanError("invalid saved-plan result fields")
        if result["corpus_sha256"] != corpus_hash:
            raise PlanError("result and artifact corpus fingerprints must agree")
        if not isinstance(result["candidates"], list) or not isinstance(result["specs"], dict):
            raise PlanError("invalid candidates/specifications")
        rows = result["candidates"]
        if result["frontier"] is not None:
            _check_type(result["frontier"], list[dict], "frontier")
            rows = rows + result["frontier"]
        for row in rows:
            _validate_candidate(row)
        for key, row in result["specs"].items():
            expected_spec = {f.name for f in fields(ModelSpec)}
            if set(row) not in (expected_spec, expected_spec - {"checkpoint"}):
                raise PlanError("invalid saved model specification fields")
            for name, annotation in get_type_hints(ModelSpec).items():
                _check_type(row.get(name) if name == "checkpoint" else row[name], annotation, name)
            ModelSpec(**row)
            canonical = key.split("ollama:", 1)[-1] if row["source"] == "ollama" else key
            if row["name"] not in (key, canonical):
                raise PlanError("specification identity must match its recorded target")
        for repo, ref in (request.model_revisions or {}).items():
            bound = result["specs"].get(repo, {}).get("checkpoint")
            if bound is None or bound["requested_revision"] != ref:
                raise PlanError("requested revision must agree with recorded checkpoint metadata")
        _check_type(result["target_models"], list[str], "target_models")
        if any(row["model"] not in result["target_models"] for row in rows):
            raise PlanError("every candidate must name a recorded target model")
        if any(key not in result["target_models"] for key in result["specs"]):
            raise PlanError("specifications must belong to recorded targets")
        _check_type(result["trace"], list[list], "trace")
        if any(len(row) != 4 or any(type(v) is not str for v in row) for row in result["trace"]):
            raise PlanError("trace rows must contain four strings")
        if result["platform"] not in ("linux", "windows", "wsl2", "macos"):
            raise PlanError("invalid saved-plan platform")
        if data["schema_version"] == SCHEMA_VERSION:
            from chimeraforge.plan_check import validate_context

            validate_context(result["replay_context"], result, request)
        _finite_input(data)
    except (TypeError, KeyError, ValueError, OverflowError) as exc:
        raise PlanError(f"invalid saved-plan structure: {exc}") from exc
    return PlanArtifact(copy.deepcopy(data))


def _validate_candidate(row: dict) -> None:
    if set(row) != {f.name for f in fields(Candidate)}:
        raise PlanError("invalid candidate fields")
    for name, annotation in get_type_hints(Candidate).items():
        if row[name] is None and annotation is float:
            continue  # non-finite predictions are serialized as unknown
        _check_type(row[name], annotation, name)
    Candidate(**row)


def check_plan(
    saved: PlanArtifact | str | Path, *, allow_network: bool = False, hf_token: str | None = None
) -> PlanCheck:
    """Compare without changing the artifact/target; Hub inspection is explicit opt-in."""
    from chimeraforge.plan_check import check

    artifact = (
        artifact_from_dict(saved.to_dict()) if isinstance(saved, PlanArtifact) else load_plan(saved)
    )
    if type(allow_network) is not bool or (hf_token is not None and type(hf_token) is not str):
        raise PlanError("invalid check network options")
    return check(artifact, allow_network=allow_network, hf_token=hf_token)


async def benchmark_plan(
    saved: PlanArtifact | str | Path,
    *,
    candidate_index: int = 0,
    model: str | None = None,
    backend: str | None = None,
    prompt: str | None = None,
    runs: int = 5,
    workload: str = "single",
    rate: float | None = None,
    concurrency: int | None = None,
    base_url: str | None = None,
) -> PlanBenchmark:
    """Measure a selected saved scenario against an explicitly contacted live endpoint."""
    from chimeraforge.bench.plan import benchmark

    return await benchmark(
        saved,
        candidate_index=candidate_index,
        model=model,
        backend=backend,
        prompt=prompt,
        runs=runs,
        workload=workload,
        rate=rate,
        concurrency=concurrency,
        base_url=base_url,
    )


def monitor_plan(
    saved: PlanArtifact | str | Path,
    request: MonitorRequest,
    *,
    candidate_index: int = 0,
    stop_event: threading.Event | None = None,
    on_window: Callable[[MonitorWindow], None] | None = None,
) -> MonitorReport:
    """Passively observe saved candidate bindings and native SLOs as separate evidence."""
    from chimeraforge.plan_monitor import monitor_saved

    return monitor_saved(
        saved, request, candidate_index=candidate_index, stop_event=stop_event, on_window=on_window
    )


def review_contribution(
    source: dict | str | Path,
    *,
    decision: str = "pending",
    reason: str | None = None,
) -> ContributionReceipt:
    """Read an unsigned contribution and record a disposition without changing trust."""
    from chimeraforge.contribution_review import review

    return review(source, decision=decision, reason=reason)


async def replay_contribution(
    source: dict | str | Path,
    *,
    prompt: str,
    output_tokens: int,
    runs: int = 5,
    model: str | None = None,
    backend: str | None = None,
    base_url: str | None = None,
    workload: str | None = None,
    rate: float | None = None,
    concurrency: int | None = None,
) -> ContributionReceipt:
    """Run an explicit live probe and report legacy equivalence gaps and native differences."""
    from chimeraforge.contribution_review import replay

    return await replay(
        source,
        prompt=prompt,
        output_tokens=output_tokens,
        runs=runs,
        model=model,
        backend=backend,
        base_url=base_url,
        workload=workload,
        rate=rate,
        concurrency=concurrency,
    )
