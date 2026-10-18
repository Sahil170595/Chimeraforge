"""Private original-byte prediction evidence bundles using the existing scorer."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
import hashlib
import logging
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar

from chimeraforge.bench.gate_inputs import MAX_RECEIPT_BYTES
from chimeraforge.plan_bundle import PlanBundle, ROLE_PATHS
from chimeraforge.prediction_bundle_inputs import (
    MAX_MANIFEST_BYTES,
    MAX_RECEIPTS,
    POLICY_PATH,
    Transport,
    absolute,
    encode,
    fail,
    manifest,
    plan_source,
    policy_bytes,
    read_directory,
    receipt_path,
    validate,
)
from chimeraforge.prediction_bundle_publication import publish
from chimeraforge.prediction_score import (
    PredictionScorePolicy,
    PredictionScorecard,
    score_predictions,
)

logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")
LIMITS = (
    "PRIVATE HANDOFF: original benchmark and harness bytes may contain private prompts, options, "
    "warnings, provider information or paths. This bundle is not a sanitized public report. "
    "Content integrity does not authenticate inputs, measurements, physical hardware, weights, "
    "independent execution or calibration. Exclusive destination creation and manifest-last "
    "readiness do not provide atomic directory visibility or crash durability. Identity checks "
    "cannot eliminate hostile concurrent rename races. Owner-only mode bits apply where supported; "
    "Windows inherits ordinary ACLs. No upload is performed."
)


def _boundary(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def call(*args: P.args, **kwargs: P.kwargs) -> R:
        from chimeraforge.api import PlanError

        try:
            return function(*args, **kwargs)
        except PlanError as exc:
            logger.warning("prediction bundle operation rejected")
            fail(retained="incomplete destination retained" in str(exc))
        except (OSError, ValueError, TypeError, KeyError, ArithmeticError, RecursionError):
            logger.warning("prediction bundle malformed input or unavailable operation")
            fail()

    return call


@dataclass(frozen=True)
class PredictionBundle:
    """Safe metadata over immutable private bytes; directory labels are never reopened."""

    _directory: Path = field(repr=False)
    _manifest_bytes: bytes = field(repr=False)
    _members: tuple[tuple[str, bytes], ...] = field(repr=False)
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    @_boundary
    def to_dict(self) -> dict:
        outer, total, _ = _scored(self)
        return {
            "schema_version": 1,
            "kind": "chimeraforge.prediction-bundle-verification",
            "status": "verified_content",
            "plan_fingerprint": outer["plan_fingerprint"],
            "manifest_sha256": hashlib.sha256(self._manifest_bytes).hexdigest(),
            "policy_sha256": outer["policy_sha256"],
            "files": outer["files"],
            "receipt_count": sum(row["path"].startswith("receipts/") for row in outer["files"]),
            "transport_bytes": total,
            "private_handoff": True,
            "source_authentication": "unverified",
            "limits": LIMITS,
        }


def _scored(bundle: PredictionBundle) -> tuple[dict, int, PredictionScorecard]:
    outer, plan, policy, receipts, total = validate(bundle)
    return outer, total, score_predictions(plan, [*receipts], policy=policy)


def _score(bundle: PredictionBundle) -> PredictionScorecard:
    return _scored(bundle)[2]


@_boundary
def create_prediction_bundle(
    saved_plan: PlanBundle | str | Path,
    benchmark_paths: list[str | Path],
    *,
    policy: PredictionScorePolicy | dict | str | Path,
    outdir: str | Path,
) -> PredictionBundle:
    from chimeraforge.plan_study import protect_output

    if (
        type(benchmark_paths) is not list
        or len(benchmark_paths) > MAX_RECEIPTS
        or any(not isinstance(path, (str, Path)) for path in benchmark_paths)
    ):
        fail()
    root = absolute(outdir)
    held = Transport()
    plan = plan_source(saved_plan, held)
    policy_raw = policy_bytes(policy, held)
    inputs = dict(plan._input_bytes)
    members = [
        ("plan/manifest.json", plan._manifest_bytes),
        ("plan/plan.json", plan._plan_bytes),
        *(
            ("plan/" + path, inputs[role])
            for role, path in ROLE_PATHS.items()
            if role != "plan" and role in inputs
        ),
        (POLICY_PATH, policy_raw),
    ]
    members.extend(
        (receipt_path(index), held.read(absolute(path), MAX_RECEIPT_BYTES))
        for index, path in enumerate(benchmark_paths)
    )
    outer = {
        "schema_version": 1,
        "kind": "chimeraforge.prediction-bundle",
        "plan_fingerprint": plan._prepare()[0].to_dict()["fingerprint"],
        "policy_sha256": hashlib.sha256(policy_raw).hexdigest(),
        "files": [
            {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
            for path, raw in members
        ],
    }
    manifest_raw = held.charge(encode(outer), MAX_MANIFEST_BYTES)
    manifest(manifest_raw)
    protect_output(root, held.paths)
    bundle = PredictionBundle(root, manifest_raw, tuple(members), tuple(dict.fromkeys(held.paths)))
    _score(bundle)
    publish(root, bundle._members, manifest_raw)
    return bundle


@_boundary
def verify_prediction_bundle(directory: str | Path) -> PredictionBundle:
    root, raw, members = read_directory(directory)
    bundle = PredictionBundle(root, raw, members)
    _score(bundle)
    return bundle


@_boundary
def score_prediction_bundle(bundle: PredictionBundle | str | Path) -> PredictionScorecard:
    if isinstance(bundle, PredictionBundle):
        return _score(bundle)
    root, raw, members = read_directory(bundle)
    return _score(PredictionBundle(root, raw, members))
