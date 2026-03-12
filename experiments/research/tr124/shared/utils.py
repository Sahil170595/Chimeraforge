"""TR124 shared utilities across phases.

Provides:
- Base model / quantization level parsing from model names
- Phase 1 baseline loading for cross-phase delta computation
- Common result directory discovery
"""

from __future__ import annotations

import contextlib
import csv
import json
import logging
from pathlib import Path
import re
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("tr124.shared")

# ── Quant-level parsing ──────────────────────────────────────────────

_QUANT_SUFFIX_RE = re.compile(
    r"-(?:q\d+_K(?:_[SM])?|q\d+_\d+|fp16|fp32)$", re.IGNORECASE
)


def extract_base_model(model_name: str) -> str:
    """Strip quantization suffix to get the base model name.

    "llama3.2-1b-q4_K_M" -> "llama3.2-1b"
    "phi-2-q8_0"          -> "phi-2"
    "gpt2"                -> "gpt2"
    """
    match = _QUANT_SUFFIX_RE.search(model_name)
    return model_name[: match.start()] if match else model_name


def extract_quant_level(model_name: str) -> str:
    """Extract quantization level from model name.

    "llama3.2-1b-q4_K_M" -> "Q4_K_M"
    "gpt2"                -> "FP16"
    """
    match = _QUANT_SUFFIX_RE.search(model_name)
    return match.group(0).lstrip("-").upper() if match else "FP16"


# ── Result directory discovery ───────────────────────────────────────


def find_latest_run(results_dir: str | Path) -> Path | None:
    """Find the most recent timestamped run directory under results_dir."""
    p = Path(results_dir)
    if not p.exists():
        p = _REPO_ROOT / results_dir
    if not p.exists():
        return None
    runs = sorted([d for d in p.iterdir() if d.is_dir()], reverse=True)
    return runs[0] if runs else None


# ── Phase 1 baseline loading ────────────────────────────────────────

_PHASE1_RESULTS = "results/eval/tr124_phase1"


def load_phase1_summary(results_dir: str = _PHASE1_RESULTS) -> dict | None:
    """Load Phase 1 summary.json."""
    run_dir = find_latest_run(results_dir)
    if run_dir is None:
        logger.warning("Phase 1 results not found at %s", results_dir)
        return None
    path = run_dir / "summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_phase1_aggregate(results_dir: str = _PHASE1_RESULTS) -> list[dict] | None:
    """Load Phase 1 aggregate.csv as list of dicts."""
    run_dir = find_latest_run(results_dir)
    if run_dir is None:
        return None
    path = run_dir / "aggregate.csv"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_phase1_per_model_quality(
    results_dir: str = _PHASE1_RESULTS,
) -> dict[str, dict[str, float]]:
    """Extract per-model quality means from Phase 1 aggregate.

    Returns: {model_name -> {metric_name -> mean_score}}
    GPU backend only (FP16 = unquantized reference).
    """
    rows = load_phase1_aggregate(results_dir)
    if not rows:
        return {}

    result: dict[str, dict[str, float]] = {}
    for row in rows:
        model = row.get("model", "")
        backend = row.get("backend", "")
        # Use GPU backend as the FP16 reference
        if backend != "transformers-gpu":
            continue

        metrics: dict[str, float] = {}
        for key, val in row.items():
            if key.endswith("_mean") and key not in ("generation_time_ms_mean",):
                metric = key.replace("_mean", "")
                with contextlib.suppress(ValueError, TypeError):
                    metrics[metric] = float(val)
        if metrics:
            result[model] = metrics

    return result
