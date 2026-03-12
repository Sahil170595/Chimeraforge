"""TR130 — Statistical analysis for Serving Stack Benchmarking.

Reads metrics.csv and GPU CSVs from the latest run.
Produces analysis.json with 18 sections:

  1. Summary
  2. Per-backend baseline (N=1 throughput)
  3. N-agent throughput curves
  4. Efficiency curves eta(N)
  5. Scaling law fitting (Amdahl, power, exponential, logistic)
  6. Cross-backend serial fraction comparison (CORE NEW)
  7. Saturation detection (N* per backend)
  8. Fairness (Jain's index per backend)
  9. TTFT comparison (Phase 4)
 10. Queue dynamics
 11. VRAM usage per backend
 12. TR129 cross-validation (Ollama serial fractions)
 13. Cold-start detection
 14. Outlier analysis
 15. Power analysis
 16. Distribution shape
 17. Request timeline
 18. Backend-native metrics (prefill/decode where available)

Statistical methods:
- 95% CI via t-distribution
- Bootstrap CIs on Amdahl serial fractions
- Shapiro-Wilk normality testing
- Cohen's d effect sizes
- Curve fitting: Amdahl, power law, exponential, logistic

Usage:
    python research/tr130/analyze.py [-v]
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

from research.tr130.shared.utils import (
    TR130_RESULTS,
    effect_label,
    find_latest_run,
    load_metrics_csv,
)

log = logging.getLogger("tr130.analyze")


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
    """Fit Amdahl, power law, exponential, and logistic models."""
    results = {}

    # Amdahl's Law
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

    # Power law
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
        }
    except Exception as exc:
        results["power_law"] = {"error": str(exc)}

    # Exponential
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
        }
    except Exception as exc:
        results["exponential"] = {"error": str(exc)}

    # Logistic
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
        }
    except Exception as exc:
        results["logistic"] = {"error": str(exc)}

    best = max(
        [(k, v.get("r_squared", -1)) for k, v in results.items() if "r_squared" in v],
        key=lambda x: x[1],
        default=("none", -1),
    )
    results["best_fit"] = best[0]
    results["best_r_squared"] = round(best[1], 4)

    return results


def _bootstrap_serial_fraction(
    n_values: np.ndarray,
    eta_values: np.ndarray,
    n_bootstrap: int = 1000,
    rng: np.random.Generator | None = None,
) -> dict:
    """Bootstrap CI for Amdahl serial fraction."""
    if rng is None:
        rng = np.random.default_rng(42)
    fractions = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, len(n_values), size=len(n_values))
        n_boot = n_values[idx]
        eta_boot = eta_values[idx]
        try:
            popt, _ = curve_fit(
                _amdahl, n_boot, eta_boot, p0=[0.1], maxfev=2000, bounds=([0], [1])
            )
            fractions.append(float(popt[0]))
        except Exception:
            pass
    if not fractions:
        return {"error": "all bootstrap fits failed"}
    arr = np.array(fractions)
    return {
        "n_successful": len(fractions),
        "mean": round(float(np.mean(arr)), 4),
        "median": round(float(np.median(arr)), 4),
        "std": round(float(np.std(arr)), 4),
        "ci95_lower": round(float(np.percentile(arr, 2.5)), 4),
        "ci95_upper": round(float(np.percentile(arr, 97.5)), 4),
        "ci99_lower": round(float(np.percentile(arr, 0.5)), 4),
        "ci99_upper": round(float(np.percentile(arr, 99.5)), 4),
    }


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
        "backends": sorted(df_all["backend"].unique().tolist()),
        "models": sorted(df_all["model"].unique().tolist()),
        "phases": sorted(df_all["phase"].unique().tolist()),
        "status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "rows_per_phase": {
            str(k): int(v) for k, v in df_all["phase"].value_counts().to_dict().items()
        },
        "rows_per_backend": {
            str(k): int(v)
            for k, v in df_all["backend"].value_counts().to_dict().items()
        },
        "rows_per_model": {
            str(k): int(v) for k, v in df_all["model"].value_counts().to_dict().items()
        },
    }


# -- 2. Per-backend baseline -----------------------------------------------


def analyze_baseline(df: pd.DataFrame) -> dict:
    """N=1 baseline per backend × model."""
    p2 = df[df["phase"] == "p2_baseline"]
    if p2.empty:
        return {"status": "no_data"}

    results = {}
    for backend in sorted(p2["backend"].unique()):
        results[backend] = {}
        for model in sorted(p2["model"].unique()):
            subset = p2[(p2["backend"] == backend) & (p2["model"] == model)]
            if subset.empty:
                results[backend][model] = {"status": "no_data"}
                continue
            wall = subset["wall_ms"].dropna().values
            tps = subset["effective_tps"].dropna().values
            entry = {"wall_ms": _full_summary(wall)}
            if len(tps) > 0:
                entry["effective_tps"] = _full_summary(tps)
                # Service rate for Amdahl context
                mean_service_s = float(np.mean(wall)) / 1000.0
                entry["mu_requests_per_s"] = (
                    round(1.0 / mean_service_s, 2) if mean_service_s > 0 else 0
                )
            if "gpu_tokens_per_s" in subset.columns:
                gpu_tps = (
                    pd.to_numeric(subset["gpu_tokens_per_s"], errors="coerce")
                    .dropna()
                    .values
                )
                if len(gpu_tps) > 0:
                    entry["gpu_tokens_per_s"] = _full_summary(gpu_tps)
            results[backend][model] = entry
    return results


# -- 3. N-agent throughput curves -------------------------------------------


def analyze_throughput_curves(df: pd.DataFrame) -> dict:
    """Per backend × model × N: mean effective_tps, total throughput."""
    p3 = df[df["phase"] == "p3_scaling"]
    if p3.empty:
        return {"status": "no_data"}

    results = {}
    for backend in sorted(p3["backend"].unique()):
        results[backend] = {}
        for model in sorted(p3["model"].unique()):
            curves = []
            subset = p3[(p3["backend"] == backend) & (p3["model"] == model)]
            for n_agents in sorted(subset["n_agents"].unique()):
                ns = subset[subset["n_agents"] == n_agents]
                tps = ns["effective_tps"].dropna().values
                if len(tps) == 0:
                    continue
                mean_tps = float(np.mean(tps))
                total_tps = mean_tps * n_agents
                curves.append(
                    {
                        "n_agents": int(n_agents),
                        "n_requests": len(tps),
                        "per_agent_tps": round(mean_tps, 2),
                        "per_agent_tps_ci95": list(_ci95(tps)),
                        "total_throughput_tps": round(total_tps, 2),
                        "wall_ms_mean": round(
                            float(np.mean(ns["wall_ms"].dropna().values)), 2
                        ),
                    }
                )
            results[backend][model] = curves
    return results


# -- 4. Efficiency curves eta(N) -------------------------------------------


def analyze_efficiency(df: pd.DataFrame, baseline: dict) -> dict:
    """eta(N) = per_agent_tps(N) / per_agent_tps(1) per backend × model."""
    p3 = df[df["phase"] == "p3_scaling"]
    if p3.empty:
        return {"status": "no_data"}

    results = {}
    for backend in sorted(p3["backend"].unique()):
        results[backend] = {}
        for model in sorted(p3["model"].unique()):
            # Get N=1 baseline TPS
            baseline_tps = None
            try:
                bl = baseline.get(backend, {}).get(model, {})
                baseline_tps = bl.get("effective_tps", {}).get("mean")
            except Exception:
                pass

            if baseline_tps is None or baseline_tps <= 0:
                # Fallback: use N=1 from p3 data
                n1 = p3[
                    (p3["backend"] == backend)
                    & (p3["model"] == model)
                    & (p3["n_agents"] == 1)
                ]
                if not n1.empty:
                    baseline_tps = float(n1["effective_tps"].mean())

            if baseline_tps is None or baseline_tps <= 0:
                results[backend][model] = {"status": "no_baseline"}
                continue

            subset = p3[(p3["backend"] == backend) & (p3["model"] == model)]
            eta_points = []
            for n_agents in sorted(subset["n_agents"].unique()):
                ns = subset[subset["n_agents"] == n_agents]
                tps = ns["effective_tps"].dropna().values
                if len(tps) == 0:
                    continue
                mean_tps = float(np.mean(tps))
                eta = mean_tps / baseline_tps
                eta_points.append(
                    {
                        "n_agents": int(n_agents),
                        "eta": round(eta, 4),
                        "per_agent_tps": round(mean_tps, 2),
                        "baseline_tps": round(baseline_tps, 2),
                    }
                )
            results[backend][model] = {
                "baseline_tps": round(baseline_tps, 2),
                "points": eta_points,
            }
    return results


# -- 5. Scaling law fitting ------------------------------------------------


def analyze_scaling_laws(efficiency: dict) -> dict:
    """Fit Amdahl + alternatives per backend × model."""
    results = {}
    for backend, models in efficiency.items():
        results[backend] = {}
        for model, data in models.items():
            if isinstance(data, dict) and "points" in data:
                pts = data["points"]
                if len(pts) < 3:
                    results[backend][model] = {"status": "insufficient_points"}
                    continue
                n_vals = np.array([p["n_agents"] for p in pts], dtype=float)
                eta_vals = np.array([p["eta"] for p in pts], dtype=float)
                results[backend][model] = _fit_scaling_law(n_vals, eta_vals)
            else:
                results[backend][model] = {"status": "no_data"}
    return results


# -- 6. Cross-backend serial fraction comparison (CORE NEW) ----------------


def analyze_cross_backend_serial_fraction(
    df: pd.DataFrame,
    efficiency: dict,
) -> dict:
    """Bootstrap CIs on Amdahl serial fractions, rank backends."""
    p3 = df[df["phase"] == "p3_scaling"]
    if p3.empty:
        return {"status": "no_data"}

    results = {"per_model": {}, "aggregate": {}}
    rng = np.random.default_rng(42)

    # Per-model comparison
    for model in sorted(p3["model"].unique()):
        model_results = {}
        for backend in sorted(p3["backend"].unique()):
            data = efficiency.get(backend, {}).get(model, {})
            if not isinstance(data, dict) or "points" not in data:
                model_results[backend] = {"status": "no_data"}
                continue
            pts = data["points"]
            if len(pts) < 3:
                model_results[backend] = {"status": "insufficient_points"}
                continue
            n_vals = np.array([p["n_agents"] for p in pts], dtype=float)
            eta_vals = np.array([p["eta"] for p in pts], dtype=float)
            bootstrap = _bootstrap_serial_fraction(n_vals, eta_vals, rng=rng)
            model_results[backend] = bootstrap
        results["per_model"][model] = model_results

    # Pairwise comparisons
    backends = sorted(p3["backend"].unique())
    comparisons = []
    for model in sorted(p3["model"].unique()):
        for i in range(len(backends)):
            for j in range(i + 1, len(backends)):
                b1, b2 = backends[i], backends[j]
                s1 = results["per_model"].get(model, {}).get(b1, {})
                s2 = results["per_model"].get(model, {}).get(b2, {})
                if "mean" not in s1 or "mean" not in s2:
                    continue
                diff = s1["mean"] - s2["mean"]
                # Approximate Cohen's d
                pooled_std = np.sqrt(
                    (s1.get("std", 0) ** 2 + s2.get("std", 0) ** 2) / 2
                )
                d = diff / pooled_std if pooled_std > 0 else 0
                # CIs overlap?
                overlap = s1.get("ci95_lower", 0) <= s2.get("ci95_upper", 0) and s2.get(
                    "ci95_lower", 0
                ) <= s1.get("ci95_upper", 0)
                comparisons.append(
                    {
                        "model": model,
                        "backend_a": b1,
                        "backend_b": b2,
                        "s_a": s1["mean"],
                        "s_b": s2["mean"],
                        "difference": round(diff, 4),
                        "cohens_d": round(d, 3),
                        "effect_size": effect_label(d),
                        "cis_overlap": overlap,
                    }
                )
    results["pairwise_comparisons"] = comparisons

    # Aggregate ranking
    backend_means = {}
    for backend in backends:
        fracs = []
        for model in results["per_model"]:
            entry = results["per_model"][model].get(backend, {})
            if "mean" in entry:
                fracs.append(entry["mean"])
        if fracs:
            backend_means[backend] = {
                "mean_serial_fraction": round(float(np.mean(fracs)), 4),
                "min_serial_fraction": round(float(np.min(fracs)), 4),
                "max_serial_fraction": round(float(np.max(fracs)), 4),
                "n_models": len(fracs),
            }
    results["aggregate"] = backend_means

    # Rank (lower serial fraction = better)
    ranked = sorted(backend_means.items(), key=lambda x: x[1]["mean_serial_fraction"])
    results["ranking"] = [
        {"rank": i + 1, "backend": b, **v} for i, (b, v) in enumerate(ranked)
    ]

    # Core question answer
    if len(ranked) >= 2:
        best = ranked[0]
        worst = ranked[-1]
        diff = worst[1]["mean_serial_fraction"] - best[1]["mean_serial_fraction"]
        results["core_finding"] = {
            "best_backend": best[0],
            "worst_backend": worst[0],
            "serial_fraction_gap": round(diff, 4),
            "is_serving_stack_bottleneck": diff > 0.05,
            "interpretation": (
                f"{worst[0]} has serial fraction {diff:.3f} higher than {best[0]}. "
                f"{'The serving stack IS the bottleneck.' if diff > 0.05 else 'The difference is small — GPU physics dominates.'}"
            ),
        }

    return results


# -- 7. Saturation detection -----------------------------------------------


def analyze_saturation(efficiency: dict) -> dict:
    """N* = point where eta < 0.5 per backend × model."""
    results = {}
    for backend, models in efficiency.items():
        results[backend] = {}
        for model, data in models.items():
            if not isinstance(data, dict) or "points" not in data:
                continue
            pts = data["points"]
            n_star = None
            for p in pts:
                if p["eta"] < 0.5:
                    n_star = p["n_agents"]
                    break
            results[backend][model] = {
                "n_star": n_star,
                "eta_at_max_n": pts[-1]["eta"] if pts else None,
                "max_n_tested": pts[-1]["n_agents"] if pts else None,
            }
    return results


# -- 8. Fairness (Jain's index) -------------------------------------------


def analyze_fairness(df: pd.DataFrame) -> dict:
    """Jain's fairness index per backend × model × N."""
    p3 = df[df["phase"] == "p3_scaling"]
    if p3.empty:
        return {"status": "no_data"}

    results = {}
    for backend in sorted(p3["backend"].unique()):
        results[backend] = {}
        for model in sorted(p3["model"].unique()):
            fairness_points = []
            subset = p3[(p3["backend"] == backend) & (p3["model"] == model)]
            for n_agents in sorted(subset["n_agents"].unique()):
                if n_agents < 2:
                    continue
                ns = subset[subset["n_agents"] == n_agents]
                # Per-agent mean TPS
                agent_means = []
                for aid in ns["agent_id"].unique():
                    agent_tps = (
                        ns[ns["agent_id"] == aid]["effective_tps"].dropna().values
                    )
                    if len(agent_tps) > 0:
                        agent_means.append(float(np.mean(agent_tps)))
                if len(agent_means) < 2:
                    continue
                jfi = _jains_index(np.array(agent_means))
                fairness_points.append(
                    {
                        "n_agents": int(n_agents),
                        "jains_index": jfi,
                        "agent_tps_means": [round(x, 2) for x in agent_means],
                        "agent_tps_cv_pct": (
                            round(
                                float(np.std(agent_means) / np.mean(agent_means) * 100),
                                1,
                            )
                            if np.mean(agent_means) > 0
                            else 0
                        ),
                    }
                )
            results[backend][model] = fairness_points
    return results


