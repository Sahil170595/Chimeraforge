"""TR129 — Statistical analysis for N-Agent Scaling Laws.

Reads metrics.csv and GPU CSVs from the latest run.
Produces analysis.json with 19 sections:

  1. Summary
  2. Single-agent baseline
  3. N-agent throughput curves
  4. Efficiency curves
  5. Scaling characterization (Amdahl, power law, exponential, logistic)
  6. Saturation detection
  7. Fairness (Jain's index)
  8. Queue dynamics
  9. Think-time effects
 10. Optimal think-time
 11. Heterogeneous model analysis
 12. Model switching overhead
 13. VRAM usage
 14. TR128 cross-validation
 15. Cold-start detection
 16. Outlier analysis
 17. Power analysis
 18. Distribution shape
 19. Request timeline analysis

Statistical methods:
- 95% CI via t-distribution
- Trimmed-mean robustness checks
- Shapiro-Wilk normality testing
- Cohen's d effect sizes
- Curve fitting: Amdahl's Law, power law, exponential, logistic

Throughput columns:
- effective_tps = completion_tokens / wall_ms   (PRIMARY — user-perceived, includes queue wait)
- gpu_tokens_per_s = completion_tokens / eval_ms (GPU decode only — sanity check, stays ~constant)

Usage:
    python research/tr129/analyze.py [-v]
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
from scipy.optimize import curve_fit

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.tr129.shared.utils import (
    TR129_RESULTS,
    effect_label,
    find_latest_run,
    load_metrics_csv,
)

log = logging.getLogger("tr129.analyze")


# -- Statistical helpers ----------------------------------------------------


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


def _load_gpu_csv(path: Path) -> pd.DataFrame | None:
    """Load a GPU metrics CSV if it exists."""
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path, exc)
        return None


def _jains_index(values: np.ndarray) -> float:
    """Jain's fairness index: (sum(x))^2 / (n * sum(x^2))."""
    n = len(values)
    if n == 0:
        return 0.0
    s = float(np.sum(values))
    s2 = float(np.sum(values**2))
    if s2 == 0:
        return 1.0
    return round(s**2 / (n * s2), 4)


# -- Scaling law models -----------------------------------------------------


def _amdahl(n, s):
    """Amdahl's Law: eta(N) = 1 / (s + (1-s)*N) where s = serial fraction."""
    return 1.0 / (s + (1.0 - s) * n)


def _power_law(n, alpha, c):
    """eta(N) = c * N^(-alpha)."""
    return c * np.power(n, -alpha)


def _exponential_decay(n, beta, c):
    """eta(N) = c * exp(-beta * (N - 1))."""
    return c * np.exp(-beta * (n - 1))


def _logistic(n, k, n0, c):
    """eta(N) = c / (1 + exp(k * (N - n0)))."""
    return c / (1.0 + np.exp(k * (n - n0)))


