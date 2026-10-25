"""Bounded offline consistency checks against independently supplied render intent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Literal, NoReturn, cast

from chimeraforge import __version__
from chimeraforge.api import MAX_PLAN_BYTES, PlanArtifact, PlanError, artifact_from_dict
from chimeraforge.deploy import (
    DeploymentError,
    MAX_EXPORT_GPUS_PER_REPLICA,
    MAX_GPU_IDENTIFIER_CHARS,
    export_deployment,
)
from chimeraforge.plan_bundle import _plain_path, _read
from chimeraforge.planner.constants import MAX_REPLICAS

MAX_CONFIG_BYTES = 2 * 1024 * 1024
MAX_COMPANION_BYTES = 64 * 1024
MAX_TOTAL_BYTES = MAX_PLAN_BYTES + 2 * MAX_CONFIG_BYTES + 2 * MAX_COMPANION_BYTES
MAX_JSON_NODES = 100_000
MAX_JSON_DEPTH = 64
MAX_JSON_INTEGER_BITS = 4096
MAX_INTENT_CHARS = 4096
MAX_CHANGES = 64


class DeploymentVerificationError(ValueError):
    """Input is invalid, unsafe, unavailable or outside bounded verifier scope."""


@dataclass(frozen=True)
class DeploymentChange:
    """Only expected-renderer paths and categories; never actual values or keys."""

    path: str
    category: str
    count: int = 1


@dataclass(frozen=True)
class DeploymentCompanion:
    name: str
    state: Literal["match", "missing", "drift"]
    expected_sha256: str
    actual_sha256: str | None


@dataclass(frozen=True)
class DeploymentVerification:
    status: Literal["match", "drift"]
    exit_code: Literal[0, 5]
    renderer_version: str
    backend: str
    source_kind: Literal["file_bytes", "artifact_snapshot"]
    plan_sha256: str
    config_sha256: str
    expected_config_sha256: str
    changes: tuple[DeploymentChange, ...]
    change_count: int
    changes_truncated: bool
    companions: tuple[DeploymentCompanion, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fail(message: str) -> NoReturn:
    raise DeploymentVerificationError(message)


def _admit(value: object, byte_limit: int) -> None:
    """Bound references before copying/encoding; shared subtrees count repeatedly."""
    stack: list[tuple[object, int]] = [(value, 0)]
    nodes, scalar_bytes = 0, 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            _fail("JSON node/depth limit exceeded")
        if type(item) is dict:
            children = 2 * len(item)
            if children > MAX_JSON_NODES - nodes - len(stack):
                _fail("JSON node limit exceeded")
            for key, child in item.items():
                if type(key) is not str:
                    _fail("JSON object keys must be strings")
                stack.append((key, depth + 1))
                stack.append((child, depth + 1))
        elif type(item) is list:
            if len(item) > MAX_JSON_NODES - nodes - len(stack):
                _fail("JSON node limit exceeded")
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            if len(item) > byte_limit:
                _fail("JSON string byte limit exceeded")
            scalar_bytes += len(item.encode("utf-8"))
        elif type(item) is int:
            if item.bit_length() > MAX_JSON_INTEGER_BITS:
                _fail("JSON integer limit exceeded")
            scalar_bytes += max(1, item.bit_length() // 3 + 1)
        elif type(item) is float:
            if not math.isfinite(item):
                _fail("JSON numbers must be finite")
            scalar_bytes += 32
        elif item is not None and type(item) is not bool:
            _fail("unsupported JSON value type")
        if scalar_bytes > byte_limit:
            _fail("JSON scalar byte limit exceeded")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON object key")
        result[key] = value
    return result


def _constant(_: str) -> None:
    _fail("JSON numbers must be finite")


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        _fail("JSON numbers must be finite")
    return value


def _json(raw: bytes, limit: int) -> dict[str, Any]:
    if not 0 < len(raw) <= limit:
        _fail("JSON byte limit exceeded")
    data = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=_constant,
        parse_float=_float,
    )
    if type(data) is not dict:
        _fail("JSON root must be an object")
    _admit(data, limit)
    return cast(dict[str, Any], data)


def _absolute(value: str | Path) -> Path:
    if not isinstance(value, (str, Path)):
        _fail("expected a file path")
    text = str(value)
    if not text or len(text) > MAX_INTENT_CHARS or any(ord(c) < 32 for c in text):
        _fail("file path exceeds verifier bounds")
    # Resolving first would hide links from the native regular-file guard.
    return Path(os.path.abspath(text))


def _aliases(paths: list[Path]) -> None:
    names = [os.path.normcase(str(path)) for path in paths]
    if len(set(names)) != len(names):
        _fail("verification input paths must not alias")
    identities = set()
    for path in paths:
        _plain_path(path)
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        identity = (info.st_dev, info.st_ino)
        if identity in identities:
            _fail("verification input file identities must not alias")
        identities.add(identity)


def _source(saved: PlanArtifact | str | Path) -> tuple[PlanArtifact, bytes, Path | None]:
    source_path = None
    if type(saved) is PlanArtifact:
        _admit(saved._data, MAX_PLAN_BYTES)
        raw = json.dumps(saved._data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    elif isinstance(saved, (str, Path)):
        source_path = _absolute(saved)
        raw = _read(source_path, MAX_PLAN_BYTES)
    else:
        _fail("expected an original saved plan or PlanArtifact")
    return artifact_from_dict(_json(raw, MAX_PLAN_BYTES)), raw, source_path


def _intent(
    image: str,
    model: str | None,
    index: int,
    devices: list[str] | None,
    groups: list[list[str]] | None,
    ports: list[int] | None,
) -> None:
    for text in (image, model):
        if text is not None and (type(text) is not str or len(text) > MAX_INTENT_CHARS):
            _fail("render text exceeds verifier bounds")
    if type(image) is not str or type(index) is not int or not 0 <= index < MAX_JSON_NODES:
        _fail("invalid render selection")
    if devices is not None:
        if type(devices) is not list or len(devices) > MAX_EXPORT_GPUS_PER_REPLICA:
            _fail("device selection exceeds verifier bounds")
        if any(type(x) is not str or len(x) > MAX_GPU_IDENTIFIER_CHARS for x in devices):
            _fail("device identifier exceeds verifier bounds")
    if groups is not None:
        if type(groups) is not list or len(groups) > MAX_REPLICAS:
            _fail("replica selection exceeds verifier bounds")
        for group in groups:
            _intent(image, model, index, group, None, None)
    if ports is not None and (type(ports) is not list or len(ports) > MAX_REPLICAS):
        _fail("replica port selection exceeds verifier bounds")


def _budget(*buffers: bytes) -> None:
    if sum(len(raw) for raw in buffers) > MAX_TOTAL_BYTES:
        _fail("cumulative held-byte limit exceeded")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pointer(parent: str, key: str | int) -> str:
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _differences(expected: dict, actual: dict) -> tuple[list[DeploymentChange], int, bool]:
    changes: list[DeploymentChange] = []
    count, truncated = 0, False

    def emit(path: str, category: str, number: int = 1) -> None:
        nonlocal count, truncated
        count += number
        if len(changes) < MAX_CHANGES:
            changes.append(DeploymentChange(path, category, number))
        else:
            truncated = True

    pending: list[tuple[str, Any, Any]] = [("", expected, actual)]
    while pending:
        path, before, after = pending.pop()
        if type(before) is not type(after):
            emit(path, "type")
        elif type(before) is dict:
            extras = sum(key not in before for key in after)
            if extras:
                emit(path, "extra_keys", extras)
            for key in reversed(before):
                if key not in after:
                    emit(_pointer(path, key), "missing_key")
                else:
                    pending.append((_pointer(path, key), before[key], after[key]))
        elif type(before) is list:
            if len(before) != len(after):
                emit(path, "array_length", abs(len(before) - len(after)))
            for index in reversed(range(min(len(before), len(after)))):
                pending.append((_pointer(path, index), before[index], after[index]))
        elif before != after:
            emit(path, "value")
    return changes, count, truncated


def verify_deployment(
    saved: PlanArtifact | str | Path,
    config_path: str | Path,
    *,
    image: str,
    model: str | None = None,
    candidate_index: int = 0,
    gpu_devices: list[str] | None = None,
    host_port: int | None = None,
    replica_gpu_devices: list[list[str]] | None = None,
    replica_host_ports: list[int] | None = None,
) -> DeploymentVerification:
    """Compare held JSON/required siblings with current-renderer independent intent."""
    try:
        _intent(image, model, candidate_index, gpu_devices, replica_gpu_devices, replica_host_ports)
        config = _absolute(config_path)
        artifact, source_raw, source_path = _source(saved)
        _aliases([config, *([source_path] if source_path else [])])
        row = artifact.candidate(candidate_index)
        spec = artifact.spec(row.model)
        for text in (row.model, spec.name if spec else None):
            if text is not None and len(text) > MAX_INTENT_CHARS:
                _fail("saved serving identity exceeds verifier bounds")
        expected = export_deployment(
            artifact,
            format="compose",
            image=image,
            model=model,
            candidate_index=candidate_index,
            gpu_devices=gpu_devices,
            host_port=host_port,
            replica_gpu_devices=replica_gpu_devices,
            replica_host_ports=replica_host_ports,
        )
        expected_raw = expected.content.encode("utf-8")
        expected_data = _json(expected_raw, MAX_CONFIG_BYTES)
        actual_raw = _read(config, MAX_CONFIG_BYTES)
        actual_data = _json(actual_raw, MAX_CONFIG_BYTES)
        buffers = [source_raw, expected_raw, actual_raw]
        _budget(*buffers)
        companions: list[DeploymentCompanion] = []
        if expected.files and set(expected.files) != {"Modelfile"}:
            _fail("renderer companion set is unsupported")
        for name, content in expected.files.items():
            path = config.parent / name
            _aliases([config, path, *([source_path] if source_path else [])])
            companion_expected = content.encode("utf-8")
            if len(companion_expected) > MAX_COMPANION_BYTES:
                _fail("expected companion exceeds byte limit")
            try:
                companion_actual = _read(path, MAX_COMPANION_BYTES)
            except FileNotFoundError:
                companion_actual = None
            buffers.extend([companion_expected, companion_actual or b""])
            _budget(*buffers)
            state: Literal["match", "missing", "drift"] = (
                "missing"
                if companion_actual is None
                else "match"
                if companion_actual == companion_expected
                else "drift"
            )
            companions.append(
                DeploymentCompanion(
                    name,
                    state,
                    _sha(companion_expected),
                    _sha(companion_actual) if companion_actual is not None else None,
                )
            )
        changes, count, truncated = _differences(expected_data, actual_data)
        for companion in companions:
            if companion.state != "match":
                count += 1
                if len(changes) < MAX_CHANGES:
                    changes.append(DeploymentChange("/companions/Modelfile", companion.state))
                else:
                    truncated = True
        return DeploymentVerification(
            "drift" if count else "match",
            5 if count else 0,
            __version__,
            expected.backend,
            "file_bytes" if source_path is not None else "artifact_snapshot",
            _sha(source_raw),
            _sha(actual_raw),
            _sha(expected_raw),
            tuple(changes),
            count,
            truncated,
            tuple(companions),
        )
    except DeploymentVerificationError:
        raise
    except (
        PlanError,
        DeploymentError,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ):
        # Native/parser errors may contain private keys, identities or paths.
        raise DeploymentVerificationError("invalid deployment verification input") from None
