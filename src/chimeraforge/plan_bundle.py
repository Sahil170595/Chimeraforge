"""A fixed directory handoff of original plan bytes and bound planner inputs."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
import hashlib
import importlib.resources as resources
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from chimeraforge.planner.models import _models_from_bytes
from chimeraforge.planner.qualityfile import _quality_from_bytes, aggregate
from chimeraforge.planner.replay import digest, json_value
from chimeraforge.planner.service import ConsumedPlanInputs

BUNDLE_VERSION = 1
MAX_MANIFEST_BYTES = 64 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024
ROLE_PATHS = {"plan": "plan.json", "corpus": "corpus.json", "quality": "quality.json"}


def _fail(message):
    from chimeraforge.api import PlanError

    raise PlanError(f"invalid plan bundle: {message}")


def _links(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _plain_path(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            if _links(part):
                _fail("links/reparse points are not supported")


def _read(path: Path, limit: int, *, package_resource: bool = False) -> bytes:
    """Read a bounded regular file once; descriptors disallow link substitution."""
    _plain_path(path)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or (before.st_nlink != 1 and not package_resource)
        or before.st_size > limit
    ):
        _fail("member must be a bounded regular file with no links")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            _fail("member changed during open")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > limit or (after.st_size, after.st_mtime_ns) != (
        before.st_size,
        before.st_mtime_ns,
    ):
        _fail("member exceeds limit or changed during consumption")
    return raw


def _artifact(raw: bytes):
    from chimeraforge.api import MAX_PLAN_BYTES, _unique_object, artifact_from_dict

    if len(raw) > MAX_PLAN_BYTES:
        _fail("plan exceeds size limit")
    return artifact_from_dict(json.loads(raw, object_pairs_hook=_unique_object))


def _required(artifact) -> dict:
    context = artifact.to_dict()["result"].get("replay_context")
    if context is None:
        _fail("legacy plan lacks required consumed-input byte bindings; save a new plan")
    corpus = context["corpus"]["input"]
    if corpus is None:
        _fail("corpus lacks an original byte binding; save a new plan")
    quality = (context["quality"] or {}).get("input")
    if context["quality"] is not None and (quality is None or quality["kind"] != "file"):
        _fail("quality lacks an original file-byte binding; save a new plan")
    if context["contributions"]["records"]:
        _fail(
            "contributions bind semantic records, not original file bytes; "
            "this plan cannot be bundled"
        )
    return {"corpus": corpus, **({"quality": quality} if quality is not None else {})}


def _quality_equivalent(before: dict, after: dict) -> bool:
    """Only the exact, verified harness role may relocate its source labels."""
    expected, current = copy.deepcopy(before), copy.deepcopy(after)
    original, local = expected["input"]["path"], current["input"]["path"]
    expected.pop("input")
    current.pop("input")
    for value, path in ((expected, original), (current, local)):
        rows = [value["aggregate"], *value["scores"]["cells"].values()]
        if any(row["source"] != path for row in rows):
            return False
        for row in rows:
            row["source"] = "verified relocated quality role"
    return expected == current


def _boundary(function):
    """Translate malformed files and bounded I/O into the shared public domain error."""
    from functools import wraps

    @wraps(function)
    def call(*args, **kwargs):
        from chimeraforge.api import PlanError

        try:
            return function(*args, **kwargs)
        except PlanError:
            raise
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise PlanError(f"invalid plan bundle: {exc}") from exc

    return call


def _manifest_rows(raw: bytes) -> dict:
    from chimeraforge.api import MAX_PLAN_BYTES, _unique_object

    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        _fail("manifest bytes exceed limit or have invalid type")
    manifest = json.loads(raw, object_pairs_hook=_unique_object)
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema_version", "plan_fingerprint", "files"}
        or type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != BUNDLE_VERSION
        or not isinstance(manifest["files"], list)
        or not 2 <= len(manifest["files"]) <= len(ROLE_PATHS)
    ):
        _fail("unsupported manifest schema/fields")
    roles = set()
    for row in manifest["files"]:
        if not isinstance(row, dict) or set(row) != {"role", "path", "sha256", "size_bytes"}:
            _fail("invalid manifest member fields")
        role = row["role"]
        if (
            not isinstance(role, str)
            or role not in ROLE_PATHS
            or role in roles
            or row["path"] != ROLE_PATHS[role]
        ):
            _fail("duplicate, unsupported or unsafe logical role/path")
        roles.add(role)
        limit = MAX_PLAN_BYTES if role == "plan" else MAX_INPUT_BYTES
        if type(row["size_bytes"]) is not int or not 0 < row["size_bytes"] <= limit:
            _fail("invalid member size")
        for value in (row["sha256"], manifest["plan_fingerprint"]):
            if (
                type(value) is not str
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                _fail("invalid manifest SHA256")
    if "plan" not in roles:
        _fail("original plan missing")
    return manifest


def _validate_held(bundle) -> dict:
    from chimeraforge.api import MAX_PLAN_BYTES

    if not isinstance(bundle._directory, Path) or not bundle._directory.is_absolute():
        _fail("held bundle location must be an absolute local path")
    if type(bundle._plan_bytes) is not bytes or not 0 < len(bundle._plan_bytes) <= MAX_PLAN_BYTES:
        _fail("held plan exceeds size limit or has invalid type")
    held = {"plan": bundle._plan_bytes}
    if type(bundle._input_bytes) is not tuple:
        _fail("held inputs must be immutable byte tuples")
    for row in bundle._input_bytes:
        if type(row) is not tuple or len(row) != 2:
            _fail("invalid held input entry")
        role, raw = row
        if type(role) is not str or role not in ROLE_PATHS or role in held:
            _fail("duplicate/unsupported held input role")
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_INPUT_BYTES:
            _fail("held input exceeds size limit or has invalid type")
        held[role] = raw
    manifest = _manifest_rows(bundle._manifest_bytes)
    if set(held) != {row["role"] for row in manifest["files"]}:
        _fail("held input membership disagrees with manifest")
    for row in manifest["files"]:
        raw = held[row["role"]]
        if len(raw) != row["size_bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            _fail("held member hash/size mismatch")
    return manifest


@dataclass(frozen=True)
class PlanBundle:
    """Defensive public metadata; consumed bytes stay in private typed state."""

    _directory: Path
    _plan_bytes: bytes = field(repr=False)
    _input_bytes: tuple[tuple[str, bytes], ...] = field(repr=False)
    _manifest_bytes: bytes = field(repr=False)

    @_boundary
    def _prepare(self):
        manifest = _validate_held(self)
        artifact = _artifact(self._plan_bytes)
        if artifact.to_dict()["fingerprint"] != manifest["plan_fingerprint"]:
            _fail("manifest and plan fingerprint disagree")
        bindings = _required(artifact)
        context = artifact.to_dict()["result"]["replay_context"]
        parsed = {}
        relocations = {}
        for role, raw in self._input_bytes:
            binding = bindings[role]
            if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
                _fail(f"{role} bytes disagree with producer binding")
            local_path = self._directory / ROLE_PATHS[role]
            parsed[role] = (
                _models_from_bytes(local_path, raw)
                if role == "corpus"
                else _quality_from_bytes(local_path, raw)
            )
            local = parsed[role]._input_receipt
            if role == "corpus":
                if digest(asdict(parsed[role])) != context[role]["sha256"]:
                    _fail("parsed corpus disagrees with producing coefficient digest")
            else:
                quality = {
                    "input": local,
                    "scores": json_value(parsed[role]),
                    "aggregate": json_value(aggregate(parsed[role])),
                }
                if not _quality_equivalent(context[role], quality):
                    _fail("parsed harness disagrees with producing scores/source")
            relocations[role] = {"state": "verified_content", "producer": binding, "local": local}
        if set(parsed) != set(bindings):
            _fail("required input roles missing")
        return artifact, ConsumedPlanInputs(parsed["corpus"], parsed.get("quality")), relocations

    def to_dict(self) -> dict:
        artifact, _, relocations = self._prepare()
        return {
            "schema_version": BUNDLE_VERSION,
            "directory": str(self._directory),
            "fingerprint": artifact.to_dict()["fingerprint"],
            "manifest": json.loads(self._manifest_bytes),
            "relocations": relocations,
            "source_authentication": "unverified",
            "limits": (
                "Content integrity does not authenticate inputs "
                "or prove served weights/performance."
            ),
        }


@_boundary
def verify(directory: str | Path) -> PlanBundle:
    from chimeraforge.api import MAX_PLAN_BYTES

    root = Path(os.path.abspath(directory))
    _plain_path(root)
    if not root.is_dir():
        _fail("bundle directory is missing")
    manifest_raw = _read(root / "manifest.json", MAX_MANIFEST_BYTES)
    manifest = _manifest_rows(manifest_raw)
    held = {}
    for row in manifest["files"]:
        role = row["role"]
        limit = MAX_PLAN_BYTES if role == "plan" else MAX_INPUT_BYTES
        raw = _read(root / row["path"], limit)
        if len(raw) != row["size_bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            _fail("member hash/size mismatch")
        held[role] = raw
    expected = {"manifest.json", *(ROLE_PATHS[role] for role in held)}
    if {entry.name for entry in root.iterdir()} != expected:
        _fail("extra or missing bundle members")
    artifact = _artifact(held["plan"])
    if artifact.to_dict()["fingerprint"] != manifest["plan_fingerprint"]:
        _fail("manifest and plan fingerprint disagree")
    if set(held) != {"plan", *_required(artifact)}:
        _fail("manifest membership disagrees with required producer inputs")
    result = PlanBundle(root, held.pop("plan"), tuple(held.items()), manifest_raw)
    result._prepare()
    return result


@_boundary
def create(plan_path: str | Path, output_directory: str | Path) -> PlanBundle:
    from chimeraforge.api import MAX_PLAN_BYTES
    from chimeraforge.plan_check import _local_file

    root = Path(os.path.abspath(output_directory))
    _plain_path(root)
    if root.exists():
        _fail("destination must not exist")
    if not root.parent.is_dir():
        _fail("destination parent must exist")
    raw_plan = _read(Path(os.path.abspath(plan_path)), MAX_PLAN_BYTES)
    artifact = _artifact(raw_plan)
    held = {"plan": raw_plan}
    for role, binding in _required(artifact).items():
        if binding["kind"] == "bundled":
            resource = resources.files("chimeraforge.planner").joinpath(
                "data", "fitted_models.json"
            )
            with resources.as_file(resource) as source:
                # SDK-managed package installations may share a hardlinked cache file.
                held[role] = _read(source, MAX_INPUT_BYTES, package_resource=True)
        else:
            source = _local_file(binding)
            if source is None:
                _fail(f"original {role} path is foreign/unavailable; create on producer host")
            held[role] = _read(source, MAX_INPUT_BYTES)
    manifest = {
        "schema_version": BUNDLE_VERSION,
        "plan_fingerprint": artifact.to_dict()["fingerprint"],
        "files": [
            {
                "role": role,
                "path": ROLE_PATHS[role],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
            for role, raw in held.items()
        ],
    }
    manifest_raw = json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8")
    result = PlanBundle(
        root,
        raw_plan,
        tuple((key, raw) for key, raw in held.items() if key != "plan"),
        manifest_raw,
    )
    result._prepare()  # Refuse all unsupported/source mismatches before any write.
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
    try:
        for role, raw in held.items():
            (staging / ROLE_PATHS[role]).write_bytes(raw)
        (staging / "manifest.json").write_bytes(manifest_raw)
        # rename cannot overwrite an existing nonempty directory; recheck empty ones too.
        if root.exists():
            _fail("destination appeared during creation")
        staging.rename(root)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return result


@_boundary
def check(saved: PlanBundle | str | Path):
    from chimeraforge.plan_check import check as check_artifact

    bundle = saved if isinstance(saved, PlanBundle) else verify(saved)
    artifact, consumed, relocations = bundle._prepare()
    return check_artifact(
        artifact,
        _bundle_inputs=consumed,
        _relocations=relocations,
        _bundle_metadata=bundle.to_dict(),
    )
