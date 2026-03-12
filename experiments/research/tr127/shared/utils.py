"""TR127 shared utilities — paths, prompt generation, data loading."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger("tr127.utils")

# ── Path anchors ──────────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_TR127 = _DIR.parent
_REPO = _TR127.parents[1]

TR127_RESULTS = _TR127 / "results"
TR127_CONFIG = _TR127 / "config.yaml"

# ── Seed paragraph for synthetic prompts ──────────────────────────────
# Single source of truth — used by both HF and Ollama prompt generators.
SEED_PARAGRAPH = (
    "The quick brown fox jumps over the lazy dog. "
    "In a world where technology evolves at an unprecedented pace, "
    "understanding the fundamental principles of computation becomes "
    "increasingly important. Machine learning models process vast "
    "amounts of data to identify patterns and make predictions. "
    "The transformer architecture introduced self-attention mechanisms "
    "that revolutionized natural language processing. Key-value caches "
    "store previously computed attention states to accelerate autoregressive "
    "generation. Memory bandwidth and compute capacity are the two primary "
    "bottlenecks in large language model inference. Context length determines "
    "how much information a model can consider when generating each token. "
    "Longer contexts require more memory for the key-value cache and more "
    "computation during the prefill phase. The quadratic scaling of attention "
    "with respect to sequence length is a fundamental computational challenge. "
)


def generate_prompt(tokenizer: Any, target_tokens: int) -> str:
    """Generate a synthetic prompt of exactly *target_tokens* tokens.

    Strategy: repeat the seed paragraph until we exceed the target, then
    truncate to exactly target_tokens by decoding the first N token IDs.
    Round-trip verification ensures the prompt tokenizes to the right length.
    """
    # Repeat seed text enough times to exceed target
    n_repeats = (target_tokens // 20) + 2  # seed is ~130 tokens, be generous
    raw_text = SEED_PARAGRAPH * n_repeats

    # Tokenize and truncate
    ids = tokenizer.encode(raw_text, add_special_tokens=False)
    if len(ids) < target_tokens:
        while len(ids) < target_tokens:
            ids = ids + ids
    ids = ids[:target_tokens]

    # Decode back to text so the prompt is exactly target_tokens when re-tokenized
    prompt = tokenizer.decode(ids, skip_special_tokens=True)

    # Round-trip verification — some tokenizers differ by ±1-2 tokens
    actual = len(tokenizer.encode(prompt, add_special_tokens=False))
    if actual != target_tokens:
        # Re-encode, truncate, decode again
        ids_rt = tokenizer.encode(prompt, add_special_tokens=False)[:target_tokens]
        prompt = tokenizer.decode(ids_rt, skip_special_tokens=True)
        actual = len(tokenizer.encode(prompt, add_special_tokens=False))

    if actual != target_tokens:
        log.warning(
            "Prompt token count mismatch: target=%d, actual=%d (delta=%+d)",
            target_tokens,
            actual,
            actual - target_tokens,
        )

    return prompt


def generate_ollama_prompt(target_tokens: int) -> str:
    """Generate an approximate-length prompt for Ollama (no tokenizer available).

    Uses the shared seed paragraph and repeats to target. Over-estimates
    slightly — Ollama reports actual ``prompt_eval_count`` so the real
    token count is always recorded regardless.
    """
    n_repeats = max(1, (target_tokens // 100) + 1)
    text = SEED_PARAGRAPH * n_repeats
    # Rough truncation by word count (~1.3 tokens per word on average)
    words = text.split()
    target_words = int(target_tokens / 1.3)
    return " ".join(words[:target_words])


def find_latest_run(results_dir: str | Path) -> Path | None:
    """Find most recent timestamped run directory (YYYYMMDD_HHMMSS)."""
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        return None
    candidates = [
        p
        for p in results_dir.iterdir()
        if p.is_dir() and len(p.name) == 15 and p.name[8] == "_"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)


def load_metrics_csv(path: str | Path, filter_ok: bool = True) -> pd.DataFrame:
    """Load metrics CSV with standard type coercions.

    Args:
        path: Path to CSV file.
        filter_ok: If True (default), keep only rows with status == 'ok'.
            Pass False to get all rows including OOM/error for analysis of
            failure patterns.
    """
    df = pd.read_csv(path)
    for col in [
        "latency_ms",
        "tokens",
        "tokens_per_s",
        "vram_peak_mb",
        "prompt_tokens",
        "context_length",
        "rep",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if filter_ok and "status" in df.columns:
        df = df[df["status"] == "ok"].copy()
    return df


def effect_label(d: float) -> str:
    """Map absolute Cohen's d to a qualitative label."""
    d = abs(d)
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


def compute_percentiles(
    values: list[float], pcts: list[int] | None = None
) -> dict[str, float]:
    """Compute p50, p95, p99 (and custom) percentiles for a list of values."""
    if pcts is None:
        pcts = [50, 95, 99]
    if not values:
        return {f"p{p}": 0.0 for p in pcts}
    arr = np.array(values)
    return {f"p{p}": float(np.percentile(arr, p)) for p in pcts}
