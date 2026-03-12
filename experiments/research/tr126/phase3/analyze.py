#!/usr/bin/env python3
"""TR126 Phase 3: Backend matrix analysis with cross-platform comparison.

Reads Phase 3 metrics.csv files (Linux). Optionally loads TR117 Windows
results for backend ranking comparison.

Analyses performed (8 total):
  1. Backend rankings — per-backend summary sorted by mean latency
  2. Per-model × backend breakdown — latency stats grouped by model
  3. Per-scenario × backend breakdown — latency stats grouped by scenario
  4. Compile effect — gpu vs gpu-compile with t-test, Cohen's d
  5. Pairwise comparisons — all backend pairs with t-test + effect size
  6. Outlier detection — IQR method, per backend
  7. Power analysis — minimum detectable effect size at current N
  8. Cross-phase validation — confirms Phase 1 environment gate passed

Usage:
    python research/tr126/phase3/analyze.py [--results-dir DIR] [-v]
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))

from research.shared.statistical_analysis import (
    compare_groups,
    detect_outliers,
)
from research.tr126.shared.utils import TR126_RESULTS, find_latest_run

logger = logging.getLogger("tr126.phase3.analyze")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dir(path: Path) -> None:
    """Create directory and parents if needed."""
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    """Write JSON with consistent formatting and UTF-8 encoding."""
    _ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _summary(values: np.ndarray) -> dict[str, float]:
    """Compute per-group latency summary: mean, median, std, CI, percentiles.

    Returns a flat dict suitable for JSON serialization. Computes 95% CI
    using t-distribution when n > 1.
    """
    if values.size == 0:
        return {
            "n": 0,
            "mean_ms": float("nan"),
            "median_ms": float("nan"),
            "std_ms": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
        }
    n = int(values.size)
    mean = float(values.mean())
    std = float(values.std(ddof=1)) if n > 1 else 0.0
    if n > 1:
        ci = stats.t.interval(0.95, n - 1, loc=mean, scale=stats.sem(values))
        ci_lower, ci_upper = float(ci[0]), float(ci[1])
    else:
        ci_lower, ci_upper = mean, mean
    return {
        "n": n,
        "mean_ms": mean,
        "median_ms": float(np.median(values)),
        "std_ms": std,
        "min_ms": float(values.min()),
        "max_ms": float(values.max()),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "p95_ms": float(np.percentile(values, 95)),
        "p99_ms": float(np.percentile(values, 99)),
    }


# ---------------------------------------------------------------------------
# Analysis 1: Backend rankings
# ---------------------------------------------------------------------------


def compute_backend_rankings(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute per-backend latency rankings sorted by mean latency (lower = better).

    Each entry includes full summary statistics plus rank position.
    """
    rankings: list[dict[str, Any]] = []
    for backend, grp in df.groupby("backend"):
        vals = grp["latency_ms"].dropna().values
        s = _summary(vals)
        s["backend"] = str(backend)
        rankings.append(s)
        logger.debug(
            "  %s: n=%d, mean=%.3f ms",
            backend,
            vals.size,
            vals.mean() if vals.size > 0 else float("nan"),
        )

    rankings.sort(key=lambda r: r.get("mean_ms", float("inf")))
    for i, r in enumerate(rankings):
        r["rank_by_mean"] = i + 1

    if rankings:
        logger.info(
            "  Winner: %s (%.3f ms)", rankings[0]["backend"], rankings[0]["mean_ms"]
        )
    return rankings


# ---------------------------------------------------------------------------
# Analysis 2: Per-model × backend breakdown
# ---------------------------------------------------------------------------


