"""TR125 Phase 2: Generate production-grade quantization decision matrix report.

Reads Phase 2 analysis (phase2_analysis.json) and produces a 12-section markdown report.

Report hierarchy:
  - Benchmark accuracy (real MMLU + ARC-Challenge) = PRIMARY quality gate
  - Generation quality (BERTScore/coherence/ROUGE-L) = SECONDARY quality signal
  - Tiered quality classification (negligible/acceptable/concerning/unacceptable)
  - Power analysis for statistical resolution

Primary quality baseline: FP16 Ollama (same instruct model, same backend).
For llama3.1-8b (no FP16): Q8_0 Ollama.

Usage:
    python research/tr125/phase2/generate_report.py [--results-dir DIR] [-v]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from research.tr125.shared.utils import (
    QUANT_PRECISION_ORDER,
    find_latest_run,
)

logger = logging.getLogger("tr125.phase2.report")

GENERATION_KEY_METRICS = ["bertscore", "coherence", "rouge_l"]


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _quant_sort_key(quant_level: str) -> int:
    """Sort key for quant levels (highest precision first)."""
    if quant_level in QUANT_PRECISION_ORDER:
        return QUANT_PRECISION_ORDER.index(quant_level)
    return 99


def _detect_non_monotonic(rows: list[dict[str, Any]], key: str) -> list[str]:
    """Detect base models with non-monotonic values across quant levels."""
    by_model: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        q = r["quant_level"]
        if q in QUANT_PRECISION_ORDER:
            idx = QUANT_PRECISION_ORDER.index(q)
            val = r.get(key)
            if val is not None:
                by_model[r["base_model"]].append((idx, val))

    non_mono = []
    for model, points in by_model.items():
        points.sort()
        for i in range(len(points) - 1):
            if points[i][1] < points[i + 1][1] - 0.01:
                non_mono.append(model)
                break
    return non_mono


def generate_report(
    run_dir: Path,
    analysis: dict[str, Any],
) -> Path:
    """Generate the Phase 2 markdown report (12 sections)."""
    lines: list[str] = []

    benchmark_rows = analysis.get("benchmark_accuracy", [])
    quality_rows = analysis.get("quality_curves", [])
    perf_rows = analysis.get("performance", [])
    cost_rows = analysis.get("cost_table", [])
    decision_matrix = analysis.get("decision_matrix", [])
    pairwise = analysis.get("pairwise_tests", [])
    diminishing = analysis.get("diminishing_returns", [])
    power_analysis = analysis.get("power_analysis", {})
    cross_phase = analysis.get("cross_phase_validation", [])
    metadata = analysis.get("metadata", {})

    all_models_bench = sorted({r["base_model"] for r in benchmark_rows})
    all_models_qual = sorted({r["base_model"] for r in quality_rows})
    base_models = sorted(set(all_models_bench) | set(all_models_qual))

    n_models = len(base_models)
    n_quants_bench = len({r["quant_level"] for r in benchmark_rows})
    total_samples = metadata.get(
        "total_samples",
        metadata.get("benchmark_samples", 0) + metadata.get("generation_samples", 0),
    )
    bench_samples = metadata.get(
        "benchmark_samples", sum(r["n_samples"] for r in benchmark_rows)
    )
    gen_samples = metadata.get(
        "generation_samples", sum(r["n_samples"] for r in quality_rows)
    )
    benchmark_tasks = metadata.get("benchmark_tasks", ["mmlu_real", "arc_challenge"])

    # ── Header ────────────────────────────────────────────────────────
    _w(lines, "# TR125 Phase 2: Quantization Decision Matrix (Production-Grade)")
    _w(lines)
    _w(lines, f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}")
    _w(
        lines,
        f"**Models:** {n_models} base models, {n_quants_bench} quant levels (incl. FP16)",
    )
    _w(
        lines,
        f"**Total Samples:** {total_samples:,} ({bench_samples:,} benchmark + {gen_samples:,} generation)",
    )
    _w(
        lines,
        f"**Benchmarks:** Real MMLU ({', '.join(benchmark_tasks)}) from HuggingFace",
    )
    _w(
        lines,
        "**Quality Baseline:** FP16 Ollama (same instruct model, same backend); "
        "Q8_0 for models without FP16",
    )
    _w(lines, "**Timing:** Ollama-native eval_duration (not wall-clock)")
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 1. Executive Summary ──────────────────────────────────────────
    _w(lines, "## 1. Executive Summary")
    _w(lines)

    # Lead with benchmark accuracy
    if benchmark_rows:
        non_baseline = [
            r for r in benchmark_rows if r["quant_level"] != r.get("primary_baseline")
        ]
        with_delta = [
            r for r in non_baseline if r.get("accuracy_delta_primary_pp") is not None
        ]

        within_3pp = [r for r in with_delta if r["accuracy_delta_primary_pp"] >= -3.0]
        within_5pp = [r for r in with_delta if r["accuracy_delta_primary_pp"] >= -5.0]

        _w(
            lines,
            f"**Finding 1 — Benchmark Accuracy:** {len(within_5pp)} of "
            f"{len(with_delta)} quantized variants maintain accuracy within 5 percentage "
            f"points of their FP16/Q8_0 baseline on real MMLU + ARC-Challenge. "
            f"{len(within_3pp)} are within 3pp (negligible degradation).",
        )
        _w(lines)

        if with_delta:
            worst = min(with_delta, key=lambda r: r.get("accuracy_delta_primary_pp", 0))
            bl = worst.get("primary_baseline", "FP16")
            _w(
                lines,
                f"**Finding 2 — Worst Accuracy Drop:** {worst['base_model']} at "
                f"{worst['quant_level']} loses **{worst.get('accuracy_delta_primary_pp', 0):+.1f}pp** "
                f"vs {bl} on benchmark accuracy.",
            )
            _w(lines)

    if quality_rows:
        non_baseline_q = [
            r for r in quality_rows if r["quant_level"] != r.get("primary_baseline")
        ]
        with_delta_q = [
            r
            for r in non_baseline_q
            if r.get("key_metric_avg_delta_primary_pct") is not None
        ]
        if with_delta_q:
            safe_5 = [
                r
                for r in with_delta_q
                if abs(r["key_metric_avg_delta_primary_pct"]) < 5.0
            ]
            _w(
                lines,
                f"**Finding 3 — Generation Quality:** {len(safe_5)} of "
                f"{len(with_delta_q)} quantized variants degrade < 5% vs baseline "
                f"on generation tasks (BERTScore, coherence, ROUGE-L).",
            )
            _w(lines)

    if perf_rows:
        native_rows = [r for r in perf_rows if r.get("native_tok_per_s_mean", 0) > 0]
        if native_rows:
            fastest = max(native_rows, key=lambda r: r["native_tok_per_s_mean"])
            slowest = min(native_rows, key=lambda r: r["native_tok_per_s_mean"])
            _w(
                lines,
                f"**Finding 4 — Throughput Range:** "
                f"{slowest['native_tok_per_s_mean']:.0f} "
                f"to {fastest['native_tok_per_s_mean']:.0f} tok/s (Ollama-native). "
                f"Fastest: {fastest['model']} ({fastest['native_tok_per_s_mean']:.0f} tok/s).",
            )
            _w(lines)

    if cost_rows:
        cheapest = min(cost_rows, key=lambda r: r["cost_per_1m_tokens"])
        _w(
            lines,
            f"**Finding 5 — Cost:** ${cheapest['cost_per_1m_tokens']:.4f}/1M tokens "
            f"({cheapest['base_model']} {cheapest['quant_level']}) "
            f"to ${max(cost_rows, key=lambda r: r['cost_per_1m_tokens'])['cost_per_1m_tokens']:.4f}/1M tokens.",
        )
        _w(lines)

    if power_analysis:
        mde_pp = power_analysis.get("mde_accuracy_pp")
        if mde_pp:
            _w(
                lines,
                f"**Finding 6 — Statistical Resolution:** Experiment can detect "
                f">{mde_pp}pp benchmark accuracy drops at 80% power (alpha=0.05).",
            )
            _w(lines)

    # Tier summary from decision matrix
    if decision_matrix:
        fitting = [d for d in decision_matrix if d["fits"]]
        tier_counts: dict[str, int] = defaultdict(int)
        for d in fitting:
            tier_counts[d["quality_tier"]] += 1
        total_fitting = len(fitting)
        if total_fitting > 0:
            tier_str = ", ".join(f"{v} {k}" for k, v in sorted(tier_counts.items()))
            _w(
                lines,
                f"**Finding 7 — Quality Tiers (fitting models):** {tier_str} "
                f"out of {total_fitting} total fitting (model, quant, VRAM) combinations.",
            )
            _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 2. Benchmark Accuracy (PRIMARY) ───────────────────────────────
    _w(lines, "## 2. Benchmark Accuracy (Primary Quality Gate)")
    _w(lines)
    _w(
        lines,
        "Exact-match accuracy on real benchmark questions from HuggingFace. "
        "**Rescored** accuracy uses regex letter extraction to handle formatting "
        'noise (e.g. "B) Ampere" -> "B"). Raw accuracy is framework exact_match. '
        "Delta in percentage points (pp) vs primary baseline.",
    )
    _w(lines)

    for base in base_models:
        base_rows = sorted(
            [r for r in benchmark_rows if r["base_model"] == base],
            key=lambda r: _quant_sort_key(r["quant_level"]),
        )
        if not base_rows:
            continue

        bl = base_rows[0].get("primary_baseline", "FP16")
        _w(lines, f"### {base} (baseline: {bl})")
        _w(lines)

        # Check which per-task keys are available
        has_mmlu = any(r.get("per_task", {}).get("mmlu_real") for r in base_rows)
        has_arc = any(r.get("per_task", {}).get("arc_challenge") for r in base_rows)

        header = "| Quant | N | Raw Acc | Rescored Acc |"
        sep = "|-------|---|---------|-------------|"
        if has_mmlu:
            header += " MMLU |"
            sep += "------|"
        if has_arc:
            header += " ARC |"
            sep += "-----|"
        header += f" vs {bl} (pp) | Tier |"
        sep += "-------------|------|"

        _w(lines, header)
        _w(lines, sep)

        for row in base_rows:
            delta = row.get("accuracy_delta_primary_pp")

            # Determine tier for this variant
            # Find matching decision_matrix entry to get tier
            tier = "---"
            for dm in decision_matrix:
                if (
                    dm["base_model"] == base
                    and dm["quant_level"] == row["quant_level"]
                    and dm.get("vram_gb", 0) >= 8.0
                ):
                    tier = dm.get("quality_tier", "---")
                    break

            cols = [
                row["quant_level"],
                str(row["n_samples"]),
                f"{row['raw_accuracy']:.3f}",
                f"{row['rescored_accuracy']:.3f}",
            ]

            if has_mmlu:
                mmlu = row.get("per_task", {}).get("mmlu_real", {})
                cols.append(f"{mmlu.get('rescored_acc', 0):.3f}" if mmlu else "---")
            if has_arc:
                arc = row.get("per_task", {}).get("arc_challenge", {})
                cols.append(f"{arc.get('rescored_acc', 0):.3f}" if arc else "---")

            if delta is not None:
                cols.append(f"{delta:+.1f}")
            else:
                cols.append("baseline")

            cols.append(tier)

            _w(lines, "| " + " | ".join(cols) + " |")
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 3. Generation Quality Curves (SECONDARY) ─────────────────────
    _w(lines, "## 3. Generation Quality Curves (Secondary Signal)")
    _w(lines)
    _w(
        lines,
        "Quality on hand-crafted generation tasks (summarization, QA, code, creative writing, "
        "classification). Delta vs primary baseline (FP16 or Q8_0). "
        "These are **secondary** to benchmark accuracy above.",
    )
    _w(lines)

    for base in base_models:
        base_rows = sorted(
            [r for r in quality_rows if r["base_model"] == base],
            key=lambda r: _quant_sort_key(r["quant_level"]),
        )
        if not base_rows:
            continue

        bl = base_rows[0].get("primary_baseline", "FP16")
        _w(lines, f"### {base} (baseline: {bl})")
        _w(lines)
        _w(
            lines,
            f"| Quant | N | BERTScore (vs {bl}) | Coherence (vs {bl}) | ROUGE-L (vs {bl}) "
            f"| Key Avg | vs {bl} |",
        )
        _w(lines, "|-------|---|-----|-----|-----|---------|---------|")

        for row in base_rows:
            cols = [row["quant_level"], str(row["n_samples"])]
            for m in GENERATION_KEY_METRICS:
                mean_val = row.get(f"{m}_mean")
                delta = row.get(f"{m}_delta_primary_pct")
                if mean_val is not None and delta is not None:
                    cols.append(f"{mean_val:.3f} ({delta:+.1f}%)")
                elif mean_val is not None:
                    cols.append(f"{mean_val:.3f}")
                else:
                    cols.append("---")

            key_avg = row.get("key_metric_avg")
            cols.append(f"{key_avg:.4f}" if key_avg is not None else "---")

            key_delta = row.get("key_metric_avg_delta_primary_pct")
            if key_delta is not None:
                cols.append(f"{key_delta:+.1f}%")
            else:
                cols.append("---")

            _w(lines, "| " + " | ".join(cols) + " |")
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 4. Native Performance ─────────────────────────────────────────
    _w(lines, "## 4. Native Performance")
    _w(lines)
    _w(
        lines,
        "Decode throughput from Ollama-native `eval_duration` (no HTTP overhead). "
        "Wall-clock shown for comparison. Overhead % = (native/wall - 1) x 100.",
    )
    _w(lines)

    for base in base_models:
        base_perf = sorted(
            [r for r in perf_rows if r["base_model"] == base],
            key=lambda r: _quant_sort_key(r["quant_level"]),
        )
        if not base_perf:
            continue

        base_cost = {r["quant_level"]: r for r in cost_rows if r["base_model"] == base}

        _w(lines, f"### {base}")
        _w(lines)
        _w(
            lines,
            "| Quant | Native tok/s | CV% | Wall tok/s | Overhead | Speedup vs baseline |",
        )
        _w(
            lines,
            "|-------|-------------|-----|-----------|----------|---------------------|",
        )

        for pr in base_perf:
            speedup = base_cost.get(pr["quant_level"], {}).get("speedup_vs_primary")
            speedup_str = f"{speedup:.2f}x" if speedup is not None else "---"
            overhead = pr.get("http_overhead_pct", 0)
            overhead_str = f"{overhead:.0f}%" if overhead > 0 else "<1%"
            _w(
                lines,
                f"| {pr['quant_level']} "
                f"| {pr['native_tok_per_s_mean']:.1f} "
                f"| {pr['native_cv_pct']:.0f} "
                f"| {pr['wall_tok_per_s_mean']:.1f} "
                f"| {overhead_str} "
                f"| {speedup_str} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 5. TTFT Analysis ──────────────────────────────────────────────
    _w(lines, "## 5. TTFT Analysis")
    _w(lines)
    _w(
        lines,
        "Time-to-first-token (prompt evaluation latency) from Ollama-native "
        "`prompt_eval_duration`.",
    )
    _w(lines)

    ttft_available = [r for r in perf_rows if r.get("ttft_ms_mean", 0) > 0]
    if ttft_available:
        for base in base_models:
            base_ttft = sorted(
                [
                    r
                    for r in perf_rows
                    if r["base_model"] == base and r.get("ttft_ms_mean", 0) > 0
                ],
                key=lambda r: _quant_sort_key(r["quant_level"]),
            )
            if not base_ttft:
                continue

            _w(lines, f"### {base}")
            _w(lines)
            _w(
                lines,
                "| Quant | TTFT Mean (ms) | TTFT Median (ms) | TTFT Std (ms) | Min | Max |",
            )
            _w(
                lines,
                "|-------|----------------|------------------|---------------|-----|-----|",
            )

            for pr in base_ttft:
                _w(
                    lines,
                    f"| {pr['quant_level']} "
                    f"| {pr['ttft_ms_mean']:.0f} "
                    f"| {pr['ttft_ms_median']:.0f} "
                    f"| {pr['ttft_ms_std']:.0f} "
                    f"| {pr['ttft_ms_min']:.0f} "
                    f"| {pr['ttft_ms_max']:.0f} |",
                )
            _w(lines)
    else:
        _w(
            lines,
            "> **Note:** TTFT data not available. Ollama `prompt_eval_duration` "
            "may not be captured in `backend_metadata`. Check framework patch.",
        )
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 6. Cost Analysis ──────────────────────────────────────────────
    _w(lines, "## 6. Cost Analysis")
    _w(lines)
    _w(
        lines,
        "Hardware cost: $0.035/hr (RTX 4080 tier). "
        "Cost = hourly_rate / (native_tok_per_s x 3600) x 1M. "
        "Savings measured vs primary baseline (FP16 or Q8_0, same Ollama backend).",
    )
    _w(lines)

    _w(
        lines,
        "| Model | Quant | Native tok/s | $/1M Tokens | Baseline $/1M | Savings vs Baseline |",
    )
    _w(
        lines,
        "|-------|-------|-------------|-------------|---------------|---------------------|",
    )
    for cr in sorted(
        cost_rows, key=lambda r: (r["base_model"], _quant_sort_key(r["quant_level"]))
    ):
        primary_cost_str = (
            f"${cr['primary_cost_per_1m']:.4f}"
            if cr.get("primary_cost_per_1m")
            else "---"
        )
        savings = cr.get("savings_vs_primary_pct")
        bl = cr.get("primary_baseline", "FP16")
        savings_str = f"{savings:+.0f}% vs {bl}" if savings is not None else "---"
        _w(
            lines,
            f"| {cr['base_model']} | {cr['quant_level']} "
            f"| {cr['native_tok_per_s']:.1f} | ${cr['cost_per_1m_tokens']:.4f} "
            f"| {primary_cost_str} | {savings_str} |",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 7. Decision Matrix (Tiered Quality) ───────────────────────────
    _w(lines, "## 7. Decision Matrix")
    _w(lines)
    _w(
        lines,
        "Per VRAM tier: which (model, quant) combinations fit and maintain quality? "
        "Quality tier determined by the **worse** of benchmark accuracy delta (pp) "
        "and generation quality delta (%). Recommended = fits VRAM AND tier is "
        '"negligible" or "acceptable".',
    )
    _w(lines)
    _w(lines, "Tier thresholds:")
    _w(lines, "- **Negligible:** bench >= -3pp AND gen >= -3%")
    _w(lines, "- **Acceptable:** bench >= -5pp AND gen >= -8%")
    _w(lines, "- **Concerning:** bench >= -10pp AND gen >= -15%")
    _w(lines, "- **Unacceptable:** worse than above")
    _w(lines)

    recommended = [r for r in decision_matrix if r["recommended"]]
    tiers = sorted({r["vram_tier"] for r in decision_matrix})

    # Group by VRAM tier
    tier_recs_map: dict[str, list[dict]] = {}
    for tier in tiers:
        tier_recs_map[tier] = sorted(
            [r for r in recommended if r["vram_tier"] == tier],
            key=lambda r: (-r.get("native_tok_per_s", 0)),
        )

    # Deduplicate identical tiers
    printed_tiers: set[str] = set()
    for i, tier in enumerate(tiers):
        if tier in printed_tiers:
            continue

        same_tiers = [tier]
        tier_models = {(r["base_model"], r["quant_level"]) for r in tier_recs_map[tier]}
        for later_tier in tiers[i + 1 :]:
            later_models = {
                (r["base_model"], r["quant_level"]) for r in tier_recs_map[later_tier]
            }
            if tier_models == later_models:
                same_tiers.append(later_tier)

        for t in same_tiers:
            printed_tiers.add(t)

        tier_label = " / ".join(same_tiers)
        _w(lines, f"### {tier_label} VRAM")
        _w(lines)

        tier_recs = tier_recs_map[tier]
        if not tier_recs:
            _w(lines, "*No quality-safe models fit this VRAM tier.*")
            _w(lines)
            continue

        _w(
            lines,
            "| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier | Native tok/s | $/1M |",
        )
        _w(
            lines,
            "|-------|-------|---------|------------------|---------------|------|-------------|------|",
        )

        for rec in tier_recs:
            bench_d = rec.get("bench_accuracy_delta_pp")
            gen_d = rec.get("gen_quality_delta_pct")
            bl = rec.get("primary_baseline", "FP16")

            bench_str = f"{bench_d:+.1f}" if bench_d is not None else "---"
            gen_str = f"{gen_d:+.1f}" if gen_d is not None else "---"
            cost_str = f"${rec['cost_per_1m']:.4f}" if rec.get("cost_per_1m") else "---"
            tok_s = rec.get("native_tok_per_s", 0)
            tok_str = f"{tok_s:.1f}" if tok_s > 0 else "---"

            _w(
                lines,
                f"| {rec['base_model']} | {rec['quant_level']} "
                f"| {rec['vram_est_gb']:.1f} GB | {bench_str} "
                f"| {gen_str} | {rec['quality_tier']} "
                f"| {tok_str} | {cost_str} |",
            )
        _w(lines)

    # Also show all non-recommended for the largest tier (full picture)
    largest_tier = tiers[-1] if tiers else None
    if largest_tier:
        non_rec = [
            d
            for d in decision_matrix
            if d["vram_tier"] == largest_tier and d["fits"] and not d["recommended"]
        ]
        if non_rec:
            _w(
                lines,
                f"### Not Recommended (fit {largest_tier} but concerning/unacceptable)",
            )
            _w(lines)
            _w(
                lines,
                "| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier |",
            )
            _w(
                lines,
                "|-------|-------|---------|------------------|---------------|------|",
            )
            for rec in sorted(
                non_rec,
                key=lambda r: (r["base_model"], _quant_sort_key(r["quant_level"])),
            ):
                bench_d = rec.get("bench_accuracy_delta_pp")
                gen_d = rec.get("gen_quality_delta_pct")
                bench_str = f"{bench_d:+.1f}" if bench_d is not None else "---"
                gen_str = f"{gen_d:+.1f}" if gen_d is not None else "---"
                _w(
                    lines,
                    f"| {rec['base_model']} | {rec['quant_level']} "
                    f"| {rec['vram_est_gb']:.1f} GB | {bench_str} "
                    f"| {gen_str} | {rec['quality_tier']} |",
                )
            _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 8. Diminishing Returns ────────────────────────────────────────
    _w(lines, "## 8. Diminishing Returns")
    _w(lines)
    _w(
        lines,
        "Marginal quality gain vs cost increase when stepping to a higher quant level. "
        "Bench gain in percentage points, gen gain is key_metric_avg difference.",
    )
    _w(lines)

    _w(
        lines,
        "| Model | Step | Bench Gain (pp) | Gen Gain | Cost Increase | Speed Loss |",
    )
    _w(
        lines,
        "|-------|------|-----------------|----------|---------------|------------|",
    )
    for dr in diminishing:
        bg = dr.get("bench_accuracy_gain_pp")
        bg_str = f"{bg:+.1f}" if bg is not None else "---"
        gg = dr.get("gen_quality_gain")
        gg_str = f"{gg:+.4f}" if gg is not None else "---"
        ci = dr.get("cost_increase_pct")
        ci_str = f"{ci:+.1f}%" if ci is not None else "---"
        sl = dr.get("speed_loss_pct")
        sl_str = f"{sl:+.1f}%" if sl is not None else "---"
        _w(
            lines,
            f"| {dr['base_model']} | {dr['from_quant']} -> {dr['to_quant']} "
            f"| {bg_str} | {gg_str} | {ci_str} | {sl_str} |",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 9. Statistical Tests ──────────────────────────────────────────
    _w(lines, "## 9. Statistical Tests")
    _w(lines)
    _w(
        lines,
        "Pairwise t-tests between adjacent quant levels. "
        "Benchmark tests use rescored exact_match (binary). "
        "Generation tests use BERTScore, coherence, ROUGE-L.",
    )
    _w(lines)

    bench_tests = [p for p in pairwise if p.get("source") == "benchmark"]
    gen_tests = [p for p in pairwise if p.get("source") == "generation"]

    # Benchmark tests
    bench_sig = [p for p in bench_tests if p["significant"]]
    if bench_tests:
        _w(
            lines,
            f"### Benchmark Accuracy Tests ({len(bench_sig)}/{len(bench_tests)} significant)",
        )
        _w(lines)
        if bench_sig:
            _w(
                lines,
                "| Model | Higher Q | Lower Q | N | Mean H | Mean L "
                "| Cohen's d | p-value |",
            )
            _w(
                lines,
                "|-------|----------|---------|---|--------|--------"
                "|-----------|---------|",
            )
            for t in sorted(
                bench_sig,
                key=lambda x: (x["base_model"], _quant_sort_key(x["quant_higher"])),
            ):
                _w(
                    lines,
                    f"| {t['base_model']} "
                    f"| {t['quant_higher']} | {t['quant_lower']} "
                    f"| {t.get('n_a', '?')} "
                    f"| {t['mean_higher']:.4f} | {t['mean_lower']:.4f} "
                    f"| {t['effect_size']:.3f} | {t['p_value']:.4f} |",
                )
            _w(lines)
        else:
            _w(
                lines,
                "*No significant benchmark accuracy differences between adjacent quant levels.*",
            )
            _w(lines)

    # Generation tests
    gen_sig = [p for p in gen_tests if p["significant"]]
    if gen_tests:
        _w(
            lines,
            f"### Generation Quality Tests ({len(gen_sig)}/{len(gen_tests)} significant)",
        )
        _w(lines)
        if gen_sig:
            _w(
                lines,
                "| Model | Metric | Higher Q | Lower Q | N | Mean H | Mean L "
                "| Cohen's d | p-value |",
            )
            _w(
                lines,
                "|-------|--------|----------|---------|---|--------|--------"
                "|-----------|---------|",
            )
            for t in sorted(gen_sig, key=lambda x: (x["base_model"], x["metric"])):
                _w(
                    lines,
                    f"| {t['base_model']} | {t['metric']} "
                    f"| {t['quant_higher']} | {t['quant_lower']} "
                    f"| {t.get('n_a', '?')} "
                    f"| {t['mean_higher']:.4f} | {t['mean_lower']:.4f} "
                    f"| {t['effect_size']:.3f} | {t['p_value']:.4f} |",
                )
            _w(lines)
        else:
            _w(
                lines,
                "*No significant generation quality differences between adjacent quant levels.*",
            )
            _w(lines)

    total_tests = len(pairwise)
    total_sig = len(bench_sig) + len(gen_sig)
    if total_tests > 0:
        _w(
            lines,
            f"**Summary:** {total_sig}/{total_tests} tests significant at p<0.05 "
            f"(benchmark: {len(bench_sig)}/{len(bench_tests)}, "
            f"generation: {len(gen_sig)}/{len(gen_tests)}).",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 10. Power Analysis ────────────────────────────────────────────
    _w(lines, "## 10. Power Analysis")
    _w(lines)
    _w(
        lines,
        "Minimum detectable effect sizes for this experiment design, computed "
        "using normal approximation at alpha=0.05, power=0.80.",
    )
    _w(lines)

    if power_analysis:
        bench_n = power_analysis.get("benchmark_n_per_variant", 0)
        gen_n = power_analysis.get("generation_n_per_variant", 0)
        mde_pp = power_analysis.get("mde_accuracy_pp")
        mde_d = power_analysis.get("mde_cohens_d")

        _w(lines, "| Metric Type | N per Variant | MDE | Interpretation |")
        _w(lines, "|------------|--------------|-----|----------------|")
        if mde_pp is not None:
            _w(
                lines,
                f"| Benchmark accuracy (binary) | {bench_n} "
                f"| {mde_pp}pp | Cannot detect <{mde_pp}pp accuracy differences |",
            )
        if mde_d is not None:
            _w(
                lines,
                f"| Generation quality (continuous) | {gen_n} "
                f"| d={mde_d} | Small effects (d<{mde_d}) are below resolution |",
            )
        _w(lines)

        _w(
            lines,
            f"**Implication:** Accuracy differences smaller than ~{mde_pp}pp "
            f"are **below our measurement resolution**. The tiered thresholds "
            f"(3pp/5pp/10pp) should be interpreted with this limitation in mind. "
            f'The "negligible" tier (-3pp) is near the detection limit.',
        )
    else:
        _w(lines, "> Power analysis data not available.")
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 11. Cross-Phase Validation ────────────────────────────────────
    _w(lines, "## 11. Cross-Phase Validation")
    _w(lines)
    _w(
        lines,
        "Phase 1 vs Phase 2 Q8_0 results for overlapping models "
        "(generation tasks only — benchmark tasks excluded). "
        "Same Ollama tags, same temp=0. Should be consistent (< 5% difference).",
    )
    _w(lines)

    if cross_phase:
        _w(
            lines,
            "| Model | Metric | Phase 1 Mean (N) | Phase 2 Mean (N) | Diff % | Status |",
        )
        _w(
            lines,
            "|-------|--------|------------------|------------------|--------|--------|",
        )
        for c in cross_phase:
            status = "OK" if c["consistent"] else "DIVERGENT"
            _w(
                lines,
                f"| {c['base_model']} | {c['metric']} "
                f"| {c['phase1_mean']:.4f} ({c['phase1_n']}) "
                f"| {c['phase2_mean']:.4f} ({c['phase2_n']}) "
                f"| {c['diff_pct']:+.1f}% | {status} |",
            )
        _w(lines)

        consistent_count = sum(1 for c in cross_phase if c["consistent"])
        _w(
            lines,
            f"**{consistent_count}/{len(cross_phase)} metrics consistent** (< 5% difference).",
        )
    else:
        _w(lines, "> Phase 1 results not found for cross-phase comparison.")
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 12. Methodology & Limitations ─────────────────────────────────
    _w(lines, "## 12. Methodology & Limitations")
    _w(lines)
    _w(lines, "### Methodology")
    _w(lines)
    _w(lines, "- **Backend:** Ollama HTTP API (`/api/generate`)")
    _w(lines, "- **Temperature:** 0.0 (greedy decoding)")
    _w(lines, "- **Repetitions:** 1 (TR124 Phase 3 confirmed temp=0 has < 2% CV)")
    _w(
        lines,
        "- **Benchmark tasks:** MMLU (285 questions, 57 subjects from cais/mmlu) + "
        "ARC-Challenge (200 questions from allenai/ai2_arc) — real HuggingFace data, "
        "generation-based scoring via exact letter match",
    )
    _w(
        lines,
        "- **Generation tasks:** summarization, QA, code_generation, creative_writing, "
        "classification (50 samples each, hand-crafted)",
    )
    _w(lines, f"- **Quant levels:** {', '.join(QUANT_PRECISION_ORDER)}")
    _w(
        lines,
        "- **Models:** llama3.2-1b, llama3.2-3b, qwen2.5-1.5b, phi-2 "
        "(all 7 levels incl FP16); llama3.1-8b (6 levels, no FP16)",
    )
    _w(
        lines,
        "- **Quality baseline:** FP16 Ollama (same instruct model, same backend) "
        "for small models; Q8_0 for llama3.1-8b",
    )
    _w(lines, "- **Primary quality gate:** Benchmark accuracy (rescored exact_match)")
    _w(
        lines,
        "- **Secondary quality signal:** Generation metrics (BERTScore, coherence, ROUGE-L)",
    )
    _w(
        lines,
        "- **Quality classification:** Tiered (negligible/acceptable/concerning/unacceptable) "
        "based on worse of benchmark accuracy (pp) and generation quality (%)",
    )
    _w(
        lines,
        "- **Performance timing:** Ollama-native `eval_duration` and "
        "`prompt_eval_duration` from `backend_metadata`",
    )
    _w(lines, "- **Cost methodology:** $0.035/hr / (native_tok_per_s x 3600) x 1M")
    _w(lines, "- **VRAM estimates:** params x bpw / 8 x 1.1 overhead factor")
    _w(lines)
    _w(lines, "### Improvements over Phase 1")
    _w(lines)
    _w(lines, "| Weakness | Phase 1 | Phase 2 |")
    _w(lines, "|----------|---------|---------|")
    _w(
        lines,
        "| Statistical power | N=50 (10/task) | N=485 benchmark + 250 generation per variant |",
    )
    _w(
        lines,
        "| Quality gate | BERTScore composite only | Real MMLU + ARC accuracy (primary) + generation (secondary) |",
    )
    _w(
        lines,
        "| Quality classification | Binary (-10% safe/unsafe) | 4-tier (negligible/acceptable/concerning/unacceptable) |",
    )
    _w(
        lines,
        "| Benchmark data | Hand-crafted 50 MMLU-style | 285 real MMLU + 200 real ARC from HuggingFace |",
    )
    _w(
        lines,
        "| Statistical resolution | Not reported | Power analysis with MDE (minimum detectable effect) |",
    )
    _w(lines, "| Throughput | Wall-clock (CV 37-42%) | Ollama-native eval_duration |")
    _w(lines, "| TTFT | Unavailable | Ollama-native prompt_eval_duration |")
    _w(
        lines,
        "| FP16 baseline | TR124 base models (confounded) | FP16 Ollama (same instruct model) |",
    )
    _w(
        lines,
        "| Model size range | All <3B | 1.2B-8B, 5 models (real VRAM tier differentiation) |",
    )
    _w(lines)
    _w(lines, "### Remaining Limitations")
    _w(lines)
    _w(
        lines,
        "- **Benchmark scoring is generation-based**: MMLU/ARC use exact letter match "
        "(with regex re-scoring), not logprob ranking. May undercount correct knowledge "
        "due to formatting errors, especially for smaller models",
    )
    _w(
        lines,
        "- **MMLU subset**: 285/14,042 questions (5 per subject). Sufficient for "
        "detecting large quant-induced drops, but per-subject accuracy has wide confidence intervals",
    )
    _w(
        lines,
        f"- **Statistical resolution**: Cannot detect accuracy differences smaller "
        f"than ~{power_analysis.get('mde_accuracy_pp', '?')}pp (below 80% power threshold)",
    )
    _w(
        lines,
        "- **Ollama quant format may differ**: Tag name suggests a quant level, "
        "but Ollama picks the closest available variant",
    )
    _w(
        lines,
        "- **VRAM estimates are approximate**: Actual usage depends on context "
        "length and batch size",
    )
    _w(
        lines,
        "- **Cost assumes sustained single-stream throughput**: "
        "Batched serving would differ",
    )
    _w(
        lines,
        "- **llama3.1-8b FP16 excluded**: ~16GB does not fit RTX 4080; Q8_0 used as baseline",
    )
    _w(
        lines,
        "- **Single GPU (RTX 4080)**: Results may not generalize to other hardware",
    )
    _w(lines)

    # Write
    report_path = run_dir / "phase2_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote Phase 2 report: %s", report_path)
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR125 Phase 2 report")
    parser.add_argument("--results-dir", default="results/eval/tr125_phase2")
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

    # Load analysis
    analysis_path = run_dir / "phase2_analysis.json"
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    else:
        logger.warning("No phase2_analysis.json — run analyze.py first")
        analysis = {}

    generate_report(run_dir, analysis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
