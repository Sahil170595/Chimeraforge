"""TR125 Phase 1: Quantization decision matrix analysis.

Reads framework output (samples.jsonl) and performs Phase 1-specific analysis:
  1. Quality curves — composite quality per (base_model, quant_level), deltas vs Q8_0
  2. Performance extraction — tok/s and TTFT from raw JSONL backend_metadata
  3. Cost derivation — $/1M tokens per quant level using TR123 methodology
  4. Decision matrix — per VRAM tier, recommend best quality-safe quant
  5. Pairwise t-tests — adjacent quant levels on key metrics
  6. Diminishing returns — quality gain per quant step vs cost increase

Primary quality baseline: Q8_0 (same instruct/chat model, same Ollama backend).
Secondary reference: TR124 Phase 1 FP16 (base model, transformers-gpu — cross-model confound).

Usage:
    python research/tr125/phase1/analyze.py [--results-dir DIR] [-v]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import logging
from pathlib import Path
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
    extract_performance_metrics,
    extract_quant_level,
    find_latest_run,
    fuzzy_model_match,
    load_tr123_fp16_costs,
    load_tr124_phase1_baselines,
)
from scripts.eval.analysis.aggregator import (
    SampleRecord,
    compute_metric_summaries,
    load_sample_jsonl,
)

logger = logging.getLogger("tr125.phase1.analyze")

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


# ── 1. Quality Curves ────────────────────────────────────────────────────────


def compute_quality_curves(
    records: list[SampleRecord],
    fp16_baselines: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Quality per (base_model, quant_level) with Q8_0 and FP16 deltas.

    Primary baseline: Q8_0 (same instruct/chat model, same Ollama backend).
    Secondary: TR124 Phase 1 FP16 (base model, different backend — confounded).

    Returns one row per (base_model, quant_level).
    """
    # Group by base model → quant level
    grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        grouped[base][quant].append(r)

    # First pass: compute Q8_0 metric means per base model
    q8_means_by_model: dict[str, dict[str, float]] = {}
    for base_model in grouped:
        if "Q8_0" in grouped[base_model]:
            q8_records = grouped[base_model]["Q8_0"]
            q8_summaries = compute_metric_summaries(q8_records, QUALITY_METRICS)
            q8_means_by_model[base_model] = {
                m: q8_summaries[m].mean for m in QUALITY_METRICS if m in q8_summaries
            }

    rows = []
    for base_model in sorted(grouped):
        quant_groups = grouped[base_model]

        # Q8_0 baseline (primary — same model variant, same backend)
        q8_means = q8_means_by_model.get(base_model, {})

        # FP16 baseline (secondary — base model, transformers-gpu)
        fp16_means: dict[str, float] = {}
        for p1_name, p1_metrics in fp16_baselines.items():
            p1_base = extract_base_model(p1_name)
            if p1_base == base_model or fuzzy_model_match(p1_base, base_model):
                fp16_means = p1_metrics
                break

        for quant_level in QUANT_PRECISION_ORDER:
            if quant_level not in quant_groups:
                continue

            q_records = quant_groups[quant_level]
            summaries = compute_metric_summaries(q_records, QUALITY_METRICS)

            row: dict[str, Any] = {
                "base_model": base_model,
                "quant_level": quant_level,
                "model_name": q_records[0].model if q_records else "",
                "n_samples": len(q_records),
            }

            for metric in QUALITY_METRICS:
                if metric not in summaries:
                    continue
                s = summaries[metric]
                row[f"{metric}_mean"] = round(s.mean, 6)
                row[f"{metric}_std"] = round(s.std, 6)
                row[f"{metric}_ci_lower"] = round(s.ci_lower, 6)
                row[f"{metric}_ci_upper"] = round(s.ci_upper, 6)

                # Primary: delta vs Q8_0 (same model variant + backend)
                if metric in q8_means and q8_means[metric] != 0:
                    delta_q8 = s.mean - q8_means[metric]
                    pct_q8 = (delta_q8 / q8_means[metric]) * 100
                    row[f"{metric}_delta_q8"] = round(delta_q8, 6)
                    row[f"{metric}_delta_q8_pct"] = round(pct_q8, 2)

                # Secondary: delta vs FP16 (cross-model, cross-backend)
                if metric in fp16_means and fp16_means[metric] != 0:
                    delta = s.mean - fp16_means[metric]
                    pct = (delta / fp16_means[metric]) * 100
                    row[f"{metric}_delta_fp16"] = round(delta, 6)
                    row[f"{metric}_delta_fp16_pct"] = round(pct, 2)

            # Composite quality (all metrics)
            means = [summaries[m].mean for m in QUALITY_METRICS if m in summaries]
            if means:
                row["composite_quality"] = round(sum(means) / len(means), 6)

            # Key-metric average (bertscore, coherence, rouge_l only)
            key_means = [summaries[m].mean for m in KEY_METRICS if m in summaries]
            if key_means:
                row["key_metric_avg"] = round(sum(key_means) / len(key_means), 6)

            # Primary: Key-metric average delta vs Q8_0
            key_deltas_q8 = [
                row[f"{m}_delta_q8_pct"]
                for m in KEY_METRICS
                if f"{m}_delta_q8_pct" in row
            ]
            if key_deltas_q8:
                row["key_metric_avg_delta_q8_pct"] = round(
                    sum(key_deltas_q8) / len(key_deltas_q8), 2
                )

            # Secondary: Key-metric average delta vs FP16
            key_deltas_fp16 = [
                row[f"{m}_delta_fp16_pct"]
                for m in KEY_METRICS
                if f"{m}_delta_fp16_pct" in row
            ]
            if key_deltas_fp16:
                row["key_metric_avg_delta_fp16_pct"] = round(
                    sum(key_deltas_fp16) / len(key_deltas_fp16), 2
                )

            rows.append(row)

    return rows


