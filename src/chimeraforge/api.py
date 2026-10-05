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
from typing import get_args, get_origin, get_type_hints

from chimeraforge import __version__
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.models import load_effective_models
from chimeraforge.planner.resolver import ModelSpec, ResolverError
from chimeraforge.planner.service import PlanResult, run_plan, validate_plan_inputs

SCHEMA_VERSION = 1
MAX_PLAN_BYTES = 8 * 1024 * 1024


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
    allow_network: bool = True
    overrides: dict | None = None

    def validate(self) -> None:
        """Reject mistyped, non-finite and impossible inputs before resolution."""
        values = asdict(self)
        for name, annotation in get_type_hints(type(self)).items():
            _check_type(values[name], annotation, name)
        _finite_input(values)
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
    inputs = asdict(request)
    inputs.pop("hf_token")
    # URL userinfo is a credential too. An authenticated endpoint is not portable.
    from urllib.parse import urlsplit, urlunsplit

    if inputs["ollama_url"]:
        url = urlsplit(inputs["ollama_url"])
        inputs["ollama_url"] = urlunsplit((url.scheme, url.netloc.split("@")[-1], url.path, "", ""))
    corpus = load_effective_models(request.models_path)
    body = _json_value(
        {
            "schema_version": SCHEMA_VERSION,
            "tool": {"name": "chimeraforge", "version": __version__},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "corpus_sha256": _digest(asdict(corpus)),
            "result": asdict(result),
        }
    )
    body["fingerprint"] = _digest(body)
    return PlanArtifact(body)


def plan(request: PlanRequest) -> PlanArtifact:
    """Plan with the same search as CLI/MCP, through a strict public boundary."""
    try:
        request.validate()
        return snapshot(request, run_plan(**asdict(request)))
    except (ValueError, OSError, ResolverError) as exc:
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
        or data["schema_version"] != SCHEMA_VERSION
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
        request = PlanRequest(**data["inputs"])
        request.validate()
        if "hf_token" in data["inputs"]:
            raise PlanError("saved plans must not contain credentials")
        result = data["result"]
        if set(result) != {f.name for f in fields(PlanResult)}:
            raise PlanError("invalid saved-plan result fields")
        if not isinstance(result["candidates"], list) or not isinstance(result["specs"], dict):
            raise PlanError("invalid candidates/specifications")
        for row in result["candidates"]:
            if set(row) != {f.name for f in fields(Candidate)}:
                raise PlanError("invalid candidate fields")
            for name, annotation in get_type_hints(Candidate).items():
                if row[name] is None and annotation is float:
                    continue  # non-finite predictions are serialized as unknown
                _check_type(row[name], annotation, name)
            Candidate(**row)
        for row in result["specs"].values():
            for name, annotation in get_type_hints(ModelSpec).items():
                _check_type(row[name], annotation, name)
            ModelSpec(**row)
        _check_type(result["target_models"], list[str], "target_models")
        if result["platform"] not in ("linux", "windows", "wsl2", "macos"):
            raise PlanError("invalid saved-plan platform")
        _finite_input(data)
    except (TypeError, KeyError, ValueError, OverflowError) as exc:
        raise PlanError(f"invalid saved-plan structure: {exc}") from exc
    return PlanArtifact(copy.deepcopy(data))