# -- 9. TTFT comparison ---------------------------------------------------


def analyze_ttft(df: pd.DataFrame) -> dict:
    """Time-to-first-token per backend × model."""
    p4 = df[df["phase"] == "p4_ttft"]
    if p4.empty:
        return {"status": "no_data"}

    if "ttft_ms" not in p4.columns:
        return {"status": "no_ttft_column"}

    results = {}
    for backend in sorted(p4["backend"].unique()):
        results[backend] = {}
        for model in sorted(p4["model"].unique()):
            subset = p4[(p4["backend"] == backend) & (p4["model"] == model)]
            ttft = pd.to_numeric(subset["ttft_ms"], errors="coerce").dropna().values
            if len(ttft) == 0:
                results[backend][model] = {"status": "no_data"}
                continue
            results[backend][model] = _full_summary(ttft)

    # Cross-backend TTFT comparisons
    comparisons = []
    backends = sorted(p4["backend"].unique())
    for model in sorted(p4["model"].unique()):
        for i in range(len(backends)):
            for j in range(i + 1, len(backends)):
                b1, b2 = backends[i], backends[j]
                d1 = results.get(b1, {}).get(model, {})
                d2 = results.get(b2, {}).get(model, {})
                if "mean" not in d1 or "mean" not in d2:
                    continue
                diff = d1["mean"] - d2["mean"]
                pooled_std = np.sqrt(
                    (d1.get("std", 0) ** 2 + d2.get("std", 0) ** 2) / 2
                )
                d = diff / pooled_std if pooled_std > 0 else 0
                comparisons.append(
                    {
                        "model": model,
                        "backend_a": b1,
                        "backend_b": b2,
                        "ttft_a_ms": d1["mean"],
                        "ttft_b_ms": d2["mean"],
                        "difference_ms": round(diff, 2),
                        "cohens_d": round(d, 3),
                        "effect_size": effect_label(d),
                    }
                )
    results["comparisons"] = comparisons
    return results


