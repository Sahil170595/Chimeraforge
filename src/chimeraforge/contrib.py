"""Contributed measurements: a fingerprinted, quarantined exchange format.

First step of the federated corpus. A contribution is one ``bench`` result with
the full environment it ran in and a content hash, exported so another user can
import it. Imports land in a local quarantine that is never blended into the
bundled corpus or the ``measure`` corpus. ``plan --contributions`` reads it only
when asked, for an exact (model, engine, quant, GPU) match, and labels the number
``contributed`` with the ids it came from.

What the hash is and is not: it proves the file is unaltered since export. It does
not prove who ran the benchmark or that the numbers are real, and nothing here
claims otherwise -- which is why imported numbers stay quarantined and labelled.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import statistics
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CONTRIBUTION_KIND = "chimeraforge-contribution"
SCHEMA_VERSION = 1
SUMMARY_DECIMALS = 4
SUMMARY_TOLERANCE = 0.5 * 10**-SUMMARY_DECIMALS + 1e-12
# The methodology every bundled row follows is 3-5 runs per config; fewer cannot
# show whether a number is stable.
MIN_RUNS = 3
# The same methodology targets CV < 5%. Above it a result is flagged, not dropped:
# an outlier published with its flag is evidence, one silently removed is not.
UNSTABLE_CV = 0.05
FINGERPRINT_FIELDS = (
    "gpu_name",
    "gpu_memory_gb",
    "gpu_driver",
    "cuda_version",
    "os",
    "platform",
    "backend_name",
    "backend_version",
    "chimeraforge_version",
)
ATTESTATION_NOTE = (
    "unsigned: the id is a SHA-256 of the fingerprint and measurements, so it proves "
    "the file is unaltered since export; it does not prove who ran it or that the "
    "numbers are real"
)


class ContribError(ValueError):
    """A contribution cannot be built, verified or imported."""


def quarantine_dir() -> Path:
    """Where imported contributions live (override the root with CHIMERAFORGE_CACHE)."""
    base = os.environ.get("CHIMERAFORGE_CACHE")
    root = Path(base) if base else Path.home() / ".cache" / "chimeraforge"
    return root / "contributions"


def _content_id(fingerprint: dict, measurements: dict) -> str:
    try:
        canonical = json.dumps(
            {"fingerprint": fingerprint, "measurements": measurements},
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise ContribError(f"contribution content cannot be encoded as JSON: {exc}") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_json_file(path: str | Path) -> object:
    """Read an exchange file, reporting malformed encoding and JSON as contribution errors."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContribError(f"could not read {path}: {exc}") from exc
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as exc:
        # JSON's integer conversion limit raises ValueError outside JSONDecodeError.
        raise ContribError(f"could not read {path}: invalid JSON: {exc}") from exc


