"""TR125 shared utilities across phases.

Provides:
- Quantization level ordering and precision metadata
- Ollama tag resolution and discovery
- Performance metric extraction from raw JSONL backend_metadata
- Cost derivation (hardware_cost / tok_per_s)
- TR124 Phase 1 FP16 baseline loading
- TR123 FP16 decode throughput loading
- Result directory discovery
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any
import urllib.request

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("tr125.shared")

# -- Quant ordering (highest precision first) --------------------------------

QUANT_PRECISION_ORDER = [
    "FP16",
    "Q8_0",
    "Q6_K",
    "Q5_K_M",
    "Q4_K_M",
    "Q3_K_S",
    "Q2_K",
]

# Approximate bits-per-weight for VRAM estimation
QUANT_BPW: dict[str, float] = {
    "FP16": 16.0,
    "Q8_0": 8.0,
    "Q6_K": 6.5,
    "Q5_K_M": 5.5,
    "Q4_K_M": 4.5,
    "Q3_K_S": 3.5,
    "Q2_K": 2.5,
}

# Hardware cost baseline ($/hr for RTX 4080 tier, from TR119)
HARDWARE_COST_PER_HOUR = 0.035

# -- Model name parsing -------------------------------------------------------

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


def fuzzy_model_match(name_a: str, name_b: str) -> bool:
    """Match model names with different separators."""

    def normalize(s):
        return s.replace("-", "").replace(".", "").lower()

    return normalize(name_a) == normalize(name_b)


# -- Ollama tag helpers --------------------------------------------------------

# Base models -> Ollama tag prefix (includes variant name for quant tags)
OLLAMA_BASE_TAGS: dict[str, str] = {
    "llama3.2-1b": "llama3.2:1b-instruct",
    "llama3.2-3b": "llama3.2:3b-instruct",
    "qwen2.5-1.5b": "qwen2.5:1.5b-instruct",
    "phi-2": "phi:2.7b-chat-v2",
    "llama3.1-8b": "llama3.1:8b-instruct",
}

# Quant level -> Ollama tag suffix (empty for default)
OLLAMA_QUANT_SUFFIXES: dict[str, str] = {
    "FP16": "-fp16",
    "Q2_K": "-q2_K",
    "Q3_K_S": "-q3_K_S",
    "Q4_K_M": "-q4_K_M",
    "Q5_K_M": "-q5_K_M",
    "Q6_K": "-q6_K",
    "Q8_0": "-q8_0",
}


def build_ollama_tag(base_tag: str, quant_level: str) -> str:
    """Construct an Ollama tag from base + quant level.

    >>> build_ollama_tag("llama3.2:1b", "Q4_K_M")
    'llama3.2:1b-q4_K_M'
    """
    suffix = OLLAMA_QUANT_SUFFIXES.get(quant_level, "")
    return f"{base_tag}{suffix}"


def list_local_ollama_tags(url: str = "http://localhost:11434") -> set[str]:
    """Query Ollama /api/tags for locally available models."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {m["name"] for m in data.get("models", [])}
    except Exception as e:
        logger.error("Cannot reach Ollama at %s: %s", url, e)
        return set()


# -- Performance extraction from raw JSONL ------------------------------------


def extract_performance_metrics(jsonl_path: Path) -> list[dict[str, Any]]:
    """Extract tok/s from raw JSONL records.

    Uses backend_metadata (Ollama-native timing) if available, otherwise
    falls back to generation_time_ms / num_tokens_generated (wall-clock).

    Returns one dict per sample with: model, backend, sample_id, task_name,
    tok_per_s, ttft_ms, generation_time_ms.
    """
    results = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)

            # Skip multiple-choice tasks (no generation)
            if d.get("task_type") == "multiple_choice":
                continue

            num_tokens = d.get("num_tokens_generated", 0)
            gen_time_ms = d.get("generation_time_ms", 0)

            # Try backend_metadata first (Ollama-native timing, more precise)
            bm = d.get("backend_metadata", {})
            eval_ms = bm.get("ollama_eval_ms", 0) if bm else 0
            prompt_eval_ms = bm.get("ollama_prompt_eval_ms", 0) if bm else 0

            if eval_ms > 0 and num_tokens > 0:
                tok_per_s = num_tokens / (eval_ms / 1000)
                ttft_ms = prompt_eval_ms
            elif gen_time_ms > 0 and num_tokens > 0:
                # Fallback: wall-clock time (includes network overhead)
                tok_per_s = num_tokens / (gen_time_ms / 1000)
                ttft_ms = 0  # not available without backend_metadata
            else:
                continue

            results.append(
                {
                    "model": d.get("model", ""),
                    "backend": d.get("backend", ""),
                    "sample_id": d.get("sample_id", ""),
                    "task_name": d.get("task_name", ""),
                    "tok_per_s": round(tok_per_s, 2),
                    "ttft_ms": round(ttft_ms, 2),
                    "num_tokens": num_tokens,
                    "generation_time_ms": round(gen_time_ms, 2),
                }
            )

    return results


