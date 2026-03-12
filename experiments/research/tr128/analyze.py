"""TR128 — Statistical analysis for 5-phase production workload experiment.

Reads metrics.csv, GPU CSVs, and ichunk_raw.jsonl from the latest run.
Produces analysis.json with sections covering:

  1. Summary
  2. Baseline characterization (Phase 1)
  3. Concurrency scaling (Phase 2) — THE core result
  4. M/D/1 deviation analysis (Phase 2)
  5. Queue depth analysis (Phase 2)
  6. Latency amplification (Phase 2)
  7. Thermal stability (Phase 3)
  8. GPU metrics summary
  9. Streaming TTFT (Phase 4)
 10. Inter-chunk stability (Phase 4)
 11. Stream vs batch comparison (Phase 4)
 12. Multi-turn degradation (Phase 5)
 13. Context strategy comparison (Phase 5)
 14. TR127 cross-validation
 15. Cold-start detection
 16. Outlier analysis
 17. Power analysis
 18. Distribution shape

Statistical methods:
- 95% CI via t-distribution
- Holm-Bonferroni multiple comparison correction
- Trimmed-mean robustness checks
- Shapiro-Wilk normality testing
- Cohen's d effect sizes

Usage:
    python research/tr128/analyze.py [-v]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import stats

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.shared.statistical_analysis import (
    compare_groups,
    detect_outliers,
)
from research.tr128.shared.utils import (
    TR128_RESULTS,
    effect_label,
    find_latest_run,
    load_metrics_csv,
)

log = logging.getLogger("tr128.analyze")


# ── Statistical helpers ──────────────────────────────────────────────


def _ci95(values: np.ndarray) -> tuple[float, float]:
    """95% confidence interval via t-distribution."""
    n = len(values)
    if n < 2:
        m = float(values[0]) if n == 1 else 0.0
        return (m, m)
    mean = float(np.mean(values))
    sem = float(stats.sem(values))
    lo, hi = stats.t.interval(0.95, df=n - 1, loc=mean, scale=sem)
    return (round(float(lo), 2), round(float(hi), 2))


def _full_summary(values: np.ndarray) -> dict:
    """Full statistical summary with normality testing."""
    n = len(values)
    if n == 0:
        return {"n": 0}
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if n > 1 else 0.0
    ci = _ci95(values)
    entry = {
        "n": n,
        "mean": round(mean, 2),
        "median": round(float(np.median(values)), 2),
        "std": round(std, 2),
        "cv_pct": round(std / mean * 100, 1) if mean > 0 else 0,
        "p50": round(float(np.percentile(values, 50)), 2),
        "p95": round(float(np.percentile(values, 95)), 2),
        "p99": round(float(np.percentile(values, 99)), 2),
        "ci95_lower": ci[0],
        "ci95_upper": ci[1],
        "min": round(float(np.min(values)), 2),
        "max": round(float(np.max(values)), 2),
    }
    if n >= 3:
        entry["skewness"] = round(float(stats.skew(values)), 3)
        entry["kurtosis"] = round(float(stats.kurtosis(values)), 3)
    if 3 <= n <= 5000:
        sw_stat, sw_p = stats.shapiro(values)
        entry["shapiro_w"] = round(float(sw_stat), 4)
        entry["shapiro_p"] = round(float(sw_p), 4)
        entry["is_normal"] = bool(sw_p > 0.05)
    return entry


def _trimmed_mean(values: np.ndarray, trim_pct: float) -> float:
    return float(stats.trim_mean(values, trim_pct))


def _holm_bonferroni(p_values: list[float], alpha: float = 0.05) -> list[dict]:
    """Holm-Bonferroni step-down correction."""
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    results = [None] * n
    rejected = True
    for rank, (orig_idx, p) in enumerate(indexed):
        threshold = alpha / (n - rank)
        sig = rejected and p < threshold
        if not sig:
            rejected = False
        results[orig_idx] = {
            "p_value": round(p, 6),
            "rank": rank + 1,
            "holm_threshold": round(threshold, 6),
            "significant_holm": bool(sig),
            "significant_bonferroni": bool(p < alpha / n),
        }
    return results


def _load_gpu_csv(path: Path) -> pd.DataFrame | None:
    """Load a GPU metrics CSV if it exists."""
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path, exc)
        return None


# ── 1. Summary ───────────────────────────────────────────────────────


def analyze_summary(df_all: pd.DataFrame) -> dict:
    status_counts = df_all["status"].value_counts().to_dict()
    ok = int((df_all["status"] == "ok").sum())
    total = len(df_all)
    return {
        "total_rows": total,
        "ok_rows": ok,
        "error_rows": total - ok,
        "ok_rate": round(ok / total, 4) if total > 0 else 0,
        "models": sorted(df_all["model"].unique().tolist()),
        "phases": sorted(df_all["phase"].unique().tolist()),
        "status_counts": status_counts,
        "rows_per_phase": df_all["phase"].value_counts().to_dict(),
        "rows_per_model": df_all["model"].value_counts().to_dict(),
    }


# ── 2. Baseline characterization (Phase 1) ──────────────────────────


def analyze_baseline(df: pd.DataFrame) -> dict:
    """Serial baseline: per-model service time distributions."""
    p1 = df[df["phase"] == "p1_baseline"]
    if p1.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p1["model"].unique()):
        subset = p1[p1["model"] == model]
        wall = subset["wall_ms"].dropna().values
        tps = subset["tokens_per_s"].dropna().values
        pe = subset["prompt_eval_ms"].dropna().values
        ev = subset["eval_ms"].dropna().values

        entry = {"wall_ms": _full_summary(wall)}

        if len(tps) > 0:
            entry["tokens_per_s"] = _full_summary(tps)
        if len(pe) > 0:
            entry["prompt_eval_ms"] = _full_summary(pe)
        if len(ev) > 0:
            entry["eval_ms"] = _full_summary(ev)

        # Theoretical max throughput (M/D/1 service rate)
        if len(wall) > 0:
            mean_service_s = float(np.mean(wall)) / 1000.0
            entry["mean_service_ms"] = round(mean_service_s * 1000, 1)
            entry["theoretical_max_rps"] = (
                round(1.0 / mean_service_s, 3) if mean_service_s > 0 else None
            )

        # Trimmed-mean robustness
        if len(wall) >= 10:
            entry["trimmed_mean_10pct"] = round(_trimmed_mean(wall, 0.10), 1)

        results[model] = entry

    return results


# ── 3. Concurrency scaling (Phase 2) — core result ──────────────────


def analyze_concurrency(df: pd.DataFrame) -> dict:
    """How does OLLAMA_NUM_PARALLEL affect latency under load?"""
    p2 = df[df["phase"] == "p2_concurrency"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        by_np = {}

        for np_level in sorted(model_data["num_parallel"].unique()):
            np_data = model_data[model_data["num_parallel"] == np_level]
            curves = {}

            for rate in sorted(np_data["arrival_rate_rps"].unique()):
                subset = np_data[np_data["arrival_rate_rps"] == rate]
                wall = subset["wall_ms"].dropna().values
                if len(wall) == 0:
                    continue

                p50 = float(np.percentile(wall, 50))
                p95 = float(np.percentile(wall, 95))
                p99 = float(np.percentile(wall, 99))

                curves[str(rate)] = {
                    "n": len(wall),
                    "mean_ms": round(float(np.mean(wall)), 1),
                    "ci95": _ci95(wall),
                    "p50_ms": round(p50, 1),
                    "p95_ms": round(p95, 1),
                    "p99_ms": round(p99, 1),
                    "p99_p50_ratio": round(p99 / p50, 2) if p50 > 0 else None,
                    "mean_queue_depth": round(
                        float(subset["queue_depth_at_submit"].mean()), 2
                    ),
                    "max_queue_depth": int(subset["queue_depth_at_submit"].max()),
                    "ok_rate": round(float((subset["status"] == "ok").mean()), 3),
                    "tokens_per_s_mean": (
                        round(float(subset["tokens_per_s"].dropna().mean()), 1)
                        if len(subset["tokens_per_s"].dropna()) > 0
                        else None
                    ),
                }

            # Saturation detection: first rate where p99 > 2x p50
            sat_rate = None
            for rate_str in sorted(curves.keys(), key=float):
                c = curves[rate_str]
                if c["p50_ms"] > 0 and c["p99_ms"] > 2 * c["p50_ms"]:
                    sat_rate = float(rate_str)
                    break

            by_np[str(int(np_level))] = {
                "curves": curves,
                "saturation_rate_rps": sat_rate,
                "n_rates_tested": len(curves),
            }

        results[model] = by_np

    # Cross-NP comparison: at each rate, how does NP=2 and NP=4 compare to NP=1?
    np_comparison = _compare_parallelism_levels(p2)
    results["_parallelism_comparison"] = np_comparison

    return results


def _compare_parallelism_levels(p2: pd.DataFrame) -> dict:
    """Pairwise comparison of NP levels at each rate with statistical tests."""
    all_tests = []
    comparisons = {}

    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        model_comps = {}

        for rate in sorted(model_data["arrival_rate_rps"].unique()):
            rate_data = model_data[model_data["arrival_rate_rps"] == rate]
            np_levels = sorted(rate_data["num_parallel"].unique())
            if len(np_levels) < 2:
                continue

            # Always compare against NP=1 as baseline
            baseline_np = np_levels[0]
            baseline_wall = (
                rate_data[rate_data["num_parallel"] == baseline_np]["wall_ms"]
                .dropna()
                .values
            )

            rate_comps = {}
            for np_level in np_levels[1:]:
                test_wall = (
                    rate_data[rate_data["num_parallel"] == np_level]["wall_ms"]
                    .dropna()
                    .values
                )
                if len(baseline_wall) < 2 or len(test_wall) < 2:
                    continue

                t_stat, p_value = stats.ttest_ind(baseline_wall, test_wall)
                baseline_mean = float(np.mean(baseline_wall))
                test_mean = float(np.mean(test_wall))
                pooled_std = np.sqrt(
                    (
                        (len(baseline_wall) - 1) * np.var(baseline_wall, ddof=1)
                        + (len(test_wall) - 1) * np.var(test_wall, ddof=1)
                    )
                    / (len(baseline_wall) + len(test_wall) - 2)
                )
                cohens_d = (
                    (test_mean - baseline_mean) / pooled_std if pooled_std > 0 else 0
                )

                comp = {
                    "baseline_np": int(baseline_np),
                    "test_np": int(np_level),
                    "baseline_mean_ms": round(baseline_mean, 1),
                    "test_mean_ms": round(test_mean, 1),
                    "change_pct": (
                        round((test_mean - baseline_mean) / baseline_mean * 100, 1)
                        if baseline_mean > 0
                        else 0
                    ),
                    "t_statistic": round(float(t_stat), 3),
                    "p_value_uncorrected": round(float(p_value), 6),
                    "cohens_d": round(float(cohens_d), 3),
                    "effect": effect_label(cohens_d),
                }
                all_tests.append((model, rate, np_level, float(p_value)))
                rate_comps[f"np{int(np_level)}_vs_np{int(baseline_np)}"] = comp

            if rate_comps:
                model_comps[str(rate)] = rate_comps

        if model_comps:
            comparisons[model] = model_comps

    # Apply Holm-Bonferroni across ALL pairwise tests
    if all_tests:
        p_values = [t[3] for t in all_tests]
        corrections = _holm_bonferroni(p_values)

        idx = 0
        for model, rate, np_level, _ in all_tests:
            if model in comparisons and str(rate) in comparisons[model]:
                baseline_np = 1  # always comparing against NP=1
                key = f"np{int(np_level)}_vs_np{int(baseline_np)}"
                if key in comparisons[model][str(rate)]:
                    comparisons[model][str(rate)][key]["significant_holm"] = (
                        corrections[idx]["significant_holm"]
                    )
                    comparisons[model][str(rate)][key]["holm_threshold"] = corrections[
                        idx
                    ]["holm_threshold"]
            idx += 1

        comparisons["_multiple_comparisons"] = {
            "n_tests": len(all_tests),
            "n_significant_uncorrected": sum(1 for _, _, _, p in all_tests if p < 0.05),
            "n_significant_holm": sum(1 for c in corrections if c["significant_holm"]),
        }

    return comparisons


# ── 4. M/D/1 deviation analysis ─────────────────────────────────────


def analyze_md1_deviation(df: pd.DataFrame, baseline: dict) -> dict:
    """Compare observed queue wait vs M/D/1 predictions.

    This is the scientific contribution: where does the simple queueing
    model break down, and why?
    """
    p2 = df[df["phase"] == "p2_concurrency"]
    if p2.empty or not baseline or baseline.get("status") == "no_data":
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_bl = baseline.get(model, {})
        mean_service_ms = model_bl.get("mean_service_ms")
        if not mean_service_ms or mean_service_ms <= 0:
            continue

        mean_service_s = mean_service_ms / 1000.0
        model_data = p2[p2["model"] == model]
        deviations = {}

        for np_level in sorted(model_data["num_parallel"].unique()):
            np_data = model_data[model_data["num_parallel"] == np_level]
            np_deviations = {}

            for rate in sorted(np_data["arrival_rate_rps"].unique()):
                subset = np_data[np_data["arrival_rate_rps"] == rate]
                wall = subset["wall_ms"].dropna().values
                pe = subset["prompt_eval_ms"].dropna().values
                ev = subset["eval_ms"].dropna().values
                ld = subset["load_duration_ms"].dropna().values

                if len(wall) < 2:
                    continue

                # Observed queue wait: wall - (prompt_eval + eval + load)
                n_min = min(len(wall), len(pe), len(ev))
                if n_min == 0:
                    continue
                compute_ms = pe[:n_min] + ev[:n_min]
                if len(ld) >= n_min:
                    compute_ms = compute_ms + ld[:n_min]
                observed_wait = wall[:n_min] - compute_ms
                observed_wait = observed_wait[observed_wait >= 0]

                # M/D/1 predicted wait
                # For NP>1, effective service rate is higher
                effective_service_s = mean_service_s / int(np_level)
                rho = float(rate) * effective_service_s
                if rho >= 1.0:
                    md1_wait_ms = float("inf")
                else:
                    # M/D/1: E[W] = rho / (2 * mu * (1 - rho))
                    # where mu = 1/service_time
                    md1_wait_ms = (rho * mean_service_ms) / (2 * (1 - rho))

                entry = {
                    "rho": round(rho, 3),
                    "is_overloaded": bool(rho >= 1.0),
                    "md1_predicted_wait_ms": (
                        round(md1_wait_ms, 1) if md1_wait_ms != float("inf") else None
                    ),
                }

                if len(observed_wait) > 0:
                    obs_mean = float(np.mean(observed_wait))
                    entry["observed_wait_ms_mean"] = round(obs_mean, 1)
                    entry["observed_wait_ms_p95"] = round(
                        float(np.percentile(observed_wait, 95)), 1
                    )

                    if md1_wait_ms != float("inf") and md1_wait_ms > 0:
                        entry["deviation_ratio"] = round(obs_mean / md1_wait_ms, 2)
                        entry["deviation_pct"] = round(
                            (obs_mean - md1_wait_ms) / md1_wait_ms * 100, 1
                        )

                np_deviations[str(rate)] = entry

            deviations[str(int(np_level))] = np_deviations

        results[model] = {
            "mean_service_ms": mean_service_ms,
            "deviations_by_np": deviations,
        }

    return results


# ── 5. Queue depth analysis ─────────────────────────────────────────


def analyze_queue_depth(df: pd.DataFrame) -> dict:
    p2 = df[df["phase"] == "p2_concurrency"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        by_np = {}

        for np_level in sorted(model_data["num_parallel"].unique()):
            np_data = model_data[model_data["num_parallel"] == np_level]
            depth_by_rate = {}

            for rate in sorted(np_data["arrival_rate_rps"].unique()):
                subset = np_data[np_data["arrival_rate_rps"] == rate]
                depths = subset["queue_depth_at_submit"].dropna().values
                if len(depths) == 0:
                    continue

                depth_by_rate[str(rate)] = {
                    "mean_depth": round(float(np.mean(depths)), 2),
                    "max_depth": int(np.max(depths)),
                    "p95_depth": round(float(np.percentile(depths, 95)), 1),
                }

            by_np[str(int(np_level))] = depth_by_rate

        results[model] = by_np

    return results


# ── 6. Latency amplification ────────────────────────────────────────


def analyze_latency_amplification(df: pd.DataFrame) -> dict:
    p2 = df[df["phase"] == "p2_concurrency"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        by_np = {}

        for np_level in sorted(model_data["num_parallel"].unique()):
            np_data = model_data[model_data["num_parallel"] == np_level]
            ratios = {}
            baseline_p50 = None

            for rate in sorted(np_data["arrival_rate_rps"].unique()):
                wall = (
                    np_data[np_data["arrival_rate_rps"] == rate]["wall_ms"]
                    .dropna()
                    .values
                )
                if len(wall) < 2:
                    continue

                p50 = float(np.percentile(wall, 50))
                p95 = float(np.percentile(wall, 95))
                p99 = float(np.percentile(wall, 99))

                if baseline_p50 is None:
                    baseline_p50 = p50

                entry = {
                    "p99_p50_ratio": round(p99 / p50, 2) if p50 > 0 else None,
                    "p95_p50_ratio": round(p95 / p50, 2) if p50 > 0 else None,
                }
                if baseline_p50 and baseline_p50 > 0:
                    entry["p50_vs_baseline"] = round(p50 / baseline_p50, 2)
                    entry["p99_vs_baseline"] = round(p99 / baseline_p50, 2)

                ratios[str(rate)] = entry

            by_np[str(int(np_level))] = ratios

        results[model] = by_np

    return results


# ── 7. Thermal stability (Phase 3) ──────────────────────────────────


def analyze_thermal(df: pd.DataFrame, run_dir: Path) -> dict:
    """Correlate GPU thermals with latency over sustained load."""
    p3 = df[df["phase"] == "p3_thermal"]
    if p3.empty:
        return {"status": "no_data"}

    # Load GPU metrics for Phase 3
    gpu_df = _load_gpu_csv(run_dir / "gpu_phase3.csv")

    results = {}
    for model in sorted(p3["model"].unique()):
        subset = p3[p3["model"] == model]
        wall = subset["wall_ms"].dropna().values
        tps = subset["tokens_per_s"].dropna().values

        if len(wall) < 5:
            continue

        entry = {
            "wall_ms": _full_summary(wall),
            "tokens_per_s": _full_summary(tps) if len(tps) > 0 else {"n": 0},
            "n_requests": len(subset),
            "duration_s": round(float(wall.sum()) / 1000, 1),
        }

        # Time-series stability: split into thirds and compare
        n = len(wall)
        third = n // 3
        if third >= 3:
            first_third = wall[:third]
            last_third = wall[-third:]
            t_stat, p_value = stats.ttest_ind(first_third, last_third)
            entry["stability"] = {
                "first_third_mean_ms": round(float(np.mean(first_third)), 1),
                "last_third_mean_ms": round(float(np.mean(last_third)), 1),
                "drift_pct": (
                    round(
                        (float(np.mean(last_third)) - float(np.mean(first_third)))
                        / float(np.mean(first_third))
                        * 100,
                        1,
                    )
                    if float(np.mean(first_third)) > 0
                    else 0
                ),
                "t_statistic": round(float(t_stat), 3),
                "p_value": round(float(p_value), 4),
                "significant_drift": bool(p_value < 0.05),
            }

            # Linear regression for trend
            indices = np.arange(n, dtype=float)
            slope, _intercept, r_val, p_reg, _ = stats.linregress(indices, wall)
            entry["trend"] = {
                "slope_ms_per_request": round(float(slope), 3),
                "r_squared": round(float(r_val**2), 4),
                "p_value": round(float(p_reg), 4),
                "significant_trend": bool(p_reg < 0.05),
            }

        results[model] = entry

    # GPU thermal analysis
    if gpu_df is not None and len(gpu_df) > 0:
        temps = gpu_df["temp_c"].dropna().values
        clocks = gpu_df["clock_mhz"].dropna().values
        utils = gpu_df["gpu_util_pct"].dropna().values

        results["_gpu"] = {
            "n_samples": len(gpu_df),
            "temp_c": _full_summary(temps) if len(temps) > 0 else {"n": 0},
            "clock_mhz": _full_summary(clocks) if len(clocks) > 0 else {"n": 0},
            "gpu_util_pct": _full_summary(utils) if len(utils) > 0 else {"n": 0},
        }

        # Thermal throttle detection
        if len(temps) > 0 and len(clocks) > 0:
            peak_clock = float(np.max(clocks))
            throttle_mask = (temps > 80) & (clocks < peak_clock * 0.9)
            results["_gpu"]["thermal_throttle"] = {
                "detected": bool(throttle_mask.any()),
                "n_samples": int(throttle_mask.sum()),
                "pct_of_run": round(float(throttle_mask.sum()) / len(temps) * 100, 1),
                "peak_clock_mhz": round(peak_clock, 0),
                "min_clock_mhz": round(float(np.min(clocks)), 0),
            }

    return results


# ── 8. GPU metrics summary ──────────────────────────────────────────


def analyze_gpu_metrics(run_dir: Path) -> dict:
    """Summarize GPU metrics across all phases."""
    results = {}

    for phase_file in sorted(run_dir.glob("gpu_phase*.csv")):
        gpu_df = _load_gpu_csv(phase_file)
        if gpu_df is None or gpu_df.empty:
            continue

        phase_name = phase_file.stem  # e.g., "gpu_phase1"
        temps = gpu_df["temp_c"].dropna().values
        clocks = gpu_df["clock_mhz"].dropna().values
        utils = gpu_df["gpu_util_pct"].dropna().values
        powers = gpu_df["power_w"].dropna().values
        mems = gpu_df["mem_used_mb"].dropna().values

        entry = {"n_samples": len(gpu_df)}
        if len(temps) > 0:
            entry["temp_c"] = {
                "min": round(float(np.min(temps)), 1),
                "max": round(float(np.max(temps)), 1),
                "mean": round(float(np.mean(temps)), 1),
            }
        if len(clocks) > 0:
            entry["clock_mhz"] = {
                "min": round(float(np.min(clocks)), 0),
                "max": round(float(np.max(clocks)), 0),
                "mean": round(float(np.mean(clocks)), 0),
            }
        if len(utils) > 0:
            entry["gpu_util_pct"] = {
                "min": round(float(np.min(utils)), 1),
                "max": round(float(np.max(utils)), 1),
                "mean": round(float(np.mean(utils)), 1),
            }
        if len(powers) > 0:
            entry["power_w"] = {
                "mean": round(float(np.mean(powers)), 1),
                "max": round(float(np.max(powers)), 1),
            }
        if len(mems) > 0:
            entry["mem_used_mb"] = {
                "min": round(float(np.min(mems)), 1),
                "max": round(float(np.max(mems)), 1),
                "mean": round(float(np.mean(mems)), 1),
            }

        results[phase_name] = entry

    return results if results else {"status": "no_gpu_data"}


# ── 9. Streaming TTFT (Phase 4) ─────────────────────────────────────


def analyze_ttft(df: pd.DataFrame) -> dict:
    p4 = df[(df["phase"] == "p4_stream") & (df["response_mode"] == "stream")]
    if p4.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p4["model"].unique()):
        model_data = p4[p4["model"] == model]
        ttft_by_rate = {}
        baseline_ttft = None

        for rate in sorted(model_data["arrival_rate_rps"].unique()):
            subset = model_data[model_data["arrival_rate_rps"] == rate]
            ttft = subset["ttft_ms"].dropna().values
            if len(ttft) == 0:
                continue

            summary = _full_summary(ttft)
            p50 = float(np.percentile(ttft, 50))
            if baseline_ttft is None:
                baseline_ttft = p50

            summary["amplification"] = (
                round(p50 / baseline_ttft, 2)
                if baseline_ttft and baseline_ttft > 0
                else 1.0
            )

            ttft_by_rate[str(rate)] = summary

        thresholds = {}
        for ms in [100, 500, 1000, 5000]:
            crossed = None
            for rate_str in sorted(ttft_by_rate.keys(), key=float):
                if ttft_by_rate[rate_str].get("median", 0) >= ms:
                    crossed = float(rate_str)
                    break
            thresholds[f"{ms}ms"] = crossed

        results[model] = {
            "by_rate": ttft_by_rate,
            "baseline_ttft_p50_ms": round(baseline_ttft, 1) if baseline_ttft else None,
            "threshold_crossings": thresholds,
        }

    return results


# ── 10. Inter-chunk stability (Phase 4) ─────────────────────────────


def analyze_ichunk(df: pd.DataFrame, run_dir: Path | None = None) -> dict:
    """Inter-chunk latency analysis (honest: NOT inter-token)."""
    p4 = df[(df["phase"] == "p4_stream") & (df["response_mode"] == "stream")]
    if p4.empty:
        return {"status": "no_data"}

    # Load raw ichunk arrays from JSONL
    raw_by_key: dict[str, list[list[float]]] = {}
    if run_dir:
        ichunk_path = run_dir / "ichunk_raw.jsonl"
        if ichunk_path.exists():
            try:
                with open(ichunk_path, encoding="utf-8") as f:
                    for line in f:
                        rec = json.loads(line)
                        key = f"{rec['model']}_{rec['rate']}_{rec['mode']}"
                        raw_by_key.setdefault(key, []).append(rec.get("ichunk_ms", []))
                log.info(
                    "Loaded %d ichunk records from ichunk_raw.jsonl",
                    sum(len(v) for v in raw_by_key.values()),
                )
            except Exception as exc:
                log.warning("Failed to load ichunk_raw.jsonl: %s", exc)

    results = {}
    for model in sorted(p4["model"].unique()):
        model_data = p4[p4["model"] == model]
        by_rate = {}

        for rate in sorted(model_data["arrival_rate_rps"].unique()):
            subset = model_data[model_data["arrival_rate_rps"] == rate]
            ichunk_mean = subset["ichunk_mean_ms"].dropna().values
            ichunk_cv = subset["ichunk_jitter_cv"].dropna().values

            if len(ichunk_mean) == 0:
                continue

            entry = {
                "n": len(ichunk_mean),
                "mean_ichunk_ms": round(float(np.mean(ichunk_mean)), 2),
                "p95_ichunk_ms": round(float(np.percentile(ichunk_mean, 95)), 2),
                "mean_jitter_cv": (
                    round(float(np.mean(ichunk_cv)), 4) if len(ichunk_cv) > 0 else None
                ),
            }

            # Pooled raw ichunk analysis
            key = f"{model}_{rate}_stream"
            if key in raw_by_key:
                all_ichunk = []
                for arr in raw_by_key[key]:
                    all_ichunk.extend(arr)
                if len(all_ichunk) >= 3:
                    entry["pooled_ichunk"] = _full_summary(np.array(all_ichunk))

            by_rate[str(rate)] = entry

        results[model] = by_rate

    return results


# ── 11. Stream vs batch comparison (Phase 4) ────────────────────────


def analyze_stream_vs_batch(df: pd.DataFrame) -> dict:
    p4 = df[df["phase"] == "p4_stream"]
    if p4.empty:
        return {"status": "no_data"}

    all_tests = []
    raw_results = []
    for model in sorted(p4["model"].unique()):
        model_data = p4[p4["model"] == model]
        for rate in sorted(model_data["arrival_rate_rps"].unique()):
            rate_data = model_data[model_data["arrival_rate_rps"] == rate]
            batch = (
                rate_data[rate_data["response_mode"] == "batch"]["wall_ms"]
                .dropna()
                .values
            )
            stream = (
                rate_data[rate_data["response_mode"] == "stream"]["wall_ms"]
                .dropna()
                .values
            )
            if len(batch) >= 2 and len(stream) >= 2:
                all_tests.append((model, rate, batch, stream))

    if not all_tests:
        return {"status": "no_paired_data"}

    p_values = []
    for model, rate, batch, stream in all_tests:
        t_stat, p_value = stats.ttest_ind(batch, stream)
        batch_mean = float(np.mean(batch))
        stream_mean = float(np.mean(stream))
        pooled_std = np.sqrt(
            (
                (len(batch) - 1) * np.var(batch, ddof=1)
                + (len(stream) - 1) * np.var(stream, ddof=1)
            )
            / (len(batch) + len(stream) - 2)
        )
        cohens_d = (stream_mean - batch_mean) / pooled_std if pooled_std > 0 else 0

        p_values.append(float(p_value))
        raw_results.append(
            {
                "model": model,
                "rate": float(rate),
                "batch_n": len(batch),
                "stream_n": len(stream),
                "batch_mean_ms": round(batch_mean, 1),
                "stream_mean_ms": round(stream_mean, 1),
                "batch_ci95": _ci95(batch),
                "stream_ci95": _ci95(stream),
                "overhead_pct": (
                    round((stream_mean - batch_mean) / batch_mean * 100, 1)
                    if batch_mean > 0
                    else 0
                ),
                "t_statistic": round(float(t_stat), 3),
                "p_value_uncorrected": round(float(p_value), 6),
                "cohens_d": round(float(cohens_d), 3),
                "effect": effect_label(cohens_d),
            }
        )

    corrections = _holm_bonferroni(p_values)
    n_tests = len(p_values)

    result = {"n_pairwise_tests": n_tests, "comparisons": {}}
    for raw, corr in zip(raw_results, corrections, strict=False):
        raw["significant_holm"] = corr["significant_holm"]
        raw["holm_threshold"] = corr["holm_threshold"]
        result["comparisons"].setdefault(raw["model"], {})[str(raw["rate"])] = raw

    result["multiple_comparisons"] = {
        "n_tests": n_tests,
        "n_significant_uncorrected": sum(
            1 for r in raw_results if r["p_value_uncorrected"] < 0.05
        ),
        "n_significant_holm": sum(1 for c in corrections if c["significant_holm"]),
    }

    return result


# ── 12. Multi-turn degradation (Phase 5) ────────────────────────────


def analyze_multiturn_degradation(df: pd.DataFrame) -> dict:
    p5 = df[df["phase"] == "p5_multiturn"]
    if p5.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p5["model"].unique()):
        model_data = p5[p5["model"] == model]
        by_strategy = {}

        for strategy in sorted(model_data["context_strategy"].unique()):
            strat_data = model_data[model_data["context_strategy"] == strategy]
            by_turn = {}

            for turn in sorted(strat_data["turn_number"].unique()):
                turn_data = strat_data[strat_data["turn_number"] == turn]
                wall = turn_data["wall_ms"].dropna().values
                pt = turn_data["prompt_tokens"].dropna().values
                tps = turn_data["tokens_per_s"].dropna().values
                pe = turn_data["prompt_eval_ms"].dropna().values

                if len(wall) == 0:
                    continue

                entry = _full_summary(wall)
                if len(pt) > 0:
                    entry["prompt_tokens_mean"] = round(float(np.mean(pt)), 0)
                if len(tps) > 0:
                    entry["tokens_per_s_mean"] = round(float(np.mean(tps)), 1)
                if len(pe) >= 2:
                    entry["prompt_eval_ms_mean"] = round(float(np.mean(pe)), 1)
                    entry["prompt_eval_ms_ci95"] = _ci95(pe)

                by_turn[str(int(turn))] = entry

            # Degradation metrics
            turns = sorted(by_turn.keys(), key=int)
            degradation = {}
            if len(turns) >= 2:
                first = by_turn[turns[0]]
                last = by_turn[turns[-1]]
                if first["mean"] > 0:
                    degradation["wall_ms_growth_pct"] = round(
                        (last["mean"] - first["mean"]) / first["mean"] * 100, 1
                    )
                if first.get("prompt_tokens_mean") and last.get("prompt_tokens_mean"):
                    degradation["prompt_tokens_growth_pct"] = round(
                        (last["prompt_tokens_mean"] - first["prompt_tokens_mean"])
                        / first["prompt_tokens_mean"]
                        * 100,
                        1,
                    )
                if len(turns) >= 3:
                    turn_nums = np.array([int(t) for t in turns])
                    wall_means = np.array([by_turn[t]["mean"] for t in turns])
                    slope, intercept, r_val, p_val, _ = stats.linregress(
                        turn_nums, wall_means
                    )
                    degradation["linear_fit"] = {
                        "slope_ms_per_turn": round(float(slope), 2),
                        "intercept_ms": round(float(intercept), 2),
                        "r_squared": round(float(r_val**2), 4),
                        "p_value": round(float(p_val), 6),
                    }

            by_strategy[strategy] = {
                "by_turn": by_turn,
                "n_conversations": len(strat_data["conversation_id"].unique()),
                "degradation": degradation,
            }

        results[model] = by_strategy

    return results


# ── 13. Context strategy comparison (Phase 5) ───────────────────────


def analyze_context_strategies(df: pd.DataFrame) -> dict:
    p5 = df[df["phase"] == "p5_multiturn"]
    if p5.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p5["model"].unique()):
        model_data = p5[p5["model"] == model]
        max_turn = model_data["turn_number"].max()

        full = (
            model_data[
                (model_data["context_strategy"] == "full")
                & (model_data["turn_number"] == max_turn)
            ]["wall_ms"]
            .dropna()
            .values
        )

        sliding = (
            model_data[
                (model_data["context_strategy"] == "sliding_window")
                & (model_data["turn_number"] == max_turn)
            ]["wall_ms"]
            .dropna()
            .values
        )

        entry = {"compared_at_turn": int(max_turn) if not pd.isna(max_turn) else None}

        if len(full) > 0:
            entry["full"] = _full_summary(full)
        if len(sliding) > 0:
            entry["sliding"] = _full_summary(sliding)

        if len(full) >= 2 and len(sliding) >= 2:
            t_stat, p_value = stats.ttest_ind(full, sliding)
            full_mean = float(np.mean(full))
            sliding_mean = float(np.mean(sliding))
            pooled_std = np.sqrt(
                (
                    (len(full) - 1) * np.var(full, ddof=1)
                    + (len(sliding) - 1) * np.var(sliding, ddof=1)
                )
                / (len(full) + len(sliding) - 2)
            )
            cohens_d = (full_mean - sliding_mean) / pooled_std if pooled_std > 0 else 0

            entry["comparison"] = {
                "t_statistic": round(float(t_stat), 3),
                "p_value": round(float(p_value), 4),
                "significant": bool(p_value < 0.05),
                "reduction_pct": (
                    round((full_mean - sliding_mean) / full_mean * 100, 1)
                    if full_mean > 0
                    else 0
                ),
                "cohens_d": round(float(cohens_d), 3),
                "effect": effect_label(cohens_d),
            }

            # Prompt tokens comparison
            full_pt = (
                model_data[
                    (model_data["context_strategy"] == "full")
                    & (model_data["turn_number"] == max_turn)
                ]["prompt_tokens"]
                .dropna()
                .values
            )
            sliding_pt = (
                model_data[
                    (model_data["context_strategy"] == "sliding_window")
                    & (model_data["turn_number"] == max_turn)
                ]["prompt_tokens"]
                .dropna()
                .values
            )

            if len(full_pt) > 0:
                entry["full_prompt_tokens_mean"] = round(float(np.mean(full_pt)), 0)
            if len(sliding_pt) > 0:
                entry["sliding_prompt_tokens_mean"] = round(
                    float(np.mean(sliding_pt)), 0
                )

        results[model] = entry

    return results


# ── 14. TR127 cross-validation ──────────────────────────────────────


def analyze_tr127_cross_validation(df: pd.DataFrame) -> dict:
    tr127_results = _DIR.parent / "tr127" / "results"
    tr127_analysis_path = None

    if tr127_results.is_dir():
        tr127_run = find_latest_run(tr127_results)
        if tr127_run:
            candidate = tr127_run / "analysis.json"
            if candidate.exists():
                tr127_analysis_path = candidate

    if tr127_analysis_path is None:
        return {"status": "tr127_not_found"}

    try:
        with open(tr127_analysis_path, encoding="utf-8") as f:
            tr127 = json.load(f)
    except Exception as exc:
        return {"status": f"tr127_load_error: {exc}"}

    tr127_prefill = tr127.get("prefill_scaling", {})
    if not tr127_prefill:
        return {"status": "tr127_no_prefill_data"}

    # Use Phase 1 baseline data (serial, zero queueing)
    p1 = df[df["phase"] == "p1_baseline"]
    if p1.empty:
        return {"status": "no_baseline_data"}

    comparisons = {}
    for model in sorted(p1["model"].unique()):
        model_p1 = p1[p1["model"] == model]
        tr128_prefill_ms = model_p1["prompt_eval_ms"].dropna().values

        if len(tr128_prefill_ms) == 0:
            continue

        comp = {
            "tr128": _full_summary(tr128_prefill_ms),
            "tr128_prompt_tokens_mean": round(
                float(model_p1["prompt_tokens"].dropna().mean()), 0
            ),
        }

        model_norm = model.replace("-", "").replace(".", "").lower()
        for key, data in tr127_prefill.items():
            key_norm = key.replace("-", "").replace(".", "").lower()
            if model_norm in key_norm:
                comp["tr127_key"] = key
                per_ctx = data.get("per_context_length", {})
                if per_ctx:
                    tr128_tokens = comp["tr128_prompt_tokens_mean"]
                    closest_ctx = min(
                        per_ctx.keys(),
                        key=lambda x: abs(int(x) - tr128_tokens),
                        default=None,
                    )
                    if closest_ctx:
                        ctx_data = per_ctx[closest_ctx]
                        comp["tr127_context"] = int(closest_ctx)
                        comp["tr127_prefill_ms_mean"] = ctx_data.get("mean")
                        tr128_mean = comp["tr128"]["mean"]
                        tr127_mean = ctx_data.get("mean")
                        if tr128_mean and tr127_mean and tr127_mean > 0:
                            comp["delta_pct"] = round(
                                (tr128_mean - tr127_mean) / tr127_mean * 100, 1
                            )
                break

        comparisons[model] = comp

    return {"comparisons": comparisons}


# ── 15. Cold-start detection ────────────────────────────────────────


def analyze_cold_start(df: pd.DataFrame) -> dict:
    results = {}

    for model in sorted(df["model"].unique()):
        model_data = df[df["model"] == model]
        per_phase = {}

        for phase in sorted(model_data["phase"].unique()):
            phase_data = model_data[model_data["phase"] == phase].sort_values(
                ["request_id", "turn_number"],
                na_position="first",
            )
            if len(phase_data) < 3:
                continue

            first_wall = float(phase_data.iloc[0]["wall_ms"])
            rest_wall = phase_data.iloc[1:]["wall_ms"].dropna().values

            if len(rest_wall) == 0:
                continue

            median_rest = float(np.median(rest_wall))
            ratio = first_wall / median_rest if median_rest > 0 else 1.0

            per_phase[phase] = {
                "first_request_ms": round(first_wall, 1),
                "median_rest_ms": round(median_rest, 1),
                "cold_ratio": round(ratio, 2),
                "is_cold": bool(ratio > 2.0),
                "load_duration_ms": round(
                    float(phase_data.iloc[0].get("load_duration_ms", 0) or 0), 1
                ),
            }

        results[model] = {"per_phase": per_phase}

    return results


# ── 16. Outlier analysis ────────────────────────────────────────────


def analyze_outliers(df: pd.DataFrame) -> dict:
    results = {}

    for phase in sorted(df["phase"].unique()):
        phase_data = df[df["phase"] == phase]
        phase_results = {}

        for model in sorted(phase_data["model"].unique()):
            wall = phase_data[phase_data["model"] == model]["wall_ms"].dropna().tolist()
            if len(wall) < 4:
                continue

            iqr_info = detect_outliers(wall, method="iqr")
            arr = np.array(wall)
            z_scores = (
                np.abs((arr - arr.mean()) / arr.std())
                if arr.std() > 0
                else np.zeros(len(arr))
            )

            phase_results[model] = {
                "n": len(wall),
                "iqr_outliers": iqr_info.get("n_outliers", 0),
                "iqr_outlier_pct": round(
                    iqr_info.get("n_outliers", 0) / len(wall) * 100, 1
                ),
                "zscore_outliers": int((z_scores > 3).sum()),
            }

        results[phase] = phase_results

    return results


# ── 17. Power analysis ──────────────────────────────────────────────


def analyze_power(df: pd.DataFrame) -> dict:
    results = {}

    for phase in sorted(df["phase"].unique()):
        phase_data = df[df["phase"] == phase]
        phase_results = {}

        for model in sorted(phase_data["model"].unique()):
            wall = phase_data[phase_data["model"] == model]["wall_ms"].dropna().values
            n = len(wall)
            if n < 3:
                continue

            mean_val = float(np.mean(wall))
            std_val = float(np.std(wall, ddof=1))

            sensitivity = {}
            for power, z_beta in [(0.80, 0.842), (0.90, 1.282), (0.95, 1.645)]:
                z_alpha = 1.96
                min_d = (z_alpha + z_beta) * np.sqrt(2.0 / n)
                min_ms = min_d * std_val if std_val > 0 else None
                sensitivity[f"power_{int(power * 100)}"] = {
                    "min_detectable_d": round(float(min_d), 3),
                    "min_detectable_ms": round(float(min_ms), 1) if min_ms else None,
                    "min_detectable_pct": (
                        round(float(min_ms) / mean_val * 100, 1)
                        if min_ms and mean_val > 0
                        else None
                    ),
                }

            # TR126-style interpretation label based on min detectable d at 80% power
            s80 = sensitivity.get("power_80", {})
            min_d_80 = s80.get("min_detectable_d", float("inf"))
            if min_d_80 < 0.2:
                interpretation = "can detect small effects"
            elif min_d_80 < 0.5:
                interpretation = "can detect small-to-medium effects"
            elif min_d_80 < 0.8:
                interpretation = "can detect medium effects"
            else:
                interpretation = "can only detect large effects — consider more samples"

            phase_results[model] = {
                "n": n,
                "mean_ms": round(mean_val, 1),
                "std_ms": round(std_val, 1),
                "cv_pct": round(std_val / mean_val * 100, 1) if mean_val > 0 else 0,
                "sensitivity": sensitivity,
                "interpretation": interpretation,
            }

        results[phase] = phase_results

    return results


# ── 18. Distribution shape ──────────────────────────────────────────


def analyze_distribution_shape(df: pd.DataFrame) -> dict:
    results = {}

    for phase in sorted(df["phase"].unique()):
        phase_data = df[df["phase"] == phase]
        phase_results = {}

        for model in sorted(phase_data["model"].unique()):
            wall = phase_data[phase_data["model"] == model]["wall_ms"].dropna().values
            if len(wall) < 8:
                continue

            skew = float(stats.skew(wall))
            kurt = float(stats.kurtosis(wall))
            mm_ratio = (
                float(np.mean(wall)) / float(np.median(wall))
                if np.median(wall) > 0
                else 1.0
            )

            entry = {
                "n": len(wall),
                "skewness": round(skew, 3),
                "kurtosis": round(kurt, 3),
                "mean_median_ratio": round(mm_ratio, 3),
                "right_skewed": bool(skew > 0.5),
                "heavy_tailed": bool(kurt > 3.0),
            }

            if 3 <= len(wall) <= 5000:
                sw_stat, sw_p = stats.shapiro(wall)
                entry["shapiro_w"] = round(float(sw_stat), 4)
                entry["shapiro_p"] = round(float(sw_p), 4)
                entry["is_normal"] = bool(sw_p > 0.05)

            phase_results[model] = entry

        results[phase] = phase_results

    return results


# ── 19. Cross-phase consistency ────────────────────────────────────


def analyze_cross_phase_consistency(df: pd.DataFrame, baseline: dict) -> dict:
    """Validate Phase 1 baseline means match Phase 2 NP=1 lowest-rate means.

    Catches data collection issues: if serial baseline disagrees with
    the NP=1/rate=0.5 condition, something is wrong.
    """
    if not baseline or baseline.get("status") == "no_data":
        return {"status": "no_baseline"}

    p2 = df[df["phase"] == "p2_concurrency"]
    if p2.empty:
        return {"status": "no_phase2"}

    checks = {}
    for model in sorted(p2["model"].unique()):
        bl = baseline.get(model, {})
        bl_mean = bl.get("wall_ms", {}).get("mean")
        if not bl_mean:
            continue

        # NP=1, lowest arrival rate
        np1 = p2[(p2["model"] == model) & (p2["num_parallel"] == 1)]
        if np1.empty:
            continue
        lowest_rate = np1["arrival_rate_rps"].min()
        p2_low = np1[np1["arrival_rate_rps"] == lowest_rate]["wall_ms"].dropna().values
        p1_vals = (
            df[(df["phase"] == "p1_baseline") & (df["model"] == model)]["wall_ms"]
            .dropna()
            .values
        )

        if len(p2_low) < 2 or len(p1_vals) < 2:
            continue

        comp = compare_groups(
            p1_vals.tolist(),
            p2_low.tolist(),
            "p1_baseline",
            f"p2_np1_rate{lowest_rate}",
            "wall_ms",
        )

        p2_mean = float(np.mean(p2_low))
        checks[model] = {
            "p1_mean_ms": round(bl_mean, 1),
            "p2_np1_lowest_rate": float(lowest_rate),
            "p2_np1_mean_ms": round(p2_mean, 1),
            "delta_pct": round(comp.percent_change, 1),
            "p_value": round(comp.p_value, 4),
            "significant": comp.significant,
            "cohens_d": round(comp.effect_size, 3),
            "effect": effect_label(comp.effect_size),
            "consistent": not comp.significant or abs(comp.effect_size) < 0.5,
        }

    n_consistent = sum(1 for c in checks.values() if c["consistent"])
    return {
        "checks": checks,
        "n_models": len(checks),
        "n_consistent": n_consistent,
        "all_consistent": n_consistent == len(checks),
    }


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR128 analysis")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    run_dir = find_latest_run(TR128_RESULTS)
    if run_dir is None:
        log.error("No results found in %s", TR128_RESULTS)
        return 1

    log.info("Analyzing run: %s", run_dir.name)

    csv_path = run_dir / "metrics.csv"
    if not csv_path.exists():
        log.error("metrics.csv not found in %s", run_dir)
        return 1

    df_all = load_metrics_csv(csv_path, filter_ok=False)
    df = load_metrics_csv(csv_path, filter_ok=True)

    log.info("Loaded %d total rows (%d ok)", len(df_all), len(df))

    # Phase 1 baseline used by Phase 4 (M/D/1)
    baseline = analyze_baseline(df)

    analysis = {
        "run_id": run_dir.name,
        "summary": analyze_summary(df_all),
        "baseline": baseline,
        "concurrency_scaling": analyze_concurrency(df),
        "md1_deviation": analyze_md1_deviation(df, baseline),
        "queue_depth": analyze_queue_depth(df),
        "latency_amplification": analyze_latency_amplification(df),
        "thermal_stability": analyze_thermal(df, run_dir),
        "gpu_metrics": analyze_gpu_metrics(run_dir),
        "ttft_analysis": analyze_ttft(df),
        "ichunk_stability": analyze_ichunk(df, run_dir=run_dir),
        "stream_vs_batch": analyze_stream_vs_batch(df),
        "multiturn_degradation": analyze_multiturn_degradation(df),
        "context_strategy_comparison": analyze_context_strategies(df),
        "tr127_cross_validation": analyze_tr127_cross_validation(df),
        "cold_start_detection": analyze_cold_start(df),
        "outlier_analysis": analyze_outliers(df),
        "power_analysis": analyze_power(df),
        "distribution_shape": analyze_distribution_shape(df),
        "cross_phase_consistency": analyze_cross_phase_consistency(df, baseline),
    }

    out_path = run_dir / "analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)

    log.info("Analysis saved: %s (%d sections)", out_path, len(analysis) - 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