# -- 10. Queue dynamics ---------------------------------------------------


def analyze_queue_dynamics(df: pd.DataFrame) -> dict:
    """In-flight depth at submit time per backend × model × N."""
    p3 = df[df["phase"] == "p3_scaling"]
    if p3.empty:
        return {"status": "no_data"}

    results = {}
    for backend in sorted(p3["backend"].unique()):
        results[backend] = {}
        for model in sorted(p3["model"].unique()):
            points = []
            subset = p3[(p3["backend"] == backend) & (p3["model"] == model)]
            for n_agents in sorted(subset["n_agents"].unique()):
                ns = subset[subset["n_agents"] == n_agents]
                depths = ns["in_flight_at_submit"].dropna().values
                if len(depths) == 0:
                    continue
                points.append(
                    {
                        "n_agents": int(n_agents),
                        "mean_depth": round(float(np.mean(depths)), 2),
                        "max_depth": int(np.max(depths)),
                        "pct_at_max": round(
                            float((depths >= n_agents - 1).sum() / len(depths) * 100), 1
                        ),
                    }
                )
            results[backend][model] = points
    return results


# -- 11. VRAM usage -------------------------------------------------------


def analyze_vram(run_dir: Path) -> dict:
    """GPU memory from GPU monitor CSVs per phase."""
    results = {}
    for phase_num in range(1, 5):
        gpu_path = run_dir / f"gpu_phase{phase_num}.csv"
        gpu_df = _load_gpu_csv(gpu_path)
        if gpu_df is None:
            continue
        mem = (
            gpu_df["mem_used_mb"].dropna().values
            if "mem_used_mb" in gpu_df.columns
            else np.array([])
        )
        if len(mem) > 0:
            results[f"phase{phase_num}"] = {
                "mem_used_mb": _full_summary(mem),
                "n_samples": len(mem),
            }
    return results


