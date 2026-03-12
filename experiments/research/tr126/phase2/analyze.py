#!/usr/bin/env python3
"""TR126 Phase 2: Compile paradox analysis with cross-platform comparison.

Reads Phase 2 metrics.csv files (Linux/Docker results). Optionally loads
TR120 Windows results for cross-platform deltas.

Analyses performed (8 total):
  1. Per-backend summary — mean, median, p95, p99, CI, per backend
  2. Per-scenario × backend breakdown — full matrix of latency stats
  3. Per-model × backend breakdown — latency stats grouped by model
  4. Compile paradox assessment — eager vs compiled, aggregate AND per-scenario
  5. Pairwise comparisons — all backend pairs, t-test + Cohen's d via shared lib
  6. Outlier detection — IQR method, per backend
  7. Power analysis — minimum detectable effect size (Cohen's d) at current N
  8. Cross-platform comparison — Linux vs Windows via TR120 baseline (if available)
  9. Cross-phase validation — confirms Phase 1 environment gate passed

Outputs (under run_dir):
  - phase2_analysis.json (full results)
  - <mode>/analysis/plots/*.png (CDF plots, if Windows baseline available)

Usage:
    python research/tr126/phase2/analyze.py [--results-dir DIR] [-v]
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
from research.tr126.shared.cross_platform_compare import (
    compute_platform_deltas,
    plot_platform_comparison,
)
from research.tr126.shared.utils import (
    TR126_RESULTS,
    find_latest_run,
    get_tr120_windows_run,
)

logger = logging.getLogger("tr126.phase2.analyze")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentiles(values: np.ndarray, ps: list[float]) -> dict[str, float]:
    """Compute named percentiles (e.g., p90, p95, p99) for a 1-D array."""
    if values.size == 0:
        return {f"p{int(p)}": float("nan") for p in ps}
    return {f"p{int(p)}": float(np.percentile(values, p)) for p in ps}


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
            "min_ms": float("nan"),
            "max_ms": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            **_percentiles(values, [90, 95, 99]),
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
        **_percentiles(values, [90, 95, 99]),
    }


def _ensure_dir(path: Path) -> None:
    """Create directory and parents if needed."""
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    """Write JSON with consistent formatting and UTF-8 encoding."""
    _ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Analysis 1: Backend summaries
# ---------------------------------------------------------------------------


def compute_backend_summaries(df: pd.DataFrame) -> dict[str, Any]:
    """Compute per-backend latency statistics.

    Returns dict keyed by backend name, each value a summary dict with
    n, mean, median, std, CI, and percentiles.
    """
    summaries: dict[str, Any] = {}
    for backend, grp in df.groupby("backend"):
        vals = grp["latency_ms"].dropna().values
        summaries[str(backend)] = _summary(vals)
        logger.debug(
            "  %s: n=%d, mean=%.3f ms",
            backend,
            vals.size,
            vals.mean() if vals.size > 0 else float("nan"),
        )
    return summaries


# ---------------------------------------------------------------------------
# Analysis 2: Scenario × backend breakdown
# ---------------------------------------------------------------------------


def compute_scenario_breakdown(df: pd.DataFrame) -> dict[str, Any]:
    """Compute per-scenario × per-backend latency statistics.

    Returns dict keyed by 'scenario/backend', each value a summary dict.
    """
    breakdown: dict[str, Any] = {}
    for (scenario, backend), grp in df.groupby(["scenario", "backend"]):
        vals = grp["latency_ms"].dropna().values
        breakdown[f"{scenario}/{backend}"] = _summary(vals)
    return breakdown


# ---------------------------------------------------------------------------
# Analysis 3: Model × backend breakdown
# ---------------------------------------------------------------------------


def compute_model_breakdown(df: pd.DataFrame) -> dict[str, Any]:
    """Compute per-model × per-backend latency statistics.

    Returns dict keyed by 'model/backend'. Provides per-model visibility
    that the aggregate backend summary obscures.
    """
    breakdown: dict[str, Any] = {}
    if "model" not in df.columns:
        return breakdown
    for (model, backend), grp in df.groupby(["model", "backend"]):
        vals = grp["latency_ms"].dropna().values
        breakdown[f"{model}/{backend}"] = _summary(vals)
    return breakdown


# ---------------------------------------------------------------------------
# Analysis 4: Compile paradox (aggregate + per-scenario)
# ---------------------------------------------------------------------------


def _assess_compile(
    eager_vals: np.ndarray,
    compile_vals: np.ndarray,
    label: str = "",
) -> dict[str, Any]:
    """Compare eager vs compiled latency for a single group.

    Uses research.shared.statistical_analysis.compare_groups for t-test,
    Cohen's d, and significance. Returns a flat dict with all comparison
    metrics, or a 'skipped' marker if insufficient data.
    """
    if eager_vals.size < 2 or compile_vals.size < 2:
        return {
            "label": label,
            "n_eager": int(eager_vals.size),
            "n_compile": int(compile_vals.size),
            "skipped": True,
        }
    comp = compare_groups(
        eager_vals.tolist(),
        compile_vals.tolist(),
        "eager",
        "compiled",
        "latency_ms",
    )
    return {
        "label": label,
        "eager_mean": comp.mean_a,
        "compile_mean": comp.mean_b,
        "eager_median": float(np.median(eager_vals)),
        "compile_median": float(np.median(compile_vals)),
        "compile_helps_mean": comp.mean_b < comp.mean_a,
        "compile_helps_median": float(np.median(compile_vals))
        < float(np.median(eager_vals)),
        "mean_delta_pct": comp.percent_change,
        "t_statistic": comp.t_statistic,
        "p_value": comp.p_value,
        "significant": comp.significant,
        "cohens_d": comp.effect_size,
        "n_eager": int(eager_vals.size),
        "n_compile": int(compile_vals.size),
    }


def compute_compile_paradox(
    df: pd.DataFrame,
    group_col: str = "scenario",
) -> list[dict[str, Any]]:
    """Assess compile paradox: eager vs compiled, aggregate + per-group.

    Returns a list of dicts. The first entry is always the aggregate
    comparison; subsequent entries are per-group breakdowns (e.g., per-scenario).
    Each entry uses compare_groups for consistent statistical testing.
    """
    eager_all = df[df["backend"] == "transformers-gpu"]["latency_ms"].dropna().values
    compile_all = (
        df[df["backend"] == "transformers-gpu-compile"]["latency_ms"].dropna().values
    )

    results: list[dict[str, Any]] = []
    results.append(_assess_compile(eager_all, compile_all, "aggregate"))

    if group_col in df.columns:
        for group_val, grp in df.groupby(group_col):
            eager = (
                grp[grp["backend"] == "transformers-gpu"]["latency_ms"].dropna().values
            )
            compiled = (
                grp[grp["backend"] == "transformers-gpu-compile"]["latency_ms"]
                .dropna()
                .values
            )
            results.append(_assess_compile(eager, compiled, str(group_val)))

    # Log aggregate result
    agg = results[0]
    if not agg.get("skipped"):
        helps = "YES" if agg["compile_helps_mean"] else "NO"
        logger.info(
            "  Compile helps mean: %s (%+.1f%%, p=%.4f, d=%.3f)",
            helps,
            agg["mean_delta_pct"],
            agg["p_value"],
            agg["cohens_d"],
        )
    return results


# ---------------------------------------------------------------------------
# Analysis 5: Pairwise backend comparisons
# ---------------------------------------------------------------------------


def compute_pairwise_comparisons(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute all-pairs t-test + Cohen's d for backends.

    Returns a list of comparison dicts. Each pair is tested once (no
    duplicates). Uses research.shared.statistical_analysis.compare_groups.
    """
    backends = sorted(df["backend"].unique())
    pairwise: list[dict[str, Any]] = []
    for i, ba in enumerate(backends):
        for bb in backends[i + 1 :]:
            va = df[df["backend"] == ba]["latency_ms"].dropna().tolist()
            vb = df[df["backend"] == bb]["latency_ms"].dropna().tolist()
            if len(va) < 2 or len(vb) < 2:
                logger.debug("  Skipping %s vs %s (n=%d, %d)", ba, bb, len(va), len(vb))
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
    logger.info(
        "  Pairwise: %d comparisons, %d significant",
        len(pairwise),
        sum(1 for p in pairwise if p["significant"]),
    )
    return pairwise


