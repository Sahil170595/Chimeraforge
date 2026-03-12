"""TR125 Phase 2: Quantization decision matrix analysis with real benchmarks.

Reads framework output (samples.jsonl) and performs 9 analyses:
  1. Benchmark accuracy — exact_match on real MMLU + ARC-Challenge (PRIMARY quality gate)
  2. Generation quality curves — BERTScore/coherence/ROUGE-L on generation tasks (SECONDARY)
  3. Native performance — tok/s and TTFT from backend_metadata (Ollama-native timing)
  4. Cost derivation — $/1M tokens per quant level using native tok/s
  5. Decision matrix — per VRAM tier, tiered quality classification
  6. Pairwise t-tests — adjacent quant levels on benchmark accuracy + generation metrics
  7. Diminishing returns — quality gain per quant step vs cost increase
  8. Power analysis — minimum detectable effect sizes for this experiment design
  9. Cross-phase validation — Phase 1 Q8_0 vs Phase 2 Q8_0 consistency

Primary quality baseline: FP16 Ollama (same instruct model, same backend — no confound).
For llama3.1-8b (no FP16), Q8_0 is used as primary baseline.

Usage:
    python research/tr125/phase2/analyze.py [--results-dir DIR] [-v]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import logging
import math
from pathlib import Path
import re
import sys
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from research.shared.statistical_analysis import compare_groups
from research.tr125.shared.utils import (
    QUANT_BPW,
    QUANT_PRECISION_ORDER,
    compute_cost_per_1m_tokens,
    extract_base_model,
    extract_quant_level,
    find_latest_run,
    fuzzy_model_match,
    load_tr123_fp16_costs,
)
from scripts.eval.analysis.aggregator import (
    SampleRecord,
    compute_metric_summaries,
    load_sample_jsonl,
)

logger = logging.getLogger("tr125.phase2.analyze")

# -- Constants ---------------------------------------------------------------

# Benchmark task names (real data from HuggingFace)
BENCHMARK_TASKS = {"mmlu_real", "arc_challenge"}

# Generation quality metrics (for hand-crafted generation tasks)
GENERATION_QUALITY_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]
GENERATION_KEY_METRICS = ["bertscore", "coherence", "rouge_l"]

# Tiered quality thresholds (both must pass for a given tier)
QUALITY_TIERS = {
    "negligible": {"bench_delta_pp": -3, "gen_delta_pct": -3},
    "acceptable": {"bench_delta_pp": -5, "gen_delta_pct": -8},
    "concerning": {"bench_delta_pp": -10, "gen_delta_pct": -15},
}

# Regex for extracting answer letter from model output
_ANSWER_LETTER_RE = re.compile(r"\b([ABCD])\b")


# -- Model params ------------------------------------------------------------

VRAM_TIERS = [
    {"name": "2GB", "vram_gb": 2.0, "description": "Integrated / low-end"},
    {"name": "4GB", "vram_gb": 4.0, "description": "GTX 1650 / MX series"},
    {"name": "6GB", "vram_gb": 6.0, "description": "RTX 3060 / GTX 1660"},
    {"name": "8GB+", "vram_gb": 8.0, "description": "RTX 3070+ / RTX 4080"},
]

PARAMS_MAP = {
    "llama3.2-1b": 1236,
    "llama3.2-3b": 3213,
    "qwen2.5-1.5b": 1543,
    "phi-2": 2700,
    "llama3.1-8b": 8030,
}


def estimate_model_vram_gb(params_m: float, bpw: float) -> float:
    """Estimate VRAM for model weights: params * bpw / 8 + 10% overhead."""
    params = params_m * 1e6
    bytes_needed = params * bpw / 8
    gb = bytes_needed / (1024**3)
    return gb * 1.1


# ── Helper: answer letter extraction ────────────────────────────────────────


def extract_answer_letter(candidate: str) -> str:
    """Extract answer letter from model output for benchmark re-scoring.

    Handles: "B", "B)", "The answer is B", "Answer: B", "B. Ampere", etc.
    Returns the extracted letter (uppercase) or the original stripped candidate.
    """
    stripped = candidate.strip().upper()

    # Exact single character
    if len(stripped) == 1 and stripped in "ABCD":
        return stripped

    # "The answer is X" or "Answer: X" pattern
    m = re.search(r"(?:answer\s*(?:is|:)\s*)([ABCD])\b", stripped, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # First standalone letter A-D found
    m = _ANSWER_LETTER_RE.search(stripped)
    if m:
        return m.group(1).upper()

    return stripped


# ── 1. Benchmark Accuracy (PRIMARY) ────────────────────────────────────────


def compute_benchmark_accuracy(
    records: list[SampleRecord],
) -> list[dict[str, Any]]:
    """Benchmark accuracy per (base_model, quant_level).

    Uses exact_match from the framework PLUS a re-scored version that
    extracts the answer letter via regex (more robust to formatting noise).

    Primary baseline: FP16 Ollama. For llama3.1-8b (no FP16): Q8_0.
    Deltas reported in percentage points (pp), not percent.
    """
    # Group by (base_model, quant_level)
    grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        if r.task_name not in BENCHMARK_TASKS:
            continue
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        grouped[base][quant].append(r)

    # Compute accuracy for each (base, quant) group
    def _accuracy(recs: list[SampleRecord]) -> dict[str, Any]:
        """Compute raw and rescored accuracy."""
        if not recs:
            return {"raw_acc": 0.0, "rescored_acc": 0.0, "n": 0}

        raw_correct = 0
        rescored_correct = 0
        by_task: dict[str, dict[str, int]] = defaultdict(
            lambda: {"n": 0, "raw": 0, "rescored": 0}
        )

        for r in recs:
            ref = (r.reference or "").strip().upper()
            # Raw: framework exact_match score
            em_score = r.metrics.get("exact_match", {}).get("score")
            raw_hit = em_score == 1.0 if em_score is not None else False
            # Rescored: extract letter from candidate
            extracted = extract_answer_letter(r.candidate or "")
            rescored_hit = extracted == ref

            raw_correct += int(raw_hit)
            rescored_correct += int(rescored_hit)

            by_task[r.task_name]["n"] += 1
            by_task[r.task_name]["raw"] += int(raw_hit)
            by_task[r.task_name]["rescored"] += int(rescored_hit)

        n = len(recs)
        per_task = {}
        for task, counts in by_task.items():
            tn = counts["n"]
            per_task[task] = {
                "n": tn,
                "raw_acc": round(counts["raw"] / tn, 4) if tn else 0,
                "rescored_acc": round(counts["rescored"] / tn, 4) if tn else 0,
            }

        return {
            "raw_acc": round(raw_correct / n, 4) if n else 0,
            "rescored_acc": round(rescored_correct / n, 4) if n else 0,
            "n": n,
            "per_task": per_task,
        }

    # First pass: compute baseline accuracies
    fp16_acc: dict[str, dict] = {}
    q8_acc: dict[str, dict] = {}
    for base in grouped:
        if "FP16" in grouped[base]:
            fp16_acc[base] = _accuracy(grouped[base]["FP16"])
        if "Q8_0" in grouped[base]:
            q8_acc[base] = _accuracy(grouped[base]["Q8_0"])

    rows = []
    for base_model in sorted(grouped):
        quant_groups = grouped[base_model]

        # Determine primary baseline
        has_fp16 = base_model in fp16_acc
        primary_acc = fp16_acc.get(base_model, q8_acc.get(base_model, {}))
        primary_label = "FP16" if has_fp16 else "Q8_0"

        for quant_level in QUANT_PRECISION_ORDER:
            if quant_level not in quant_groups:
                continue

            acc = _accuracy(quant_groups[quant_level])

            # Delta vs primary baseline (in percentage points)
            primary_val = primary_acc.get("rescored_acc", 0)
            delta_pp = None
            if primary_val > 0:
                delta_pp = round((acc["rescored_acc"] - primary_val) * 100, 1)

            row: dict[str, Any] = {
                "base_model": base_model,
                "quant_level": quant_level,
                "model_name": (
                    quant_groups[quant_level][0].model
                    if quant_groups[quant_level]
                    else ""
                ),
                "n_samples": acc["n"],
                "primary_baseline": primary_label,
                # Raw accuracy (framework exact_match)
                "raw_accuracy": acc["raw_acc"],
                # Rescored accuracy (regex letter extraction)
                "rescored_accuracy": acc["rescored_acc"],
                # Delta vs primary baseline in percentage points
                "accuracy_delta_primary_pp": delta_pp,
                # Per-benchmark breakdown
                "per_task": acc.get("per_task", {}),
            }

            # Delta vs Q8_0
            q8_val = q8_acc.get(base_model, {}).get("rescored_acc", 0)
            if q8_val > 0:
                row["accuracy_delta_q8_pp"] = round(
                    (acc["rescored_acc"] - q8_val) * 100, 1
                )

            rows.append(row)

    return rows


# ── 2. Generation Quality Curves (SECONDARY) ───────────────────────────────


def compute_quality_curves(
    records: list[SampleRecord],
) -> list[dict[str, Any]]:
    """Generation quality per (base_model, quant_level) with FP16 and Q8_0 deltas.

    Operates on GENERATION tasks only (excludes benchmark tasks).
    Primary baseline: FP16 Ollama; secondary: Q8_0.
    """
    # Filter out benchmark tasks
    gen_records = [r for r in records if r.task_name not in BENCHMARK_TASKS]

    grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in gen_records:
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        grouped[base][quant].append(r)

    # First pass: compute FP16 and Q8_0 metric means
    fp16_means: dict[str, dict[str, float]] = {}
    q8_means: dict[str, dict[str, float]] = {}

    for base_model in grouped:
        if "FP16" in grouped[base_model]:
            summaries = compute_metric_summaries(
                grouped[base_model]["FP16"], GENERATION_QUALITY_METRICS
            )
            fp16_means[base_model] = {
                m: summaries[m].mean
                for m in GENERATION_QUALITY_METRICS
                if m in summaries
            }
        if "Q8_0" in grouped[base_model]:
            summaries = compute_metric_summaries(
                grouped[base_model]["Q8_0"], GENERATION_QUALITY_METRICS
            )
            q8_means[base_model] = {
                m: summaries[m].mean
                for m in GENERATION_QUALITY_METRICS
                if m in summaries
            }

    rows = []
    for base_model in sorted(grouped):
        quant_groups = grouped[base_model]

        primary_means = fp16_means.get(base_model, {})
        primary_label = "FP16"
        if not primary_means:
            primary_means = q8_means.get(base_model, {})
            primary_label = "Q8_0"

        q8_model_means = q8_means.get(base_model, {})

        for quant_level in QUANT_PRECISION_ORDER:
            if quant_level not in quant_groups:
                continue

            q_records = quant_groups[quant_level]
            summaries = compute_metric_summaries(q_records, GENERATION_QUALITY_METRICS)

            row: dict[str, Any] = {
                "base_model": base_model,
                "quant_level": quant_level,
                "model_name": q_records[0].model if q_records else "",
                "n_samples": len(q_records),
                "primary_baseline": primary_label,
            }

            for metric in GENERATION_QUALITY_METRICS:
                if metric not in summaries:
                    continue
                s = summaries[metric]
                row[f"{metric}_mean"] = round(s.mean, 6)
                row[f"{metric}_std"] = round(s.std, 6)
                row[f"{metric}_ci_lower"] = round(s.ci_lower, 6)
                row[f"{metric}_ci_upper"] = round(s.ci_upper, 6)

                if metric in primary_means and primary_means[metric] != 0:
                    delta = s.mean - primary_means[metric]
                    pct = (delta / primary_means[metric]) * 100
                    row[f"{metric}_delta_primary"] = round(delta, 6)
                    row[f"{metric}_delta_primary_pct"] = round(pct, 2)

                if metric in q8_model_means and q8_model_means[metric] != 0:
                    delta_q8 = s.mean - q8_model_means[metric]
                    pct_q8 = (delta_q8 / q8_model_means[metric]) * 100
                    row[f"{metric}_delta_q8"] = round(delta_q8, 6)
                    row[f"{metric}_delta_q8_pct"] = round(pct_q8, 2)

            # Key-metric average (bertscore, coherence, rouge_l)
            key_means = [
                summaries[m].mean for m in GENERATION_KEY_METRICS if m in summaries
            ]
            if key_means:
                row["key_metric_avg"] = round(sum(key_means) / len(key_means), 6)

            # Primary delta of key-metric average
            key_deltas = [
                row[f"{m}_delta_primary_pct"]
                for m in GENERATION_KEY_METRICS
                if f"{m}_delta_primary_pct" in row
            ]
            if key_deltas:
                row["key_metric_avg_delta_primary_pct"] = round(
                    sum(key_deltas) / len(key_deltas), 2
                )

            rows.append(row)

    return rows


# ── 3. Native Performance Extraction ───────────────────────────────────────


def extract_native_performance(
    records: list[SampleRecord],
) -> list[dict[str, Any]]:
    """Extract native Ollama timing from backend_metadata in SampleRecords."""
    results = []
    for r in records:
        if r.task_type == "multiple_choice":
            continue

        bm = r.backend_metadata or {}
        eval_ms = bm.get("ollama_eval_ms", 0)
        prompt_eval_ms = bm.get("ollama_prompt_eval_ms", 0)
        n_tok = r.num_tokens_generated

        native_tok_per_s = 0.0
        if eval_ms > 0 and n_tok > 0:
            native_tok_per_s = n_tok / (eval_ms / 1000)

        wall_tok_per_s = 0.0
        if r.generation_time_ms > 0 and n_tok > 0:
            wall_tok_per_s = n_tok / (r.generation_time_ms / 1000)

        if native_tok_per_s <= 0 and wall_tok_per_s <= 0:
            continue

        results.append(
            {
                "model": r.model,
                "base_model": extract_base_model(r.model),
                "quant_level": extract_quant_level(r.model),
                "sample_id": r.sample_id,
                "task_name": r.task_name,
                "native_tok_per_s": round(native_tok_per_s, 2),
                "wall_tok_per_s": round(wall_tok_per_s, 2),
                "ttft_ms": round(prompt_eval_ms, 2),
                "eval_ms": round(eval_ms, 2),
                "generation_time_ms": round(r.generation_time_ms, 2),
                "num_tokens": n_tok,
            }
        )

    return results


def aggregate_performance(
    perf_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate native and wall-clock performance per model variant."""
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in perf_records:
        by_model[p["model"]].append(p)

    rows = []
    for model_name in sorted(by_model):
        records = by_model[model_name]
        n = len(records)
        if n == 0:
            continue

        def _stats(values: list[float]) -> dict[str, float]:
            if not values:
                return {"mean": 0, "median": 0, "std": 0, "min": 0, "max": 0}
            vs = sorted(values)
            mean = sum(vs) / len(vs)
            std = (sum((x - mean) ** 2 for x in vs) / max(len(vs) - 1, 1)) ** 0.5
            return {
                "mean": round(mean, 2),
                "median": round(vs[len(vs) // 2], 2),
                "std": round(std, 2),
                "min": round(vs[0], 2),
                "max": round(vs[-1], 2),
            }

        native_vals = [
            r["native_tok_per_s"] for r in records if r["native_tok_per_s"] > 0
        ]
        wall_vals = [r["wall_tok_per_s"] for r in records if r["wall_tok_per_s"] > 0]
        ttft_vals = [r["ttft_ms"] for r in records if r["ttft_ms"] > 0]

        native_stats = _stats(native_vals)
        wall_stats = _stats(wall_vals)
        ttft_stats = _stats(ttft_vals)

        overhead_pct = 0.0
        if native_stats["mean"] > 0 and wall_stats["mean"] > 0:
            overhead_pct = round(
                (native_stats["mean"] / wall_stats["mean"] - 1) * 100, 1
            )

        rows.append(
            {
                "model": model_name,
                "base_model": extract_base_model(model_name),
                "quant_level": extract_quant_level(model_name),
                "n_samples": n,
                "native_tok_per_s_mean": native_stats["mean"],
                "native_tok_per_s_median": native_stats["median"],
                "native_tok_per_s_std": native_stats["std"],
                "native_tok_per_s_min": native_stats["min"],
                "native_tok_per_s_max": native_stats["max"],
                "wall_tok_per_s_mean": wall_stats["mean"],
                "wall_tok_per_s_median": wall_stats["median"],
                "wall_tok_per_s_std": wall_stats["std"],
                "ttft_ms_mean": ttft_stats["mean"],
                "ttft_ms_median": ttft_stats["median"],
                "ttft_ms_std": ttft_stats["std"],
                "ttft_ms_min": ttft_stats["min"],
                "ttft_ms_max": ttft_stats["max"],
                "http_overhead_pct": overhead_pct,
                "native_cv_pct": (
                    round(native_stats["std"] / native_stats["mean"] * 100, 1)
                    if native_stats["mean"] > 0
                    else 0
                ),
            }
        )

    return rows


# ── 4. Cost Derivation ─────────────────────────────────────────────────────


def compute_cost_table(
    perf_rows: list[dict[str, Any]],
    fp16_costs: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Derive $/1M tokens per (model, quant_level) using native tok/s."""
    fp16_baseline: dict[str, dict[str, float]] = {}
    q8_baseline: dict[str, dict[str, float]] = {}

    for pr in perf_rows:
        tok_s = pr["native_tok_per_s_mean"]
        if tok_s <= 0:
            continue
        if pr["quant_level"] == "FP16":
            fp16_baseline[pr["base_model"]] = {
                "tok_per_s": tok_s,
                "cost_per_1m": compute_cost_per_1m_tokens(tok_s),
            }
        if pr["quant_level"] == "Q8_0":
            q8_baseline[pr["base_model"]] = {
                "tok_per_s": tok_s,
                "cost_per_1m": compute_cost_per_1m_tokens(tok_s),
            }

    rows = []
    for pr in perf_rows:
        tok_s = pr["native_tok_per_s_mean"]
        if tok_s <= 0:
            continue
        cost_1m = compute_cost_per_1m_tokens(tok_s)
        base = pr["base_model"]

        primary = fp16_baseline.get(base, q8_baseline.get(base, {}))
        primary_tok_s = primary.get("tok_per_s")
        primary_cost = primary.get("cost_per_1m")
        primary_label = "FP16" if base in fp16_baseline else "Q8_0"
        speedup = round(tok_s / primary_tok_s, 2) if primary_tok_s else None
        savings_pct = (
            round((1 - cost_1m / primary_cost) * 100, 1)
            if primary_cost and primary_cost > 0
            else None
        )

        tr123_cost = None
        tr123_tok_s = None
        for tr123_name, tr123_data in fp16_costs.items():
            if tr123_name == base or fuzzy_model_match(tr123_name, base):
                tr123_cost = tr123_data.get("cost_per_1m", 0)
                tr123_tok_s = tr123_data.get("decode_tok_per_s", 0)
                break

        rows.append(
            {
                "model": pr["model"],
                "base_model": base,
                "quant_level": pr["quant_level"],
                "native_tok_per_s": tok_s,
                "cost_per_1m_tokens": cost_1m,
                "primary_baseline": primary_label,
                "primary_cost_per_1m": primary_cost,
                "primary_tok_per_s": primary_tok_s,
                "speedup_vs_primary": speedup,
                "savings_vs_primary_pct": savings_pct,
                "tr123_cost_per_1m": tr123_cost,
                "tr123_tok_per_s": tr123_tok_s,
            }
        )

    return rows


# ── 5. Decision Matrix (Tiered Quality) ────────────────────────────────────


def classify_quality_tier(
    bench_delta_pp: float | None,
    gen_delta_pct: float | None,
) -> str:
    """Classify quality into a tier based on benchmark accuracy + generation quality.

    Tier determined by the WORSE of the two criteria.
    """
    # Baselines get negligible by definition
    if bench_delta_pp is not None and bench_delta_pp == 0.0:
        return "negligible"

    # Default to worst case if data missing
    b = bench_delta_pp if bench_delta_pp is not None else -999
    g = gen_delta_pct if gen_delta_pct is not None else -999

    for tier_name in ("negligible", "acceptable", "concerning"):
        thresholds = QUALITY_TIERS[tier_name]
        if b >= thresholds["bench_delta_pp"] and g >= thresholds["gen_delta_pct"]:
            return tier_name

    return "unacceptable"


def build_decision_matrix(
    benchmark_rows: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
    perf_rows: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per VRAM tier, recommend quant levels with tiered quality classification.

    Uses benchmark accuracy (primary) + generation quality (secondary).
    Recommended = fits VRAM AND tier in ("negligible", "acceptable").
    """
    perf_by_model: dict[str, dict] = {r["model"]: r for r in perf_rows}
    cost_by_model: dict[str, dict] = {r["model"]: r for r in cost_rows}

    bench_by_key: dict[tuple[str, str], dict] = {}
    for br in benchmark_rows:
        bench_by_key[(br["base_model"], br["quant_level"])] = br

    quality_by_key: dict[tuple[str, str], dict] = {}
    for qr in quality_rows:
        quality_by_key[(qr["base_model"], qr["quant_level"])] = qr

    # Collect all (base_model, quant_level) combos
    all_combos: set[tuple[str, str]] = set()
    for br in benchmark_rows:
        all_combos.add((br["base_model"], br["quant_level"]))
    for qr in quality_rows:
        all_combos.add((qr["base_model"], qr["quant_level"]))

    recommendations = []
    for tier in VRAM_TIERS:
        tier_vram = tier["vram_gb"]

        for base, quant in sorted(all_combos):
            params_m = PARAMS_MAP.get(base, 1500)
            bpw = QUANT_BPW.get(quant, 4.5)
            vram_est = estimate_model_vram_gb(params_m, bpw)
            fits = vram_est <= tier_vram

            br = bench_by_key.get((base, quant), {})
            qr = quality_by_key.get((base, quant), {})

            bench_delta = br.get("accuracy_delta_primary_pp")
            gen_delta = qr.get("key_metric_avg_delta_primary_pct")

            model_name = br.get("model_name") or qr.get("model_name", "")
            primary_label = br.get("primary_baseline") or qr.get(
                "primary_baseline", "FP16"
            )

            # Baselines get 0 delta
            if quant == primary_label:
                bench_delta = 0.0
                gen_delta = 0.0
            elif quant in ("FP16", "Q8_0"):
                if bench_delta is None:
                    bench_delta = 0.0
                if gen_delta is None:
                    gen_delta = 0.0

            quality_tier = classify_quality_tier(bench_delta, gen_delta)

            tok_s = perf_by_model.get(model_name, {}).get("native_tok_per_s_mean", 0)
            cost_1m = cost_by_model.get(model_name, {}).get("cost_per_1m_tokens")

            recommendations.append(
                {
                    "vram_tier": tier["name"],
                    "vram_gb": tier_vram,
                    "base_model": base,
                    "quant_level": quant,
                    "model_name": model_name,
                    "vram_est_gb": round(vram_est, 2),
                    "fits": fits,
                    "quality_tier": quality_tier,
                    "bench_accuracy_delta_pp": bench_delta,
                    "gen_quality_delta_pct": gen_delta,
                    "primary_baseline": primary_label,
                    "native_tok_per_s": tok_s,
                    "cost_per_1m": cost_1m,
                    "recommended": fits
                    and quality_tier in ("negligible", "acceptable"),
                }
            )

    return recommendations


# ── 6. Pairwise T-Tests ────────────────────────────────────────────────────


def pairwise_adjacent_tests(
    benchmark_records: list[SampleRecord],
    gen_records: list[SampleRecord],
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """Pairwise t-tests between adjacent quant levels.

    Runs on both:
    - Benchmark records: exact_match (binary) — tests accuracy differences
    - Generation records: bertscore, coherence, rouge_l — tests quality differences
    """
    results = []

    # -- Benchmark accuracy tests --
    bench_grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in benchmark_records:
        if r.task_name not in BENCHMARK_TASKS:
            continue
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        bench_grouped[base][quant].append(r)

    for base_model in sorted(bench_grouped):
        available = [q for q in QUANT_PRECISION_ORDER if q in bench_grouped[base_model]]

        for i in range(len(available) - 1):
            qa, qb = available[i], available[i + 1]

            # Use rescored accuracy (binary 0/1 per sample)
            def _rescored_scores(recs: list[SampleRecord]) -> list[float]:
                scores = []
                for r in recs:
                    ref = (r.reference or "").strip().upper()
                    extracted = extract_answer_letter(r.candidate or "")
                    scores.append(1.0 if extracted == ref else 0.0)
                return scores

            vals_a = _rescored_scores(bench_grouped[base_model][qa])
            vals_b = _rescored_scores(bench_grouped[base_model][qb])

            if len(vals_a) >= 2 and len(vals_b) >= 2:
                cr = compare_groups(
                    vals_a,
                    vals_b,
                    group_a_name=f"{base_model}/{qa}",
                    group_b_name=f"{base_model}/{qb}",
                    metric_name="benchmark_accuracy",
                    alpha=alpha,
                )
                results.append(
                    {
                        "base_model": base_model,
                        "quant_higher": qa,
                        "quant_lower": qb,
                        "metric": "benchmark_accuracy",
                        "source": "benchmark",
                        "n_a": len(vals_a),
                        "n_b": len(vals_b),
                        "mean_higher": round(cr.mean_a, 6),
                        "mean_lower": round(cr.mean_b, 6),
                        "difference": round(cr.difference, 6),
                        "percent_change": round(cr.percent_change, 2),
                        "t_statistic": round(cr.t_statistic, 4),
                        "p_value": round(cr.p_value, 4),
                        "effect_size": round(cr.effect_size, 4),
                        "significant": bool(cr.significant),
                    }
                )

    # -- Generation quality tests --
    gen_grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in gen_records:
        if r.task_name in BENCHMARK_TASKS:
            continue
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        gen_grouped[base][quant].append(r)

    for base_model in sorted(gen_grouped):
        available = [q for q in QUANT_PRECISION_ORDER if q in gen_grouped[base_model]]

        for i in range(len(available) - 1):
            qa, qb = available[i], available[i + 1]

            for metric in GENERATION_KEY_METRICS:
                vals_a = [
                    float(r.metrics[metric]["score"])
                    for r in gen_grouped[base_model][qa]
                    if metric in r.metrics
                    and r.metrics[metric].get("score") is not None
                ]
                vals_b = [
                    float(r.metrics[metric]["score"])
                    for r in gen_grouped[base_model][qb]
                    if metric in r.metrics
                    and r.metrics[metric].get("score") is not None
                ]

                if len(vals_a) >= 2 and len(vals_b) >= 2:
                    cr = compare_groups(
                        vals_a,
                        vals_b,
                        group_a_name=f"{base_model}/{qa}",
                        group_b_name=f"{base_model}/{qb}",
                        metric_name=metric,
                        alpha=alpha,
                    )
                    results.append(
                        {
                            "base_model": base_model,
                            "quant_higher": qa,
                            "quant_lower": qb,
                            "metric": metric,
                            "source": "generation",
                            "n_a": len(vals_a),
                            "n_b": len(vals_b),
                            "mean_higher": round(cr.mean_a, 6),
                            "mean_lower": round(cr.mean_b, 6),
                            "difference": round(cr.difference, 6),
                            "percent_change": round(cr.percent_change, 2),
                            "t_statistic": round(cr.t_statistic, 4),
                            "p_value": round(cr.p_value, 4),
                            "effect_size": round(cr.effect_size, 4),
                            "significant": bool(cr.significant),
                        }
                    )

    return results


# ── 7. Diminishing Returns ─────────────────────────────────────────────────


def compute_diminishing_returns(
    benchmark_rows: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Quality gain per quant step vs cost increase.

    Reports both benchmark accuracy gain (pp) and generation quality gain.
    """
    bench_by_key = {(r["base_model"], r["quant_level"]): r for r in benchmark_rows}
    quality_by_key = {(r["base_model"], r["quant_level"]): r for r in quality_rows}
    cost_by_key = {(r["base_model"], r["quant_level"]): r for r in cost_rows}

    all_bases = sorted({r["base_model"] for r in benchmark_rows + quality_rows})
    results = []

    for base in all_bases:
        available = [
            q
            for q in QUANT_PRECISION_ORDER
            if (base, q) in bench_by_key or (base, q) in quality_by_key
        ]

        for i in range(len(available) - 1):
            q_higher = available[i]
            q_lower = available[i + 1]

            # Benchmark accuracy gain
            br_h = bench_by_key.get((base, q_higher), {})
            br_l = bench_by_key.get((base, q_lower), {})
            bench_gain_pp = None
            if (
                br_h.get("rescored_accuracy") is not None
                and br_l.get("rescored_accuracy") is not None
            ):
                bench_gain_pp = round(
                    (br_h["rescored_accuracy"] - br_l["rescored_accuracy"]) * 100, 1
                )

            # Generation quality gain
            qr_h = quality_by_key.get((base, q_higher), {})
            qr_l = quality_by_key.get((base, q_lower), {})
            gen_gain = None
            if (
                qr_h.get("key_metric_avg") is not None
                and qr_l.get("key_metric_avg") is not None
            ):
                gen_gain = round(qr_h["key_metric_avg"] - qr_l["key_metric_avg"], 6)

            # Cost change
            cr_h = cost_by_key.get((base, q_higher), {})
            cr_l = cost_by_key.get((base, q_lower), {})
            cost_increase_pct = None
            if (
                cr_h.get("cost_per_1m_tokens")
                and cr_l.get("cost_per_1m_tokens")
                and cr_l["cost_per_1m_tokens"] > 0
            ):
                cost_increase_pct = round(
                    (cr_h["cost_per_1m_tokens"] - cr_l["cost_per_1m_tokens"])
                    / cr_l["cost_per_1m_tokens"]
                    * 100,
                    1,
                )

            speed_loss_pct = None
            if cr_l.get("native_tok_per_s", 0) > 0:
                speed_loss_pct = round(
                    (1 - cr_h.get("native_tok_per_s", 0) / cr_l["native_tok_per_s"])
                    * 100,
                    1,
                )

            results.append(
                {
                    "base_model": base,
                    "from_quant": q_lower,
                    "to_quant": q_higher,
                    "bench_accuracy_gain_pp": bench_gain_pp,
                    "gen_quality_gain": gen_gain,
                    "cost_increase_pct": cost_increase_pct,
                    "speed_loss_pct": speed_loss_pct,
                }
            )

    return results


# ── 8. Power Analysis ──────────────────────────────────────────────────────


def compute_power_analysis(
    benchmark_n: int,
    generation_n: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    """Compute minimum detectable effect sizes for this experiment.

    Uses normal approximation for power calculations.
    """
    try:
        from scipy.stats import norm

        z_alpha = norm.ppf(1 - alpha / 2)
        z_power = norm.ppf(power)
    except ImportError:
        # Fallback: z_0.025 = 1.96, z_0.80 = 0.842
        z_alpha = 1.96
        z_power = 0.842

    # Binary metrics (benchmark accuracy) — two-proportion z-test
    # MDE at worst-case p=0.5
    if benchmark_n > 0:
        mde_accuracy = (z_alpha + z_power) * math.sqrt(2 * 0.5 * 0.5 / benchmark_n)
        mde_accuracy_pp = round(mde_accuracy * 100, 1)
    else:
        mde_accuracy_pp = None

    # Continuous metrics (generation quality) — two-sample t-test
    mde_cohens_d = (
        round((z_alpha + z_power) * math.sqrt(2 / generation_n), 3)
        if generation_n > 0
        else None
    )

    return {
        "benchmark_n_per_variant": benchmark_n,
        "generation_n_per_variant": generation_n,
        "alpha": alpha,
        "power": power,
        "mde_accuracy_pp": mde_accuracy_pp,
        "mde_cohens_d": mde_cohens_d,
        "interpretation": (
            (
                f"Can detect >{mde_accuracy_pp}pp accuracy drop (benchmark, N={benchmark_n}) "
                f"and Cohen's d > {mde_cohens_d} (generation, N={generation_n}) "
                f"at {int(power*100)}% power, alpha={alpha}"
            )
            if mde_accuracy_pp and mde_cohens_d
            else "Insufficient data for power analysis"
        ),
    }


# ── 9. Cross-Phase Validation ──────────────────────────────────────────────


def cross_phase_validation(
    phase2_records: list[SampleRecord],
    phase1_dir: str = "results/eval/tr125",
) -> list[dict[str, Any]]:
    """Compare Phase 1 Q8_0 results against Phase 2 Q8_0 for small models."""
    phase1_run = find_latest_run(phase1_dir)
    if phase1_run is None:
        logger.warning("No Phase 1 results found at %s", phase1_dir)
        return []

    phase1_jsonl = phase1_run / "samples.jsonl"
    if not phase1_jsonl.exists():
        logger.warning("No Phase 1 samples.jsonl found")
        return []

    phase1_records = load_sample_jsonl(phase1_jsonl)
    phase1_gen = [r for r in phase1_records if r.task_type != "multiple_choice"]

    def _q8_records(records: list[SampleRecord]) -> dict[str, list[SampleRecord]]:
        grouped: dict[str, list[SampleRecord]] = defaultdict(list)
        for r in records:
            if extract_quant_level(r.model) == "Q8_0":
                grouped[extract_base_model(r.model)].append(r)
        return grouped

    phase1_q8 = _q8_records(phase1_gen)
    phase2_q8 = _q8_records(
        [
            r
            for r in phase2_records
            if r.task_type != "multiple_choice" and r.task_name not in BENCHMARK_TASKS
        ]
    )

    results = []
    for base_model in sorted(set(phase1_q8) & set(phase2_q8)):
        p1_summaries = compute_metric_summaries(
            phase1_q8[base_model], GENERATION_KEY_METRICS
        )
        p2_summaries = compute_metric_summaries(
            phase2_q8[base_model], GENERATION_KEY_METRICS
        )

        for metric in GENERATION_KEY_METRICS:
            if metric not in p1_summaries or metric not in p2_summaries:
                continue
            p1_mean = p1_summaries[metric].mean
            p2_mean = p2_summaries[metric].mean
            diff_pct = ((p2_mean - p1_mean) / p1_mean * 100) if p1_mean != 0 else 0.0

            results.append(
                {
                    "base_model": base_model,
                    "metric": metric,
                    "phase1_mean": round(p1_mean, 6),
                    "phase1_n": len(phase1_q8[base_model]),
                    "phase2_mean": round(p2_mean, 6),
                    "phase2_n": len(phase2_q8[base_model]),
                    "diff_pct": round(diff_pct, 2),
                    "consistent": abs(diff_pct) < 5.0,
                }
            )

    return results


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR125 Phase 2 analysis")
    parser.add_argument("--results-dir", default="results/eval/tr125_phase2")
    parser.add_argument("--phase1-dir", default="results/eval/tr125")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_dir = find_latest_run(args.results_dir)
    if run_dir is None:
        logger.error("No runs found in %s", args.results_dir)
        return 1

    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl in %s", run_dir)
        return 1

    logger.info("Analyzing %s", run_dir)
    all_records = load_sample_jsonl(jsonl_path)

    # Split into benchmark vs generation records
    benchmark_records = [r for r in all_records if r.task_name in BENCHMARK_TASKS]
    gen_records = [
        r
        for r in all_records
        if r.task_type != "multiple_choice" and r.task_name not in BENCHMARK_TASKS
    ]

    logger.info(
        "Loaded %d records: %d benchmark, %d generation",
        len(all_records),
        len(benchmark_records),
        len(gen_records),
    )

    # Load cross-TR references
    fp16_costs = load_tr123_fp16_costs()
    if fp16_costs:
        logger.info("Loaded TR123 FP16 costs for %d models", len(fp16_costs))

    # 1. Benchmark accuracy (PRIMARY)
    benchmark_rows = compute_benchmark_accuracy(all_records)
    logger.info("Benchmark accuracy: %d rows", len(benchmark_rows))

    # 2. Generation quality curves (SECONDARY)
    quality_rows = compute_quality_curves(all_records)
    logger.info("Generation quality: %d rows", len(quality_rows))

    # 3. Native performance (all records)
    all_gen_records = [r for r in all_records if r.task_type != "multiple_choice"]
    perf_records = extract_native_performance(all_gen_records)
    perf_rows = aggregate_performance(perf_records)
    logger.info(
        "Performance: %d variants (%d samples)", len(perf_rows), len(perf_records)
    )

    native_count = sum(1 for p in perf_records if p["native_tok_per_s"] > 0)
    ttft_count = sum(1 for p in perf_records if p["ttft_ms"] > 0)
    logger.info(
        "Native timing: %d/%d have eval_ms, %d/%d have TTFT",
        native_count,
        len(perf_records),
        ttft_count,
        len(perf_records),
    )

    # 4. Cost
    cost_rows = compute_cost_table(perf_rows, fp16_costs)
    logger.info("Cost table: %d rows", len(cost_rows))

    # 5. Decision matrix (tiered quality)
    decision_matrix = build_decision_matrix(
        benchmark_rows, quality_rows, perf_rows, cost_rows
    )
    recommended = sum(1 for d in decision_matrix if d["recommended"])
    tier_counts = defaultdict(int)
    for d in decision_matrix:
        if d["fits"]:
            tier_counts[d["quality_tier"]] += 1
    logger.info(
        "Decision matrix: %d entries, %d recommended", len(decision_matrix), recommended
    )
    logger.info("Quality tiers (fitting models): %s", dict(tier_counts))

    # 6. Pairwise t-tests (benchmark + generation)
    pairwise = pairwise_adjacent_tests(benchmark_records, gen_records)
    bench_sig = sum(
        1 for p in pairwise if p["significant"] and p["source"] == "benchmark"
    )
    gen_sig = sum(
        1 for p in pairwise if p["significant"] and p["source"] == "generation"
    )
    bench_total = sum(1 for p in pairwise if p["source"] == "benchmark")
    gen_total = sum(1 for p in pairwise if p["source"] == "generation")
    logger.info(
        "Pairwise: benchmark %d/%d sig, generation %d/%d sig",
        bench_sig,
        bench_total,
        gen_sig,
        gen_total,
    )

    # 7. Diminishing returns
    diminishing = compute_diminishing_returns(benchmark_rows, quality_rows, cost_rows)
    logger.info("Diminishing returns: %d steps", len(diminishing))

    # 8. Power analysis
    bench_n_per_variant = len(benchmark_records) // max(len(benchmark_rows), 1)
    gen_n_per_variant = len(gen_records) // max(len(quality_rows), 1)
    power_analysis = compute_power_analysis(bench_n_per_variant, gen_n_per_variant)
    logger.info("Power analysis: %s", power_analysis["interpretation"])

    # 9. Cross-phase validation
    cross_phase = cross_phase_validation(all_records, args.phase1_dir)
    if cross_phase:
        consistent = sum(1 for c in cross_phase if c["consistent"])
        logger.info("Cross-phase: %d/%d consistent", consistent, len(cross_phase))

    # Print summary
    print(f"\n{'='*70}")
    print(f"TR125 Phase 2 Analysis — {len(all_records)} total samples")
    print(f"  Benchmark: {len(benchmark_records)} ({', '.join(BENCHMARK_TASKS)})")
    print(f"  Generation: {len(gen_records)} (5 tasks)")
    print(f"{'='*70}")

    print("\n--- Benchmark Accuracy (PRIMARY) ---")
    for row in benchmark_rows:
        delta_str = ""
        d = row.get("accuracy_delta_primary_pp")
        bl = row.get("primary_baseline", "FP16")
        if d is not None:
            delta_str = f" (vs {bl}: {d:+.1f}pp)"
        print(
            f"  {row['base_model']:16s} {row['quant_level']:8s} "
            f"acc={row['rescored_accuracy']:.3f} (raw={row['raw_accuracy']:.3f}){delta_str}"
        )

    print("\n--- Generation Quality (SECONDARY) ---")
    for row in quality_rows:
        d = row.get("key_metric_avg_delta_primary_pct")
        bl = row.get("primary_baseline", "FP16")
        delta_str = f" (vs {bl}: {d:+.1f}%)" if d is not None else ""
        print(
            f"  {row['base_model']:16s} {row['quant_level']:8s} "
            f"key_avg={row.get('key_metric_avg', 0):.4f}{delta_str}"
        )

    print("\n--- Power Analysis ---")
    print(f"  {power_analysis['interpretation']}")

    print("\n--- Pairwise Tests ---")
    print(f"  Benchmark: {bench_sig}/{bench_total} significant")
    print(f"  Generation: {gen_sig}/{gen_total} significant")

    if cross_phase:
        print("\n--- Cross-Phase Validation ---")
        for c in cross_phase:
            status = "OK" if c["consistent"] else "DIFF"
            print(
                f"  [{status}] {c['base_model']:16s} {c['metric']:12s} "
                f"P1={c['phase1_mean']:.4f} P2={c['phase2_mean']:.4f} ({c['diff_pct']:+.1f}%)"
            )

    # Save
    analysis = {
        "benchmark_accuracy": benchmark_rows,
        "quality_curves": quality_rows,
        "performance": perf_rows,
        "cost_table": cost_rows,
        "decision_matrix": decision_matrix,
        "pairwise_tests": pairwise,
        "diminishing_returns": diminishing,
        "power_analysis": power_analysis,
        "cross_phase_validation": cross_phase,
        "metadata": {
            "total_samples": len(all_records),
            "benchmark_samples": len(benchmark_records),
            "generation_samples": len(gen_records),
            "native_timing_count": native_count,
            "ttft_count": ttft_count,
            "tr123_costs_loaded": bool(fp16_costs),
            "benchmark_tasks": sorted(BENCHMARK_TASKS),
            "quality_tiers": QUALITY_TIERS,
        },
    }
    out_path = run_dir / "phase2_analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    logger.info("Saved analysis to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
