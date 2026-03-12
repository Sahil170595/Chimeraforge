"""TR131 statistical utilities — matches TR126 rigor.

Provides: Welch's t-test, Cohen's d, 95% CIs, outlier detection (IQR),
power analysis, Mann-Whitney U, descriptive stats with percentiles.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy import stats as sp_stats


@dataclass
class DescriptiveStats:
    """Full descriptive statistics for a sample."""

    n: int
    mean: float
    median: float
    std: float
    ci_low: float
    ci_high: float
    p90: float
    p95: float
    p99: float
    min_val: float
    max_val: float
    iqr: float
    outlier_count: int
    outlier_pct: float

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "mean": round(self.mean, 4),
            "median": round(self.median, 4),
            "std": round(self.std, 4),
            "ci_95": [round(self.ci_low, 4), round(self.ci_high, 4)],
            "p90": round(self.p90, 4),
            "p95": round(self.p95, 4),
            "p99": round(self.p99, 4),
            "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
            "iqr": round(self.iqr, 4),
            "outlier_count": self.outlier_count,
            "outlier_pct": round(self.outlier_pct, 2),
        }


@dataclass
class PairwiseResult:
    """Result of a two-sample comparison."""

    group_a: str
    group_b: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    delta_abs: float
    delta_pct: float
    cohens_d: float
    effect_size_label: str  # negligible/small/medium/large
    t_statistic: float
    p_value: float
    significant: bool  # at alpha=0.05
    mann_whitney_u: float | None
    mann_whitney_p: float | None

    def to_dict(self) -> dict:
        d = {
            "group_a": self.group_a,
            "group_b": self.group_b,
            "n_a": self.n_a,
            "n_b": self.n_b,
            "mean_a": round(self.mean_a, 4),
            "mean_b": round(self.mean_b, 4),
            "delta_abs": round(self.delta_abs, 4),
            "delta_pct": round(self.delta_pct, 2),
            "cohens_d": round(self.cohens_d, 4),
            "effect_size": self.effect_size_label,
            "t_statistic": round(self.t_statistic, 4),
            "p_value": self.p_value,
            "significant_p05": self.significant,
        }
        if self.mann_whitney_u is not None:
            d["mann_whitney_u"] = round(self.mann_whitney_u, 2)
            d["mann_whitney_p"] = self.mann_whitney_p
        return d


def descriptive(values: list | np.ndarray) -> DescriptiveStats:
    """Compute full descriptive statistics with 95% CI and outlier detection."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n == 0:
        return DescriptiveStats(
            n=0,
            mean=0,
            median=0,
            std=0,
            ci_low=0,
            ci_high=0,
            p90=0,
            p95=0,
            p99=0,
            min_val=0,
            max_val=0,
            iqr=0,
            outlier_count=0,
            outlier_pct=0,
        )

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    median = float(np.median(arr))

    # 95% CI using t-distribution
    if n > 1 and std > 0:
        se = std / math.sqrt(n)
        t_crit = sp_stats.t.ppf(0.975, df=n - 1)
        ci_low = mean - t_crit * se
        ci_high = mean + t_crit * se
    else:
        ci_low = ci_high = mean

    # Percentiles
    p90, p95, p99 = np.percentile(arr, [90, 95, 99]) if n > 1 else (mean,) * 3

    # IQR outlier detection (Tukey fence)
    q1, q3 = np.percentile(arr, [25, 75]) if n > 1 else (mean, mean)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers = np.sum((arr < lower_fence) | (arr > upper_fence))

    return DescriptiveStats(
        n=n,
        mean=mean,
        median=median,
        std=std,
        ci_low=ci_low,
        ci_high=ci_high,
        p90=float(p90),
        p95=float(p95),
        p99=float(p99),
        min_val=float(np.min(arr)),
        max_val=float(np.max(arr)),
        iqr=float(iqr),
        outlier_count=int(outliers),
        outlier_pct=float(outliers / n * 100) if n > 0 else 0.0,
    )


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d — standardized mean difference (pooled std)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    var_a = np.var(a, ddof=1)
    var_b = np.var(b, ddof=1)
    pooled_std = math.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
    if pooled_std == 0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled_std)


