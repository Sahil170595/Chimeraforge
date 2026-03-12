"""TR125 Phase 1: Generate quantization decision matrix report.

Reads framework output + Phase 1 analysis and produces an 8-section markdown report.

Primary quality baseline: Q8_0 (same instruct/chat model, same Ollama backend).
Secondary reference: TR124 Phase 1 FP16 (base model, transformers-gpu — confounded).

Usage:
    python research/tr125/phase1/generate_report.py [--results-dir DIR] [-v]
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

logger = logging.getLogger("tr125.phase1.report")

QUALITY_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]
KEY_METRICS = ["bertscore", "coherence", "rouge_l"]


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _detect_non_monotonic(quality_rows: list[dict[str, Any]]) -> list[str]:
    """Detect base models with non-monotonic quality vs quant level."""
    by_model: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in quality_rows:
        q = r["quant_level"]
        if q in QUANT_PRECISION_ORDER:
            idx = QUANT_PRECISION_ORDER.index(q)
            km = r.get("key_metric_avg")
            if km is not None:
                by_model[r["base_model"]].append((idx, km))

    non_mono = []
    for model, points in by_model.items():
        points.sort()  # sort by precision order index (highest precision first)
        for i in range(len(points) - 1):
            if points[i][1] < points[i + 1][1] - 0.01:
                non_mono.append(model)
                break
    return non_mono


def generate_report(
    run_dir: Path,
    analysis: dict[str, Any],
) -> Path:
    """Generate the Phase 1 markdown report."""
    lines: list[str] = []

    quality_rows = analysis.get("quality_curves", [])
    perf_rows = analysis.get("performance", [])
    cost_rows = analysis.get("cost_table", [])
    decision_matrix = analysis.get("decision_matrix", [])
    pairwise = analysis.get("pairwise_tests", [])
    diminishing = analysis.get("diminishing_returns", [])
    cross_refs = analysis.get("cross_references", {})

    n_models = len({r["base_model"] for r in quality_rows})
    n_quants = len({r["quant_level"] for r in quality_rows})
    n_samples = sum(r["n_samples"] for r in quality_rows)

    # ── Header ────────────────────────────────────────────────────────
    _w(lines, "# TR125 Phase 1: Quantization Decision Matrix")
    _w(lines)
    _w(lines, f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}")
    _w(lines, f"**Models:** {n_models} base models, {n_quants} quant levels")
    _w(lines, f"**Total Samples:** {n_samples}")
    _w(
        lines,
        "**Quality Baseline:** Q8_0 (same instruct/chat model, same Ollama backend)",
    )
    _w(
        lines,
        f"**TR124 FP16 Reference:** {'loaded' if cross_refs.get('tr124_phase1_loaded') else 'not available'} (secondary — base model, different backend)",
    )
    _w(
        lines,
        f"**TR123 Cost Data:** {'loaded' if cross_refs.get('tr123_costs_loaded') else 'not available'}",
    )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 1. Executive Summary ──────────────────────────────────────────
    _w(lines, "## 1. Executive Summary")
    _w(lines)

    # Findings use Q8_0 delta (primary)
    if quality_rows:
        non_q8 = [r for r in quality_rows if r["quant_level"] != "Q8_0"]
        safe_5 = [
            r
            for r in non_q8
            if r.get("key_metric_avg_delta_q8_pct") is not None
            and abs(r["key_metric_avg_delta_q8_pct"]) < 5.0
        ]
        safe_10 = [
            r
            for r in non_q8
            if r.get("key_metric_avg_delta_q8_pct") is not None
            and r["key_metric_avg_delta_q8_pct"] > -10.0
        ]

        _w(
            lines,
            f"**Finding 1 — Quality Safe Zone (vs Q8_0):** {len(safe_5)} of "
            f"{len(non_q8)} quant variants degrade < 5% vs Q8_0, "
            f"and {len(safe_10)} degrade < 10% "
            f"on key metrics (BERTScore, coherence, ROUGE-L).",
        )
        _w(lines)

        worst = min(non_q8, key=lambda r: r.get("key_metric_avg_delta_q8_pct", 0))
        _w(
            lines,
            f"**Finding 2 — Worst Degradation:** {worst['base_model']} at "
            f"{worst['quant_level']} loses **{worst.get('key_metric_avg_delta_q8_pct', 0):.1f}%** "
            f"vs Q8_0.",
        )
        _w(lines)

        # Model robustness ranking
        model_worst: dict[str, float] = {}
        for r in non_q8:
            d = r.get("key_metric_avg_delta_q8_pct")
            if d is not None:
                base = r["base_model"]
                if base not in model_worst or d < model_worst[base]:
                    model_worst[base] = d
        if model_worst:
            best_model = max(model_worst, key=model_worst.get)
            _w(
                lines,
                f"**Finding 3 — Most Robust Model:** {best_model} — "
                f"worst quant still only {model_worst[best_model]:+.1f}% vs Q8_0.",
            )
            _w(lines)

    if perf_rows:
        fastest = max(perf_rows, key=lambda r: r["tok_per_s_mean"])
        slowest = min(perf_rows, key=lambda r: r["tok_per_s_mean"])
        _w(
            lines,
            f"**Finding 4 — Throughput Range:** "
            f"{slowest['tok_per_s_mean']:.0f} "
            f"to {fastest['tok_per_s_mean']:.0f} tok/s (wall-clock, includes HTTP overhead). "
            f"Fastest: {fastest['model']} ({fastest['tok_per_s_mean']:.0f} tok/s).",
        )
        _w(lines)

    if cost_rows:
        cheapest = min(cost_rows, key=lambda r: r["cost_per_1m_tokens"])
        most_expensive = max(cost_rows, key=lambda r: r["cost_per_1m_tokens"])
        _w(
            lines,
            f"**Finding 5 — Cost Range:** "
            f"${cheapest['cost_per_1m_tokens']:.4f} "
            f"to ${most_expensive['cost_per_1m_tokens']:.4f} per 1M tokens (Ollama on RTX 4080).",
        )
        _w(lines)

    # Non-monotonic quality warning
    if quality_rows:
        non_mono = _detect_non_monotonic(quality_rows)
        if non_mono:
            _w(
                lines,
                f"**Caveat — Non-Monotonic Quality:** {', '.join(non_mono)} show(s) "
                f"lower quant levels outperforming higher ones on key metrics. "
                f"With N=50 samples per variant (10 per task), metric noise likely "
                f"exceeds the quality differences between adjacent quant levels. "
                f"Only Q2_K degradation is statistically significant (see Section 7).",
            )
            _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 2. Quality Curves ─────────────────────────────────────────────
    _w(lines, "## 2. Quality Curves")
    _w(lines)
    _w(
        lines,
        "Quality per (model, quant level). Delta measured vs **Q8_0** "
        "(same instruct/chat model, same Ollama backend).",
    )
    _w(lines)
    _w(
        lines,
        "> **Baseline note:** Ollama tags use instruct/chat model variants "
        "(e.g., `llama3.2:1b-instruct`), while TR124 Phase 1 FP16 baselines used "
        "base models (`unsloth/Llama-3.2-1B`). These are different model weights "
        "for llama and qwen. Q8_0 from the same Ollama run is the correct baseline "
        "for measuring quantization effects.",
    )
    _w(lines)

    base_models = sorted({r["base_model"] for r in quality_rows})
    for base in base_models:
        _w(lines, f"### {base}")
        _w(lines)
        _w(
            lines,
            "| Quant | N | BERTScore (vs Q8_0) | Coherence (vs Q8_0) | ROUGE-L (vs Q8_0) "
            "| Key Avg | vs Q8_0 |",
        )
        _w(lines, "|-------|---|-----|-----|-----|---------|---------|")

        base_rows = [r for r in quality_rows if r["base_model"] == base]
        for row in base_rows:
            cols = [row["quant_level"], str(row["n_samples"])]
            for m in KEY_METRICS:
                mean_val = row.get(f"{m}_mean")
                delta = row.get(f"{m}_delta_q8_pct")
                if mean_val is not None and delta is not None:
                    cols.append(f"{mean_val:.3f} ({delta:+.1f}%)")
                elif mean_val is not None:
                    cols.append(f"{mean_val:.3f}")
                else:
                    cols.append("---")

            key_avg = row.get("key_metric_avg")
            cols.append(f"{key_avg:.4f}" if key_avg is not None else "---")

            key_delta = row.get("key_metric_avg_delta_q8_pct")
            if key_delta is not None:
                marker = " **" if key_delta < -10 else ""
                cols.append(f"{key_delta:+.1f}%{marker}")
            else:
                cols.append("---")

            _w(lines, "| " + " | ".join(cols) + " |")
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 3. Performance Curves ─────────────────────────────────────────
    _w(lines, "## 3. Performance Curves")
    _w(lines)
    _w(
        lines,
        "Decode throughput (tok/s) per variant. Speedup measured vs Q8_0 "
        "(same Ollama backend). Wall-clock timing includes HTTP overhead.",
    )
    _w(lines)
    _w(
        lines,
        "> **Note:** TTFT (time-to-first-token) is unavailable — Ollama's "
        "`backend_metadata` was not captured by the eval framework serializer. "
        "All TTFT values would be 0ms and are omitted.",
    )
    _w(lines)

    for base in base_models:
        _w(lines, f"### {base}")
        _w(lines)
        _w(lines, "| Quant | tok/s (mean) | tok/s (std) | Speedup vs Q8_0 |")
        _w(lines, "|-------|-------------|-------------|-----------------|")

        base_perf = [r for r in perf_rows if r["base_model"] == base]
        base_cost = {r["quant_level"]: r for r in cost_rows if r["base_model"] == base}

        for pr in sorted(
            base_perf,
            key=lambda r: (
                QUANT_PRECISION_ORDER.index(r["quant_level"])
                if r["quant_level"] in QUANT_PRECISION_ORDER
                else 99
            ),
        ):
            speedup = base_cost.get(pr["quant_level"], {}).get("speedup_vs_q8")
            speedup_str = f"{speedup:.2f}x" if speedup is not None else "---"
            _w(
                lines,
                f"| {pr['quant_level']} | {pr['tok_per_s_mean']:.1f} "
                f"| {pr['tok_per_s_std']:.1f} "
                f"| {speedup_str} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 4. Cost Analysis ──────────────────────────────────────────────
    _w(lines, "## 4. Cost Analysis")
    _w(lines)
    _w(
        lines,
        "Hardware cost: $0.035/hr (RTX 4080 tier). "
        "Cost = hourly_rate / (tok_per_s × 3600) × 1M. "
        "Savings measured vs Q8_0 (same Ollama backend).",
    )
    _w(lines)

    _w(lines, "| Model | Quant | tok/s | $/1M Tokens | Q8_0 $/1M | Savings vs Q8_0 |")
    _w(lines, "|-------|-------|-------|-------------|-----------|-----------------|")
    for cr in sorted(
        cost_rows,
        key=lambda r: (
            r["base_model"],
            (
                QUANT_PRECISION_ORDER.index(r["quant_level"])
                if r["quant_level"] in QUANT_PRECISION_ORDER
                else 99
            ),
        ),
    ):
        q8_str = f"${cr['q8_cost_per_1m']:.4f}" if cr.get("q8_cost_per_1m") else "---"
        savings = cr.get("savings_vs_q8_pct")
        savings_str = f"{savings:+.0f}%" if savings is not None else "---"
        _w(
            lines,
            f"| {cr['base_model']} | {cr['quant_level']} "
            f"| {cr['tok_per_s']:.1f} | ${cr['cost_per_1m_tokens']:.4f} "
            f"| {q8_str} | {savings_str} |",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 5. Decision Matrix ────────────────────────────────────────────
    _w(lines, "## 5. Decision Matrix")
    _w(lines)
    _w(
        lines,
        "Per VRAM tier: which (model, quant) combinations fit and maintain "
        "quality (< 10% degradation vs Q8_0)?",
    )
    _w(lines)

    recommended = [r for r in decision_matrix if r["recommended"]]
    tiers = sorted({r["vram_tier"] for r in decision_matrix})

    # Check for models excluded from all tiers
    all_base_models = {r["base_model"] for r in decision_matrix}
    recommended_models = {r["base_model"] for r in recommended}
    excluded_models = all_base_models - recommended_models
    if excluded_models:
        _w(
            lines,
            f"> **Excluded models:** {', '.join(sorted(excluded_models))} "
            f"exceed 10% degradation vs Q8_0 at ALL quant levels.",
        )
        _w(lines)

    # Deduplicate identical tiers
    tier_recs_map: dict[str, list[dict]] = {}
    for tier in tiers:
        tier_recs_map[tier] = sorted(
            [r for r in recommended if r["vram_tier"] == tier],
            key=lambda r: r.get("tok_per_s", 0),
            reverse=True,
        )

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

        tier_label = " / ".join(f"{t}" for t in same_tiers)
        _w(lines, f"### {tier_label} VRAM")
        _w(lines)

        tier_recs = tier_recs_map[tier]
        if not tier_recs:
            _w(lines, "*No quality-safe models fit this VRAM tier.*")
            _w(lines)
            continue

        _w(lines, "| Model | Quant | VRAM Est | vs Q8_0 | tok/s | $/1M |")
        _w(lines, "|-------|-------|---------|---------|-------|------|")

        for rec in tier_recs:
            delta = rec.get("key_metric_delta_q8_pct")
            delta_str = f"{delta:+.1f}%" if delta is not None else "---"
            cost_str = f"${rec['cost_per_1m']:.4f}" if rec.get("cost_per_1m") else "---"
            _w(
                lines,
                f"| {rec['base_model']} | {rec['quant_level']} "
                f"| {rec['vram_est_gb']:.1f} GB | {delta_str} "
                f"| {rec['tok_per_s']:.1f} | {cost_str} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # ── 6. Diminishing Returns ────────────────────────────────────────
    _w(lines, "## 6. Diminishing Returns")
    _w(lines)
    _w(
        lines,
        "Marginal quality gain vs cost increase when stepping to a higher quant level.",
    )
    _w(lines)

    _w(lines, "| Model | Step | Quality Gain | Cost Increase | Speed Loss |")
    _w(lines, "|-------|------|-------------|---------------|------------|")
    for dr in diminishing:
        qg = dr.get("quality_gain")
        qg_str = f"{qg:+.4f}" if qg is not None else "---"
        ci = dr.get("cost_increase_pct")
        ci_str = f"{ci:+.1f}%" if ci is not None else "---"
        sl = dr.get("speed_loss_pct")
        sl_str = f"{sl:+.1f}%" if sl is not None else "---"
        _w(
            lines,
            f"| {dr['base_model']} | {dr['from_quant']} -> {dr['to_quant']} "
            f"| {qg_str} | {ci_str} | {sl_str} |",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 7. Statistical Tests ──────────────────────────────────────────
    _w(lines, "## 7. Statistical Tests")
    _w(lines)
    _w(
        lines,
        "Pairwise t-tests between adjacent quant levels on key metrics. "
        "Only significant results shown (p < 0.05).",
    )
    _w(lines)

    sig_tests = [p for p in pairwise if p["significant"]]
    if sig_tests:
        _w(
            lines,
            "| Model | Metric | Higher Q | Lower Q | Mean H | Mean L "
            "| Cohen's d | p-value |",
        )
        _w(
            lines,
            "|-------|--------|----------|---------|--------|--------"
            "|-----------|---------|",
        )
        for t in sorted(sig_tests, key=lambda x: (x["base_model"], x["metric"])):
            _w(
                lines,
                f"| {t['base_model']} | {t['metric']} "
                f"| {t['quant_higher']} | {t['quant_lower']} "
                f"| {t['mean_higher']:.4f} | {t['mean_lower']:.4f} "
                f"| {t['effect_size']:.3f} | {t['p_value']:.4f} |",
            )
        _w(lines)
    else:
        _w(lines, "*No significant differences between adjacent quant levels.*")
        _w(lines)

    total_tests = len(pairwise)
    _w(
        lines,
        (
            f"Total tests: {total_tests}, significant: {len(sig_tests)} "
            f"({len(sig_tests)/total_tests*100:.0f}%)"
            if total_tests > 0
            else ""
        ),
    )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # ── 8. Methodology & Limitations ──────────────────────────────────
    _w(lines, "## 8. Methodology & Limitations")
    _w(lines)
    _w(lines, "### Methodology")
    _w(lines)
    _w(lines, "- **Backend:** Ollama HTTP API (`/api/generate`)")
    _w(lines, "- **Temperature:** 0.0 (greedy decoding)")
    _w(lines, "- **Repetitions:** 1 (TR124 Phase 3 confirmed temp=0 has < 2% CV)")
    _w(lines, "- **Quant levels:** Q2_K, Q3_K_S, Q4_K_M, Q5_K_M, Q6_K, Q8_0")
    _w(
        lines,
        "- **Quality baseline:** Q8_0 from same Ollama run (same model variant + backend)",
    )
    _w(lines, "- **Quality metrics:** " + ", ".join(QUALITY_METRICS))
    _w(lines, "- **Key metrics for decisions:** " + ", ".join(KEY_METRICS))
    _w(lines, "- **Cost methodology:** TR123 (hardware_cost / tok_per_s × 1M)")
    _w(lines, "- **VRAM estimates:** params × bpw / 8 × 1.1 overhead factor")
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines)
    _w(
        lines,
        "- **Base vs instruct model confound:** TR124 Phase 1 FP16 baselines "
        "used base models (`unsloth/Llama-3.2-1B`, `Qwen/Qwen2.5-1.5B`) while "
        "Ollama tags reference instruct/chat variants (`llama3.2:1b-instruct`, "
        "`qwen2.5:1.5b-instruct`, `phi:2.7b-chat-v2`). For llama and qwen these "
        "are different model weights — FP16 deltas mix instruct-tuning effects "
        "with quantization effects. Q8_0 is the correct quantization baseline. "
        "phi-2 is unaffected (same weights, chat template only).",
    )
    _w(
        lines,
        "- **Wall-clock throughput:** tok/s derived from `generation_time_ms / "
        "num_tokens_generated` (includes HTTP overhead, model loading, and prompt "
        "processing). Ollama-native `eval_duration` was not captured by the eval "
        "framework serializer. Relative comparisons between quant levels remain valid.",
    )
    _w(
        lines,
        "- **TTFT unavailable:** `backend_metadata` (including `prompt_eval_ms`) "
        "is not serialized by the eval framework's `SampleRecord`. A framework patch "
        "would be needed for TTFT measurement.",
    )
    _w(
        lines,
        "- **Non-monotonic quality:** Some models show lower quant levels "
        "scoring higher than adjacent higher ones (e.g., llama3.2-1b Q4_K_M > Q8_0). "
        "With N=50 samples (10 per task), metric variance likely exceeds the true "
        "quality difference between adjacent quant levels. Only Q2_K degradation "
        "reaches statistical significance.",
    )
    _w(
        lines,
        "- Ollama's actual quant format may differ from the tag name (Ollama "
        "picks the closest available variant)",
    )
    _w(lines, "- No benchmark accuracy available (Ollama lacks logprob support)")
    _w(
        lines,
        "- VRAM estimates are approximate; actual usage depends on context "
        "length and batch size",
    )
    _w(
        lines,
        "- Cost derivation assumes sustained single-stream throughput; "
        "batched serving would differ",
    )
    _w(lines)

    # Write
    report_path = run_dir / "phase1_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote Phase 1 report: %s", report_path)
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR125 Phase 1 report")
    parser.add_argument("--results-dir", default="results/eval/tr125")
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
    analysis_path = run_dir / "phase1_analysis.json"
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    else:
        logger.warning("No phase1_analysis.json — run analyze.py first")
        analysis = {}

    generate_report(run_dir, analysis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
