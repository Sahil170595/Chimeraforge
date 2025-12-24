"""Statistical analysis tools for TR117 benchmark results."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import scipy.stats as stats


@dataclass
class StatisticalSummary:
    """Statistical summary of a metric."""

    mean: float
    median: float
    std: float
    min: float
    max: float
    q25: float
    q75: float
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    n: int


@dataclass
class ComparisonResult:
    """Statistical comparison between two groups."""

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
    effect_size: float  # Cohen's d


def compute_summary(values: list[float]) -> StatisticalSummary:
    """Compute statistical summary with confidence intervals."""
    if not values:
        return StatisticalSummary(
            mean=0,
            median=0,
            std=0,
            min=0,
            max=0,
            q25=0,
            q75=0,
            ci_lower=0,
            ci_upper=0,
            n=0,
        )

    arr = np.array(values)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    n = len(arr)

    # 95% confidence interval
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
    """Compare two groups with t-test and effect size."""
    arr_a = np.array(group_a)
    arr_b = np.array(group_b)

    mean_a = float(np.mean(arr_a))
    mean_b = float(np.mean(arr_b))
    difference = mean_b - mean_a
    percent_change = (difference / mean_a * 100) if mean_a != 0 else 0

    # Independent t-test
    t_stat, p_value = stats.ttest_ind(arr_a, arr_b)
    t_stat_f = float(t_stat)
    p_value_f = float(p_value)

    # Cohen's d effect size
    pooled_std = np.sqrt(
        (
            (len(arr_a) - 1) * np.var(arr_a, ddof=1)
            + (len(arr_b) - 1) * np.var(arr_b, ddof=1)
        )
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
        t_statistic=t_stat_f,
        p_value=p_value_f,
        significant=p_value_f < alpha,
        effect_size=float(cohens_d),
    )


def anova_backends(data: dict[str, list[float]]) -> dict[str, Any]:
    """Perform one-way ANOVA across backends."""
    groups = list(data.values())
    f_stat, p_value = stats.f_oneway(*groups)

    p_value_f = float(p_value)
    return {
        "f_statistic": float(f_stat),
        "p_value": p_value_f,
        "significant": p_value_f < 0.05,
        "groups": list(data.keys()),
        "n_groups": len(data),
    }


def compute_percentiles(
    values: list[float], percentiles: list[int]
) -> dict[int, float]:
    """Compute specified percentiles."""
    if not values:
        return dict.fromkeys(percentiles, 0.0)

    arr = np.array(values)
    return {p: float(np.percentile(arr, p)) for p in percentiles}


def detect_outliers(values: list[float], method: str = "iqr") -> dict[str, Any]:
    """Detect outliers using IQR or Z-score method."""
    if not values:
        return {"outliers": [], "indices": [], "method": method}

    arr = np.array(values)

    if method == "iqr":
        q25, q75 = np.percentile(arr, [25, 75])
        iqr = q75 - q25
        lower = q25 - 1.5 * iqr
        upper = q75 + 1.5 * iqr
        outlier_mask = (arr < lower) | (arr > upper)
    else:  # z-score
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


def bootstrap_confidence_interval(
    values: list[float],
    n_iterations: int = 10000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute bootstrap confidence interval."""
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


def save_statistical_report(
    summaries: dict[str, StatisticalSummary],
    comparisons: list[ComparisonResult],
    anova_results: dict[str, Any],
    output_path: Path,
) -> None:
    """Save statistical analysis report to JSON."""
    report = {
        "summaries": {
            name: {
                "mean": float(s.mean),
                "median": float(s.median),
                "std": float(s.std),
                "min": float(s.min),
                "max": float(s.max),
                "q25": float(s.q25),
                "q75": float(s.q75),
                "ci_95_lower": float(s.ci_lower),
                "ci_95_upper": float(s.ci_upper),
                "n": int(s.n),
            }
            for name, s in summaries.items()
        },
        "pairwise_comparisons": [
            {
                "group_a": str(c.group_a),
                "group_b": str(c.group_b),
                "metric": str(c.metric),
                "mean_a": float(c.mean_a),
                "mean_b": float(c.mean_b),
                "difference": float(c.difference),
                "percent_change": float(c.percent_change),
                "t_statistic": float(c.t_statistic),
                "p_value": float(c.p_value),
                "significant": bool(c.significant),
                "effect_size_cohens_d": float(c.effect_size),
            }
            for c in comparisons
        ],
        "anova": {
            "f_statistic": float(anova_results["f_statistic"]),
            "p_value": float(anova_results["p_value"]),
            "significant": bool(anova_results["significant"]),
            "groups": anova_results["groups"],
            "n_groups": int(anova_results["n_groups"]),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    """Example usage."""
    import pandas as pd

    # Load metrics
    df = pd.read_csv("results/tr117/metrics.csv")

    # Filter to OK runs only
    df_ok = df[df["status"] == "ok"]

    # Compute summaries per backend
    summaries = {}
    for backend in df_ok["backend"].unique():
        backend_data = df_ok[df_ok["backend"] == backend]["latency_ms"].tolist()
        summaries[backend] = compute_summary(backend_data)

    # Pairwise comparisons
    comparisons = []
    backends = list(summaries.keys())
    for i, backend_a in enumerate(backends):
        for backend_b in backends[i + 1 :]:
            data_a = df_ok[df_ok["backend"] == backend_a]["latency_ms"].tolist()
            data_b = df_ok[df_ok["backend"] == backend_b]["latency_ms"].tolist()
            comp = compare_groups(data_a, data_b, backend_a, backend_b, "latency_ms")
            comparisons.append(comp)

    # ANOVA
    anova_data = {
        backend: df_ok[df_ok["backend"] == backend]["latency_ms"].tolist()
        for backend in backends
    }
    anova_results = anova_backends(anova_data)

    # Save report
    save_statistical_report(
        summaries,
        comparisons,
        anova_results,
        Path("results/tr117/statistical_analysis.json"),
    )
    print("Statistical analysis saved to results/tr117/statistical_analysis.json")


if __name__ == "__main__":
    main()