# -- 12. TR129 cross-validation -------------------------------------------


def analyze_tr129_crossval(scaling_laws: dict) -> dict:
    """Compare Ollama serial fractions with TR129."""
    # Load TR129 analysis if available
    tr129_dir = _DIR.parent / "tr129" / "results"
    tr129_run = find_latest_run(tr129_dir) if tr129_dir.exists() else None
    if tr129_run is None:
        return {"status": "tr129_results_not_found"}

    tr129_json = tr129_run / "analysis.json"
    if not tr129_json.exists():
        return {"status": "tr129_analysis_not_found"}

    try:
        with open(tr129_json) as f:
            tr129 = json.load(f)
    except Exception as exc:
        return {"status": f"tr129_load_error: {exc}"}

    tr129_scaling = tr129.get("scaling_characterization", {})
    ollama_scaling = scaling_laws.get("ollama", {})

    comparisons = []
    for model in ollama_scaling:
        tr130_entry = ollama_scaling[model]
        tr130_s = tr130_entry.get("amdahl", {}).get("serial_fraction")

        # TR129 stores per-model, find matching entry
        tr129_entry = tr129_scaling.get(model, {})
        tr129_s = tr129_entry.get("amdahl", {}).get("serial_fraction")

        if tr130_s is not None and tr129_s is not None:
            diff = abs(tr130_s - tr129_s)
            comparisons.append(
                {
                    "model": model,
                    "tr130_s": round(tr130_s, 4),
                    "tr129_s": round(tr129_s, 4),
                    "absolute_difference": round(diff, 4),
                    "within_5pct": diff < 0.05,
                    "within_10pct": diff < 0.10,
                }
            )

    return {
        "comparisons": comparisons,
        "all_within_5pct": (
            all(c["within_5pct"] for c in comparisons) if comparisons else None
        ),
    }