# ---------------------------------------------------------------------------
# Analysis 6: Outlier detection
# ---------------------------------------------------------------------------


def compute_outlier_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Run IQR outlier detection per backend.

    Returns dict keyed by backend name with total count, outlier count,
    outlier percentage, and up to 5 example outlier values.
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
            "outlier_values": od["outliers"][:5],
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

    Uses the approximation: d = (z_alpha + z_beta) * sqrt(2/n)
    where n is the smallest per-backend sample count.

    Also computes the minimum detectable latency difference in ms
    using the pooled std across backends for practical interpretation.
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

    # Practical interpretation: convert Cohen's d to ms using pooled std
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
# Analysis 8: Cross-platform comparison
# ---------------------------------------------------------------------------


def compute_cross_platform(
    df: pd.DataFrame,
    windows_df: pd.DataFrame | None,
    out_dir: Path,
    mode: str,
) -> list[dict[str, Any]] | None:
    """Compute per-group deltas between Linux and Windows.

    Returns list of delta dicts, or None if no Windows data.
    Also generates CDF comparison plots.
    """
    if windows_df is None or windows_df.empty:
        logger.info("  No Windows baseline available for cross-platform comparison")
        return None

    logger.info(
        "  Cross-platform: %d Linux vs %d Windows samples", len(df), len(windows_df)
    )
    xplat = compute_platform_deltas(
        df,
        windows_df,
        group_cols=["scenario", "backend"],
        value_col="latency_ms",
    )

    # Plot CDFs
    plots_dir = out_dir / "plots"
    _ensure_dir(plots_dir)
    plot_platform_comparison(
        df,
        windows_df,
        value_col="latency_ms",
        label=f"{mode} latency",
        out_path=plots_dir / f"cdf_{mode}_cross_platform.png",
    )
    logger.info("  CDF plot saved: %s", plots_dir / f"cdf_{mode}_cross_platform.png")

    return xplat.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Analysis 9: Cross-phase validation
