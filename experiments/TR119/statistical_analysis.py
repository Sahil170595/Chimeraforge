#!/usr/bin/env python3
"""
TR119: Statistical analysis with frontier lab rigor.

Provides:
- Hypothesis testing (t-tests, ANOVA)
- Effect sizes (Cohen's d)
- Bootstrap confidence intervals
- Pairwise comparisons with p-values
- Outlier detection
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import scipy.stats as stats

# Reuse TR117's statistical analysis infrastructure
try:
    from scripts.tr117.statistical_analysis import (
        ComparisonResult,
        StatisticalSummary,
        anova_backends,
        bootstrap_confidence_interval,
        compare_groups,
        compute_percentiles,
        compute_summary,
        detect_outliers,
    )
except ImportError:
    # Fallback implementation if TR117 not available
    @dataclass
    class StatisticalSummary:
        mean: float
        median: float
        std: float
        min: float
        max: float
        q25: float
        q75: float
        ci_lower: float
        ci_upper: float
        n: int

    @dataclass
    class ComparisonResult:
        group_a: str
        group_b: str
        metric: str
        mean_a: float
        mean_b: float
        difference: float
        percent_change: float
        t_statistic: float
        p_value: float
        significant: bool
        effect_size: float

    def compute_summary(values: list[float]) -> StatisticalSummary:
        if not values:
            return StatisticalSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        arr = np.array(values)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1))
        n = len(arr)
        ci = stats.t.interval(0.95, n - 1, loc=mean, scale=stats.sem(arr))
        return StatisticalSummary(
            mean=mean,
            median=float(np.median(arr)),
            std=std,
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            q25=float(np.percentile(arr, 25)),
            q75=float(np.percentile(arr, 75)),
            ci_lower=float(ci[0]),
            ci_upper=float(ci[1]),
            n=n,
        )

    def compare_groups(
        group_a: list[float],
        group_b: list[float],
        group_a_name: str,
        group_b_name: str,
        metric_name: str,
        alpha: float = 0.05,
    ) -> ComparisonResult:
        arr_a = np.array(group_a)
        arr_b = np.array(group_b)
        mean_a = float(np.mean(arr_a))
        mean_b = float(np.mean(arr_b))
        difference = mean_b - mean_a
        percent_change = (difference / mean_a * 100) if mean_a != 0 else 0
        t_stat, p_value = stats.ttest_ind(arr_a, arr_b)
        pooled_std = np.sqrt(
            ((len(arr_a) - 1) * np.var(arr_a, ddof=1) + (len(arr_b) - 1) * np.var(arr_b, ddof=1))
            / (len(arr_a) + len(arr_b) - 2)
        )
        cohens_d = difference / pooled_std if pooled_std != 0 else 0
        return ComparisonResult(
            group_a=group_a_name,
            group_b=group_b_name,
            metric=metric_name,
            mean_a=mean_a,
            mean_b=mean_b,
            difference=difference,
            percent_change=percent_change,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            significant=float(p_value) < alpha,
            effect_size=float(cohens_d),
        )

    def anova_backends(data: dict[str, list[float]]) -> dict[str, Any]:
        groups = list(data.values())
        f_stat, p_value = stats.f_oneway(*groups)
        return {
            "f_statistic": float(f_stat),
            "p_value": float(p_value),
            "significant": float(p_value) < 0.05,
            "groups": list(data.keys()),
            "n_groups": len(data),
        }

    def bootstrap_confidence_interval(
        values: list[float], n_iterations: int = 10000, confidence: float = 0.95
    ) -> tuple[float, float]:
        if not values:
            return 0.0, 0.0
        arr = np.array(values)
        bootstrap_means = []
        for _ in range(n_iterations):
            sample = np.random.choice(arr, size=len(arr), replace=True)
            bootstrap_means.append(np.mean(sample))
        alpha = 1 - confidence
        lower = np.percentile(bootstrap_means, alpha / 2 * 100)
        upper = np.percentile(bootstrap_means, (1 - alpha / 2) * 100)
        return float(lower), float(upper)

    def compute_percentiles(values: list[float], percentiles: list[int]) -> dict[int, float]:
        if not values:
            return dict.fromkeys(percentiles, 0.0)
        arr = np.array(values)
        return {p: float(np.percentile(arr, p)) for p in percentiles}

    def detect_outliers(values: list[float], method: str = "iqr") -> dict[str, Any]:
        if not values:
            return {"outliers": [], "indices": [], "method": method}
        arr = np.array(values)
        if method == "iqr":
            q25, q75 = np.percentile(arr, [25, 75])
            iqr = q75 - q25
            lower = q25 - 1.5 * iqr
            upper = q75 + 1.5 * iqr
            outlier_mask = (arr < lower) | (arr > upper)
        else:
            z_scores = np.abs(stats.zscore(arr))
            outlier_mask = z_scores > 3
        outlier_indices = np.where(outlier_mask)[0].tolist()
        outlier_values = arr[outlier_mask].tolist()
        return {
            "outliers": outlier_values,
            "indices": outlier_indices,
            "count": len(outlier_indices),
            "method": method,
        }


def analyze_cost_statistics(
    cost_df: Any,  # pd.DataFrame
    metric: str = "total_cost_usd_per_1m_tokens_on_demand",
) -> dict[str, Any]:
    """
    Perform statistical analysis on cost metrics across backends.

    Returns:
        {
            "summaries": {backend: StatisticalSummary},
            "pairwise_comparisons": [ComparisonResult],
            "anova": dict,
            "bootstrap_cis": {backend: (lower, upper)},
        }
    """
    summaries: dict[str, StatisticalSummary] = {}
    comparisons: list[ComparisonResult] = []
    bootstrap_cis: dict[str, tuple[float, float]] = {}

    backends = cost_df["backend"].unique()
    
    # Compute summaries per backend
    for backend in backends:
        backend_data = cost_df[cost_df["backend"] == backend][metric].dropna().tolist()
        if backend_data:
            summaries[backend] = compute_summary(backend_data)
            bootstrap_cis[backend] = bootstrap_confidence_interval(backend_data)

    # Pairwise comparisons
    backend_list = list(summaries.keys())
    for i, backend_a in enumerate(backend_list):
        for backend_b in backend_list[i + 1:]:
            data_a = cost_df[cost_df["backend"] == backend_a][metric].dropna().tolist()
            data_b = cost_df[cost_df["backend"] == backend_b][metric].dropna().tolist()
            if data_a and data_b:
                comp = compare_groups(data_a, data_b, backend_a, backend_b, metric)
                comparisons.append(comp)

    # ANOVA
    anova_data = {
        backend: cost_df[cost_df["backend"] == backend][metric].dropna().tolist()
        for backend in backends
        if len(cost_df[cost_df["backend"] == backend][metric].dropna()) > 0
    }
    anova_results = anova_backends(anova_data) if len(anova_data) > 1 else {}

    return {
        "summaries": {k: {
            "mean": v.mean,
            "median": v.median,
            "std": v.std,
            "ci_95_lower": v.ci_lower,
            "ci_95_upper": v.ci_upper,
            "n": v.n,
        } for k, v in summaries.items()},
        "pairwise_comparisons": [
            {
                "group_a": c.group_a,
                "group_b": c.group_b,
                "metric": c.metric,
                "mean_a": c.mean_a,
                "mean_b": c.mean_b,
                "difference": c.difference,
                "percent_change": c.percent_change,
                "t_statistic": c.t_statistic,
                "p_value": c.p_value,
                "significant": c.significant,
                "effect_size_cohens_d": c.effect_size,
            }
            for c in comparisons
        ],
        "anova": anova_results,
        "bootstrap_cis": {k: {"lower": v[0], "upper": v[1]} for k, v in bootstrap_cis.items()},
    }


def save_statistical_report(
    analysis: dict[str, Any],
    output_path: Path,
) -> None:
    """Save statistical analysis report to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")


