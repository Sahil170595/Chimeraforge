"""TR124 Phase 3: Sampling variance analysis.

Reads framework output (samples.jsonl) and performs Phase 3-specific analysis:
  1. Per-(model, backend, task, sample) variance across repetitions
  2. Coefficient of variation (CV) as reproducibility measure
  3. Levene's test for variance homogeneity across backends
  4. Repeatability summary: % of measurements under CV thresholds
  5. Cross-phase comparison: Phase 3 variance envelope vs Phase 1 means

Usage:
    python research/tr124/phase3/analyze.py [--results-dir DIR]
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

from research.tr124.shared.utils import find_latest_run
from scripts.eval.analysis.aggregator import (
    SampleRecord,
    aggregate_by_group,
    load_sample_jsonl,
)

logger = logging.getLogger("tr124.phase3.analyze")

QUALITY_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]


def compute_per_sample_variance(
    records: list[SampleRecord],
) -> list[dict[str, Any]]:
    """Compute variance stats per (model, backend, task, sample_id, metric).

    Returns one row per (model, backend, metric) with aggregated CV stats.
    """
    groups = aggregate_by_group(records, ["model", "backend", "task_name", "sample_id"])

    # Collect per-(model, backend, metric) CV values
    mb_metric_cvs: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    mb_metric_means: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    mb_metric_stds: dict[tuple[str, str, str], list[float]] = defaultdict(list)

    for (model, backend, task, sid), reps in groups.items():
        if len(reps) < 2:
            continue

        for metric in QUALITY_METRICS:
            scores = [
                float(r.metrics[metric]["score"])
                for r in reps
                if metric in r.metrics and r.metrics[metric].get("score") is not None
            ]
            if len(scores) < 2:
                continue

            mean_s = sum(scores) / len(scores)
            std_s = (sum((x - mean_s) ** 2 for x in scores) / (len(scores) - 1)) ** 0.5
            cv = std_s / mean_s if mean_s > 0 else float("inf")

            key = (model, backend, metric)
            mb_metric_cvs[key].append(cv)
            mb_metric_means[key].append(mean_s)
            mb_metric_stds[key].append(std_s)

    rows = []
    for (model, backend, metric), cvs in sorted(mb_metric_cvs.items()):
        means = mb_metric_means[(model, backend, metric)]
        stds = mb_metric_stds[(model, backend, metric)]

        rows.append(
            {
                "model": model,
                "backend": backend,
                "metric": metric,
                "n_samples": len(cvs),
                "grand_mean": round(sum(means) / len(means), 6),
                "mean_std": round(sum(stds) / len(stds), 6),
                "mean_cv": round(sum(cvs) / len(cvs), 6),
                "median_cv": round(sorted(cvs)[len(cvs) // 2], 6),
                "max_cv": round(max(cvs), 6),
                "min_cv": round(min(cvs), 6),
                "stability": _interpret_cv(sum(cvs) / len(cvs)),
            }
        )

    return rows


def _interpret_cv(cv: float) -> str:
    if cv < 0.05:
        return "very stable"
    if cv < 0.15:
        return "stable"
    if cv < 0.30:
        return "moderate"
    return "high variance"


def compute_repeatability_summary(
    records: list[SampleRecord],
) -> dict[str, Any]:
    """Overall repeatability stats: % of measurements under CV thresholds."""
    groups = aggregate_by_group(records, ["model", "backend", "task_name", "sample_id"])
    all_cvs: list[float] = []

    for (model, backend, task, sid), reps in groups.items():
        if len(reps) < 2:
            continue
        for metric in QUALITY_METRICS:
            scores = [
                float(r.metrics[metric]["score"])
                for r in reps
                if metric in r.metrics and r.metrics[metric].get("score") is not None
            ]
            if len(scores) >= 2:
                mean_s = sum(scores) / len(scores)
                if mean_s > 0:
                    std_s = (
                        sum((x - mean_s) ** 2 for x in scores) / (len(scores) - 1)
                    ) ** 0.5
                    all_cvs.append(std_s / mean_s)

    if not all_cvs:
        return {"error": "no multi-rep data"}

    n = len(all_cvs)
    return {
        "n_measurements": n,
        "mean_cv": round(sum(all_cvs) / n, 4),
        "median_cv": round(sorted(all_cvs)[n // 2], 4),
        "max_cv": round(max(all_cvs), 4),
        "pct_cv_under_05": round(sum(1 for cv in all_cvs if cv < 0.05) / n * 100, 1),
        "pct_cv_under_10": round(sum(1 for cv in all_cvs if cv < 0.10) / n * 100, 1),
        "pct_cv_under_20": round(sum(1 for cv in all_cvs if cv < 0.20) / n * 100, 1),
    }


def levene_variance_test(
    records: list[SampleRecord],
) -> dict[str, dict[str, Any]]:
    """Brown-Forsythe test per metric: do backends produce different variance?"""
    try:
        from scipy import stats as sp_stats
    except ImportError:
        return {"error": "scipy not available"}

    groups = aggregate_by_group(records, ["model", "backend", "task_name", "sample_id"])

    results = {}
    for metric in QUALITY_METRICS:
        backend_variances: dict[str, list[float]] = defaultdict(list)
        for (model, backend, task, sid), reps in groups.items():
            scores = [
                float(r.metrics[metric]["score"])
                for r in reps
                if metric in r.metrics and r.metrics[metric].get("score") is not None
            ]
            if len(scores) >= 2:
                mean_s = sum(scores) / len(scores)
                var = sum((x - mean_s) ** 2 for x in scores) / (len(scores) - 1)
                backend_variances[backend].append(var)

        backends = sorted(backend_variances.keys())
        if len(backends) < 2:
            results[metric] = {"error": f"< 2 backends ({len(backends)})"}
            continue

        data = [backend_variances[b] for b in backends]
        try:
            stat, p = sp_stats.levene(*data, center="median")
            results[metric] = {
                "statistic": round(float(stat), 4),
                "p_value": round(float(p), 4),
                "significant": bool(p < 0.05),
                "backends": backends,
            }
        except Exception as e:
            results[metric] = {"error": str(e)}

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="TR124 Phase 3 analysis")
    parser.add_argument("--results-dir", default="results/eval/tr124_phase3")
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
    records = load_sample_jsonl(jsonl_path)
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    logger.info("Loaded %d records (%d generation)", len(records), len(gen_records))

    # Analyses
    variance_rows = compute_per_sample_variance(gen_records)
    repeatability = compute_repeatability_summary(gen_records)
    levene_results = levene_variance_test(gen_records)

    # Print summary
    print(f"\n{'='*60}")
    print(f"TR124 Phase 3 Variance Analysis — {len(gen_records)} samples")
    print(f"{'='*60}")

    if "error" not in repeatability:
        print("\n--- Repeatability ---")
        print(f"  Mean CV: {repeatability['mean_cv']:.4f}")
        print(f"  CV < 5%:  {repeatability['pct_cv_under_05']:.1f}% of measurements")
        print(f"  CV < 10%: {repeatability['pct_cv_under_10']:.1f}% of measurements")
        print(f"  CV < 20%: {repeatability['pct_cv_under_20']:.1f}% of measurements")

    print("\n--- Per-Model Variance ---")
    for row in variance_rows:
        print(
            f"  {row['model']:20s} {row['backend']:25s} {row['metric']:15s} "
            f"CV={row['mean_cv']:.4f} ({row['stability']})"
        )

    print("\n--- Levene's Test (Backend Variance Equality) ---")
    if isinstance(levene_results, dict) and "error" not in levene_results:
        for metric, result in levene_results.items():
            if "error" in result:
                print(f"  {metric:15s}: {result['error']}")
            else:
                sig = "SIGNIFICANT" if result["significant"] else "not significant"
                print(
                    f"  {metric:15s}: F={result['statistic']:.3f}, "
                    f"p={result['p_value']:.4f} ({sig})"
                )

    # Save
    analysis = {
        "variance_by_model_backend": variance_rows,
        "repeatability": repeatability,
        "levene_tests": levene_results,
    }
    out_path = run_dir / "phase3_analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    logger.info("Saved analysis to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
