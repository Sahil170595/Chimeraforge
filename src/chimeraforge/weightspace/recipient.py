"""Execute a standalone linear text classifier in a clean CPU worker."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from .manifest import ManifestError, _load_json, _object, verify_bundle
from .staging import stage_bundle

WORKER_TIMEOUT_SECONDS = 90


@dataclass(frozen=True)
class RecipientPrediction:
    source_manifest_sha256: str
    staged_manifest_sha256: str
    recipient_sha256: str
    class_index: int
    label: str
    logits: tuple[float, ...]
    artifact_bytes: int
    worker_rss_bytes: int

    def to_dict(self) -> dict:
        return {**asdict(self), "logits": list(self.logits)}


def _strings(values: object, field: str) -> list[str]:
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(v, str) and v for v in values)
    ):
        raise ManifestError(f"{field} must be a nonempty array of nonempty strings")
    if len(set(values)) != len(values):
        raise ManifestError(f"{field} contains duplicates")
    return values


def verify_recipient(
    manifest: str | Path,
    text: str,
    root: str | Path | None = None,
    *,
    expected_sha256: str | None = None,
) -> RecipientPrediction:
    """Return CPU logits, class and worker RSS using only the declared staged runtime closure."""
    if not isinstance(text, str):
        raise ManifestError("recipient input must be text")
    with tempfile.TemporaryDirectory(prefix="chimeraforge-recipient-") as scratch:
        staged = stage_bundle(
            manifest, Path(scratch) / "stage", root, expected_sha256=expected_sha256
        )
        directory = Path(staged.directory)
        bundle = verify_bundle(directory / "manifest.json", expected_sha256=staged.manifest_sha256)
        if (
            bundle.codec["id"] != "linear-recipient-v1"
            or not bundle.codec["exact"]
            or bundle.codec["parameters"]
        ):
            raise ManifestError("unsupported recipient codec or parameters")
        roles = {f.role: f for f in bundle.files}
        if set(roles) != {"recipient", "transform", "labels"} or len(roles) != len(bundle.files):
            raise ManifestError("recipient closure requires exactly weights, transform and labels")
        for role, identity in (("transform", "transform"), ("labels", "classes")):
            if bundle.identities.get(identity) != roles[role].sha256:
                raise ManifestError(f"recipient {role} identity mismatch")
        tensors = [t.to_dict() for t in sorted(bundle.tensors, key=lambda t: t.name)]
        identity = hashlib.sha256(
            json.dumps(tensors, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if (
            bundle.identities["target"] != identity
            or bundle.identities.get("recipient") != identity
        ):
            raise ManifestError("recipient logical identity mismatch")
        transform = _object(
            _load_json((directory / roles["transform"].path).read_bytes()), "transform"
        )
        labels = _object(_load_json((directory / roles["labels"].path).read_bytes()), "labels")
        if (
            transform.get("schema") != "word-count-v1"
            or type(transform.get("lowercase")) is not bool
        ):
            raise ManifestError("unsupported recipient feature transform")
        vocabulary = _strings(transform.get("vocabulary"), "vocabulary")
        if any(w.split() != [w] or (transform["lowercase"] and w.lower() != w) for w in vocabulary):
            raise ManifestError("vocabulary tokens must be reachable after the declared transform")
        if labels.get("schema") != "ordered-labels-v1":
            raise ManifestError("unsupported ordered labels")
        request = {
            "weights": roles["recipient"].path,
            "text": text,
            "transform": transform,
            "labels": _strings(labels.get("labels"), "labels"),
            "tensors": tensors,
        }
        try:
            worker = subprocess.run(
                [sys.executable, "-I", str(Path(__file__).with_name("_recipient_worker.py"))],
                cwd=directory,
                input=json.dumps(request).encode(),
                capture_output=True,
                timeout=WORKER_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ManifestError("recipient worker failed to complete") from exc
        if not worker.stdout:
            raise ManifestError("recipient worker failed without a result")
        observed = _object(_load_json(worker.stdout), "worker result")
        if worker.returncode:
            raise ManifestError(str(observed.get("error", "recipient worker failed")))
        return RecipientPrediction(
            staged.source_manifest_sha256,
            staged.manifest_sha256,
            identity,
            observed["class_index"],
            observed["label"],
            tuple(observed["logits"]),
            sum(f.size_bytes for f in bundle.files),
            observed["worker_rss_bytes"],
        )