# -- 13. Cold-start detection ---------------------------------------------


def analyze_cold_start(df: pd.DataFrame) -> dict:
    """Detect cold-start outliers in first few requests per backend × model."""
    results = {}
    for phase in ["p2_baseline", "p3_scaling"]:
        phase_df = df[df["phase"] == phase]
        if phase_df.empty:
            continue
        for backend in sorted(phase_df["backend"].unique()):
            key = f"{phase}_{backend}"
            results[key] = {}
            for model in sorted(phase_df["model"].unique()):
                subset = phase_df[
                    (phase_df["backend"] == backend) & (phase_df["model"] == model)
                ].sort_values("request_sequence")
                if len(subset) < 5:
                    continue
                first_3 = subset.head(3)["wall_ms"].values
                rest = subset.iloc[3:]["wall_ms"].values
                if len(rest) < 3:
                    continue
                mean_first = float(np.mean(first_3))
                mean_rest = float(np.mean(rest))
                ratio = mean_first / mean_rest if mean_rest > 0 else 0
                results[key][model] = {
                    "first_3_mean_ms": round(mean_first, 2),
                    "rest_mean_ms": round(mean_rest, 2),
                    "ratio": round(ratio, 2),
                    "cold_start_detected": ratio > 1.5,
                }
    return results


