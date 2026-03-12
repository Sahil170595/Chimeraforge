"""TR128 shared utilities — paths, prompt generation, CSV loading."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("tr128.utils")

# ── Path anchors ──────────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_TR128 = _DIR.parent
_REPO = _TR128.parents[1]

TR128_RESULTS = _TR128 / "results"
TR128_CONFIG = _TR128 / "config.yaml"

# ── Seed paragraph for synthetic prompts ──────────────────────────────
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


def generate_ollama_prompt(target_tokens: int) -> str:
    """Generate an approximate-length prompt for Ollama (no tokenizer).

    Uses the shared seed paragraph and repeats to target. Over-estimates
    slightly — Ollama reports actual ``prompt_eval_count`` so the real
    token count is always recorded regardless.
    """
    n_repeats = max(1, (target_tokens // 100) + 1)
    text = SEED_PARAGRAPH * n_repeats
    words = text.split()
    target_words = int(target_tokens / 1.3)
    return " ".join(words[:target_words])


def generate_prompt_lengths(
    n: int,
    distribution: str = "uniform",
    low: int = 100,
    high: int = 300,
    rng: np.random.Generator | None = None,
) -> list[int]:
    """Generate a list of prompt token-count targets from a distribution."""
    if rng is None:
        rng = np.random.default_rng(42)

    if distribution == "uniform":
        lengths = rng.integers(low, high + 1, size=n)
    elif distribution == "lognormal":
        mu = np.log(200)
        sigma = 0.5
        raw = rng.lognormal(mu, sigma, size=n)
        lengths = np.clip(raw, low, high).astype(int)
    elif distribution == "bimodal":
        n_low = n // 2
        n_high = n - n_low
        lo = rng.integers(low, low + 50, size=n_low)
        hi = rng.integers(high - 50, high + 1, size=n_high)
        lengths = np.concatenate([lo, hi])
        rng.shuffle(lengths)
    else:
        raise ValueError(f"Unknown distribution: {distribution}")

    return [int(x) for x in lengths]


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
    """Load metrics CSV with standard type coercions."""
    df = pd.read_csv(path)
    numeric_cols = [
        "wall_ms",
        "ttft_ms",
        "ichunk_mean_ms",
        "ichunk_p95_ms",
        "ichunk_jitter_cv",
        "prompt_tokens",
        "completion_tokens",
        "prompt_eval_ms",
        "eval_ms",
        "total_duration_ms",
        "load_duration_ms",
        "tokens_per_s",
        "queue_depth_at_submit",
        "arrival_rate_rps",
        "turn_number",
        "request_id",
        "num_parallel",
    ]
    for col in numeric_cols:
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


# ── CSV field names (single source of truth) ─────────────────────────
# Union schema — phase-specific columns blank where N/A.
# "ichunk" = inter-chunk (honest name — NOT inter-token).
CSV_FIELDNAMES = [
    "phase",
    "model",
    "num_parallel",
    "arrival_pattern",
    "arrival_rate_rps",
    "prompt_distribution",
    "response_mode",
    "request_id",
    "queue_depth_at_submit",
    "wall_ms",
    "ttft_ms",
    "ichunk_mean_ms",
    "ichunk_p95_ms",
    "ichunk_jitter_cv",
    "prompt_tokens",
    "completion_tokens",
    "prompt_eval_ms",
    "eval_ms",
    "total_duration_ms",
    "load_duration_ms",
    "tokens_per_s",
    "turn_number",
    "conversation_id",
    "context_strategy",
    "status",
]
