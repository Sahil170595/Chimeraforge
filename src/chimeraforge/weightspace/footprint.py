"""Calculate artifact storage and declared materialization costs from a verified bundle."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import prod
from pathlib import Path

from .manifest import (
    DTYPE_BYTES,
    ManifestError,
    VerifiedBundle,
    _count,
    _digest,
    _object,
    verify_bundle,
)


@dataclass(frozen=True)
class Footprint:
    manifest_sha256: str
    cold_transfer_bytes: int
    additional_transfer_bytes: int
    unique_on_disk_bytes: int
    materialized_weight_bytes: int
    auxiliary_resident_bytes: int | None
    unknown_auxiliaries: tuple[str, ...]
    staging_bytes: int
    runtime_workspace_bytes: int | None

    def to_dict(self) -> dict:
        return {**asdict(self), "unknown_auxiliaries": list(self.unknown_auxiliaries)}


def _materialized(bundle: VerifiedBundle) -> int:
    aliases = _object(bundle.metadata.get("tensor_aliases", {}), "metadata.tensor_aliases")
    tensors = {t.name: t for t in bundle.tensors}
    for name, target in aliases.items():
        if (
            name not in tensors
            or not isinstance(target, str)
            or target not in tensors
            or target in aliases
        ):
            raise ManifestError(f"invalid direct tensor alias: {name}")
        left, right = tensors[name], tensors[target]
        if (left.dtype, left.shape, left.sha256) != (right.dtype, right.shape, right.sha256):
            raise ManifestError(f"aliased tensors differ: {name}")
    return sum(
        DTYPE_BYTES[t.dtype] * prod(t.shape) for name, t in tensors.items() if name not in aliases
    )


def _auxiliaries(bundle: VerifiedBundle) -> tuple[int | None, tuple[str, ...]]:
    # A distinct runtime component can use memory even if it shares its file bytes with another.
    auxiliaries = {
        f.path for f in bundle.files if "inference" in f.phases and f.role != "recipient"
    }
    values = _object(bundle.metadata.get("resident_bytes", {}), "metadata.resident_bytes")
    if set(values) - auxiliaries:
        raise ManifestError("resident_bytes names a file outside the inference auxiliaries")
    unknown = tuple(sorted(path for path in auxiliaries if values.get(path) is None))
    known = sum(_count(size, path) for path, size in values.items() if size is not None)
    return (None if unknown else known), unknown


def estimate_footprint(
    manifest: str | Path,
    root: str | Path | None = None,
    *,
    expected_sha256: str | None = None,
    cached_sha256: Iterable[str] = (),
) -> Footprint:
    """Verify the bundle and count physical storage, logical tensors and declared overheads."""
    bundle = verify_bundle(manifest, root, expected_sha256=expected_sha256)
    cache = {_digest(d, "cached file") for d in cached_sha256}
    all_files = {f.sha256: f.size_bytes for f in bundle.files}
    deployment = {f.sha256: f.size_bytes for f in bundle.files if set(f.phases) != {"build"}}
    cold = sum(deployment.values())
    weight_bytes = _materialized(bundle)
    auxiliary, missing = _auxiliaries(bundle)
    workspace = bundle.metadata.get("runtime_workspace_bytes")
    if workspace is not None:
        workspace = _count(workspace, "runtime_workspace_bytes")
    # If a decode is requested, the decoded contiguous target must coexist with source bytes.
    decoded = any("decode" in f.phases for f in bundle.files)
    return Footprint(
        bundle.manifest_sha256,
        cold,
        sum(n for h, n in deployment.items() if h not in cache),
        sum(all_files.values()),
        weight_bytes,
        auxiliary,
        missing,
        cold + (weight_bytes if decoded else 0),
        workspace,
    )
