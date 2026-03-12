"""TR130 shared utilities — paths, CSV schema, prompt generation, helpers."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("tr130.utils")

# ── Path anchors ──────────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_TR130 = _DIR.parent
_REPO = _TR130.parents[1]

TR130_RESULTS = _TR130 / "results"
TR130_CONFIG = _TR130 / "config.yaml"

# ── Models (same 3 as TR129) ─────────────────────────────────────────
MODELS = [
    {
        "name": "llama3.2-1b",
        "ollama_tag": "llama3.2:1b",
        "hf_id": "meta-llama/Llama-3.2-1B-Instruct",
        "params_m": 1200,
        "gated": True,
    },
    {
        "name": "qwen2.5-1.5b",
        "ollama_tag": "qwen2.5:1.5b",
        "hf_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "params_m": 1500,
        "gated": False,
    },
    {
        "name": "llama3.2-3b",
        "ollama_tag": "llama3.2:3b",
        "hf_id": "meta-llama/Llama-3.2-3B-Instruct",
        "params_m": 3200,
        "gated": True,
    },
]

BACKENDS = ["ollama", "vllm", "tgi"]

# ── Seed paragraph for synthetic prompts (same as TR128/TR129) ───────
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
    """Generate an approximate-length prompt (no tokenizer)."""
    n_repeats = max(1, (target_tokens // 100) + 1)
    text = SEED_PARAGRAPH * n_repeats
    words = text.split()
    target_words = int(target_tokens / 1.3)
    return " ".join(words[:target_words])


def generate_prompts(
    n: int, rng: np.random.Generator | None = None, low: int = 100, high: int = 300
) -> list[str]:
    """Generate n prompts with uniform random token-count targets."""
    if rng is None:
        rng = np.random.default_rng(42)
    lengths = rng.integers(low, high + 1, size=n)
    return [generate_ollama_prompt(int(l)) for l in lengths]


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
        "n_agents",
        "request_sequence",
        "in_flight_at_submit",
        "wall_ms",
        "prompt_tokens",
        "completion_tokens",
        "prefill_ms",
        "decode_ms",
        "effective_tps",
        "gpu_tokens_per_s",
        "submit_time_s",
        "complete_time_s",
        "ttft_ms",
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
    """Compute p50, p95, p99 (and custom) percentiles."""
    if pcts is None:
        pcts = [50, 95, 99]
    if not values:
        return {f"p{p}": 0.0 for p in pcts}
    arr = np.array(values)
    return {f"p{p}": float(np.percentile(arr, p)) for p in pcts}


def write_rows(
    writer: csv.DictWriter,
    results: list,
    phase: str,
    backend_name: str,
    model_name: str,
    n_agents: int,
) -> int:
    """Write AgentRequestResult list to CSV. Returns count."""
    count = 0
    for r in results:
        row = {
            "phase": phase,
            "backend": backend_name,
            "model": model_name,
            "agent_id": r.agent_id,
            "n_agents": n_agents,
            "request_id": r.request_id,
            "request_sequence": r.request_sequence,
            "in_flight_at_submit": r.in_flight_at_submit,
            "wall_ms": round(r.wall_ms, 2),
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "prefill_ms": round(r.prefill_ms, 2) if r.prefill_ms is not None else "",
            "decode_ms": round(r.decode_ms, 2) if r.decode_ms is not None else "",
            "effective_tps": round(r.effective_tps, 2),
            "gpu_tokens_per_s": (
                round(r.gpu_tokens_per_s, 2) if r.gpu_tokens_per_s is not None else ""
            ),
            "ttft_ms": round(r.ttft_ms, 2) if r.ttft_ms is not None else "",
            "submit_time_s": r.submit_time_s,
            "complete_time_s": r.complete_time_s,
            "status": r.status,
        }
        writer.writerow(row)
        count += 1
    return count


# ── CSV field names (single source of truth) ─────────────────────────
# backend column added for multi-backend comparison
# prefill_ms / decode_ms available for Ollama + TGI, None for vLLM
# ttft_ms available only for Phase 4 (streaming)
CSV_FIELDNAMES = [
    "phase",
    "backend",
    "model",
    "agent_id",
    "n_agents",
    "request_id",
    "request_sequence",
    "in_flight_at_submit",
    "wall_ms",
    "prompt_tokens",
    "completion_tokens",
    "prefill_ms",
    "decode_ms",
    "effective_tps",
    "gpu_tokens_per_s",
    "ttft_ms",
    "submit_time_s",
    "complete_time_s",
    "status",
]