def compute_model_breakdown(df: pd.DataFrame) -> dict[str, Any]:
    """Compute per-model × per-backend latency statistics.

    Returns dict keyed by 'model/backend'. This reveals whether backend
    rankings are consistent across model sizes or if rankings flip for
    different models.
    """
    breakdown: dict[str, Any] = {}
    if "model" not in df.columns:
        return breakdown
    for (model, backend), grp in df.groupby(["model", "backend"]):
        vals = grp["latency_ms"].dropna().values
        breakdown[f"{model}/{backend}"] = _summary(vals)
    logger.info("  Model breakdown: %d entries", len(breakdown))
    return breakdown


# ---------------------------------------------------------------------------
# Analysis 3: Per-scenario × backend breakdown
# ---------------------------------------------------------------------------


def compute_scenario_breakdown(df: pd.DataFrame) -> dict[str, Any]:
    """Compute per-scenario × per-backend latency statistics.

    Returns dict keyed by 'scenario/backend'. Shows whether certain
    scenarios (e.g., long prompts) change backend rankings.
    """
    breakdown: dict[str, Any] = {}
    if "scenario" not in df.columns:
        return breakdown
    for (scenario, backend), grp in df.groupby(["scenario", "backend"]):
        vals = grp["latency_ms"].dropna().values
        breakdown[f"{scenario}/{backend}"] = _summary(vals)
    return breakdown


# ---------------------------------------------------------------------------
# Analysis 4: Compile effect
# ---------------------------------------------------------------------------


def compute_compile_effect(df: pd.DataFrame) -> dict[str, Any] | None:
    """Compare transformers-gpu (eager) vs transformers-gpu-compile.

    Uses research.shared.statistical_analysis.compare_groups for
    consistent t-test, Cohen's d, and significance testing.
    Returns None if insufficient data for comparison.
    """
    gpu = df[df["backend"] == "transformers-gpu"]["latency_ms"].dropna()
    gpu_compile = df[df["backend"] == "transformers-gpu-compile"]["latency_ms"].dropna()
    if gpu.size < 2 or gpu_compile.size < 2:
        logger.info(
            "  Compile effect: skipped (n_eager=%d, n_compile=%d)",
            gpu.size,
            gpu_compile.size,
        )
        return None

    comp = compare_groups(
        gpu.tolist(),
        gpu_compile.tolist(),
        "gpu-eager",
        "gpu-compile",
        "latency_ms",
    )
    result = {
        "gpu_mean": comp.mean_a,
        "gpu_compile_mean": comp.mean_b,
        "delta_ms": comp.difference,
        "delta_pct": comp.percent_change,
        "compile_helps": comp.mean_b < comp.mean_a,
        "t_statistic": comp.t_statistic,
        "p_value": comp.p_value,
        "significant": comp.significant,
        "cohens_d": comp.effect_size,
        "n_eager": int(gpu.size),
        "n_compile": int(gpu_compile.size),
    }
    helps = "YES" if comp.mean_b < comp.mean_a else "NO"
    logger.info(
        "  Compile helps: %s (%+.1f%%, p=%.4f, d=%.3f)",
        helps,
        comp.percent_change,
        comp.p_value,
        comp.effect_size,
    )
    return result


# ---------------------------------------------------------------------------
# Analysis 5: Pairwise backend comparisons
# ---------------------------------------------------------------------------