# ---------------------------------------------------------------------------


def cross_phase_validation() -> dict[str, Any]:
    """Validate that Phase 1 environment gate passed before Phase 2 ran.

    Loads the latest Phase 1 environment.json and checks:
    - Overall pass status
    - CUDA availability
    - Triton importability
    - torch.compile inductor (no fallback)

    Returns a validation dict with pass/fail and details.
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
        logger.warning("  Cross-phase: Phase 1 FAILED — Phase 2 results may be invalid")

    return validation


# ---------------------------------------------------------------------------
# Orchestrator: analyze_mode
# ---------------------------------------------------------------------------


def analyze_mode(
    df: pd.DataFrame,
    mode: str,
    out_dir: Path,
    windows_df: pd.DataFrame | None,
) -> dict[str, Any]:
    """Orchestrate all analyses for a single mode.

    Calls each analysis function in sequence, assembles results into
    a single dict. This is a thin orchestrator — all logic lives in
    the individual analysis functions above.
    """
    logger.info("Analyzing %s: %d samples", mode, len(df))
    results: dict[str, Any] = {"mode": mode, "n_total": len(df)}

    results["by_backend"] = compute_backend_summaries(df)
    results["by_scenario_backend"] = compute_scenario_breakdown(df)
    results["by_model_backend"] = compute_model_breakdown(df)
    results["compile_paradox"] = compute_compile_paradox(df, group_col="scenario")
    results["pairwise_comparisons"] = compute_pairwise_comparisons(df)
    results["outliers"] = compute_outlier_stats(df)
    results["power_analysis"] = compute_power_analysis(df)
    results["cross_platform"] = compute_cross_platform(df, windows_df, out_dir, mode)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR126 Phase 2 analysis")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Phase 2 results directory. Auto-discovers latest if not set.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results_root = _REPO / "research" / "tr126" / "results" / "phase2"
    if args.results_dir:
        run_dir = Path(args.results_dir)
    else:
        run_dir = find_latest_run(results_root)
        if run_dir is None:
            logger.error("No Phase 2 results found under %s", results_root)
            return 1

    logger.info("Analyzing: %s", run_dir)

    # Cross-phase validation (before any analysis)
    xphase = cross_phase_validation()
    logger.info(
        "Cross-phase validation: %s",
        "PASS" if xphase.get("phase1_pass") else "FAIL/MISSING",
    )

    # Load Windows baseline (if available)
    windows_run = get_tr120_windows_run()
    logger.info("Windows baseline: %s", windows_run or "not found")

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
        df = df[df["status"] == "ok"] if "status" in df.columns else df

        if df.empty:
            logger.warning("  %s: 0 OK samples — skipping", mode)
            continue

        # Load matching Windows mode data
        windows_df = None
        if windows_run:
            win_csv = windows_run / mode / "metrics.csv"
            if win_csv.is_file():
                windows_df = pd.read_csv(win_csv)
                if "status" in windows_df.columns:
                    windows_df = windows_df[windows_df["status"] == "ok"]

        out_dir = run_dir / mode / "analysis"
        _ensure_dir(out_dir)

        mode_results = analyze_mode(df, mode, out_dir, windows_df)
        analysis[mode] = mode_results
        modes_analyzed += 1

    if modes_analyzed == 0:
        logger.error("No modes had data to analyze")
        return 1

    # Save combined analysis
    analysis_path = run_dir / "phase2_analysis.json"
    _write_json(analysis_path, analysis)
    logger.info(
        "Analysis saved: %s (%d modes, 9 analyses per mode)",
        analysis_path,
        modes_analyzed,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