# -- Cost derivation -----------------------------------------------------------


def compute_cost_per_1m_tokens(
    tok_per_s: float,
    hourly_rate: float = HARDWARE_COST_PER_HOUR,
) -> float:
    """Compute $/1M tokens from throughput and hourly hardware cost.

    cost_per_token = hourly_rate / (tok_per_s * 3600)
    cost_per_1m = cost_per_token * 1_000_000
    """
    if tok_per_s <= 0:
        return float("inf")
    cost_per_token = hourly_rate / (tok_per_s * 3600)
    return round(cost_per_token * 1_000_000, 4)


# -- Cross-TR data loading ----------------------------------------------------


def load_tr124_phase1_baselines(
    results_dir: str = "results/eval/tr124_phase1",
) -> dict[str, dict[str, float]]:
    """Load TR124 Phase 1 FP16 per-model quality baselines.

    Returns: {model_name -> {metric_name -> mean_score}}
    """
    from research.tr124.shared.utils import load_phase1_per_model_quality

    return load_phase1_per_model_quality(results_dir)


def load_tr123_fp16_costs(
    csv_path: str | None = None,
) -> dict[str, dict[str, float]]:
    """Load TR123 FP16 decode throughput from cost_table_all_tiers.csv.

    Returns: {model_name -> {"decode_tok_per_s": float, "cost_per_1m": float}}
    """
    if csv_path is None:
        # Find the TR123 run that has cost_table_all_tiers.csv
        tr123_dir = _REPO_ROOT / "research" / "tr123" / "results"
        if not tr123_dir.exists():
            logger.warning("TR123 results not found at %s", tr123_dir)
            return {}
        runs = sorted([d for d in tr123_dir.iterdir() if d.is_dir()], reverse=True)
        csv_path = None
        for run in runs:
            candidate = run / "cost_table_all_tiers.csv"
            if candidate.exists():
                csv_path = str(candidate)
                break
        if csv_path is None:
            logger.warning("No cost_table_all_tiers.csv found in TR123 results")
            return {}

    path = Path(csv_path)
    if not path.exists():
        logger.warning("TR123 cost table not found: %s", csv_path)
        return {}

    result: dict[str, dict[str, float]] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row.get("model", "")
            backend = row.get("backend", "")
            # Use GPU backend only
            if "gpu" not in backend.lower():
                continue

            try:
                decode_tok_s = float(row.get("decode_tok_per_s_mean", 0))
                cost_1m = float(row.get("decode_cost_per_1m_mean", 0))
            except (ValueError, TypeError):
                continue

            if model not in result or decode_tok_s > result[model].get(
                "decode_tok_per_s", 0
            ):
                result[model] = {
                    "decode_tok_per_s": decode_tok_s,
                    "cost_per_1m": cost_1m,
                }

    return result


# -- Result directory discovery ------------------------------------------------


def find_latest_run(results_dir: str | Path) -> Path | None:
    """Find the most recent timestamped run directory."""
    p = Path(results_dir)
    if not p.exists():
        p = _REPO_ROOT / results_dir
    if not p.exists():
        return None
    runs = sorted([d for d in p.iterdir() if d.is_dir()], reverse=True)
    return runs[0] if runs else None
