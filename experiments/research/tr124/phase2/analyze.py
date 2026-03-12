"""TR124 Phase 2: Quantization degradation analysis.

Reads framework output (samples.jsonl) and performs Phase 2-specific analysis:
  1. Group records by base model → quant level
  2. Compute quality deltas within each base model (Q8_0 vs Q4_K_M)
  3. Compare against Phase 1 FP16 baselines (cross-phase delta)
  4. Pairwise t-tests within each base model across quant levels
  5. Compute composite degradation rankings

Usage:
    python research/tr124/phase2/analyze.py [--results-dir DIR] [--phase1-dir DIR]
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
from research.tr124.shared.utils import (
    extract_base_model,
    extract_quant_level,
    find_latest_run,
    load_phase1_per_model_quality,
)
from scripts.eval.analysis.aggregator import (
    SampleRecord,
    compute_metric_summaries,
    load_sample_jsonl,
)

logger = logging.getLogger("tr124.phase2.analyze")

QUALITY_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]

# Quant precision order: higher = better quality (for determining reference)
QUANT_PRECISION_ORDER = ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]


def group_by_base_model(
    records: list[SampleRecord],
) -> dict[str, dict[str, list[SampleRecord]]]:
    """Group records by base model, then by quant level.

    Returns: {base_model -> {quant_level -> [records]}}
    """
    grouped: dict[str, dict[str, list[SampleRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        base = extract_base_model(r.model)
        quant = extract_quant_level(r.model)
        grouped[base][quant].append(r)
    return dict(grouped)


def compute_degradation_table(
    records: list[SampleRecord],
    phase1_baselines: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Compute quality per (base_model, quant_level) with deltas.

    Delta computation:
    - Within-run delta: relative to highest-precision quant in THIS run
    - Cross-phase delta: relative to Phase 1 FP16 baseline (if available)
    """
    by_base = group_by_base_model(records)
    rows = []

    for base_model, quant_groups in sorted(by_base.items()):
        # Find highest-precision quant level in this run as local reference
        local_ref_quant = None
        for q in QUANT_PRECISION_ORDER:
            if q in quant_groups:
                local_ref_quant = q
                break

        # Local reference means
        ref_means: dict[str, float] = {}
        if local_ref_quant:
            ref_summaries = compute_metric_summaries(
                quant_groups[local_ref_quant], QUALITY_METRICS
            )
            ref_means = {m: s.mean for m, s in ref_summaries.items()}

        # Phase 1 FP16 reference means (cross-phase)
        # Map base model names: "llama3.2-1b" → "llama-3.2-1b" (Phase 1 naming)
        phase1_means: dict[str, float] = {}
        if phase1_baselines:
            # Try exact match first, then fuzzy
            for p1_name, p1_metrics in phase1_baselines.items():
                p1_base = extract_base_model(p1_name)
                if p1_base == base_model or _fuzzy_model_match(p1_base, base_model):
                    phase1_means = p1_metrics
                    break

        for quant_level, q_records in sorted(quant_groups.items()):
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

                # Within-run delta (vs highest quant in this run)
                if metric in ref_means and ref_means[metric] != 0:
                    delta = s.mean - ref_means[metric]
                    pct = (delta / ref_means[metric]) * 100
                    row[f"{metric}_delta_local"] = round(delta, 6)
                    row[f"{metric}_delta_local_pct"] = round(pct, 2)

                # Cross-phase delta (vs Phase 1 FP16)
                if metric in phase1_means and phase1_means[metric] != 0:
                    delta = s.mean - phase1_means[metric]
                    pct = (delta / phase1_means[metric]) * 100
                    row[f"{metric}_delta_fp16"] = round(delta, 6)
                    row[f"{metric}_delta_fp16_pct"] = round(pct, 2)

            # Composite quality
            means = [summaries[m].mean for m in QUALITY_METRICS if m in summaries]
            if means:
                row["composite_quality"] = round(sum(means) / len(means), 6)

            rows.append(row)

    return rows


def _fuzzy_model_match(name_a: str, name_b: str) -> bool:
    """Match model names with different separators (llama-3.2-1b vs llama3.2-1b)."""

    def normalize(s):
        return s.replace("-", "").replace(".", "").lower()

    return normalize(name_a) == normalize(name_b)


def pairwise_quant_comparison(
    records: list[SampleRecord],
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """Pairwise t-tests across quant levels within each base model."""
    by_base = group_by_base_model(records)
    results = []

    for base_model, quant_groups in sorted(by_base.items()):
        quant_levels = sorted(quant_groups.keys())
        if len(quant_levels) < 2:
            continue

        for metric in QUALITY_METRICS:
            for i, qa in enumerate(quant_levels):
                for qb in quant_levels[i + 1 :]:
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
                                "quant_a": qa,
                                "quant_b": qb,
                                "metric": metric,
                                "mean_a": cr.mean_a,
                                "mean_b": cr.mean_b,
                                "difference": cr.difference,
                                "percent_change": cr.percent_change,
                                "t_statistic": cr.t_statistic,
                                "p_value": cr.p_value,
                                "effect_size": cr.effect_size,
                                "significant": cr.significant,
                            }
                        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="TR124 Phase 2 analysis")
    parser.add_argument("--results-dir", default="results/eval/tr124_phase2")
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

    # Load Phase 1 FP16 baselines
    phase1_baselines = load_phase1_per_model_quality(args.phase1_dir)
    if phase1_baselines:
        logger.info("Loaded Phase 1 baselines for %d models", len(phase1_baselines))
    else:
        logger.warning("No Phase 1 baselines found — cross-phase deltas unavailable")

    # Analysis
    degrad = compute_degradation_table(gen_records, phase1_baselines)
    comparisons = pairwise_quant_comparison(gen_records)

    # Print summary
    print(f"\n{'='*60}")
    print(f"TR124 Phase 2 Quantization Analysis — {len(gen_records)} samples")
    print(f"{'='*60}")

    print("\n--- Degradation Table ---")
    for row in degrad:
        composite = row.get("composite_quality", 0)
        delta_strs = []
        for m in QUALITY_METRICS:
            d = row.get(f"{m}_delta_local_pct")
            if d is not None:
                delta_strs.append(f"{m}:{d:+.1f}%")
        delta_summary = ", ".join(delta_strs[:3]) if delta_strs else "ref"
        print(
            f"  {row['base_model']:20s} {row['quant_level']:8s} "
            f"composite={composite:.4f}  [{delta_summary}]"
        )

    sig_count = sum(1 for c in comparisons if c["significant"])
    print("\n--- Pairwise Comparisons ---")
    print(f"  {sig_count}/{len(comparisons)} significant (alpha=0.05)")
    for c in comparisons:
        if c["significant"]:
            print(
                f"  * {c['base_model']}/{c['metric']}: "
                f"{c['quant_a']} vs {c['quant_b']}, "
                f"d={c['effect_size']:.3f}, p={c['p_value']:.4f}"
            )

    # Save
    analysis = {
        "degradation_table": degrad,
        "pairwise_comparisons": comparisons,
        "phase1_baselines_loaded": bool(phase1_baselines),
        "n_significant": sig_count,
        "n_comparisons": len(comparisons),
    }
    out_path = run_dir / "phase2_analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    logger.info("Saved analysis to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