def _number(value: object, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContribError(f"{field} must be a finite number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ContribError(f"{field} must be finite") from exc
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise ContribError(
            f"{field} must be finite and {'positive' if positive else 'nonnegative'}"
        )
    return number


def _text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContribError(f"{field} must be a nonempty string")


def _samples(value: object, field: str, *, positive: bool = False) -> list[float]:
    if not isinstance(value, list):
        raise ContribError(f"{field} must be a list of samples")
    return [_number(sample, field, positive=positive) for sample in value]


def _instability_flags(cv: float) -> list[str]:
    if cv <= UNSTABLE_CV:
        return []
    return [
        f"unstable: decode CV {cv:.1%} exceeds the {UNSTABLE_CV:.0%} methodology target; "
        "kept and flagged, not dropped"
    ]


def _decode_summary(decode: list[float]) -> tuple[float, float]:
    try:
        mean = statistics.fmean(decode)
        cv = statistics.stdev(decode) / mean
    except (OverflowError, ValueError) as exc:
        raise ContribError("decode samples cannot produce finite summary statistics") from exc
    _number(mean, "decode_tps_mean", positive=True)
    _number(cv, "decode_tps_cv")
    return mean, cv


def _validate_fingerprint(fp: dict) -> None:
    from chimeraforge.planner.constants import BACKENDS, QUANT_BPW

    for field in (
        *FINGERPRINT_FIELDS,
        "model",
        "backend",
        "quant",
        "context_length",
        "workload",
    ):
        if field not in fp:
            raise ContribError(f"fingerprint.{field} is required")
    for field in (
        "gpu_name",
        "os",
        "platform",
        "backend_name",
        "chimeraforge_version",
        "model",
        "workload",
    ):
        _text(fp[field], f"fingerprint.{field}")
    for field in ("gpu_driver", "cuda_version", "backend_version"):
        if fp[field] is not None:
            _text(fp[field], f"fingerprint.{field}")
    if fp["gpu_memory_gb"] is not None:
        _number(fp["gpu_memory_gb"], "fingerprint.gpu_memory_gb", positive=True)
    if not isinstance(fp["backend"], str) or fp["backend"] not in BACKENDS:
        raise ContribError("fingerprint.backend must name a supported backend")
    if fp["backend_name"] != fp["backend"]:
        raise ContribError("fingerprint.backend_name must match backend")
    if not isinstance(fp["quant"], str) or fp["quant"] not in QUANT_BPW:
        raise ContribError(
            "fingerprint.quant must be explicitly known; label the served artifact with --quant"
        )
    if (
        isinstance(fp["context_length"], bool)
        or not isinstance(fp["context_length"], int)
        or fp["context_length"] <= 0
    ):
        raise ContribError("fingerprint.context_length must be a positive integer")


def _validate_measurements(m: dict) -> float:
    decode = _samples(m.get("decode_tps"), "decode_tps", positive=True)
    if len(decode) < MIN_RUNS:
        raise ContribError(f"{len(decode)} runs; a contribution needs at least {MIN_RUNS}")
    ttft = _samples(m.get("ttft_ms"), "ttft_ms")
    if len(ttft) != len(decode):
        raise ContribError("ttft_ms must contain one sample per decode run")
    mean, cv = _decode_summary(decode)
    for field, expected in (("decode_tps_mean", mean), ("decode_tps_cv", cv)):
        actual = _number(m.get(field), field, positive=field == "decode_tps_mean")
        if not math.isclose(actual, expected, rel_tol=0, abs_tol=SUMMARY_TOLERANCE):
            raise ContribError(f"{field} disagrees with the decode samples")
    _text(m.get("measured_at"), "measured_at")
    try:
        timestamp = datetime.fromisoformat(m["measured_at"])
    except ValueError as exc:
        raise ContribError("measured_at must be an ISO timestamp with timezone") from exc
    if timestamp.tzinfo is None:
        raise ContribError("measured_at must include its timezone")
    return cv


def build_contribution(result: dict) -> dict:
    """One ``bench`` result (as ``result_to_dict`` writes it) -> a contribution.

    Raises:
        ContribError: no GPU name (the number cannot be attributed to hardware),
            or fewer than MIN_RUNS runs.
    """
    if not isinstance(result, dict):
        raise ContribError("bench result must be an object")
    env = result.get("environment") or {}
    if not isinstance(env, dict):
        raise ContribError("bench environment must be an object")
    if not env.get("gpu_name"):
        raise ContribError(
            "the bench result names no GPU, so its numbers cannot be attributed to "
            "hardware; re-run bench where NVML can read the device"
        )
    warnings = result.get("warnings") or []
    if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
        raise ContribError("bench warnings must be strings")
    if any("recorded but NOT applied" in warning for warning in warnings):
        raise ContribError(
            "quant was recorded but NOT applied; benchmark an explicitly served quantized artifact"
        )
    runs = result.get("individual_runs") or []
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ContribError("individual_runs must be a list of run objects")
    decode = [_number(r.get("throughput_tps"), "decode_tps", positive=True) for r in runs]
    if len(decode) < MIN_RUNS:
        raise ContribError(f"{len(decode)} runs; a contribution needs at least {MIN_RUNS}")
    ttft = [_number(r.get("ttft_ms"), "ttft_ms") for r in runs]
    fingerprint = {k: env.get(k) for k in FINGERPRINT_FIELDS}
    fingerprint.update(
        model=result.get("model"),
        backend=result.get("backend"),
        quant=result.get("quant"),
        context_length=result.get("context_length"),
        workload=result.get("workload"),
    )
    _validate_fingerprint(fingerprint)
    mean, cv = _decode_summary(decode)
    measurements = {
        "decode_tps": decode,
        "ttft_ms": ttft,
        "decode_tps_mean": round(mean, SUMMARY_DECIMALS),
        "decode_tps_cv": round(cv, SUMMARY_DECIMALS),
        "measured_at": result.get("timestamp"),
    }
    _validate_measurements(measurements)
    flags = _instability_flags(cv)
    return {
        "kind": CONTRIBUTION_KIND,
        "schema_version": SCHEMA_VERSION,
        "id": _content_id(fingerprint, measurements),
        "fingerprint": fingerprint,
        "measurements": measurements,
        "flags": flags,
        "attestation": {"signed": False, "note": ATTESTATION_NOTE},
    }


def verify_contribution(data: dict) -> None:
    """Raise unless ``data`` is a well-formed contribution whose id matches its content."""
    if not isinstance(data, dict) or data.get("kind") != CONTRIBUTION_KIND:
        raise ContribError(f"not a contribution (kind must be {CONTRIBUTION_KIND!r})")
    if type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ContribError(f"schema_version {data.get('schema_version')!r} is not {SCHEMA_VERSION}")
    fingerprint, measurements = data.get("fingerprint"), data.get("measurements")
    if not isinstance(fingerprint, dict) or not isinstance(measurements, dict):
        raise ContribError("fingerprint and measurements are required")
    if _content_id(fingerprint, measurements) != data.get("id"):
        raise ContribError("content hash mismatch: the file was altered after export")
    _validate_fingerprint(fingerprint)
    cv = _validate_measurements(measurements)
    if data.get("flags") != _instability_flags(cv):
        raise ContribError("flags disagree with instability derived from decode samples")
    attestation = data.get("attestation")
    if (
        not isinstance(attestation, dict)
        or attestation.get("signed") is not False
        or attestation != {"signed": False, "note": ATTESTATION_NOTE}
    ):
        raise ContribError(
            "contributions are unsigned; an attestation cannot claim a verified signer"
        )


def import_contribution(path: str | Path) -> tuple[str, bool]:
    """Verify and copy a contribution into quarantine. Returns (id, newly added)."""
    data = read_json_file(path)
    verify_contribution(data)
    dest = quarantine_dir() / f"{data['id']}.json"
    if dest.exists():
        return data["id"], False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data["id"], True


def load_quarantine() -> list[dict]:
    """Every quarantined contribution that still verifies; others are logged and skipped."""
    out = []
    folder = quarantine_dir()
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            data = read_json_file(path)
            verify_contribution(data)
        except ContribError as exc:
            logger.warning("skipping quarantined contribution %s: %s", path.name, exc)
            continue
        out.append(data)
    return out


def contributed_decode(
    contributions: list[dict],
    models: tuple[str, ...],
    backend: str,
    quant: str,
    gpu_name: str,
) -> dict | None:
    """The quarantined evidence for one exact cell, or None.

    The GPU is matched by resolving each contribution's driver-reported name (and
    memory, where recorded) to a hardware-DB entry; an ambiguous or unknown name
    matches nothing. The value is the median of the contributions' mean decode
    rates, so one outlier cannot move it far.
    """
    from chimeraforge.planner.hardware import match_driver_name

    hits = []
    for c in contributions:
        fp = c["fingerprint"]
        if fp.get("model") not in models or (fp.get("backend"), fp.get("quant")) != (
            backend,
            quant,
        ):
            continue
        spec = match_driver_name(fp.get("gpu_name") or "", fp.get("gpu_memory_gb"))
        if spec is None or spec.name != gpu_name:
            continue
        hits.append(c)
    if not hits:
        return None
    means = [c["measurements"]["decode_tps_mean"] for c in hits]
    clusters = sorted(
        {
            f"{c['fingerprint'].get('backend_name')} {c['fingerprint'].get('backend_version')}"
            f" / driver {c['fingerprint'].get('gpu_driver')}"
            for c in hits
        }
    )
    return {
        "decode_tps": statistics.median(means),
        "contributions": len(hits),
        "ids": [c["id"][:12] for c in hits],
        "full_ids": [c["id"] for c in hits],
        "clusters": clusters,
        "flagged": sum(bool(c.get("flags")) for c in hits),
    }
