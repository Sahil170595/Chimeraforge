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
import os
import statistics
from pathlib import Path

logger = logging.getLogger(__name__)

CONTRIBUTION_KIND = "chimeraforge-contribution"
SCHEMA_VERSION = 1
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
    canonical = json.dumps(
        {"fingerprint": fingerprint, "measurements": measurements},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_contribution(result: dict) -> dict:
    """One ``bench`` result (as ``result_to_dict`` writes it) -> a contribution.

    Raises:
        ContribError: no GPU name (the number cannot be attributed to hardware),
            or fewer than MIN_RUNS runs.
    """
    env = result.get("environment") or {}
    if not env.get("gpu_name"):
        raise ContribError(
            "the bench result names no GPU, so its numbers cannot be attributed to "
            "hardware; re-run bench where NVML can read the device"
        )
    runs = result.get("individual_runs") or []
    decode = [float(r["throughput_tps"]) for r in runs if r.get("throughput_tps")]
    if len(decode) < MIN_RUNS:
        raise ContribError(f"{len(decode)} runs; a contribution needs at least {MIN_RUNS}")
    ttft = [float(r["ttft_ms"]) for r in runs if r.get("ttft_ms") is not None]
    fingerprint = {k: env.get(k) for k in FINGERPRINT_FIELDS}
    fingerprint.update(
        model=result.get("model"),
        backend=result.get("backend"),
        quant=result.get("quant") or "FP16",
        context_length=result.get("context_length"),
        workload=result.get("workload"),
    )
    mean = statistics.fmean(decode)
    cv = statistics.stdev(decode) / mean if mean > 0 else 0.0
    measurements = {
        "decode_tps": decode,
        "ttft_ms": ttft,
        "decode_tps_mean": round(mean, 4),
        "decode_tps_cv": round(cv, 4),
        "measured_at": result.get("timestamp"),
    }
    flags = []
    if cv > UNSTABLE_CV:
        flags.append(
            f"unstable: decode CV {cv:.1%} exceeds the {UNSTABLE_CV:.0%} methodology target; "
            "kept and flagged, not dropped"
        )
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
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ContribError(f"schema_version {data.get('schema_version')!r} is not {SCHEMA_VERSION}")
    fingerprint, measurements = data.get("fingerprint"), data.get("measurements")
    if not isinstance(fingerprint, dict) or not isinstance(measurements, dict):
        raise ContribError("fingerprint and measurements are required")
    if _content_id(fingerprint, measurements) != data.get("id"):
        raise ContribError("content hash mismatch: the file was altered after export")
    if len(measurements.get("decode_tps") or []) < MIN_RUNS:
        raise ContribError(f"fewer than {MIN_RUNS} runs")


def import_contribution(path: str | Path) -> tuple[str, bool]:
    """Verify and copy a contribution into quarantine. Returns (id, newly added)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContribError(f"could not read {path}: {exc}") from exc
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
            data = json.loads(path.read_text(encoding="utf-8"))
            verify_contribution(data)
        except (OSError, json.JSONDecodeError, ContribError) as exc:
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
        "clusters": clusters,
        "flagged": sum(bool(c.get("flags")) for c in hits),
    }
