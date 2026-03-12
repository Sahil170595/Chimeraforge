"""TR124 Phase 1: Post-run analysis.

Reads the framework-generated artifacts (samples.jsonl, aggregate.csv,
summary.json) and performs Phase 1-specific analysis:
  1. Backend equivalence (ANOVA + Holm-Bonferroni)
  2. Quality scaling vs parameter count
  3. Quality-cost Pareto frontier (cross-ref TR123)
  4. Composite quality rankings

Usage:
    python research/tr124/phase1/analyze.py [--results-dir DIR]

The eval framework already generates eval_report.md with these analyses.
This script is for standalone re-analysis or deeper dives.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from scripts.eval.analysis.aggregator import (
    SampleRecord,
    aggregate_by_group,
    compute_metric_summaries,
    load_sample_jsonl,
)
from scripts.eval.analysis.comparisons import (
    anova_across_backends,
    compute_quality_rank_table,
    holm_bonferroni_correction,
    pairwise_backend_comparison,
)

logger = logging.getLogger("tr124.phase1.analyze")

QUALITY_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]


def analyze_backend_equivalence(records: list[SampleRecord]) -> dict:
    """ANOVA + pairwise tests: do backends produce different quality?"""
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    results = {}

    for metric in QUALITY_METRICS:
        anova = anova_across_backends(gen_records, metric)
        pairwise = pairwise_backend_comparison(gen_records, metric)
        corrected = holm_bonferroni_correction(pairwise)

        results[metric] = {
            "anova": anova,
            "pairwise_corrected": corrected,
            "any_significant": any(c["significant_corrected"] for c in corrected),
        }

    return results


def analyze_quality_scaling(records: list[SampleRecord]) -> list[dict]:
    """Per-model composite quality, ordered by parameter count."""
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    model_groups = aggregate_by_group(gen_records, ["model"])

    rows = []
    for (model,), recs in sorted(model_groups.items()):
        summaries = compute_metric_summaries(recs, QUALITY_METRICS)
        means = {m: s.mean for m, s in summaries.items()}
        composite = sum(means.values()) / len(means) if means else 0

        rows.append(
            {
                "model": model,
                "n_samples": len(recs),
                "metrics": means,
                "composite_quality": round(composite, 6),
            }
        )

    rows.sort(key=lambda r: r["composite_quality"], reverse=True)
    return rows


def analyze_rankings(records: list[SampleRecord]) -> dict:
    """Quality rankings by model and backend."""
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    return {
        "by_model": compute_quality_rank_table(gen_records, QUALITY_METRICS, "model"),
        "by_backend": compute_quality_rank_table(
            gen_records, QUALITY_METRICS, "backend"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="TR124 Phase 1 analysis")
    parser.add_argument(
        "--results-dir",
        default="results/eval/tr124_phase1",
        help="Phase 1 results directory",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Find latest run
    results_path = Path(args.results_dir)
    if not results_path.is_absolute():
        results_path = _REPO / results_path
    runs = sorted([d for d in results_path.iterdir() if d.is_dir()], reverse=True)
    if not runs:
        logger.error("No runs found in %s", results_path)
        return 1

    run_dir = runs[0]
    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl in %s", run_dir)
        return 1

    logger.info("Analyzing %s", run_dir)
    records = load_sample_jsonl(jsonl_path)
    logger.info("Loaded %d records", len(records))

    # Run analyses
    equiv = analyze_backend_equivalence(records)
    scaling = analyze_quality_scaling(records)
    rankings = analyze_rankings(records)

    # Print summary
    print(f"\n{'='*60}")
    print(f"TR124 Phase 1 Analysis — {len(records)} samples")
    print(f"{'='*60}")

    print("\n--- Backend Equivalence ---")
    for metric, result in equiv.items():
        anova = result["anova"]
        sig = "SIGNIFICANT" if result["any_significant"] else "not significant"
        p = anova.get("p_value", "N/A")
        print(f"  {metric:15s}: F={anova.get('f_statistic', 0):.2f}, p={p}, {sig}")

    print("\n--- Quality Scaling ---")
    for row in scaling:
        print(f"  {row['model']:20s}: composite={row['composite_quality']:.4f}")

    print("\n--- Rankings (by model) ---")
    for row in rankings["by_model"]:
        print(f"  {row['model']:20s}: rank={row.get('composite_rank', 0):.1f}")

    # Save analysis JSON
    analysis = {
        "backend_equivalence": equiv,
        "quality_scaling": scaling,
        "rankings": rankings,
    }
    out_path = run_dir / "phase1_analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    logger.info("Saved analysis to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