def effect_size_label(d: float) -> str:
    """Classify Cohen's d magnitude."""
    d_abs = abs(d)
    if d_abs < 0.2:
        return "negligible"
    if d_abs < 0.5:
        return "small"
    if d_abs < 0.8:
        return "medium"
    return "large"


def pairwise_compare(
    a: list | np.ndarray,
    b: list | np.ndarray,
    label_a: str = "A",
    label_b: str = "B",
    alpha: float = 0.05,
    nonparametric: bool = True,
) -> PairwiseResult:
    """Full pairwise comparison: Welch's t-test + Cohen's d + optional Mann-Whitney."""
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    a_arr = a_arr[~np.isnan(a_arr)]
    b_arr = b_arr[~np.isnan(b_arr)]

    na, nb = len(a_arr), len(b_arr)
    mean_a = float(np.mean(a_arr)) if na > 0 else 0.0
    mean_b = float(np.mean(b_arr)) if nb > 0 else 0.0
    delta_abs = mean_b - mean_a
    delta_pct = (delta_abs / mean_a * 100) if mean_a != 0 else 0.0

    # Welch's t-test
    if na >= 2 and nb >= 2:
        t_stat, p_val = sp_stats.ttest_ind(a_arr, b_arr, equal_var=False)
        t_stat = float(t_stat)
        p_val = float(p_val)
    else:
        t_stat, p_val = 0.0, 1.0

    # Cohen's d
    d = cohens_d(a_arr, b_arr)
    label = effect_size_label(d)

    # Mann-Whitney U (non-parametric robustness check)
    mw_u, mw_p = None, None
    if nonparametric and na >= 2 and nb >= 2:
        try:
            mw_u_val, mw_p_val = sp_stats.mannwhitneyu(
                a_arr,
                b_arr,
                alternative="two-sided",
            )
            mw_u = float(mw_u_val)
            mw_p = float(mw_p_val)
        except ValueError:
            pass

    return PairwiseResult(
        group_a=label_a,
        group_b=label_b,
        n_a=na,
        n_b=nb,
        mean_a=mean_a,
        mean_b=mean_b,
        delta_abs=delta_abs,
        delta_pct=delta_pct,
        cohens_d=d,
        effect_size_label=label,
        t_statistic=t_stat,
        p_value=p_val,
        significant=p_val < alpha,
        mann_whitney_u=mw_u,
        mann_whitney_p=mw_p,
    )


def power_analysis(n: int, alpha: float = 0.05) -> dict:
    """Minimum detectable effect size (Cohen's d) at given N and alpha.

    Uses the approximation: d_min ≈ t_crit * sqrt(2/n)
    For a two-sample t-test with equal n.
    """
    if n < 2:
        return {
            "n": n,
            "min_detectable_d": float("inf"),
            "interpretation": "insufficient",
        }

    df = 2 * n - 2
    t_crit = sp_stats.t.ppf(1 - alpha / 2, df=df)
    d_min = t_crit * math.sqrt(2 / n)

    return {
        "n_per_group": n,
        "alpha": alpha,
        "min_detectable_d": round(d_min, 3),
        "interpretation": effect_size_label(d_min),
    }


def bonferroni_correction(p_values: list[float], alpha: float = 0.05) -> list[dict]:
    """Apply Bonferroni correction to a family of p-values."""
    k = len(p_values)
    corrected_alpha = alpha / k if k > 0 else alpha
    return [
        {
            "original_p": p,
            "corrected_alpha": corrected_alpha,
            "significant_bonferroni": p < corrected_alpha,
        }
        for p in p_values
    ]


def holm_stepdown(p_values: list[tuple[str, float]], alpha: float = 0.05) -> list[dict]:
    """Holm step-down correction for multiple comparisons.

    Args:
        p_values: List of (label, p_value) tuples
        alpha: Family-wise error rate

    Returns:
        List of dicts with corrected significance.
    """
    k = len(p_values)
    sorted_pvals = sorted(p_values, key=lambda x: x[1])
    results = []

    all_sig = True
    for i, (label, p) in enumerate(sorted_pvals):
        threshold = alpha / (k - i)
        is_sig = all_sig and (p < threshold)
        if not is_sig:
            all_sig = False
        results.append(
            {
                "label": label,
                "p_value": p,
                "holm_threshold": round(threshold, 6),
                "significant_holm": is_sig,
                "rank": i + 1,
            }
        )

    return results