def main() -> int:
    """Run statistical analysis on TR119 cost data."""
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description="TR119 statistical analysis")
    parser.add_argument(
        "--cost-summary",
        default=None,
        help="Cost summary JSON (defaults to latest in results/processed)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (defaults to results/processed/statistical_analysis.json)",
    )
    args = parser.parse_args()

    from pathlib import Path
    import sys

    _REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

    # Reuse TR118's artifact_utils for path resolution
    try:
        from scripts.tr118.artifact_utils import resolve_repo_path
    except ImportError:
        # Fallback if TR118 not available
        def resolve_repo_path(repo_root: Path, path_value: str | Path) -> Path:
            p = Path(path_value)
            if p.is_absolute():
                return p
            return (repo_root / p).resolve()

    # Load cost data
    if args.cost_summary:
        cost_path = resolve_repo_path(_REPO_ROOT, str(args.cost_summary))
    else:
        # Find latest cost summary
        results_dir = resolve_repo_path(_REPO_ROOT, "scripts/tr119/results")
        processed_dir = results_dir / "processed"
        cost_files = sorted(processed_dir.glob("cost_energy_summary*.json"), key=lambda p: p.stat().st_mtime)
        if not cost_files:
            print("No cost summary found")
            return 1
        cost_path = cost_files[-1]

    cost_data = json.loads(cost_path.read_text(encoding="utf-8"))
    cost_df = pd.DataFrame(cost_data.get("rows", []))

    if cost_df.empty:
        print("No cost data to analyze")
        return 1

    # Analyze cost statistics (overall + per-mode when available)
    analysis: dict[str, Any] = {"overall": analyze_cost_statistics(cost_df)}
    if "mode" in cost_df.columns:
        analysis["by_mode"] = {}
        for mode in sorted(cost_df["mode"].dropna().unique()):
            subset = cost_df[cost_df["mode"] == mode]
            if not subset.empty:
                analysis["by_mode"][str(mode)] = analyze_cost_statistics(subset)

    # Save report
    if args.output:
        out_path = resolve_repo_path(_REPO_ROOT, str(args.output))
    else:
        out_path = cost_path.parent / "statistical_analysis.json"
    
    save_statistical_report(analysis, out_path)
    print(f"Statistical analysis saved to {out_path}")

    # Print summary
    def _print_summary(label: str, data: dict[str, Any]) -> None:
        print(f"\n=== Statistical Summary ({label}) ===")
        for backend, summary in data.get("summaries", {}).items():
            print(f"{backend}:")
            print(f"  Mean: ${summary['mean']:.4f}/1M tokens")
            print(f"  95% CI: [${summary['ci_95_lower']:.4f}, ${summary['ci_95_upper']:.4f}]")
            print(f"  n={summary['n']}")

        if data.get("pairwise_comparisons"):
            print("\n=== Significant Differences (p < 0.05) ===")
            for comp in data["pairwise_comparisons"]:
                if comp["significant"]:
                    print(f"{comp['group_a']} vs {comp['group_b']}:")
                    print(f"  Difference: ${comp['difference']:.4f} ({comp['percent_change']:.1f}%)")
                    print(f"  p-value: {comp['p_value']:.4f}, Cohen's d: {comp['effect_size_cohens_d']:.3f}")

        if data.get("anova", {}).get("significant"):
            print(
                f"\n=== ANOVA: Significant (F={data['anova']['f_statistic']:.2f}, "
                f"p={data['anova']['p_value']:.4f}) ==="
            )

    if "by_mode" in analysis and analysis["by_mode"]:
        for mode, data in analysis["by_mode"].items():
            _print_summary(str(mode), data)
    else:
        _print_summary("overall", analysis.get("overall", analysis))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