def _fit_scaling_law(n_values: np.ndarray, eta_values: np.ndarray) -> dict:
    """Fit Amdahl, power law, exponential, and logistic models to efficiency data."""
    results = {}

    # Amdahl's Law: eta = 1 / (s + (1-s)*N), 1 parameter (most parsimonious)
    try:
        popt, _ = curve_fit(
            _amdahl, n_values, eta_values, p0=[0.1], maxfev=5000, bounds=([0], [1])
        )
        pred = _amdahl(n_values, *popt)
        ss_res = float(np.sum((eta_values - pred) ** 2))
        ss_tot = float(np.sum((eta_values - np.mean(eta_values)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        n_star = int(np.ceil(1.0 / popt[0])) if popt[0] > 0 else None
        results["amdahl"] = {
            "serial_fraction": round(float(popt[0]), 6),
            "r_squared": round(r2, 4),
            "predicted_n_star": n_star,
            "formula": f"eta(N) = 1 / ({popt[0]:.4f} + {1-popt[0]:.4f}*N)",
        }
    except Exception as exc:
        results["amdahl"] = {"error": str(exc)}

    # Power law: eta = c * N^(-alpha)
    try:
        popt, _ = curve_fit(
            _power_law,
            n_values,
            eta_values,
            p0=[0.5, 1.0],
            maxfev=5000,
            bounds=([0, 0], [5, 2]),
        )
        pred = _power_law(n_values, *popt)
        ss_res = float(np.sum((eta_values - pred) ** 2))
        ss_tot = float(np.sum((eta_values - np.mean(eta_values)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        results["power_law"] = {
            "alpha": round(float(popt[0]), 4),
            "c": round(float(popt[1]), 4),
            "r_squared": round(r2, 4),
            "formula": f"eta(N) = {popt[1]:.3f} * N^(-{popt[0]:.3f})",
        }
    except Exception as exc:
        results["power_law"] = {"error": str(exc)}

    # Exponential: eta = c * exp(-beta(N-1))
    try:
        popt, _ = curve_fit(
            _exponential_decay,
            n_values,
            eta_values,
            p0=[0.1, 1.0],
            maxfev=5000,
            bounds=([0, 0], [5, 2]),
        )
        pred = _exponential_decay(n_values, *popt)
        ss_res = float(np.sum((eta_values - pred) ** 2))
        ss_tot = float(np.sum((eta_values - np.mean(eta_values)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        results["exponential"] = {
            "beta": round(float(popt[0]), 4),
            "c": round(float(popt[1]), 4),
            "r_squared": round(r2, 4),
            "formula": f"eta(N) = {popt[1]:.3f} * exp(-{popt[0]:.3f}*(N-1))",
        }
    except Exception as exc:
        results["exponential"] = {"error": str(exc)}

    # Logistic: eta = c / (1 + exp(k*(N - n0)))
    try:
        popt, _ = curve_fit(
            _logistic,
            n_values,
            eta_values,
            p0=[1.0, 4.0, 1.0],
            maxfev=5000,
            bounds=([0, 0, 0], [10, 20, 2]),
        )
        pred = _logistic(n_values, *popt)
        ss_res = float(np.sum((eta_values - pred) ** 2))
        ss_tot = float(np.sum((eta_values - np.mean(eta_values)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        results["logistic"] = {
            "k": round(float(popt[0]), 4),
            "n0": round(float(popt[1]), 4),
            "c": round(float(popt[2]), 4),
            "r_squared": round(r2, 4),
            "formula": f"eta(N) = {popt[2]:.3f} / (1 + exp({popt[0]:.3f}*(N-{popt[1]:.3f})))",
        }
    except Exception as exc:
        results["logistic"] = {"error": str(exc)}

    # Best fit
    best = max(
        [(k, v.get("r_squared", -1)) for k, v in results.items() if "r_squared" in v],
        key=lambda x: x[1],
        default=("none", -1),
    )
    results["best_fit"] = best[0]
    results["best_r_squared"] = round(best[1], 4)

    return results


# -- 1. Summary -------------------------------------------------------------


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
        "status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "rows_per_phase": {
            str(k): int(v) for k, v in df_all["phase"].value_counts().to_dict().items()
        },
        "rows_per_model": {
            str(k): int(v) for k, v in df_all["model"].value_counts().to_dict().items()
        },
    }


# -- 2. Single-agent baseline -----------------------------------------------


def analyze_baseline(df: pd.DataFrame) -> dict:
    """N=1 baseline: per-model throughput distributions (effective_tps + gpu_tokens_per_s)."""
    p1 = df[df["phase"] == "p1_baseline"]
    if p1.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p1["model"].unique()):
        subset = p1[p1["model"] == model]
        wall = subset["wall_ms"].dropna().values
        tps = subset["effective_tps"].dropna().values
        gpu_tps = subset["gpu_tokens_per_s"].dropna().values

        entry = {"wall_ms": _full_summary(wall)}
        if len(tps) > 0:
            entry["effective_tps"] = _full_summary(tps)
        if len(gpu_tps) > 0:
            entry["gpu_tokens_per_s"] = _full_summary(gpu_tps)

        if len(wall) > 0:
            mean_service_s = float(np.mean(wall)) / 1000.0
            entry["mean_service_ms"] = round(mean_service_s * 1000, 1)

        if len(wall) >= 10:
            entry["trimmed_mean_10pct"] = round(_trimmed_mean(wall, 0.10), 1)

        results[model] = entry

    return results


# -- 3. N-agent throughput curves -------------------------------------------


def analyze_throughput_curves(df: pd.DataFrame, baseline: dict) -> dict:
    """Total and per-agent tok/s vs N for each model.

    Reports effective_tps as primary metric and gpu_tokens_per_s as sanity check
    (gpu_tokens_per_s should stay roughly constant with N, confirming the GPU
    is always running at full speed and degradation is all in queue wait).
    """
    p2 = df[df["phase"] == "p2_scaling"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        curves = {}

        for n_agents in sorted(model_data["n_agents"].unique()):
            n_data = model_data[model_data["n_agents"] == n_agents]
            tps = n_data["effective_tps"].dropna().values
            gpu_tps = n_data["gpu_tokens_per_s"].dropna().values
            wall = n_data["wall_ms"].dropna().values

            if len(tps) == 0:
                continue

            # Per-agent throughput (effective)
            per_agent_tps = _full_summary(tps)

            # GPU decode throughput (sanity check — should be ~constant)
            gpu_tps_summary = _full_summary(gpu_tps) if len(gpu_tps) > 0 else {"n": 0}

            # Total system throughput: sum of per-agent means
            per_agent_means = []
            for aid in sorted(n_data["agent_id"].unique()):
                agent_data = n_data[n_data["agent_id"] == aid]
                agent_tps = agent_data["effective_tps"].dropna().values
                if len(agent_tps) > 0:
                    per_agent_means.append(float(np.mean(agent_tps)))

            total_system_tps = sum(per_agent_means)

            curves[str(int(n_agents))] = {
                "n_agents": int(n_agents),
                "per_agent_tps": per_agent_tps,
                "gpu_tokens_per_s": gpu_tps_summary,
                "total_system_tps": round(total_system_tps, 2),
                "wall_ms": _full_summary(wall),
                "n_ok": int((n_data["status"] == "ok").sum()),
                "n_total": len(n_data),
            }

        results[model] = curves

    return results


# -- 4. Efficiency curves ---------------------------------------------------


def analyze_efficiency(df: pd.DataFrame, baseline: dict) -> dict:
    """eta(N) = per_agent_tps(N) / per_agent_tps(1) for each model.

    Prefers Phase 1 baseline (50 measurements, more precise) over Phase 2 N=1
    (30 measurements) for the denominator.
    """
    p2 = df[df["phase"] == "p2_scaling"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]

        # Prefer Phase 1 baseline (50 measurements, more precise)
        bl_entry = baseline.get(model, {})
        bl_tps = bl_entry.get("effective_tps", {})
        baseline_tps = bl_tps.get("mean", 0)

        if baseline_tps <= 0:
            # Fall back to Phase 2 N=1
            n1_data = model_data[model_data["n_agents"] == 1]
            n1_tps = n1_data["effective_tps"].dropna().values
            baseline_tps = float(np.mean(n1_tps)) if len(n1_tps) > 0 else 0

        if baseline_tps <= 0:
            results[model] = {"error": "no baseline throughput"}
            continue

        efficiency_curve = {}
        for n_agents in sorted(model_data["n_agents"].unique()):
            n_data = model_data[model_data["n_agents"] == n_agents]
            tps = n_data["effective_tps"].dropna().values
            if len(tps) == 0:
                continue

            mean_tps = float(np.mean(tps))
            eta = mean_tps / baseline_tps

            efficiency_curve[str(int(n_agents))] = {
                "n_agents": int(n_agents),
                "mean_per_agent_tps": round(mean_tps, 2),
                "baseline_tps": round(baseline_tps, 2),
                "efficiency_eta": round(eta, 4),
                "efficiency_pct": round(eta * 100, 1),
                "ci95_tps": _ci95(tps),
            }

        results[model] = {
            "baseline_tps": round(baseline_tps, 2),
            "baseline_source": "phase1" if bl_tps.get("mean", 0) > 0 else "phase2_n1",
            "curve": efficiency_curve,
        }

    return results


# -- 5. Scaling characterization --------------------------------------------


def analyze_scaling_laws(efficiency: dict) -> dict:
    """Fit Amdahl, power law, exponential, logistic to eta(N) curves."""
    if efficiency.get("status") == "no_data":
        return {"status": "no_data"}

    results = {}
    for model, data in efficiency.items():
        if not isinstance(data, dict) or "curve" not in data:
            continue

        curve = data["curve"]
        n_vals = []
        eta_vals = []
        for n_str, entry in sorted(curve.items(), key=lambda x: int(x[0])):
            n_vals.append(int(n_str))
            eta_vals.append(entry["efficiency_eta"])

        if len(n_vals) < 3:
            results[model] = {"error": "insufficient data points for fitting"}
            continue

        n_arr = np.array(n_vals, dtype=float)
        eta_arr = np.array(eta_vals, dtype=float)
        results[model] = _fit_scaling_law(n_arr, eta_arr)

    return results


# -- 6. Saturation detection ------------------------------------------------


def analyze_saturation(efficiency: dict) -> dict:
    """Find N* where eta < 50% (half-throughput point)."""
    if efficiency.get("status") == "no_data":
        return {"status": "no_data"}

    results = {}
    for model, data in efficiency.items():
        if not isinstance(data, dict) or "curve" not in data:
            continue

        curve = data["curve"]
        n_star = None

        for n_str in sorted(curve.keys(), key=lambda x: int(x)):
            eta = curve[n_str]["efficiency_eta"]
            if eta < 0.5 and n_star is None:
                n_star = int(n_str)

        last_n = max(int(k) for k in curve)
        last_eta = curve[str(last_n)]["efficiency_eta"]

        results[model] = {
            "n_star_50pct": n_star,
            "saturated": n_star is not None,
            "last_n_tested": last_n,
            "last_eta": round(last_eta, 4),
            "last_eta_pct": round(last_eta * 100, 1),
        }

    return results


# -- 7. Fairness (Jain's index) ---------------------------------------------


def analyze_fairness(df: pd.DataFrame) -> dict:
    """Jain's index and CV of per-agent throughput at each N."""
    p2 = df[df["phase"] == "p2_scaling"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        model_results = {}

        for n_agents in sorted(model_data["n_agents"].unique()):
            n_data = model_data[model_data["n_agents"] == n_agents]

            # Per-agent mean throughput
            agent_means = []
            for aid in sorted(n_data["agent_id"].unique()):
                agent_data = n_data[n_data["agent_id"] == aid]
                tps = agent_data["effective_tps"].dropna().values
                if len(tps) > 0:
                    agent_means.append(float(np.mean(tps)))

            if not agent_means:
                continue

            arr = np.array(agent_means)
            jain = _jains_index(arr)
            cv = (
                float(np.std(arr, ddof=1) / np.mean(arr) * 100)
                if np.mean(arr) > 0 and len(arr) > 1
                else 0.0
            )

            model_results[str(int(n_agents))] = {
                "n_agents": int(n_agents),
                "jains_index": jain,
                "cv_pct": round(cv, 2),
                "per_agent_means": [round(x, 2) for x in agent_means],
                "min_agent_tps": round(float(min(agent_means)), 2),
                "max_agent_tps": round(float(max(agent_means)), 2),
                "spread_ratio": (
                    round(max(agent_means) / min(agent_means), 3)
                    if min(agent_means) > 0
                    else None
                ),
            }

        results[model] = model_results

    return results


# -- 8. Queue dynamics -------------------------------------------------------


def analyze_queue_dynamics(df: pd.DataFrame) -> dict:
    """in_flight distribution at each N level."""
    p2 = df[df["phase"] == "p2_scaling"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        model_results = {}

        for n_agents in sorted(model_data["n_agents"].unique()):
            n_data = model_data[model_data["n_agents"] == n_agents]
            in_flight = n_data["in_flight_at_submit"].dropna().values

            if len(in_flight) == 0:
                continue

            distribution = {}
            for v in range(int(n_agents)):
                count = int(np.sum(in_flight == v))
                distribution[str(v)] = count

            model_results[str(int(n_agents))] = {
                "n_agents": int(n_agents),
                "mean_in_flight": round(float(np.mean(in_flight)), 2),
                "max_in_flight": int(np.max(in_flight)),
                "distribution": distribution,
                "max_possible": int(n_agents) - 1,
                "utilization": round(
                    float(np.mean(in_flight)) / max(int(n_agents) - 1, 1), 3
                ),
            }

        results[model] = model_results

    return results


# -- 9. Think-time effects ---------------------------------------------------


def analyze_think_time(df: pd.DataFrame, efficiency: dict) -> dict:
    """eta at different think times for N=4.

    TWO throughput perspectives:
    - per_request_tps: completion_tokens / wall_ms (how fast each call returns)
    - sustained_tps:   completion_tokens / (wall_ms + think_time_ms)
                       (actual token production rate including idle time)

    total_system_tps uses SUSTAINED metric so it never exceeds GPU ceiling.
    per_request efficiency (eta_per_request) shows contention reduction.
    sustained efficiency (eta_sustained) shows real agent productivity.
    """
    p3 = df[df["phase"] == "p3_think_time"]
    if p3.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p3["model"].unique()):
        model_data = p3[p3["model"] == model]

        # Get N=1 baseline from efficiency data
        eff_data = efficiency.get(model, {})
        baseline_tps = eff_data.get("baseline_tps", 0)

        model_results = {}
        for think_ms in sorted(model_data["think_time_ms"].unique()):
            tt_data = model_data[model_data["think_time_ms"] == think_ms]
            tps = tt_data["effective_tps"].dropna().values
            wall = tt_data["wall_ms"].dropna().values

            if len(tps) == 0:
                continue

            mean_tps = float(np.mean(tps))
            mean_wall = float(np.mean(wall))
            think_val = float(think_ms)

            # Per-request efficiency (how fast each call completes)
            eta_per_request = mean_tps / baseline_tps if baseline_tps > 0 else 0

            # Duty cycle: fraction of time agent is actively requesting
            duty_cycle = (
                mean_wall / (mean_wall + think_val)
                if (mean_wall + think_val) > 0
                else 1.0
            )

            # Sustained per-agent throughput (tokens per second of REAL time)
            sustained_per_agent = mean_tps * duty_cycle

            # Sustained efficiency (real agent productivity vs baseline)
            eta_sustained = (
                sustained_per_agent / baseline_tps if baseline_tps > 0 else 0
            )

            # Total system throughput: use SUSTAINED metric
            # This is the actual token production rate and never exceeds GPU ceiling
            per_agent_sustained = []
            for aid in sorted(tt_data["agent_id"].unique()):
                agent_data = tt_data[tt_data["agent_id"] == aid]
                agent_tps = agent_data["effective_tps"].dropna().values
                agent_wall = agent_data["wall_ms"].dropna().values
                if len(agent_tps) > 0 and len(agent_wall) > 0:
                    a_mean_tps = float(np.mean(agent_tps))
                    a_mean_wall = float(np.mean(agent_wall))
                    a_duty = (
                        a_mean_wall / (a_mean_wall + think_val)
                        if (a_mean_wall + think_val) > 0
                        else 1.0
                    )
                    per_agent_sustained.append(a_mean_tps * a_duty)

            total_sustained_tps = sum(per_agent_sustained)

            # Also keep per-request total for reference (burst rate)
            per_agent_burst = []
            for aid in sorted(tt_data["agent_id"].unique()):
                agent_tps_vals = (
                    tt_data[tt_data["agent_id"] == aid]["effective_tps"].dropna().values
                )
                if len(agent_tps_vals) > 0:
                    per_agent_burst.append(float(np.mean(agent_tps_vals)))
            total_burst_tps = sum(per_agent_burst)

            model_results[str(int(think_ms))] = {
                "think_time_ms": int(think_ms),
                "per_agent_tps": _full_summary(tps),
                "total_system_tps": round(total_sustained_tps, 2),
                "total_burst_tps": round(total_burst_tps, 2),
                "duty_cycle": round(duty_cycle, 4),
                "eta_per_request": round(eta_per_request, 4),
                "eta_sustained": round(eta_sustained, 4),
                "sustained_per_agent_tps": round(sustained_per_agent, 2),
                "wall_ms": _full_summary(wall),
                "n_ok": int((tt_data["status"] == "ok").sum()),
                "n_total": len(tt_data),
            }

        results[model] = model_results

    return results


# -- 10. Optimal think-time -------------------------------------------------


def analyze_optimal_think_time(think_time: dict) -> dict:
    """Find think_time maximizing sustained total throughput for each model.

    Uses total_system_tps (sustained, duty-cycle-corrected) not burst rate.
    """
    if think_time.get("status") == "no_data":
        return {"status": "no_data"}

    results = {}
    for model, data in think_time.items():
        if not isinstance(data, dict):
            continue

        best_tt = None
        best_total = 0.0
        all_points = []

        for tt_str, entry in data.items():
            total = entry.get("total_system_tps", 0)
            burst = entry.get("total_burst_tps", total)
            duty = entry.get("duty_cycle", 1.0)
            tt = int(tt_str)
            all_points.append(
                {
                    "think_time_ms": tt,
                    "total_system_tps": round(total, 2),
                    "total_burst_tps": round(burst, 2),
                    "duty_cycle": round(duty, 4),
                }
            )
            if total > best_total:
                best_total = total
                best_tt = tt

        results[model] = {
            "optimal_think_time_ms": best_tt,
            "max_total_tps": round(best_total, 2),
            "all_points": sorted(all_points, key=lambda x: x["think_time_ms"]),
        }

    return results


# -- 11. Heterogeneous model analysis ---------------------------------------


def analyze_heterogeneous(df: pd.DataFrame) -> dict:
    """Mixed vs homogeneous throughput in Phase 4."""
    p4 = df[df["phase"] == "p4_heterogeneous"]
    if p4.empty:
        return {"status": "no_data"}

    results = {}
    for config_id in sorted(p4["config_id"].unique()):
        cfg_data = p4[p4["config_id"] == config_id]
        tps = cfg_data["effective_tps"].dropna().values
        wall = cfg_data["wall_ms"].dropna().values

        per_model = {}
        for model in sorted(cfg_data["model"].unique()):
            m_data = cfg_data[cfg_data["model"] == model]
            m_tps = m_data["effective_tps"].dropna().values
            if len(m_tps) > 0:
                per_model[model] = {
                    "n_requests": len(m_data),
                    "mean_tps": round(float(np.mean(m_tps)), 2),
                    "ci95": _ci95(m_tps),
                }

        # Per-agent breakdown
        agent_means = []
        for aid in sorted(cfg_data["agent_id"].unique()):
            a_tps = (
                cfg_data[cfg_data["agent_id"] == aid]["effective_tps"].dropna().values
            )
            if len(a_tps) > 0:
                agent_means.append(float(np.mean(a_tps)))

        arr = np.array(agent_means) if agent_means else np.array([0.0])
        total_tps = sum(agent_means)

        results[config_id] = {
            "n_ok": int((cfg_data["status"] == "ok").sum()),
            "n_total": len(cfg_data),
            "overall_tps": _full_summary(tps) if len(tps) > 0 else {"n": 0},
            "wall_ms": _full_summary(wall) if len(wall) > 0 else {"n": 0},
            "per_model": per_model,
            "total_system_tps": round(total_tps, 2),
            "jains_index": _jains_index(arr),
            "models_used": sorted(cfg_data["model"].unique().tolist()),
        }

    return results


# -- 12. Model switching overhead -------------------------------------------


def analyze_model_switching(df: pd.DataFrame, heterogeneous: dict) -> dict:
    """Compare homo_1b (Phase 4) vs N=4 llama3.2-1b (Phase 2)."""
    p2 = df[
        (df["phase"] == "p2_scaling")
        & (df["model"] == "llama3.2-1b")
        & (df["n_agents"] == 4)
    ]
    p4_homo = df[(df["phase"] == "p4_heterogeneous") & (df["config_id"] == "homo_1b")]

    if p2.empty or p4_homo.empty:
        return {"status": "insufficient_data"}

    p2_tps = p2["effective_tps"].dropna().values
    p4_tps = p4_homo["effective_tps"].dropna().values

    if len(p2_tps) == 0 or len(p4_tps) == 0:
        return {"status": "no_throughput_data"}

    # t-test
    t_stat, p_val = stats.ttest_ind(p2_tps, p4_tps)

    # Cohen's d
    pooled_std = np.sqrt(
        (
            (len(p2_tps) - 1) * np.var(p2_tps, ddof=1)
            + (len(p4_tps) - 1) * np.var(p4_tps, ddof=1)
        )
        / (len(p2_tps) + len(p4_tps) - 2)
    )
    cohens_d = (
        (float(np.mean(p2_tps)) - float(np.mean(p4_tps))) / pooled_std
        if pooled_std > 0
        else 0
    )

    return {
        "phase2_n4_1b": {
            "n": len(p2_tps),
            "mean_tps": round(float(np.mean(p2_tps)), 2),
            "ci95": _ci95(p2_tps),
        },
        "phase4_homo_1b": {
            "n": len(p4_tps),
            "mean_tps": round(float(np.mean(p4_tps)), 2),
            "ci95": _ci95(p4_tps),
        },
        "difference_pct": (
            round(
                (float(np.mean(p4_tps)) - float(np.mean(p2_tps)))
                / float(np.mean(p2_tps))
                * 100,
                2,
            )
            if float(np.mean(p2_tps)) > 0
            else 0
        ),
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_val), 6),
        "significant": bool(p_val < 0.05),
        "cohens_d": round(float(cohens_d), 4),
        "effect_size": effect_label(cohens_d),
        "interpretation": (
            "Phase 4 homo_1b significantly faster than Phase 2 N=4"
            if p_val < 0.05 and float(np.mean(p4_tps)) > float(np.mean(p2_tps))
            else "No significant difference"
        ),
        "confounds": [
            "Ollama restarted with OLLAMA_MAX_LOADED_MODELS=3 before Phase 4",
            "Phase 4 runs after Phase 3 (~60 min into experiment) vs Phase 2 (~5 min in)",
            "Different warmup sequence (all 3 models warmed in Phase 4 vs 1 in Phase 2)",
            "Cannot isolate MAX_LOADED_MODELS effect from thermal/ordering confounds",
        ],
    }


# -- 13. VRAM usage ---------------------------------------------------------


def analyze_vram(run_dir: Path) -> dict:
    """Memory vs N and vs model mix from GPU CSVs."""
    results = {}

    for phase_num in range(1, 5):
        gpu_path = run_dir / f"gpu_phase{phase_num}.csv"
        gpu_df = _load_gpu_csv(gpu_path)
        if gpu_df is None:
            results[f"phase{phase_num}"] = {"status": "no_gpu_data"}
            continue

        mem = gpu_df["mem_used_mb"].dropna().values
        if len(mem) == 0:
            results[f"phase{phase_num}"] = {"status": "no_mem_data"}
            continue

        results[f"phase{phase_num}"] = {
            "mean_mb": round(float(np.mean(mem)), 1),
            "max_mb": round(float(np.max(mem)), 1),
            "min_mb": round(float(np.min(mem)), 1),
            "std_mb": round(float(np.std(mem)), 1),
            "n_samples": len(mem),
        }

    return results


# -- 14. TR128 cross-validation ---------------------------------------------


def analyze_cross_validation(df: pd.DataFrame) -> dict:
    """Compare N=1 (Phase 1) with TR128 Phase 1 if available."""
    p1 = df[df["phase"] == "p1_baseline"]
    if p1.empty:
        return {"status": "no_data"}

    # Try loading TR128 results
    tr128_results = Path(_REPO) / "research" / "tr128" / "results"
    tr128_run = find_latest_run(tr128_results)

    if tr128_run is None:
        return {
            "status": "no_tr128_data",
            "note": "TR128 results not found for cross-validation",
        }

    try:
        tr128_csv = tr128_run / "metrics.csv"
        tr128_df = load_metrics_csv(tr128_csv)
        tr128_p1 = tr128_df[tr128_df["phase"] == "p1_baseline"]
    except Exception as exc:
        return {"status": f"tr128_load_error: {exc}"}

    if tr128_p1.empty:
        return {"status": "tr128_no_baseline"}

    results = {}
    for model in sorted(p1["model"].unique()):
        tr129_tps = p1[p1["model"] == model]["effective_tps"].dropna().values

        # TR128 uses tokens_per_s (GPU-side: completion_tokens / eval_ms).
        # For fair comparison, compute wall-clock effective_tps from TR128 data:
        # effective_tps = completion_tokens / wall_ms * 1000
        tr128_model = tr128_p1[tr128_p1["model"] == model]
        if "effective_tps" in tr128_p1.columns:
            tr128_tps = tr128_model["effective_tps"].dropna().values
            metric_note = "effective_tps (native)"
        elif "wall_ms" in tr128_p1.columns and "completion_tokens" in tr128_p1.columns:
            # Compute wall-clock-based effective throughput
            wall_ms = tr128_model["wall_ms"].dropna().values
            comp_tok = tr128_model["completion_tokens"].dropna().values
            mask = (wall_ms > 0) & (comp_tok > 0)
            tr128_tps = (comp_tok[mask] / wall_ms[mask]) * 1000.0
            metric_note = "computed from wall_ms (fair comparison)"
        elif "tokens_per_s" in tr128_p1.columns:
            # Fallback: GPU-side metric (will be higher, note the mismatch)
            tr128_tps = tr128_model["tokens_per_s"].dropna().values
            metric_note = "tokens_per_s (GPU-side, NOT comparable)"
        else:
            results[model] = {"status": "no_tps_column_in_tr128"}
            continue

        if len(tr129_tps) == 0 or len(tr128_tps) == 0:
            results[model] = {"status": "missing_data"}
            continue

        tr129_mean = float(np.mean(tr129_tps))
        tr128_mean = float(np.mean(tr128_tps))
        diff_pct = (tr129_mean - tr128_mean) / tr128_mean * 100 if tr128_mean > 0 else 0

        # t-test
        t_stat, p_val = stats.ttest_ind(tr129_tps, tr128_tps)

        results[model] = {
            "tr129_mean_tps": round(tr129_mean, 2),
            "tr128_mean_tps": round(tr128_mean, 2),
            "difference_pct": round(diff_pct, 2),
            "within_10pct": abs(diff_pct) <= 10,
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_val), 6),
            "metric_note": metric_note,
        }

    return results


# -- 15. Cold-start detection -----------------------------------------------


def analyze_cold_start(df: pd.DataFrame) -> dict:
    """Detect cold-start effects (first few requests slower)."""
    results = {}
    n_warmup = 5

    for phase in sorted(df["phase"].unique()):
        phase_data = df[df["phase"] == phase]
        phase_results = {}

        for model in sorted(phase_data["model"].unique()):
            model_data = phase_data[phase_data["model"] == model]

            # Use request_sequence for ordering within each agent
            for aid in sorted(model_data["agent_id"].unique()):
                agent_data = model_data[model_data["agent_id"] == aid].sort_values(
                    "request_sequence"
                )
                wall = agent_data["wall_ms"].dropna().values

                if len(wall) < n_warmup + 5:
                    continue

                first = wall[:n_warmup]
                rest = wall[n_warmup:]

                _t_stat, p_val = stats.ttest_ind(first, rest)
                mean_diff = float(np.mean(first)) - float(np.mean(rest))

                key = f"{model}_agent{aid}"
                phase_results[key] = {
                    "first_n_mean_ms": round(float(np.mean(first)), 1),
                    "rest_mean_ms": round(float(np.mean(rest)), 1),
                    "diff_ms": round(mean_diff, 1),
                    "cold_start_detected": bool(p_val < 0.05 and mean_diff > 0),
                    "p_value": round(float(p_val), 6),
                }

        if phase_results:
            results[phase] = phase_results

    return results


# -- 16. Outlier analysis ---------------------------------------------------


def analyze_outliers(df: pd.DataFrame) -> dict:
    """IQR-based outlier detection on wall_ms."""
    results = {}

    for phase in sorted(df["phase"].unique()):
        phase_data = df[df["phase"] == phase]
        phase_results = {}

        for model in sorted(phase_data["model"].unique()):
            model_data = phase_data[phase_data["model"] == model]
            wall = model_data["wall_ms"].dropna().values

            if len(wall) < 10:
                continue

            q1 = float(np.percentile(wall, 25))
            q3 = float(np.percentile(wall, 75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            n_low = int(np.sum(wall < lower))
            n_high = int(np.sum(wall > upper))
            n_outliers = n_low + n_high

            phase_results[model] = {
                "n_total": len(wall),
                "n_outliers": n_outliers,
                "outlier_pct": round(n_outliers / len(wall) * 100, 2),
                "n_low": n_low,
                "n_high": n_high,
                "iqr_bounds": [round(lower, 1), round(upper, 1)],
                "q1": round(q1, 1),
                "q3": round(q3, 1),
            }

        if phase_results:
            results[phase] = phase_results

    return results


# -- 17. Power analysis -----------------------------------------------------


def analyze_power(df: pd.DataFrame) -> dict:
    """Assess whether sample sizes are sufficient to detect differences."""
    p2 = df[df["phase"] == "p2_scaling"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        n_levels = sorted(model_data["n_agents"].unique())

        if len(n_levels) < 2:
            continue

        # Compare N=1 vs max N
        n1_data = model_data[model_data["n_agents"] == n_levels[0]]
        n_max_data = model_data[model_data["n_agents"] == n_levels[-1]]
        n1_tps = n1_data["effective_tps"].dropna().values
        nmax_tps = n_max_data["effective_tps"].dropna().values

        if len(n1_tps) < 2 or len(nmax_tps) < 2:
            continue

        # Observed effect size
        pooled_std = np.sqrt(
            (
                (len(n1_tps) - 1) * np.var(n1_tps, ddof=1)
                + (len(nmax_tps) - 1) * np.var(nmax_tps, ddof=1)
            )
            / (len(n1_tps) + len(nmax_tps) - 2)
        )
        d = (
            abs(float(np.mean(n1_tps)) - float(np.mean(nmax_tps))) / pooled_std
            if pooled_std > 0
            else 0
        )

        # Required n for 80% power at observed effect size
        from scipy.stats import norm

        z_alpha = norm.ppf(0.975)
        z_beta = norm.ppf(0.80)
        n_required = int(np.ceil(2 * ((z_alpha + z_beta) / d) ** 2)) if d > 0 else 999

        results[model] = {
            "observed_effect_size_d": round(d, 4),
            "effect_label": effect_label(d),
            "n_per_group_actual": min(len(n1_tps), len(nmax_tps)),
            "n_per_group_required_80pct": n_required,
            "adequately_powered": min(len(n1_tps), len(nmax_tps)) >= n_required,
            "comparison": f"N={n_levels[0]} vs N={n_levels[-1]}",
        }

    return results


# -- 18. Distribution shape -------------------------------------------------


def analyze_distribution(df: pd.DataFrame) -> dict:
    """Distribution shape analysis (normality, skew, modality)."""
    results = {}

    for phase in sorted(df["phase"].unique()):
        phase_data = df[df["phase"] == phase]
        phase_results = {}

        for model in sorted(phase_data["model"].unique()):
            model_data = phase_data[phase_data["model"] == model]
            tps = model_data["effective_tps"].dropna().values

            if len(tps) < 8:
                continue

            entry = {
                "n": len(tps),
                "mean": round(float(np.mean(tps)), 2),
                "std": round(float(np.std(tps, ddof=1)), 2),
                "skewness": round(float(stats.skew(tps)), 3),
                "kurtosis": round(float(stats.kurtosis(tps)), 3),
            }

            if 3 <= len(tps) <= 5000:
                sw_stat, sw_p = stats.shapiro(tps)
                entry["shapiro_w"] = round(float(sw_stat), 4)
                entry["shapiro_p"] = round(float(sw_p), 4)
                entry["is_normal"] = bool(sw_p > 0.05)

            phase_results[model] = entry

        if phase_results:
            results[phase] = phase_results

    return results


# -- 19. Request timeline analysis ------------------------------------------


def analyze_request_timeline(df: pd.DataFrame) -> dict:
    """Characterize serialization patterns using submit_time_s / complete_time_s.

    For each model and N-level in Phase 2, computes:
    - Mean overlap ratio: fraction of time multiple agents had active requests
    - Serialization degree: fraction of time only 1 request was active
    - Timeline span: total wall time from first submit to last complete
    - Request gap analysis: time between one request completing and another starting
    """
    p2 = df[df["phase"] == "p2_scaling"]
    if p2.empty:
        return {"status": "no_data"}

    # Check that timeline columns exist and have data
    if "submit_time_s" not in p2.columns or "complete_time_s" not in p2.columns:
        return {"status": "no_timeline_columns"}

    results = {}
    for model in sorted(p2["model"].unique()):
        model_data = p2[p2["model"] == model]
        model_results = {}

        for n_agents in sorted(model_data["n_agents"].unique()):
            n_data = model_data[model_data["n_agents"] == n_agents]
            submits = n_data["submit_time_s"].dropna().values
            completes = n_data["complete_time_s"].dropna().values

            if len(submits) < 2 or len(completes) < 2:
                continue

            # Pair up submit/complete times per request
            paired = n_data[["submit_time_s", "complete_time_s"]].dropna()
            if len(paired) < 2:
                continue

            submit_arr = paired["submit_time_s"].values
            complete_arr = paired["complete_time_s"].values

            # Timeline span
            t_start = float(np.min(submit_arr))
            t_end = float(np.max(complete_arr))
            span_s = t_end - t_start

            if span_s <= 0:
                continue

            # Build a time-sampled concurrency profile at 1ms resolution
            n_bins = min(int(span_s * 1000), 100000)  # cap at 100k bins
            if n_bins < 10:
                continue

            bin_edges = np.linspace(t_start, t_end, n_bins + 1)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
            concurrency = np.zeros(n_bins, dtype=int)

            for s, c in zip(submit_arr, complete_arr, strict=False):
                mask = (bin_centers >= s) & (bin_centers <= c)
                concurrency[mask] += 1

            # Active bins (at least 1 request in flight)
            active_mask = concurrency >= 1
            n_active = int(np.sum(active_mask))

            # Overlap bins (2+ requests in flight simultaneously)
            overlap_mask = concurrency >= 2
            n_overlap = int(np.sum(overlap_mask))

            # Serial bins (exactly 1 request in flight)
            serial_mask = concurrency == 1
            n_serial = int(np.sum(serial_mask))

            # Idle bins (0 requests in flight)
            idle_mask = concurrency == 0
            n_idle = int(np.sum(idle_mask))

            overlap_ratio = n_overlap / n_active if n_active > 0 else 0.0
            serialization_degree = n_serial / n_active if n_active > 0 else 1.0
            idle_fraction = n_idle / n_bins if n_bins > 0 else 0.0

            # Mean concurrency during active periods
            mean_concurrency = (
                float(np.mean(concurrency[active_mask])) if n_active > 0 else 0.0
            )

            # Request gap analysis: sort by completion time, compute gaps
            order = np.argsort(complete_arr)
            sorted_completes = complete_arr[order]
            sorted_submits = submit_arr[order]

            # Gap = next submit - previous complete (if next submit > prev complete)
            gaps = []
            for i in range(1, len(sorted_completes)):
                gap = sorted_submits[i] - sorted_completes[i - 1]
                if gap > 0:
                    gaps.append(float(gap))

            gap_stats = {}
            if gaps:
                gap_arr = np.array(gaps)
                gap_stats = {
                    "n_gaps": len(gaps),
                    "mean_gap_s": round(float(np.mean(gap_arr)), 4),
                    "median_gap_s": round(float(np.median(gap_arr)), 4),
                    "max_gap_s": round(float(np.max(gap_arr)), 4),
                    "total_gap_s": round(float(np.sum(gap_arr)), 4),
                }
            else:
                gap_stats = {
                    "n_gaps": 0,
                    "note": "no gaps — requests always overlapping",
                }

            # Concurrency distribution
            concurrency_dist = {}
            for level in range(int(n_agents) + 1):
                count = int(np.sum(concurrency == level))
                if count > 0:
                    concurrency_dist[str(level)] = count

            model_results[str(int(n_agents))] = {
                "n_agents": int(n_agents),
                "timeline_span_s": round(span_s, 3),
                "n_requests": len(paired),
                "overlap_ratio": round(overlap_ratio, 4),
                "serialization_degree": round(serialization_degree, 4),
                "idle_fraction": round(idle_fraction, 4),
                "mean_concurrency_active": round(mean_concurrency, 3),
                "concurrency_distribution": concurrency_dist,
                "gap_analysis": gap_stats,
            }

        if model_results:
            results[model] = model_results

    return results


# -- Main -------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR129 analysis")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    run_dir = find_latest_run(TR129_RESULTS)
    if run_dir is None:
        log.error("No run directory found in %s", TR129_RESULTS)
        return 1

    csv_path = run_dir / "metrics.csv"
    if not csv_path.exists():
        log.error("No metrics.csv in %s", run_dir)
        return 1

    log.info("Analyzing %s", csv_path)
    df_all = load_metrics_csv(csv_path, filter_ok=False)
    df = load_metrics_csv(csv_path, filter_ok=True)

    log.info("Loaded %d rows (%d ok)", len(df_all), len(df))

    # Run all 19 analysis sections
    analysis = {}

    log.info("  1/19: Summary")
    analysis["summary"] = analyze_summary(df_all)

    log.info("  2/19: Baseline")
    analysis["baseline"] = analyze_baseline(df)

    log.info("  3/19: Throughput curves")
    analysis["throughput_curves"] = analyze_throughput_curves(df, analysis["baseline"])

    log.info("  4/19: Efficiency curves")
    analysis["efficiency"] = analyze_efficiency(df, analysis["baseline"])

    log.info("  5/19: Scaling characterization")
    analysis["scaling_laws"] = analyze_scaling_laws(analysis["efficiency"])

    log.info("  6/19: Saturation detection")
    analysis["saturation"] = analyze_saturation(analysis["efficiency"])

    log.info("  7/19: Fairness")
    analysis["fairness"] = analyze_fairness(df)

    log.info("  8/19: Queue dynamics")
    analysis["queue_dynamics"] = analyze_queue_dynamics(df)

    log.info("  9/19: Think-time effects")
    analysis["think_time"] = analyze_think_time(df, analysis["efficiency"])

    log.info("  10/19: Optimal think-time")
    analysis["optimal_think_time"] = analyze_optimal_think_time(analysis["think_time"])

    log.info("  11/19: Heterogeneous analysis")
    analysis["heterogeneous"] = analyze_heterogeneous(df)

    log.info("  12/19: Model switching overhead")
    analysis["model_switching"] = analyze_model_switching(df, analysis["heterogeneous"])

    log.info("  13/19: VRAM usage")
    analysis["vram"] = analyze_vram(run_dir)

    log.info("  14/19: TR128 cross-validation")
    analysis["cross_validation"] = analyze_cross_validation(df)

    log.info("  15/19: Cold-start detection")
    analysis["cold_start"] = analyze_cold_start(df)

    log.info("  16/19: Outlier analysis")
    analysis["outliers"] = analyze_outliers(df)

    log.info("  17/19: Power analysis")
    analysis["power_analysis"] = analyze_power(df)

    log.info("  18/19: Distribution shape")
    analysis["distribution"] = analyze_distribution(df)

    log.info("  19/19: Request timeline")
    analysis["request_timeline"] = analyze_request_timeline(df)

    # Write output
    out_path = run_dir / "analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)

    log.info("Analysis written to %s (%d sections)", out_path, len(analysis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