# -- 14. Outlier analysis -------------------------------------------------


def analyze_outliers(df: pd.DataFrame) -> dict:
    """IQR-based outlier detection per backend × model."""
    results = {}
    for backend in sorted(df["backend"].unique()):
        results[backend] = {}
        for model in sorted(df["model"].unique()):
            subset = df[(df["backend"] == backend) & (df["model"] == model)]
            wall = subset["wall_ms"].dropna().values
            if len(wall) < 10:
                continue
            q1, q3 = np.percentile(wall, [25, 75])
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = wall[(wall < lower) | (wall > upper)]
            results[backend][model] = {
                "n_total": len(wall),
                "n_outliers": len(outliers),
                "outlier_pct": round(len(outliers) / len(wall) * 100, 1),
                "iqr": round(float(iqr), 2),
                "lower_fence": round(float(lower), 2),
                "upper_fence": round(float(upper), 2),
            }
    return results


# -- 15. Power analysis ---------------------------------------------------


def analyze_power(df: pd.DataFrame) -> dict:
    """Sample size adequacy analysis."""
    results = {}
    for backend in sorted(df["backend"].unique()):
        results[backend] = {}
        for model in sorted(df["model"].unique()):
            subset = df[(df["backend"] == backend) & (df["model"] == model)]
            tps = subset["effective_tps"].dropna().values
            if len(tps) < 5:
                continue
            mean = float(np.mean(tps))
            std = float(np.std(tps, ddof=1))
            cv = std / mean if mean > 0 else 0
            # Minimum detectable effect at 80% power
            # n > (z_alpha + z_beta)^2 * sigma^2 / delta^2
            z = 1.96 + 0.84  # alpha=0.05, beta=0.20
            delta_5pct = mean * 0.05
            n_needed = (
                (z**2 * std**2 / delta_5pct**2) if delta_5pct > 0 else float("inf")
            )
            results[backend][model] = {
                "n_samples": len(tps),
                "mean_tps": round(mean, 2),
                "std_tps": round(std, 2),
                "cv": round(cv, 3),
                "n_needed_for_5pct_effect": int(np.ceil(n_needed)),
                "adequately_powered": len(tps) >= n_needed,
            }
    return results