def compute_pairwise_comparisons(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute all-pairs t-test + Cohen's d for backends.

    Returns a list of comparison dicts. Each pair tested once. Uses shared
    statistical_analysis.compare_groups for consistency.
    """
    backends = sorted(df["backend"].unique())
    pairwise: list[dict[str, Any]] = []
    for i, ba in enumerate(backends):
        for bb in backends[i + 1 :]:
            va = df[df["backend"] == ba]["latency_ms"].dropna().tolist()
            vb = df[df["backend"] == bb]["latency_ms"].dropna().tolist()
            if len(va) < 2 or len(vb) < 2:
                continue
            comp = compare_groups(va, vb, ba, bb, "latency_ms")
            pairwise.append(
                {
                    "group_a": comp.group_a,
                    "group_b": comp.group_b,
                    "mean_a": comp.mean_a,
                    "mean_b": comp.mean_b,
                    "difference": comp.difference,
                    "percent_change": comp.percent_change,
                    "t_statistic": comp.t_statistic,
                    "p_value": comp.p_value,
                    "significant": comp.significant,
                    "cohens_d": comp.effect_size,
                }
            )
    n_sig = sum(1 for p in pairwise if p["significant"])
    logger.info("  Pairwise: %d comparisons, %d significant", len(pairwise), n_sig)
    return pairwise


# ---------------------------------------------------------------------------
# Analysis 6: Outlier detection
# ---------------------------------------------------------------------------


def compute_outlier_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Run IQR outlier detection per backend.

    Returns dict keyed by backend with outlier counts and percentages.
    """
    results: dict[str, Any] = {}
    total_outliers = 0
    for backend, grp in df.groupby("backend"):
        vals = grp["latency_ms"].dropna().tolist()
        od = detect_outliers(vals, method="iqr")
        results[str(backend)] = {
            "n_total": len(vals),
            "n_outliers": od["count"],
            "outlier_pct": round(100.0 * od["count"] / len(vals), 1) if vals else 0.0,
        }
        total_outliers += od["count"]
    logger.info("  Outliers: %d total across %d backends", total_outliers, len(results))
    return results


# ---------------------------------------------------------------------------
# Analysis 7: Power analysis
# ---------------------------------------------------------------------------


def compute_power_analysis(
    df: pd.DataFrame,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    """Compute minimum detectable effect size (Cohen's d) at current N.

    Uses approximation: d = (z_alpha + z_beta) * sqrt(2/n).
    Also converts to practical ms delta using pooled std.
    """
    group_sizes = [grp["latency_ms"].dropna().size for _, grp in df.groupby("backend")]
    if not group_sizes:
        return {
            "n_per_group": 0,
            "min_detectable_d": float("nan"),
            "interpretation": "no data",
        }

    min_n = min(group_sizes)
    if min_n < 2:
        return {
            "n_per_group": min_n,
            "min_detectable_d": float("nan"),
            "interpretation": "insufficient samples",
        }

    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    min_d = (z_alpha + z_beta) * math.sqrt(2.0 / min_n)

    all_vals = df["latency_ms"].dropna().values
    pooled_std = float(all_vals.std(ddof=1)) if all_vals.size > 1 else 0.0
    min_detectable_ms = min_d * pooled_std

    if min_d < 0.2:
        interp = "can detect small effects"
    elif min_d < 0.5:
        interp = "can detect small-to-medium effects"
    elif min_d < 0.8:
        interp = "can detect medium effects"
    else:
        interp = "can only detect large effects — consider more samples"

    result = {
        "n_per_group": min_n,
        "n_backends": len(group_sizes),
        "alpha": alpha,
        "power": power,
        "min_detectable_d": round(min_d, 3),
        "min_detectable_ms": round(min_detectable_ms, 3),
        "pooled_std_ms": round(pooled_std, 3),
        "interpretation": interp,
    }
    logger.info(
        "  Power: d=%.3f (%.3f ms), N=%d/group — %s",
        min_d,
        min_detectable_ms,
        min_n,
        interp,
    )
    return result


# ---------------------------------------------------------------------------
# Analysis 8: Cross-phase validation
# ---------------------------------------------------------------------------


def cross_phase_validation() -> dict[str, Any]:
    """Validate that Phase 1 environment gate passed before Phase 3 ran.

    Loads the latest Phase 1 environment.json and checks:
    - Overall pass status
    - CUDA availability
    - Triton importability
    - torch.compile inductor (no fallback)
    """
    phase1_root = TR126_RESULTS / "phase1"
    run_dir = find_latest_run(phase1_root)

    if run_dir is None:
        logger.warning("  Cross-phase: No Phase 1 results found")
        return {
            "validated": False,
            "detail": "no Phase 1 results found",
            "phase1_dir": str(phase1_root),
        }

    env_path = run_dir / "environment.json"
    if not env_path.is_file():
        logger.warning("  Cross-phase: environment.json not found in %s", run_dir)
        return {
            "validated": False,
            "detail": "environment.json missing",
            "phase1_dir": str(run_dir),
        }

    env = json.loads(env_path.read_text(encoding="utf-8"))
    checks = env.get("checks", {})
    overall_pass = env.get("pass", False)

    validation = {
        "validated": True,
        "phase1_dir": str(run_dir),
        "phase1_pass": overall_pass,
        "cuda_ok": checks.get("cuda_available", {}).get("pass", False),
        "triton_ok": checks.get("triton_importable", {}).get("pass", False),
        "compile_ok": checks.get("torch_compile_inductor", {}).get("pass", False),
        "gpu_name": checks.get("cuda_available", {}).get("detail", "N/A"),
        "triton_version": checks.get("triton_importable", {}).get("detail", "N/A"),
    }

    if overall_pass:
        logger.info(
            "  Cross-phase: Phase 1 PASSED (Triton %s, GPU %s)",
            validation["triton_version"],
            validation["gpu_name"],
        )
    else:
        logger.warning("  Cross-phase: Phase 1 FAILED — Phase 3 results may be invalid")

    return validation


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def analyze_mode(df: pd.DataFrame, mode: str) -> dict[str, Any]:
    """Orchestrate all per-mode analyses.

    Thin orchestrator — all logic lives in the individual analysis
    functions above.
    """
    logger.info("Analyzing %s: %d samples", mode, len(df))
    results: dict[str, Any] = {"mode": mode, "n_total": len(df)}

    results["rankings"] = compute_backend_rankings(df)
    results["by_model_backend"] = compute_model_breakdown(df)
    results["by_scenario_backend"] = compute_scenario_breakdown(df)
    results["compile_effect"] = compute_compile_effect(df)
    results["pairwise_comparisons"] = compute_pairwise_comparisons(df)
    results["outliers"] = compute_outlier_stats(df)
    results["power_analysis"] = compute_power_analysis(df)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR126 Phase 3 analysis")
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results_root = _REPO / "research" / "tr126" / "results" / "phase3"
    if args.results_dir:
        run_dir = Path(args.results_dir)
    else:
        run_dir = find_latest_run(results_root)
        if run_dir is None:
            logger.error("No Phase 3 results found under %s", results_root)
            return 1

    logger.info("Analyzing: %s", run_dir)

    # Cross-phase validation (before any analysis)
    xphase = cross_phase_validation()
    logger.info(
        "Cross-phase validation: %s",
        "PASS" if xphase.get("phase1_pass") else "FAIL/MISSING",
    )

    analysis: dict[str, Any] = {
        "run_dir": str(run_dir),
        "cross_phase_validation": xphase,
    }
    modes_analyzed = 0

    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        csv_path = run_dir / mode / "metrics.csv"
        if not csv_path.is_file():
            logger.info("Skipping %s (no metrics.csv)", mode)
            continue

        df = pd.read_csv(csv_path)
        if "status" in df.columns:
            df = df[df["status"] == "ok"]

        if df.empty:
            logger.warning("  %s: 0 OK samples — skipping", mode)
            continue

        mode_results = analyze_mode(df, mode)
        analysis[mode] = mode_results
        modes_analyzed += 1

        for r in mode_results.get("rankings", []):
            logger.info(
                "    #%d %s: %.3f ms (n=%d)",
                r["rank_by_mean"],
                r["backend"],
                r["mean_ms"],
                r["n"],
            )

    if modes_analyzed == 0:
        logger.error("No modes had data to analyze")
        return 1

    analysis_path = run_dir / "phase3_analysis.json"
    _write_json(analysis_path, analysis)
    logger.info(
        "Analysis saved: %s (%d modes, 8 analyses per mode)",
        analysis_path,
        modes_analyzed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
