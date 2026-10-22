"""Fixed inventory and bounded original-byte capture for private prediction handoffs."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

from chimeraforge.bench.gate_inputs import MAX_POLICY_BYTES, MAX_RECEIPT_BYTES, sha
from chimeraforge.plan_bundle import (
    BUNDLE_VERSION,
    MAX_INPUT_BYTES,
    MAX_MANIFEST_BYTES,
    ROLE_PATHS,
    PlanBundle,
    _artifact,
    _capture_inputs,
    _manifest_rows,
    _plain_path,
    _read,
)
from chimeraforge.prediction_score import (
    MAX_RECEIPTS,
    PredictionScorePolicy,
    _HeldJSON,
    _decode_json,
    _protected,
)

if TYPE_CHECKING:
    from chimeraforge.prediction_bundle import PredictionBundle

MAX_TRANSPORT_BYTES = 32 * 1024 * 1024
BASE_PATHS = ("plan/manifest.json", "plan/plan.json", "plan/corpus.json")
QUALITY_PATH = "plan/quality.json"
POLICY_PATH = "policy.json"
OUTER_FIELDS = {"schema_version", "kind", "plan_fingerprint", "policy_sha256", "files"}


def fail(*, retained: bool = False) -> NoReturn:
    from chimeraforge.api import PlanError

    raise PlanError(
        "invalid prediction bundle" + ("; incomplete destination retained" if retained else "")
    ) from None


def absolute(path: str | Path) -> Path:
    if not isinstance(path, (str, Path)):
        fail()
    return Path(os.path.abspath(path))


def encode(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def receipt_path(index: int) -> str:
    return f"receipts/{index:04d}.json"


def check_inventory(directory: Path, expected: set[str], *, retained: bool = False) -> None:
    """Stream only bounded expected names plus EOF or the first unexpected/duplicate entry."""
    seen: set[str] = set()
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name not in expected or entry.name in seen:
                    fail(retained=retained)
                seen.add(entry.name)
    except OSError:
        fail(retained=retained)
    if seen != expected:
        fail(retained=retained)


def limit_for(logical: str) -> int:
    from chimeraforge.api import MAX_PLAN_BYTES

    if logical in ("manifest.json", "plan/manifest.json"):
        return int(MAX_MANIFEST_BYTES)
    if logical == "plan/plan.json":
        return int(MAX_PLAN_BYTES)
    if logical == POLICY_PATH:
        return int(MAX_POLICY_BYTES)
    return int(
        MAX_INPUT_BYTES if logical in ("plan/corpus.json", QUALITY_PATH) else MAX_RECEIPT_BYTES
    )


class Transport:
    """Charge each occurrence; repeated input paths retain the first bounded bytes."""

    def __init__(self) -> None:
        self.total = 0
        self.paths: list[Path] = []
        self.cache: dict[Path, bytes] = {}

    def charge(self, raw: bytes, limit: int) -> bytes:
        if type(raw) is not bytes or not 0 < len(raw) <= min(
            limit, MAX_TRANSPORT_BYTES - self.total
        ):
            fail()
        self.total += len(raw)
        return raw

    def read(self, path: Path, limit: int, *, package_resource: bool = False) -> bytes:
        path = absolute(path)
        if path in self.cache:
            raw = self.charge(self.cache[path], limit)
        else:
            remaining = min(limit, MAX_TRANSPORT_BYTES - self.total)
            if remaining <= 0:
                fail()
            raw = self.charge(_read(path, remaining, package_resource=package_resource), limit)
            self.cache[path] = raw
        self.paths.append(path)
        return raw


def plan_source(saved: PlanBundle | str | Path, held: Transport) -> PlanBundle:
    if type(saved) is PlanBundle:
        bundle = cast(PlanBundle, saved)
        held.charge(bundle._manifest_bytes, MAX_MANIFEST_BYTES)
        held.charge(bundle._plan_bytes, limit_for("plan/plan.json"))
        if type(bundle._input_bytes) is not tuple:
            fail()
        for role, raw in bundle._input_bytes:
            held.charge(raw, MAX_INPUT_BYTES)
        bundle._prepare()
        manifest = _manifest_rows(bundle._manifest_bytes)
        held.paths.extend([bundle._directory, bundle._directory / "manifest.json"])
        held.paths.extend(bundle._directory / row["path"] for row in manifest["files"])
        return bundle
    root = absolute(saved)
    _plain_path(root)
    if root.is_dir():
        manifest_raw = held.read(root / "manifest.json", MAX_MANIFEST_BYTES)
        manifest = _manifest_rows(manifest_raw)
        members = {
            row["role"]: held.read(root / row["path"], limit_for("plan/" + row["path"]))
            for row in manifest["files"]
        }
        check_inventory(root, {"manifest.json", *(ROLE_PATHS[role] for role in members)})
        result = PlanBundle(root, members.pop("plan"), tuple(members.items()), manifest_raw)
        held.paths.append(root)
    else:
        raw_plan = held.read(root, limit_for("plan/plan.json"))
        artifact = _artifact(raw_plan)
        captured = _capture_inputs(artifact, _reader=held.read)
        members = {"plan": raw_plan, **{role: raw for role, (raw, _) in captured.items()}}
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
                for role, raw in members.items()
            ],
        }
        manifest_raw = held.charge(encode(manifest), MAX_MANIFEST_BYTES)
        result = PlanBundle(
            root.parent,
            raw_plan,
            tuple((role, raw) for role, raw in members.items() if role != "plan"),
            manifest_raw,
        )
    result._prepare()
    return result


def policy_bytes(source: PredictionScorePolicy | dict | str | Path, held: Transport) -> bytes:
    if isinstance(source, (str, Path)):
        return held.read(absolute(source), MAX_POLICY_BYTES)
    data = asdict(source) if type(source) is PredictionScorePolicy else source
    if type(data) is not dict:
        fail()
    return held.charge(encode(data), MAX_POLICY_BYTES)


def manifest(raw: bytes) -> dict:
    data = _decode_json(raw, MAX_MANIFEST_BYTES)
    if (
        set(data) != OUTER_FIELDS
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["kind"] != "chimeraforge.prediction-bundle"
        or not sha(data["plan_fingerprint"])
        or not sha(data["policy_sha256"])
        or type(data["files"]) is not list
        or not 4 <= len(data["files"]) <= 5 + MAX_RECEIPTS
    ):
        fail()
    paths = []
    for row in data["files"]:
        if (
            type(row) is not dict
            or set(row) != {"path", "sha256", "size_bytes"}
            or type(row["path"]) is not str
        ):
            fail()
        paths.append(row["path"])
    prefix = [*BASE_PATHS, *([QUALITY_PATH] if QUALITY_PATH in paths else []), POLICY_PATH]
    count = len(paths) - len(prefix)
    if not 0 <= count <= MAX_RECEIPTS or paths != prefix + [
        receipt_path(index) for index in range(count)
    ]:
        fail()
    for row in data["files"]:
        if (
            not sha(row["sha256"])
            or type(row["size_bytes"]) is not int
            or not 0 < row["size_bytes"] <= limit_for(row["path"])
        ):
            fail()
    if (
        next(row["sha256"] for row in data["files"] if row["path"] == POLICY_PATH)
        != data["policy_sha256"]
    ):
        fail()
    return data


def validate(bundle: PredictionBundle) -> tuple[dict, PlanBundle, _HeldJSON, list[_HeldJSON], int]:
    from chimeraforge.prediction_bundle import PredictionBundle

    if (
        type(bundle) is not PredictionBundle
        or not isinstance(bundle._directory, Path)
        or not bundle._directory.is_absolute()
        or not _protected(bundle._protected_paths)
        or type(bundle._members) is not tuple
    ):
        fail()
    outer = manifest(bundle._manifest_bytes)
    held = Transport()
    held.charge(bundle._manifest_bytes, MAX_MANIFEST_BYTES)
    if len(bundle._members) != len(outer["files"]):
        fail()
    members: dict[str, bytes] = {}
    for pair, row in zip(bundle._members, outer["files"]):
        if type(pair) is not tuple or len(pair) != 2 or pair[0] != row["path"]:
            fail()
        raw = held.charge(pair[1], limit_for(row["path"]))
        if len(raw) != row["size_bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            fail()
        members[pair[0]] = raw
    plan = PlanBundle(
        bundle._directory / "plan",
        members["plan/plan.json"],
        tuple(
            (role, members["plan/" + path])
            for role, path in ROLE_PATHS.items()
            if role != "plan" and "plan/" + path in members
        ),
        members["plan/manifest.json"],
    )
    artifact, _, _ = plan._prepare()
    if artifact.to_dict()["fingerprint"] != outer["plan_fingerprint"]:
        fail()
    protected = tuple(
        dict.fromkeys(
            (
                bundle._directory,
                bundle._directory / "manifest.json",
                *(bundle._directory / path for path in members),
                *bundle._protected_paths,
            )
        )
    )
    policy = _HeldJSON(members[POLICY_PATH], protected)
    receipts = [
        _HeldJSON(members[receipt_path(index)], protected)
        for index in range(sum(path.startswith("receipts/") for path in members))
    ]
    return outer, plan, policy, receipts, held.total


def read_directory(directory: str | Path) -> tuple[Path, bytes, tuple[tuple[str, bytes], ...]]:
    root = absolute(directory)
    _plain_path(root)
    if not root.is_dir():
        fail()
    held = Transport()
    raw = held.read(root / "manifest.json", MAX_MANIFEST_BYTES)
    outer = manifest(raw)
    members = tuple(
        (row["path"], held.read(root / row["path"], limit_for(row["path"])))
        for row in outer["files"]
    )
    expected_root = {"manifest.json", "policy.json", "plan", "receipts"}
    check_inventory(root, expected_root)
    for name in ("plan", "receipts"):
        folder = root / name
        _plain_path(folder)
        if not folder.is_dir():
            fail()
        check_inventory(
            folder, {path.split("/")[1] for path, _ in members if path.startswith(name + "/")}
        )
    return root, raw, members