# ── 2. Performance Extraction ────────────────────────────────────────────────


def aggregate_performance(
    perf_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate tok/s and TTFT per (model, base_model, quant_level).

    Returns one row per model variant with mean/median/std tok/s and TTFT.
    """
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in perf_records:
        by_model[p["model"]].append(p)

    rows = []
    for model_name in sorted(by_model):
        records = by_model[model_name]
        tok_values = [r["tok_per_s"] for r in records if r["tok_per_s"] > 0]
        ttft_values = [r["ttft_ms"] for r in records if r["ttft_ms"] > 0]

        if not tok_values:
            continue

        tok_values_sorted = sorted(tok_values)
        ttft_sorted = sorted(ttft_values) if ttft_values else [0]
        n = len(tok_values)

        rows.append(
            {
                "model": model_name,
                "base_model": extract_base_model(model_name),
                "quant_level": extract_quant_level(model_name),
                "n_samples": n,
                "tok_per_s_mean": round(sum(tok_values) / n, 2),
                "tok_per_s_median": round(tok_values_sorted[n // 2], 2),
                "tok_per_s_std": round(
                    (
                        sum((x - sum(tok_values) / n) ** 2 for x in tok_values)
                        / max(n - 1, 1)
                    )
                    ** 0.5,
                    2,
                ),
                "tok_per_s_min": round(min(tok_values), 2),
                "tok_per_s_max": round(max(tok_values), 2),
                "ttft_ms_mean": (
                    round(sum(ttft_values) / len(ttft_values), 2) if ttft_values else 0
                ),
                "ttft_ms_median": round(ttft_sorted[len(ttft_sorted) // 2], 2),
            }
        )

    return rows


# ── 3. Cost Derivation ───────────────────────────────────────────────────────


def compute_cost_table(
    perf_rows: list[dict[str, Any]],
    fp16_costs: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Derive $/1M tokens per (model, quant_level).

    Primary comparison: Q8_0 within Ollama (same-backend baseline).
    Secondary reference: FP16 from TR123 (cross-backend, for context only).
    """
    # Build Q8_0 baseline lookup per base model (intra-Ollama)
    q8_baseline: dict[str, dict[str, float]] = {}
    for pr in perf_rows:
        if pr["quant_level"] == "Q8_0":
            tok_s = pr["tok_per_s_mean"]
            q8_baseline[pr["base_model"]] = {
                "tok_per_s": tok_s,
                "cost_per_1m": compute_cost_per_1m_tokens(tok_s),
            }

    rows = []
    for pr in perf_rows:
        tok_s = pr["tok_per_s_mean"]
        cost_1m = compute_cost_per_1m_tokens(tok_s)
        base = pr["base_model"]

        # Primary: Q8_0 intra-Ollama comparison
        q8 = q8_baseline.get(base, {})
        q8_tok_s = q8.get("tok_per_s")
        q8_cost = q8.get("cost_per_1m")
        speedup_vs_q8 = round(tok_s / q8_tok_s, 2) if q8_tok_s else None
        savings_vs_q8_pct = (
            round((1 - cost_1m / q8_cost) * 100, 1) if q8_cost and q8_cost > 0 else None
        )

        # Secondary: FP16 cross-backend reference (TR123 transformers-gpu)
        fp16_cost = None
        fp16_tok_s = None
        for tr123_name, tr123_data in fp16_costs.items():
            if tr123_name == base or fuzzy_model_match(tr123_name, base):
                fp16_cost = tr123_data.get("cost_per_1m", 0)
                fp16_tok_s = tr123_data.get("decode_tok_per_s", 0)
                break

        rows.append(
            {
                "model": pr["model"],
                "base_model": base,
                "quant_level": pr["quant_level"],
                "tok_per_s": tok_s,
                "cost_per_1m_tokens": cost_1m,
                # Intra-Ollama Q8_0 baseline (primary)
                "q8_cost_per_1m": q8_cost,
                "q8_tok_per_s": q8_tok_s,
                "speedup_vs_q8": speedup_vs_q8,
                "savings_vs_q8_pct": savings_vs_q8_pct,
                # Cross-backend FP16 reference (secondary)
                "fp16_cost_per_1m": fp16_cost,
                "fp16_tok_per_s": fp16_tok_s,
            }
        )

    return rows


# ── 4. Decision Matrix ───────────────────────────────────────────────────────

# VRAM tiers and approximate capacity (GB available for model weights)
VRAM_TIERS = [
    {"name": "2GB", "vram_gb": 2.0, "description": "Integrated / low-end"},
    {"name": "4GB", "vram_gb": 4.0, "description": "GTX 1650 / MX series"},
    {"name": "6GB", "vram_gb": 6.0, "description": "RTX 3060 / GTX 1660"},
    {"name": "8GB+", "vram_gb": 8.0, "description": "RTX 3070+ / RTX 4080"},
]


def estimate_model_vram_gb(params_m: float, bpw: float) -> float:
    """Estimate VRAM for model weights given params and bits-per-weight.

    VRAM ≈ params * bpw / 8 (bytes) + overhead (~10%)
    """
    params = params_m * 1e6
    bytes_needed = params * bpw / 8
    gb = bytes_needed / (1024**3)
    return gb * 1.1  # 10% overhead for KV cache and framework


def build_decision_matrix(
    quality_rows: list[dict[str, Any]],
    perf_rows: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per VRAM tier, recommend best quality-safe quant with highest tok/s.

    Quality-safe = key_metric_avg_delta_q8_pct > -10% vs Q8_0
    (same model variant, same backend — valid quantization comparison).
    """
    # Build lookup tables
    perf_by_model: dict[str, dict] = {r["model"]: r for r in perf_rows}
    cost_by_model: dict[str, dict] = {r["model"]: r for r in cost_rows}

    # Model params from config names
    params_map = {
        "llama3.2-1b": 1236,
        "qwen2.5-1.5b": 1543,
        "phi-2": 2700,
    }

    recommendations = []
    for tier in VRAM_TIERS:
        tier_vram = tier["vram_gb"]

        for qr in quality_rows:
            base = qr["base_model"]
            quant = qr["quant_level"]
            model_name = qr["model_name"]
            params_m = params_map.get(base, 1500)
            bpw = QUANT_BPW.get(quant, 4.5)

            vram_est = estimate_model_vram_gb(params_m, bpw)
            fits = vram_est <= tier_vram

            # Use Q8_0 delta (primary) for quality threshold
            delta_q8 = qr.get("key_metric_avg_delta_q8_pct")
            # Q8_0 itself has delta=0 by definition — always safe
            if quant == "Q8_0":
                quality_safe = True
                delta_q8 = 0.0
            else:
                quality_safe = delta_q8 is not None and delta_q8 > -10.0

            tok_s = perf_by_model.get(model_name, {}).get("tok_per_s_mean", 0)
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
                    "quality_safe": quality_safe,
                    "key_metric_delta_q8_pct": delta_q8,
                    "tok_per_s": tok_s,
                    "cost_per_1m": cost_1m,
                    "recommended": fits and quality_safe,
                }
            )

    return recommendations


# ── 5. Pairwise T-Tests ──────────────────────────────────────────────────────


def pairwise_adjacent_tests(
    records: list[SampleRecord],
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """Pairwise t-tests between adjacent quant levels within each base model.

    Only tests adjacent levels (Q8_0 vs Q6_K, Q6_K vs Q5_K_M, etc.) on key metrics.
    """
    grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        grouped[base][quant].append(r)

    results = []
    for base_model in sorted(grouped):
        quant_groups = grouped[base_model]
        available = [q for q in QUANT_PRECISION_ORDER if q in quant_groups]

        for i in range(len(available) - 1):
            qa, qb = available[i], available[i + 1]

            for metric in KEY_METRICS:
                values_a = [
                    float(r.metrics[metric]["score"])
                    for r in quant_groups[qa]
                    if metric in r.metrics
                    and r.metrics[metric].get("score") is not None
                ]
                values_b = [
                    float(r.metrics[metric]["score"])
                    for r in quant_groups[qb]
                    if metric in r.metrics
                    and r.metrics[metric].get("score") is not None
                ]

                if len(values_a) >= 2 and len(values_b) >= 2:
                    cr = compare_groups(
                        values_a,
                        values_b,
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


# ── 6. Diminishing Returns ───────────────────────────────────────────────────


def compute_diminishing_returns(
    quality_rows: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Quality gain per quant step vs cost increase.

    For each base model, compute the marginal quality gain and cost change
    when stepping from one quant level to the next higher.
    """
    # Index quality and cost by (base_model, quant_level)
    quality_by_key: dict[tuple[str, str], dict] = {}
    for qr in quality_rows:
        quality_by_key[(qr["base_model"], qr["quant_level"])] = qr

    cost_by_key: dict[tuple[str, str], dict] = {}
    for cr in cost_rows:
        cost_by_key[(cr["base_model"], cr["quant_level"])] = cr

    base_models = sorted({qr["base_model"] for qr in quality_rows})
    results = []

    for base in base_models:
        available = [q for q in QUANT_PRECISION_ORDER if (base, q) in quality_by_key]

        for i in range(len(available) - 1):
            q_higher = available[i]
            q_lower = available[i + 1]

            qr_h = quality_by_key.get((base, q_higher), {})
            qr_l = quality_by_key.get((base, q_lower), {})
            cr_h = cost_by_key.get((base, q_higher), {})
            cr_l = cost_by_key.get((base, q_lower), {})

            quality_gain = None
            km_h = qr_h.get("key_metric_avg")
            km_l = qr_l.get("key_metric_avg")
            if km_h is not None and km_l is not None:
                quality_gain = round(km_h - km_l, 6)

            cost_h = cr_h.get("cost_per_1m_tokens")
            cost_l = cr_l.get("cost_per_1m_tokens")
            cost_increase = None
            cost_increase_pct = None
            if cost_h is not None and cost_l is not None and cost_l > 0:
                cost_increase = round(cost_h - cost_l, 4)
                cost_increase_pct = round((cost_increase / cost_l) * 100, 1)

            tok_h = cr_h.get("tok_per_s", 0)
            tok_l = cr_l.get("tok_per_s", 0)
            speed_loss_pct = None
            if tok_l > 0:
                speed_loss_pct = round((1 - tok_h / tok_l) * 100, 1)

            results.append(
                {
                    "base_model": base,
                    "from_quant": q_lower,
                    "to_quant": q_higher,
                    "quality_gain": quality_gain,
                    "cost_increase": cost_increase,
                    "cost_increase_pct": cost_increase_pct,
                    "speed_loss_pct": speed_loss_pct,
                }
            )

    return results


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR125 Phase 1 analysis")
    parser.add_argument("--results-dir", default="results/eval/tr125")
    parser.add_argument("--phase1-dir", default="results/eval/tr124_phase1")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Find latest run
    run_dir = find_latest_run(args.results_dir)
    if run_dir is None:
        logger.error("No runs found in %s", args.results_dir)
        return 1

    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl in %s", run_dir)
        return 1

    logger.info("Analyzing %s", run_dir)
    records = load_sample_jsonl(jsonl_path)
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    logger.info("Loaded %d records (%d generation)", len(records), len(gen_records))

    # Load cross-TR references
    fp16_baselines = load_tr124_phase1_baselines(args.phase1_dir)
    if fp16_baselines:
        logger.info("Loaded TR124 Phase 1 baselines for %d models", len(fp16_baselines))
    else:
        logger.warning("No TR124 Phase 1 baselines found — FP16 deltas unavailable")

    fp16_costs = load_tr123_fp16_costs()
    if fp16_costs:
        logger.info("Loaded TR123 FP16 costs for %d models", len(fp16_costs))
    else:
        logger.warning("No TR123 cost data found — speedup/savings unavailable")

    # 1. Quality curves
    quality_rows = compute_quality_curves(gen_records, fp16_baselines)
    logger.info("Quality curves: %d rows", len(quality_rows))

    # 2. Performance extraction
    perf_records = extract_performance_metrics(jsonl_path)
    perf_rows = aggregate_performance(perf_records)
    logger.info("Performance: %d model variants", len(perf_rows))

    # 3. Cost derivation
    cost_rows = compute_cost_table(perf_rows, fp16_costs)
    logger.info("Cost table: %d rows", len(cost_rows))

    # 4. Decision matrix
    decision_matrix = build_decision_matrix(quality_rows, perf_rows, cost_rows)
    logger.info("Decision matrix: %d entries", len(decision_matrix))

    # 5. Pairwise t-tests
    pairwise = pairwise_adjacent_tests(gen_records)
    sig_count = sum(1 for p in pairwise if p["significant"])
    logger.info("Pairwise tests: %d/%d significant", sig_count, len(pairwise))

    # 6. Diminishing returns
    diminishing = compute_diminishing_returns(quality_rows, cost_rows)
    logger.info("Diminishing returns: %d steps", len(diminishing))

    # Print summary
    print(f"\n{'='*70}")
    print(f"TR125 Phase 1 Analysis — {len(gen_records)} samples")
    print(f"{'='*70}")

    print("\n--- Quality Curves (vs Q8_0) ---")
    for row in quality_rows:
        q8_str = ""
        d = row.get("key_metric_avg_delta_q8_pct")
        if d is not None:
            q8_str = f" (vs Q8_0: {d:+.1f}%)"
        fp16_str = ""
        d2 = row.get("key_metric_avg_delta_fp16_pct")
        if d2 is not None:
            fp16_str = f" [FP16 ref: {d2:+.1f}%]"
        print(
            f"  {row['base_model']:16s} {row['quant_level']:8s} "
            f"key_avg={row.get('key_metric_avg', 0):.4f}{q8_str}{fp16_str}"
        )

    print("\n--- Performance ---")
    for row in perf_rows:
        print(
            f"  {row['model']:28s} {row['tok_per_s_mean']:7.1f} tok/s  "
            f"TTFT={row['ttft_ms_mean']:.0f}ms"
        )

    print("\n--- Cost ---")
    for row in cost_rows:
        savings = row.get("savings_vs_q8_pct")
        savings_str = f" ({savings:+.0f}% vs Q8_0)" if savings is not None else ""
        print(
            f"  {row['model']:28s} ${row['cost_per_1m_tokens']:.4f}/1M tok{savings_str}"
        )

    print("\n--- Pairwise Tests ---")
    print(f"  {sig_count}/{len(pairwise)} significant (alpha=0.05)")

    # Save
    analysis = {
        "quality_curves": quality_rows,
        "performance": perf_rows,
        "cost_table": cost_rows,
        "decision_matrix": decision_matrix,
        "pairwise_tests": pairwise,
        "diminishing_returns": diminishing,
        "cross_references": {
            "tr124_phase1_loaded": bool(fp16_baselines),
            "tr123_costs_loaded": bool(fp16_costs),
        },
    }
    out_path = run_dir / "phase1_analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    logger.info("Saved analysis to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
