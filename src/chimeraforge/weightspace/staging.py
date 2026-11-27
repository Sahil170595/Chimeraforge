"""Stage immutable runtime generations and atomically select a verified generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from .manifest import (
    CHUNK_BYTES,
    SCHEMA,
    ArtifactFile,
    ManifestError,
    VerifiedBundle,
    _digest,
    _load_json,
    _member,
    _object,
    verify_bundle,
)

POINTER = "current.json"
GENERATIONS = "generations"
STAGE_SCHEMA = "weightspace-stage/v1"


@dataclass(frozen=True)
class StagedBundle:
    directory: str
    source_manifest_sha256: str
    manifest_sha256: str
    files: tuple[str, ...]

    def to_dict(self) -> dict:
        return {**asdict(self), "files": list(self.files)}


def _directory(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ManifestError(f"expected a real directory: {path.name}")


def _pointer(directory: Path) -> str:
    ptr = _member(directory, POINTER)
    with ptr.open("rb") as stream:
        data = stream.read(4097)
    if len(data) > 4096:
        raise ManifestError("oversized stage pointer")
    record = _object(_load_json(data), "stage pointer")
    if record.get("schema") != STAGE_SCHEMA:
        raise ManifestError("unrecognized stage pointer")
    return _digest(record.get("manifest_sha256"), "stage pointer")


def _verify_generation(manifest: Path, digest: str) -> None:
    bundle = verify_bundle(manifest, expected_sha256=digest)
    directory = manifest.parent
    contents: dict[Path, set[str]] = {directory: {"manifest.json"}}
    for item in bundle.files:
        parent = directory
        for part in item.path.split("/"):
            contents.setdefault(parent, set()).add(part)
            parent = parent / part
    for parent, expected in contents.items():
        _directory(parent)
        if {p.name for p in parent.iterdir()} != expected:
            raise ManifestError("unexpected or missing entries in staged generation")


def current_bundle(destination: str | Path) -> Path:
    """Return the verified manifest in the generation selected by the stage pointer."""
    directory = Path(destination)
    try:
        _directory(directory)
        digest = _pointer(directory)
        manifest = _member(directory, f"{GENERATIONS}/{digest}/manifest.json")
        _verify_generation(manifest, digest)
        return manifest
    except OSError as exc:
        raise ManifestError("cannot resolve the current staged generation") from exc


def _initialize(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    _directory(directory)
    for child in directory.iterdir():
        if child.name == POINTER:
            _pointer(directory)
        elif child.name != GENERATIONS:
            raise ManifestError("destination contains files outside the staging store")
    generations = directory / GENERATIONS
    generations.mkdir(exist_ok=True)
    _directory(generations)
    return generations


def _copy_verified(root: Path, target: Path, item: ArtifactFile) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with _member(root, item.path).open("rb") as source, target.open("xb") as output:
        while chunk := source.read(CHUNK_BYTES):
            size += len(chunk)
            if size > item.size_bytes:
                raise ManifestError(f"source size changed during staging: {item.path}")
            digest.update(chunk)
            output.write(chunk)
    if size != item.size_bytes or digest.hexdigest() != item.sha256:
        raise ManifestError(f"source changed during staging: {item.path}")


def _runtime_manifest(verified: VerifiedBundle, files: list[ArtifactFile]) -> bytes:
    body = {
        "schema": SCHEMA,
        "codec": verified.codec,
        "identities": verified.identities,
        "files": [item.to_dict() for item in files],
        "tensors": [item.to_dict() for item in verified.tensors],
        "metadata": verified.metadata,
    }
    return (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()


def stage_bundle(
    manifest: str | Path,
    destination: str | Path,
    root: str | Path | None = None,
    *,
    expected_sha256: str | None = None,
) -> StagedBundle:
    """Stage verified load/inference files and change current.json after all copies succeed."""
    path = Path(manifest)
    verified = verify_bundle(path, root, expected_sha256=expected_sha256)
    members = [item for item in verified.files if {"load", "inference"}.intersection(item.phases)]
    if not members:
        raise ManifestError("no runtime files to stage; materialize the target first")
    if any(item.path.split("/")[0].casefold() == "manifest.json" for item in members):
        raise ManifestError("runtime file collides with staged manifest.json")
    body = _runtime_manifest(verified, members)
    digest = hashlib.sha256(body).hexdigest()
    directory = Path(destination).absolute()
    src = Path(root) if root is not None else path.parent
    if src.resolve().is_relative_to(directory.resolve()) or path.resolve().is_relative_to(
        directory.resolve()
    ):
        raise ManifestError("staging store overlaps source inputs")
    try:
        generations = _initialize(directory)
        published = generations / digest
        with tempfile.TemporaryDirectory(prefix=".stage-", dir=generations) as scratch:
            tempdir = Path(scratch)
            if not published.exists():
                new = tempdir / "generation"
                new.mkdir()
                for item in members:
                    _copy_verified(src, new / item.path, item)
                (new / "manifest.json").write_bytes(body)
                _verify_generation(new / "manifest.json", digest)
                try:
                    new.rename(published)
                except OSError:
                    if not published.is_dir():
                        raise
            # An existing generation may belong to a concurrent writer.
            finished = _member(directory, f"{GENERATIONS}/{digest}/manifest.json")
            _verify_generation(finished, digest)
            pointer = {"schema": STAGE_SCHEMA, "manifest_sha256": digest}
            temp_pointer = tempdir / "pointer.json"
            temp_pointer.write_bytes(json.dumps(pointer).encode())
            os.replace(temp_pointer, directory / POINTER)
    except OSError as exc:
        raise ManifestError("unable to publish runtime generation") from exc
    return StagedBundle(
        str(published), verified.manifest_sha256, digest, tuple(i.path for i in members)
    )