# -- 16. Distribution shape -----------------------------------------------


def analyze_distributions(df: pd.DataFrame) -> dict:
    """Distribution shape metrics per backend × model."""
    results = {}
    for backend in sorted(df["backend"].unique()):
        results[backend] = {}
        for model in sorted(df["model"].unique()):
            subset = df[(df["backend"] == backend) & (df["model"] == model)]
            wall = subset["wall_ms"].dropna().values
            if len(wall) < 10:
                continue
            results[backend][model] = {
                "wall_ms": _full_summary(wall),
                "trimmed_mean_5pct": round(_trimmed_mean(wall, 0.05), 2),
                "trimmed_mean_10pct": round(_trimmed_mean(wall, 0.10), 2),
            }
    return results


# -- 17. Request timeline -------------------------------------------------


def analyze_timeline(df: pd.DataFrame) -> dict:
    """Request start/end timeline per backend × model at highest N."""
    p3 = df[df["phase"] == "p3_scaling"]
    if p3.empty:
        return {"status": "no_data"}

    results = {}
    for backend in sorted(p3["backend"].unique()):
        results[backend] = {}
        for model in sorted(p3["model"].unique()):
            subset = p3[(p3["backend"] == backend) & (p3["model"] == model)]
            if subset.empty:
                continue
            max_n = subset["n_agents"].max()
            ns = subset[subset["n_agents"] == max_n]
            if "submit_time_s" in ns.columns and "complete_time_s" in ns.columns:
                results[backend][model] = {
                    "n_agents": int(max_n),
                    "n_requests": len(ns),
                    "total_duration_s": round(
                        float(ns["complete_time_s"].max() - ns["submit_time_s"].min()),
                        2,
                    ),
                    "mean_gap_between_submits_ms": round(
                        float(ns["submit_time_s"].diff().dropna().mean() * 1000), 2
                    ),
                }
    return results


# -- 18. Backend-native metrics -------------------------------------------


def analyze_backend_native(df: pd.DataFrame) -> dict:
    """Compare prefill/decode breakdown where available."""
    results = {}
    for backend in sorted(df["backend"].unique()):
        backend_df = df[df["backend"] == backend]

        # Check if this backend has timing breakdown
        has_prefill = (
            "prefill_ms" in backend_df.columns
            and pd.to_numeric(backend_df["prefill_ms"], errors="coerce").dropna().any()
        )
        has_decode = (
            "decode_ms" in backend_df.columns
            and pd.to_numeric(backend_df["decode_ms"], errors="coerce").dropna().any()
        )

        results[backend] = {
            "has_prefill_ms": bool(has_prefill),
            "has_decode_ms": bool(has_decode),
        }

        if has_prefill or has_decode:
            for model in sorted(backend_df["model"].unique()):
                subset = backend_df[backend_df["model"] == model]
                model_entry = {}
                if has_prefill:
                    vals = (
                        pd.to_numeric(subset["prefill_ms"], errors="coerce")
                        .dropna()
                        .values
                    )
                    if len(vals) > 0:
                        model_entry["prefill_ms"] = _full_summary(vals)
                if has_decode:
                    vals = (
                        pd.to_numeric(subset["decode_ms"], errors="coerce")
                        .dropna()
                        .values
                    )
                    if len(vals) > 0:
                        model_entry["decode_ms"] = _full_summary(vals)
                if model_entry:
                    results[backend][model] = model_entry
    return results


