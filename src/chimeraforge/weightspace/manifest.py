"""Validate the version-one deployment sidecar and hash its local files."""

from __future__ import annotations

import hashlib
import json
import os
import math
from pathlib import Path, PureWindowsPath
import re
import stat
from dataclasses import dataclass
from typing import Any

SCHEMA = "weightspace-manifest/v1"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
ROLES = {
    "base",
    "payload",
    "recipient",
    "decoder",
    "adapter",
    "config",
    "transform",
    "labels",
    "tokenizer",
    "auxiliary",
    "donor",
}
PHASES = {"build", "decode", "load", "inference"}
DTYPE_BYTES = {
    "BOOL": 1,
    "I8": 1,
    "U8": 1,
    "I16": 2,
    "U16": 2,
    "F16": 2,
    "BF16": 2,
    "I32": 4,
    "U32": 4,
    "F32": 4,
    "I64": 8,
    "U64": 8,
    "F64": 8,
}


class ManifestError(ValueError):
    """The manifest or an artifact failed local verification."""


def _fail_constant(value: str):
    raise ManifestError(f"non-finite JSON number: {value}")


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ManifestError("non-finite JSON number")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(data: bytes) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_finite_float,
            parse_constant=_fail_constant,
        )
    except ManifestError:
        raise
    except (ValueError, RecursionError) as exc:
        raise ManifestError("invalid UTF-8 JSON") from exc


def _object(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list:
    if not isinstance(value, list):
        raise ManifestError(f"{label} must be an array")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ManifestError(f"invalid SHA-256 for {label}")
    return value


def _count(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ManifestError(f"{label} must be a nonnegative integer")
    return value


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError("expected a portable relative file path")
    parts = value.split("/")
    if any(
        part in {"", ".", ".."}
        or part.endswith((" ", "."))
        or PureWindowsPath(part).is_reserved()
        or any(ord(c) < 32 or c in '<>:"\\|?*' for c in part)
        for part in parts
    ):
        raise ManifestError(f"invalid relative file path: {value!r}")
    return value


@dataclass(frozen=True)
class ArtifactFile:
    path: str
    role: str
    phases: tuple[str, ...]
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict:
        return {**vars(self), "phases": list(self.phases)}


@dataclass(frozen=True)
class LogicalTensor:
    name: str
    dtype: str
    shape: tuple[int, ...]
    sha256: str

    def to_dict(self) -> dict:
        return {**vars(self), "shape": list(self.shape)}


@dataclass(frozen=True)
class VerifiedBundle:
    manifest_sha256: str
    codec: dict
    identities: dict[str, str]
    files: tuple[ArtifactFile, ...]
    tensors: tuple[LogicalTensor, ...]
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "status": "verified",
            "manifest_sha256": self.manifest_sha256,
            "codec": self.codec,
            "declared_identities": self.identities,
            "files": [f.to_dict() for f in self.files],
            "declared_tensors": [t.to_dict() for t in self.tensors],
        }


def _file(value: Any) -> ArtifactFile:
    data = _object(value, "file")
    path = _path(data.get("path"))
    role = data.get("role")
    if not isinstance(role, str) or role not in ROLES:
        raise ManifestError(f"unsupported role for {path}")
    phases = _array(data.get("phases"), "phases")
    if (
        not phases
        or any(not isinstance(p, str) or p not in PHASES for p in phases)
        or len(set(phases)) != len(phases)
    ):
        raise ManifestError(f"invalid phases for {path}")
    return ArtifactFile(
        path,
        role,
        tuple(phases),
        _count(data.get("size_bytes"), path),
        _digest(data.get("sha256"), path),
    )


def _tensor(value: Any) -> LogicalTensor:
    data = _object(value, "tensor")
    name, dtype = data.get("name"), data.get("dtype")
    if not isinstance(name, str) or not name or name == "__metadata__":
        raise ManifestError("invalid logical tensor name")
    if not isinstance(dtype, str) or dtype not in DTYPE_BYTES:
        raise ManifestError(f"unsupported logical dtype for {name}")
    shape = tuple(_count(n, name) for n in _array(data.get("shape"), name))
    return LogicalTensor(name, dtype, shape, _digest(data.get("sha256"), name))


def _member(root: Path, relative: str) -> Path:
    path = root
    for part in relative.split("/"):
        path = path / part
        info = path.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ManifestError(f"linked bundle path is unsupported: {relative}")
    if not stat.S_ISREG(info.st_mode):
        raise ManifestError(f"expected a regular bundle file: {relative}")
    return path


def _check_file(root: Path, item: ArtifactFile) -> None:
    try:
        path = _member(root, item.path)
        with path.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size != item.size_bytes:
                raise ManifestError(f"size mismatch: {item.path}")
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise ManifestError(f"cannot read bundle file: {item.path}") from exc
    if actual != item.sha256:
        raise ManifestError(f"SHA-256 mismatch: {item.path}")


def verify_bundle(
    manifest: str | Path, root: str | Path | None = None, *, expected_sha256: str | None = None
) -> VerifiedBundle:
    """Verify declared physical files relative to root (default: the manifest directory)."""
    path = Path(manifest)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise ManifestError("cannot read weight-space manifest") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest exceeds size limit")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != _digest(expected_sha256, "manifest"):
        raise ManifestError("manifest SHA-256 mismatch")
    data = _object(_load_json(raw), "manifest")
    if data.get("schema") != SCHEMA:
        raise ManifestError("unsupported weight-space manifest schema")
    codec = _object(data.get("codec"), "codec")
    if not isinstance(codec.get("id"), str) or not re.fullmatch(
        r"[a-z][a-z0-9-]*-v[1-9][0-9]*", codec["id"]
    ):
        raise ManifestError("expected a versioned codec ID")
    if type(codec.get("exact")) is not bool:
        raise ManifestError("codec.exact must be boolean")
    _object(codec.get("parameters"), "codec.parameters")
    identities = {
        k: _digest(v, k) for k, v in _object(data.get("identities"), "identities").items()
    }
    if "target" not in identities:
        raise ManifestError("identities.target is required")
    files = tuple(_file(v) for v in _array(data.get("files"), "files"))
    if not files or len({f.path.casefold() for f in files}) != len(files):
        raise ManifestError("empty inventory or duplicate file paths")
    tensors = tuple(_tensor(v) for v in _array(data.get("tensors"), "tensors"))
    if len({t.name for t in tensors}) != len(tensors):
        raise ManifestError("duplicate logical tensor names")
    metadata = _object(data.get("metadata", {}), "metadata")
    for item in files:
        _check_file(Path(root) if root is not None else path.parent, item)
    return VerifiedBundle(digest, codec, identities, files, tensors, metadata)
