"""Closed operator intent, distinct from optimizer and checkpoint evidence."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import cast

from chimeraforge import __version__
from chimeraforge.serving_target import ServingTarget

MAX_DECLARATION_BYTES = 64 * 1024
MAX_SERVING_INTEGER = 1 << 20
MAX_SERVING_TEXT = 4096
DECLARATION_KIND = "chimeraforge.serving-declaration"
ARGV_PROFILE = "chimeraforge-native-hf-v1"
REFERENCE_RELEASES = {"vllm": "v0.30.0", "sglang": "v0.5.20"}
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_UNKNOWN = {
    "throughput_tps": None,
    "latency_ms": None,
    "quality": None,
    "memory_gib": None,
    "feasibility": None,
    "deployment_ready": None,
    "cost_per_token": None,
    "price_per_hour": None,
    "monthly_cost": None,
    "image_compatibility": None,
}


class ServingDeclarationError(ValueError):
    """Invalid or unsupported operator intent, input or output."""


def _bounded(data: object) -> None:
    from chimeraforge.deployment_verify import _admit

    try:
        if type(data) is not dict:
            raise ValueError
        _admit(data, MAX_DECLARATION_BYTES)
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        raise ServingDeclarationError(
            "serving declaration exceeds its bounded JSON contract"
        ) from None


@dataclass(frozen=True)
class ServingRequest:
    model: str
    revision: str
    backend: str
    image: str
    replicas: int = 1
    tensor_parallel: int = 1
    pipeline_parallel: int = 1
    context_length: int = 4096
    batch_size: int = 1
    dtype: str = "FP16"
    kv_quant: str = "fp16"
    prefix_caching: bool = False
    max_num_batched_tokens: int | None = None


def _request(value: ServingRequest) -> ServingRequest:
    from chimeraforge.deploy import MAX_EXPORT_GPUS_PER_REPLICA, _image
    from chimeraforge.planner.constants import MAX_REPLICAS, CHUNK_TILE_ALIGNMENT

    if type(value) is not ServingRequest:
        raise ServingDeclarationError("expected a typed ServingRequest")
    for text in (
        value.model,
        value.revision,
        value.backend,
        value.image,
        value.dtype,
        value.kv_quant,
    ):
        if type(text) is not str or len(text) > MAX_SERVING_TEXT:
            raise ServingDeclarationError("invalid bounded serving text")
    if not _REPO.fullmatch(value.model) or ".." in value.model or "--" in value.model:
        raise ServingDeclarationError("model must be an explicit namespace/repository")
    if not _REVISION.fullmatch(value.revision):
        raise ServingDeclarationError("revision must be an operator-claimed lowercase40hex commit")
    if value.backend not in REFERENCE_RELEASES or value.dtype not in ("FP16", "BF16"):
        raise ServingDeclarationError("serving supports vLLM/SGLang with FP16 or BF16 weights")
    if value.kv_quant not in ("fp16", "q8") or type(value.prefix_caching) is not bool:
        raise ServingDeclarationError("unsupported KV or prefix-cache setting")
    if value.backend == "sglang" and value.dtype != "FP16" and value.kv_quant == "fp16":
        raise ServingDeclarationError("SGLang implicit KV dtype does not establish FP16 cache")
    for name, maximum in (
        ("replicas", MAX_REPLICAS),
        ("tensor_parallel", MAX_EXPORT_GPUS_PER_REPLICA),
        ("pipeline_parallel", MAX_EXPORT_GPUS_PER_REPLICA),
        ("context_length", MAX_SERVING_INTEGER),
        ("batch_size", MAX_SERVING_INTEGER),
    ):
        item = getattr(value, name)
        if type(item) is not int or not 1 <= item <= maximum:
            raise ServingDeclarationError("serving integer exceeds its native bound")
    if value.tensor_parallel * value.pipeline_parallel > MAX_EXPORT_GPUS_PER_REPLICA:
        raise ServingDeclarationError("TP times PP exceeds native per-replica GPU bound")
    tokens = value.max_num_batched_tokens
    if tokens is not None and (
        value.backend != "vllm"
        or type(tokens) is not int
        or not max(CHUNK_TILE_ALIGNMENT, value.batch_size) <= tokens <= MAX_SERVING_INTEGER
        or tokens % CHUNK_TILE_ALIGNMENT
    ):
        raise ServingDeclarationError("unsupported bounded native chunked-prefill token setting")
    try:
        _image(value.image)
    except ValueError:
        raise ServingDeclarationError(
            "image needs an explicit non-latest tag or sha256 digest"
        ) from None
    return value


def _digest(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ServingDeclaration:
    """An edit-detecting operator claim; never a PlanArtifact or capacity result."""

    _data: dict

    def to_dict(self) -> dict:
        _bounded(self._data)
        return copy.deepcopy(self._data)

    @property
    def request(self) -> ServingRequest:
        _bounded(self._data)
        return _request(ServingRequest(**copy.deepcopy(self._data["request"])))

    @property
    def fingerprint(self) -> str:
        _bounded(self._data)
        return cast(str, self._data["fingerprint"])

    def save(self, path: str | Path) -> None:
        from chimeraforge.plan_bundle import _plain_path

        admitted = declaration_from_dict(self.to_dict())
        target = Path(path)
        try:
            _plain_path(target)
            raw = (json.dumps(admitted.to_dict(), indent=2, allow_nan=False) + "\n").encode("utf-8")
            if len(raw) > MAX_DECLARATION_BYTES:
                raise ValueError
            with target.open("xb") as stream:
                stream.write(raw)
        except (OSError, ValueError, TypeError):
            raise ServingDeclarationError("cannot publish new serving declaration") from None


def declare_serving(request: ServingRequest) -> ServingDeclaration:
    request = _request(request)
    data = {
        "kind": DECLARATION_KIND,
        "schema_version": 1,
        "tool": {"name": "chimeraforge", "version": __version__},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "argv_profile": ARGV_PROFILE,
        "reference_release": REFERENCE_RELEASES[request.backend],
        "request": asdict(request),
        "claims": copy.deepcopy(_UNKNOWN),
        "evidence": "operator-declared; revision/image/model/runtime are unverified",
    }
    data["fingerprint"] = _digest(data)
    return declaration_from_dict(data)


def declaration_from_dict(value: dict) -> ServingDeclaration:
    _bounded(value)
    try:
        expected = {
            "kind",
            "schema_version",
            "tool",
            "created_at",
            "argv_profile",
            "reference_release",
            "request",
            "claims",
            "evidence",
            "fingerprint",
        }
        if type(value) is not dict or set(value) != expected:
            raise ValueError
        if (
            value["kind"] != DECLARATION_KIND
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
        ):
            raise ValueError
        if type(value["request"]) is not dict or set(value["request"]) != {
            f.name for f in fields(ServingRequest)
        }:
            raise ValueError
        request = _request(ServingRequest(**value["request"]))
        if (
            value["argv_profile"] != ARGV_PROFILE
            or value["reference_release"] != REFERENCE_RELEASES[request.backend]
        ):
            raise ValueError
        if type(value["claims"]) is not dict or value["claims"] != _UNKNOWN:
            raise ValueError
        if value["evidence"] != "operator-declared; revision/image/model/runtime are unverified":
            raise ValueError
        tool = value["tool"]
        if (
            type(tool) is not dict
            or set(tool) != {"name", "version"}
            or tool["name"] != "chimeraforge"
            or type(tool["version"]) is not str
            or not 1 <= len(tool["version"]) <= 64
        ):
            raise ValueError
        if (
            type(value["created_at"]) is not str
            or len(value["created_at"]) > 64
            or datetime.fromisoformat(value["created_at"]).tzinfo is None
        ):
            raise ValueError
        body = {k: v for k, v in value.items() if k != "fingerprint"}
        if (
            value["fingerprint"] != _digest(body)
            or len(json.dumps(value).encode("utf-8")) > MAX_DECLARATION_BYTES
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise ServingDeclarationError("invalid serving declaration") from None
    return ServingDeclaration(copy.deepcopy(value))


def load_serving_declaration(path: str | Path) -> ServingDeclaration:
    from chimeraforge.deployment_verify import _json
    from chimeraforge.plan_bundle import _read

    try:
        return declaration_from_dict(
            _json(_read(Path(path), MAX_DECLARATION_BYTES), MAX_DECLARATION_BYTES)
        )
    except (OSError, ValueError, TypeError, RecursionError):
        raise ServingDeclarationError("invalid serving declaration input") from None


def receive(value: ServingDeclaration | str | Path) -> ServingDeclaration:
    return (
        declaration_from_dict(value.to_dict())
        if isinstance(value, ServingDeclaration)
        else load_serving_declaration(value)
    )


def projection(declaration: ServingDeclaration) -> tuple[ServingTarget, dict]:
    request = declaration.request
    target = ServingTarget(
        request.model,
        request.backend,
        request.dtype,
        request.replicas,
        request.tensor_parallel,
        request.pipeline_parallel,
        request.batch_size,
        request.replicas * request.tensor_parallel * request.pipeline_parallel,
    )
    settings = {
        "mode": "online",
        "context_length": request.context_length,
        "kv_quant": request.kv_quant,
        "prefix_cache_hit_rate": request.prefix_caching,
        "max_num_batched_tokens": request.max_num_batched_tokens,
    }
    return target, settings