# -- Main ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR130 analysis")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    run_dir = find_latest_run(TR130_RESULTS)
    if run_dir is None:
        log.error("No run directory found in %s", TR130_RESULTS)
        return 1

    csv_path = run_dir / "metrics.csv"
    if not csv_path.exists():
        log.error("No metrics.csv found in %s", run_dir)
        return 1

    log.info("Analyzing %s", csv_path)
    df_all = load_metrics_csv(csv_path, filter_ok=False)
    df = load_metrics_csv(csv_path, filter_ok=True)
    log.info("Loaded %d total rows, %d ok rows", len(df_all), len(df))

    # Run all 18 sections
    log.info("Section 1/18: Summary")
    s01 = analyze_summary(df_all)

    log.info("Section 2/18: Baseline")
    s02 = analyze_baseline(df)

    log.info("Section 3/18: Throughput curves")
    s03 = analyze_throughput_curves(df)

    log.info("Section 4/18: Efficiency")
    s04 = analyze_efficiency(df, s02)

    log.info("Section 5/18: Scaling laws")
    s05 = analyze_scaling_laws(s04)

    log.info("Section 6/18: Cross-backend serial fraction (CORE)")
    s06 = analyze_cross_backend_serial_fraction(df, s04)

    log.info("Section 7/18: Saturation")
    s07 = analyze_saturation(s04)

    log.info("Section 8/18: Fairness")
    s08 = analyze_fairness(df)

    log.info("Section 9/18: TTFT")
    s09 = analyze_ttft(df)

    log.info("Section 10/18: Queue dynamics")
    s10 = analyze_queue_dynamics(df)

    log.info("Section 11/18: VRAM")
    s11 = analyze_vram(run_dir)

    log.info("Section 12/18: TR129 cross-validation")
    s12 = analyze_tr129_crossval(s05)

    log.info("Section 13/18: Cold-start")
    s13 = analyze_cold_start(df)

    log.info("Section 14/18: Outliers")
    s14 = analyze_outliers(df)

    log.info("Section 15/18: Power analysis")
    s15 = analyze_power(df)

    log.info("Section 16/18: Distribution shape")
    s16 = analyze_distributions(df)

    log.info("Section 17/18: Timeline")
    s17 = analyze_timeline(df)

    log.info("Section 18/18: Backend-native metrics")
    s18 = analyze_backend_native(df)

    analysis = {
        "summary": s01,
        "baseline": s02,
        "throughput_curves": s03,
        "efficiency": s04,
        "scaling_laws": s05,
        "cross_backend_serial_fraction": s06,
        "saturation": s07,
        "fairness": s08,
        "ttft": s09,
        "queue_dynamics": s10,
        "vram": s11,
        "tr129_crossval": s12,
        "cold_start": s13,
        "outliers": s14,
        "power_analysis": s15,
        "distributions": s16,
        "timeline": s17,
        "backend_native_metrics": s18,
    }

    out_path = run_dir / "analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)

    log.info("Analysis saved to %s", out_path)
    log.info(
        "  %d backends, %d models, %d total ok rows",
        len(s01.get("backends", [])),
        len(s01.get("models", [])),
        s01.get("ok_rows", 0),
    )

    # Log core finding
    core = s06.get("core_finding", {})
    if core:
        log.info("  CORE FINDING: %s", core.get("interpretation", "N/A"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
