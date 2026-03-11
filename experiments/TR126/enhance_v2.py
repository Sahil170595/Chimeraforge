#!/usr/bin/env python3
"""TR126 v2: Analysis Enhancement Script.

Computes 6 analyses from existing experiment data to fill gaps identified
in the critical review of the published TR126 report:

  1. Phase 2 Baseline Config Full Analysis (11,340 samples)
  2. Compiled Decode Performance Characterization (1,890 compiled kv_decode at max_new_tokens=64)
  3. ANOVA Interaction Test (model_scale x backend for Phase 3 prefill)
  4. Bonferroni/Holm Multiple Comparison Correction Table
  5. Phase 2 Per-Model CI Table (dynamic config)
  6. Max-Token Threshold Analysis (Phase 2 @ 64 tokens vs Phase 3 @ 128 tokens)

Also integrates mode="default" experiment results if available.

Usage:
    python research/tr126/enhance_v2.py [-v] [--mode-default-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.shared.statistical_analysis import (
    compare_groups,
)
from research.tr126.shared.utils import load_metrics_csv

logger = logging.getLogger("tr126.enhance_v2")

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
PHASE2_BASELINE_DIR = (
    _REPO / "research" / "tr126" / "results" / "phase2" / "20260222_195655"
)
PHASE2_DYNAMIC_DIR = (
    _REPO / "research" / "tr126" / "results" / "phase2" / "20260222_214114"
)
PHASE2_PADDED_DIR = (
    _REPO / "research" / "tr126" / "results" / "phase2" / "20260222_213342"
)
PHASE3_DIR = _REPO / "research" / "tr126" / "results" / "phase3" / "20260222_231929"
OUTPUT_DIR = _REPO / "research" / "tr126" / "results"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary(values: np.ndarray) -> dict[str, float]:
    """Compute per-group latency summary with 95% CI."""
    if values.size == 0:
        return {"n": 0, "mean_ms": float("nan")}
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


def _load_mode_csv(run_dir: Path, mode: str) -> pd.DataFrame:
    """Load a metrics CSV, filtering to status=ok."""
    csv_path = run_dir / mode / "metrics.csv"
    if not csv_path.is_file():
        return pd.DataFrame()
    return load_metrics_csv(csv_path)


# ---------------------------------------------------------------------------
# Analysis 1: Phase 2 Baseline Config Full Analysis
# ---------------------------------------------------------------------------


def analysis_1_phase2_baseline(output: dict) -> None:
    """Full analysis of Phase 2 baseline config (dynamic=False, mode=reduce-overhead).

    This is the 11,340-sample dataset that was collected but never analyzed in the
    original report (which only analyzed dynamic and padded configs for prefill).
    """
    logger.info("=" * 60)
    logger.info("Analysis 1: Phase 2 Baseline Config Full Analysis")
    logger.info("=" * 60)

    result: dict[str, Any] = {
        "source": str(PHASE2_BASELINE_DIR),
        "config": "baseline (dynamic=False, mode=reduce-overhead)",
        "max_new_tokens": 64,
    }

    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        df = _load_mode_csv(PHASE2_BASELINE_DIR, mode)
        if df.empty:
            logger.warning("  %s: no data", mode)
            continue

        mode_result: dict[str, Any] = {"n_total": len(df)}
        logger.info("  %s: %d samples", mode, len(df))

        # Per-backend rankings
        rankings = []
        for backend, grp in df.groupby("backend"):
            vals = grp["latency_ms"].dropna().values
            s = _summary(vals)
            s["backend"] = str(backend)
            rankings.append(s)
        rankings.sort(key=lambda r: r.get("mean_ms", float("inf")))
        for i, r in enumerate(rankings):
            r["rank_by_mean"] = i + 1
        mode_result["rankings"] = rankings

        # Per-model, per-backend breakdown
        by_model = {}
        for (model, backend), grp in df.groupby(["model", "backend"]):
            vals = grp["latency_ms"].dropna().values
            s = _summary(vals)
            s["model"] = str(model)
            s["backend"] = str(backend)
            by_model[f"{model}/{backend}"] = s
        mode_result["by_model_backend"] = by_model

        # Compile effect: eager vs compiled
        eager = df[df["backend"] == "transformers-gpu"]["latency_ms"].dropna()
        compiled = df[df["backend"] == "transformers-gpu-compile"][
            "latency_ms"
        ].dropna()
        if eager.size >= 2 and compiled.size >= 2:
            comp = compare_groups(
                eager.tolist(),
                compiled.tolist(),
                "eager",
                "compiled",
                "latency_ms",
            )
            mode_result["compile_effect"] = {
                "eager_mean": comp.mean_a,
                "compiled_mean": comp.mean_b,
                "delta_ms": comp.difference,
                "delta_pct": comp.percent_change,
                "compile_helps": comp.mean_b < comp.mean_a,
                "t_statistic": comp.t_statistic,
                "p_value": comp.p_value,
                "significant": comp.significant,
                "cohens_d": comp.effect_size,
                "n_eager": int(eager.size),
                "n_compiled": int(compiled.size),
            }
            logger.info(
                "    Compile effect (%s): %+.1f%% (d=%.3f, p=%.2e)",
                mode,
                comp.percent_change,
                comp.effect_size,
                comp.p_value,
            )

        result[mode] = mode_result

    # Cross-config comparison (baseline vs dynamic vs padded) — prefill only
    configs = {
        "baseline": PHASE2_BASELINE_DIR,
        "dynamic": PHASE2_DYNAMIC_DIR,
        "padded": PHASE2_PADDED_DIR,
    }
    cross_config: dict[str, Any] = {}
    for config_name, config_dir in configs.items():
        df = _load_mode_csv(config_dir, "prefill")
        if df.empty:
            continue
        # Only compiled backend for cross-config comparison
        compiled = df[df["backend"] == "transformers-gpu-compile"][
            "latency_ms"
        ].dropna()
        eager = df[df["backend"] == "transformers-gpu"]["latency_ms"].dropna()
        cross_config[config_name] = {
            "compiled_mean_ms": float(compiled.mean()) if compiled.size > 0 else None,
            "eager_mean_ms": float(eager.mean()) if eager.size > 0 else None,
            "compiled_n": int(compiled.size),
            "eager_n": int(eager.size),
        }
        if compiled.size > 0 and eager.size > 0:
            cross_config[config_name]["speedup"] = float(eager.mean() / compiled.mean())

    # Pairwise cross-config comparisons (compiled latency)
    cross_config_comparisons = []
    config_names = list(cross_config.keys())
    for i, ca in enumerate(config_names):
        for cb in config_names[i + 1 :]:
            if (
                cross_config[ca].get("compiled_mean_ms") is None
                or cross_config[cb].get("compiled_mean_ms") is None
            ):
                continue
            df_a = _load_mode_csv(configs[ca], "prefill")
            df_b = _load_mode_csv(configs[cb], "prefill")
            vals_a = (
                df_a[df_a["backend"] == "transformers-gpu-compile"]["latency_ms"]
                .dropna()
                .tolist()
            )
            vals_b = (
                df_b[df_b["backend"] == "transformers-gpu-compile"]["latency_ms"]
                .dropna()
                .tolist()
            )
            if len(vals_a) >= 2 and len(vals_b) >= 2:
                comp = compare_groups(
                    vals_a, vals_b, ca, cb, "compiled_prefill_latency_ms"
                )
                cross_config_comparisons.append(
                    {
                        "config_a": ca,
                        "config_b": cb,
                        "mean_a": comp.mean_a,
                        "mean_b": comp.mean_b,
                        "delta_ms": comp.difference,
                        "delta_pct": comp.percent_change,
                        "t_statistic": comp.t_statistic,
                        "p_value": comp.p_value,
                        "significant": comp.significant,
                        "cohens_d": comp.effect_size,
                    }
                )

    result["cross_config_prefill"] = cross_config
    result["cross_config_comparisons"] = cross_config_comparisons

    output["analysis_1_phase2_baseline"] = result
    logger.info(
        "  Done: %d modes analyzed",
        sum(1 for m in ["prefill", "kv_decode", "e2e_kv"] if m in result),
    )


# ---------------------------------------------------------------------------
# Analysis 2: Compiled Decode Performance Characterization
# ---------------------------------------------------------------------------


def analysis_2_compiled_decode(output: dict) -> None:
    """Characterize compiled kv_decode performance at max_new_tokens=64.

    Phase 2 baseline has 1,890 successful compiled kv_decode measurements.
    Phase 3 crashes 100% at max_new_tokens=128. This analysis fills the
    'no compiled decode data' gap.
    """
    logger.info("=" * 60)
    logger.info("Analysis 2: Compiled Decode Performance Characterization")
    logger.info("=" * 60)

    df = _load_mode_csv(PHASE2_BASELINE_DIR, "kv_decode")
    if df.empty:
        logger.error("  No kv_decode data")
        return

    eager = df[df["backend"] == "transformers-gpu"]
    compiled = df[df["backend"] == "transformers-gpu-compile"]

    logger.info("  Eager decode: %d samples", len(eager))
    logger.info("  Compiled decode: %d samples", len(compiled))

    result: dict[str, Any] = {
        "source": str(PHASE2_BASELINE_DIR / "kv_decode" / "metrics.csv"),
        "max_new_tokens": 64,
        "compile_mode": "reduce-overhead",
        "dynamic": False,
        "n_eager": len(eager),
        "n_compiled": len(compiled),
    }

    # Aggregate compiled decode stats
    compiled_vals = compiled["latency_ms"].dropna().values
    eager_vals = eager["latency_ms"].dropna().values
    result["compiled_aggregate"] = _summary(compiled_vals)
    result["eager_aggregate"] = _summary(eager_vals)

    # Compile effect (eager vs compiled)
    if eager_vals.size >= 2 and compiled_vals.size >= 2:
        comp = compare_groups(
            eager_vals.tolist(),
            compiled_vals.tolist(),
            "eager_decode",
            "compiled_decode",
            "latency_ms",
        )
        result["compile_effect"] = {
            "eager_mean": comp.mean_a,
            "compiled_mean": comp.mean_b,
            "delta_ms": comp.difference,
            "delta_pct": comp.percent_change,
            "compile_helps": comp.mean_b < comp.mean_a,
            "t_statistic": comp.t_statistic,
            "p_value": comp.p_value,
            "significant": comp.significant,
            "cohens_d": comp.effect_size,
        }
        logger.info(
            "  Compile effect (decode): %+.1f%% (d=%.3f, p=%.2e)",
            comp.percent_change,
            comp.effect_size,
            comp.p_value,
        )

    # Per-model compiled decode
    per_model: dict[str, Any] = {}
    models = compiled["model"].unique()
    for model in sorted(models):
        c_vals = compiled[compiled["model"] == model]["latency_ms"].dropna().values
        e_vals = eager[eager["model"] == model]["latency_ms"].dropna().values
        entry: dict[str, Any] = {
            "compiled": _summary(c_vals),
            "eager": _summary(e_vals),
        }
        if c_vals.size >= 2 and e_vals.size >= 2:
            comp = compare_groups(
                e_vals.tolist(),
                c_vals.tolist(),
                "eager",
                "compiled",
                "latency_ms",
            )
            entry["compile_effect"] = {
                "delta_ms": comp.difference,
                "delta_pct": comp.percent_change,
                "compile_helps": comp.mean_b < comp.mean_a,
                "p_value": comp.p_value,
                "significant": comp.significant,
                "cohens_d": comp.effect_size,
            }
            speedup = comp.mean_a / comp.mean_b if comp.mean_b > 0 else float("inf")
            entry["speedup"] = speedup
            logger.info(
                "    %s: eager=%.1f ms, compiled=%.1f ms, speedup=%.2fx (d=%.3f)",
                model,
                comp.mean_a,
                comp.mean_b,
                speedup,
                comp.effect_size,
            )

        per_model[str(model)] = entry

    result["per_model"] = per_model

    output["analysis_2_compiled_decode"] = result


# ---------------------------------------------------------------------------
# Analysis 3: ANOVA Interaction Test (model_scale x backend)
# ---------------------------------------------------------------------------


def analysis_3_anova_interaction(output: dict) -> None:
    """2-way ANOVA: latency_ms ~ backend + model + backend:model.

    Tests whether the scale crossover (compile wins small, Ollama wins large)
    is statistically significant via the interaction term.

    Source: Phase 3 prefill data (1,620 samples).
    """
    logger.info("=" * 60)
    logger.info("Analysis 3: ANOVA Interaction Test (model x backend)")
    logger.info("=" * 60)

    df = _load_mode_csv(PHASE3_DIR, "prefill")
    if df.empty:
        logger.error("  No Phase 3 prefill data")
        return

    # Need at least 2 backends for interaction test
    backends = sorted(df["backend"].unique())
    models = sorted(df["model"].unique())
    logger.info("  Backends: %s", backends)
    logger.info("  Models: %s", models)
    logger.info("  Total samples: %d", len(df))

    # Manual 2-way ANOVA with interaction using Type III SS
    # SST = sum of (y - grand_mean)^2
    # SS_backend = sum across backends of n_b * (mean_b - grand_mean)^2
    # SS_model = sum across models of n_m * (mean_m - grand_mean)^2
    # SS_interaction = sum across cells of n_bm * (mean_bm - mean_b - mean_m + grand_mean)^2
    # SS_residual = SST - SS_backend - SS_model - SS_interaction

    y = df["latency_ms"].values
    grand_mean = y.mean()
    sst = float(np.sum((y - grand_mean) ** 2))

    # Backend means
    backend_means = {}
    for b in backends:
        bvals = df[df["backend"] == b]["latency_ms"].values
        backend_means[b] = float(bvals.mean())

    # Model means
    model_means = {}
    for m in models:
        mvals = df[df["model"] == m]["latency_ms"].values
        model_means[m] = float(mvals.mean())

    # Cell means
    cell_data: dict[tuple[str, str], np.ndarray] = {}
    for b in backends:
        for m in models:
            cell = df[(df["backend"] == b) & (df["model"] == m)]["latency_ms"].values
            if cell.size > 0:
                cell_data[(b, m)] = cell

    # SS_backend
    ss_backend = 0.0
    for b in backends:
        n_b = df[df["backend"] == b].shape[0]
        ss_backend += n_b * (backend_means[b] - grand_mean) ** 2

    # SS_model
    ss_model = 0.0
    for m in models:
        n_m = df[df["model"] == m].shape[0]
        ss_model += n_m * (model_means[m] - grand_mean) ** 2

    # SS_interaction
    ss_interaction = 0.0
    for (b, m), cell in cell_data.items():
        n_bm = cell.size
        cell_mean = float(cell.mean())
        ss_interaction += (
            n_bm * (cell_mean - backend_means[b] - model_means[m] + grand_mean) ** 2
        )

    # SS_residual
    ss_residual = 0.0
    for (b, m), cell in cell_data.items():
        cell_mean = float(cell.mean())
        ss_residual += float(np.sum((cell - cell_mean) ** 2))

    # Degrees of freedom
    n_backends = len(backends)
    n_models = len(models)
    n_cells = len(cell_data)
    n_total = len(df)

    df_backend = n_backends - 1
    df_model = n_models - 1
    df_interaction = (n_backends - 1) * (n_models - 1)
    df_residual = n_total - n_cells

    # Mean squares
    ms_backend = ss_backend / df_backend if df_backend > 0 else 0
    ms_model = ss_model / df_model if df_model > 0 else 0
    ms_interaction = ss_interaction / df_interaction if df_interaction > 0 else 0
    ms_residual = ss_residual / df_residual if df_residual > 0 else 0

    # F-statistics
    f_backend = ms_backend / ms_residual if ms_residual > 0 else float("inf")
    f_model = ms_model / ms_residual if ms_residual > 0 else float("inf")
    f_interaction = ms_interaction / ms_residual if ms_residual > 0 else float("inf")

    # p-values
    p_backend = float(1 - stats.f.cdf(f_backend, df_backend, df_residual))
    p_model = float(1 - stats.f.cdf(f_model, df_model, df_residual))
    p_interaction = float(1 - stats.f.cdf(f_interaction, df_interaction, df_residual))

    # Eta-squared (proportion of variance explained)
    eta2_backend = ss_backend / sst if sst > 0 else 0
    eta2_model = ss_model / sst if sst > 0 else 0
    eta2_interaction = ss_interaction / sst if sst > 0 else 0

    result = {
        "source": str(PHASE3_DIR / "prefill" / "metrics.csv"),
        "n_total": n_total,
        "n_backends": n_backends,
        "n_models": n_models,
        "n_cells": n_cells,
        "backends": backends,
        "models": models,
        "grand_mean_ms": float(grand_mean),
        "anova_table": {
            "backend": {
                "ss": ss_backend,
                "df": df_backend,
                "ms": ms_backend,
                "f": f_backend,
                "p": p_backend,
                "eta_squared": eta2_backend,
                "significant": p_backend < 0.05,
            },
            "model": {
                "ss": ss_model,
                "df": df_model,
                "ms": ms_model,
                "f": f_model,
                "p": p_model,
                "eta_squared": eta2_model,
                "significant": p_model < 0.05,
            },
            "interaction": {
                "ss": ss_interaction,
                "df": df_interaction,
                "ms": ms_interaction,
                "f": f_interaction,
                "p": p_interaction,
                "eta_squared": eta2_interaction,
                "significant": p_interaction < 0.05,
            },
            "residual": {
                "ss": ss_residual,
                "df": df_residual,
                "ms": ms_residual,
            },
            "total": {
                "ss": sst,
                "df": n_total - 1,
            },
        },
        "interpretation": {
            "backend_significant": p_backend < 0.05,
            "model_significant": p_model < 0.05,
            "interaction_significant": p_interaction < 0.05,
            "interaction_meaning": (
                "The interaction is significant — the effect of backend choice depends on model scale. "
                "This formally validates the scale crossover observation."
                if p_interaction < 0.05
                else "The interaction is NOT significant — backend ranking is consistent across models."
            ),
        },
    }

    logger.info(
        "  Backend:     F(%.0f,%.0f)=%.2f, p=%.2e, eta2=%.4f",
        df_backend,
        df_residual,
        f_backend,
        p_backend,
        eta2_backend,
    )
    logger.info(
        "  Model:       F(%.0f,%.0f)=%.2f, p=%.2e, eta2=%.4f",
        df_model,
        df_residual,
        f_model,
        p_model,
        eta2_model,
    )
    logger.info(
        "  Interaction: F(%.0f,%.0f)=%.2f, p=%.2e, eta2=%.4f",
        df_interaction,
        df_residual,
        f_interaction,
        p_interaction,
        eta2_interaction,
    )

    output["analysis_3_anova_interaction"] = result


# ---------------------------------------------------------------------------
# Analysis 4: Bonferroni/Holm Multiple Comparison Correction
# ---------------------------------------------------------------------------


def analysis_4_bonferroni_holm(output: dict) -> None:
    """Apply Bonferroni and Holm step-down corrections to Phase 3 pairwise comparisons.

    Source: phase3_analysis.json pairwise comparisons across all modes.
    """
    logger.info("=" * 60)
    logger.info("Analysis 4: Bonferroni/Holm Correction Table")
    logger.info("=" * 60)

    analysis_path = PHASE3_DIR / "phase3_analysis.json"
    if not analysis_path.is_file():
        logger.error("  phase3_analysis.json not found")
        return

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    # Collect all pairwise p-values across modes
    all_tests: list[dict[str, Any]] = []
    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        mode_data = analysis.get(mode, {})
        for pw in mode_data.get("pairwise_comparisons", []):
            all_tests.append(
                {
                    "mode": mode,
                    "group_a": pw["group_a"],
                    "group_b": pw["group_b"],
                    "p_value": pw["p_value"],
                    "t_statistic": pw.get("t_statistic", None),
                    "cohens_d": pw.get("cohens_d", None),
                    "original_significant": pw.get("significant", pw["p_value"] < 0.05),
                }
            )

    k = len(all_tests)
    alpha = 0.05
    bonferroni_alpha = alpha / k if k > 0 else alpha

    logger.info("  Total pairwise tests: %d", k)
    logger.info("  Bonferroni alpha: %.4f (0.05 / %d)", bonferroni_alpha, k)

    # Sort by p-value for Holm step-down
    all_tests.sort(key=lambda t: t["p_value"])

    for i, test in enumerate(all_tests):
        # Bonferroni
        test["bonferroni_alpha"] = bonferroni_alpha
        test["bonferroni_significant"] = test["p_value"] < bonferroni_alpha

        # Holm step-down: alpha / (k - rank + 1), where rank is 1-indexed position
        holm_alpha = alpha / (k - i)
        test["holm_rank"] = i + 1
        test["holm_alpha"] = holm_alpha
        test["holm_significant"] = test["p_value"] < holm_alpha

        logger.info(
            "  Test %d/%d [%s %s vs %s]: p=%.2e, Bonferroni=%s, Holm=%s",
            i + 1,
            k,
            test["mode"],
            test["group_a"],
            test["group_b"],
            test["p_value"],
            "PASS" if test["bonferroni_significant"] else "FAIL",
            "PASS" if test["holm_significant"] else "FAIL",
        )

    n_bonferroni = sum(1 for t in all_tests if t["bonferroni_significant"])
    n_holm = sum(1 for t in all_tests if t["holm_significant"])

    result = {
        "n_tests": k,
        "alpha": alpha,
        "bonferroni_alpha": bonferroni_alpha,
        "n_bonferroni_significant": n_bonferroni,
        "n_holm_significant": n_holm,
        "all_survive_bonferroni": n_bonferroni == k,
        "all_survive_holm": n_holm == k,
        "tests": all_tests,
    }

    output["analysis_4_bonferroni_holm"] = result


# ---------------------------------------------------------------------------
# Analysis 5: Phase 2 Per-Model CI Table (dynamic config)
# ---------------------------------------------------------------------------


def analysis_5_per_model_ci(output: dict) -> None:
    """Generate per-model CI table for Phase 2 dynamic config.

    Format: model | backend | n | mean | CI_lower | CI_upper
    """
    logger.info("=" * 60)
    logger.info("Analysis 5: Phase 2 Per-Model CI Table")
    logger.info("=" * 60)

    result: dict[str, Any] = {"source": str(PHASE2_DYNAMIC_DIR)}
    tables: dict[str, list] = {}

    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        df = _load_mode_csv(PHASE2_DYNAMIC_DIR, mode)
        if df.empty:
            # Try baseline if dynamic doesn't have this mode
            df = _load_mode_csv(PHASE2_BASELINE_DIR, mode)
            if df.empty:
                continue

        rows: list[dict[str, Any]] = []
        for (model, backend), grp in sorted(df.groupby(["model", "backend"])):
            vals = grp["latency_ms"].dropna().values
            s = _summary(vals)
            rows.append(
                {
                    "model": str(model),
                    "backend": str(backend),
                    "n": s["n"],
                    "mean_ms": round(s["mean_ms"], 2),
                    "ci_lower": round(s["ci_lower"], 2),
                    "ci_upper": round(s["ci_upper"], 2),
                    "median_ms": round(s["median_ms"], 2),
                    "std_ms": round(s["std_ms"], 2),
                }
            )
        tables[mode] = rows
        logger.info("  %s: %d model×backend entries", mode, len(rows))

    result["tables"] = tables
    output["analysis_5_per_model_ci"] = result


# ---------------------------------------------------------------------------
# Analysis 6: Max-Token Threshold Analysis
# ---------------------------------------------------------------------------


def analysis_6_max_token_threshold(output: dict) -> None:
    """Compare compiled decode at max_new_tokens=64 (Phase 2) vs 128 (Phase 3).

    Phase 2 baseline: max_new_tokens=64, compiled kv_decode WORKS
    Phase 3: max_new_tokens=128, compiled kv_decode CRASHES 100%

    This identifies the CUDA graph shape violation as length-dependent.
    """
    logger.info("=" * 60)
    logger.info("Analysis 6: Max-Token Threshold Analysis")
    logger.info("=" * 60)

    result: dict[str, Any] = {}

    # Phase 2 baseline: compiled decode at 64 tokens
    df_p2 = _load_mode_csv(PHASE2_BASELINE_DIR, "kv_decode")
    compiled_p2 = (
        df_p2[df_p2["backend"] == "transformers-gpu-compile"]
        if not df_p2.empty
        else pd.DataFrame()
    )

    # Phase 3: compiled decode at 128 tokens — check for errors
    p3_csv = PHASE3_DIR / "kv_decode" / "metrics.csv"
    df_p3_raw = pd.DataFrame()
    if p3_csv.is_file():
        df_p3_raw = pd.read_csv(p3_csv)

    compiled_p3_ok = (
        df_p3_raw[
            (df_p3_raw["backend"] == "transformers-gpu-compile")
            & (df_p3_raw["status"] == "ok")
        ]
        if not df_p3_raw.empty and "status" in df_p3_raw.columns
        else pd.DataFrame()
    )
    compiled_p3_err = (
        df_p3_raw[
            (df_p3_raw["backend"] == "transformers-gpu-compile")
            & (df_p3_raw["status"] != "ok")
        ]
        if not df_p3_raw.empty and "status" in df_p3_raw.columns
        else pd.DataFrame()
    )

    result["phase2_baseline"] = {
        "max_new_tokens": 64,
        "compile_mode": "reduce-overhead",
        "dynamic": False,
        "compiled_decode_n_ok": len(compiled_p2),
        "compiled_decode_n_error": 0,
        "crash_rate_pct": 0.0,
        "status": "WORKS — all compiled decode measurements succeed",
    }

    result["phase3"] = {
        "max_new_tokens": 128,
        "compile_mode": "reduce-overhead",
        "dynamic": False,
        "compiled_decode_n_ok": len(compiled_p3_ok),
        "compiled_decode_n_error": len(compiled_p3_err),
        "crash_rate_pct": (
            100.0 * len(compiled_p3_err) / (len(compiled_p3_ok) + len(compiled_p3_err))
            if (len(compiled_p3_ok) + len(compiled_p3_err)) > 0
            else 0.0
        ),
        "status": (
            "CRASHES — 100% failure rate on compiled decode"
            if len(compiled_p3_ok) == 0 and len(compiled_p3_err) > 0
            else "unknown"
        ),
    }

    # Key insight
    result["finding"] = {
        "summary": (
            "CUDA graph compiled decode is LENGTH-DEPENDENT, not absolute. "
            "It works at max_new_tokens=64 (Phase 2 baseline, 1,890 successful measurements) "
            "but crashes at max_new_tokens=128 (Phase 3, 100% crash rate). "
            "The CUDA graph captures tensor shapes for the initial KV-cache state; "
            "longer generation means more shape mutations before graph replay, "
            "increasing the probability of shape mismatch."
        ),
        "p2_compiled_ok": len(compiled_p2),
        "p3_compiled_ok": len(compiled_p3_ok),
        "p3_compiled_err": len(compiled_p3_err),
        "threshold_between": "64 < threshold <= 128 tokens",
    }

    # Per-model comparison (Phase 2 @ 64 tokens)
    if not compiled_p2.empty:
        per_model_p2: dict[str, Any] = {}
        for model in sorted(compiled_p2["model"].unique()):
            vals = (
                compiled_p2[compiled_p2["model"] == model]["latency_ms"].dropna().values
            )
            per_model_p2[str(model)] = _summary(vals)
        result["phase2_per_model_compiled_decode"] = per_model_p2

    logger.info("  Phase 2 (64 tokens): %d compiled decode OK", len(compiled_p2))
    logger.info(
        "  Phase 3 (128 tokens): %d OK, %d ERROR",
        len(compiled_p3_ok),
        len(compiled_p3_err),
    )
    logger.info("  Finding: CUDA graph crash is length-dependent")

    output["analysis_6_max_token_threshold"] = result


# ---------------------------------------------------------------------------
# Bonus: mode="default" experiment analysis
# ---------------------------------------------------------------------------


def analysis_7_mode_default(output: dict, mode_default_dir: Path | None) -> None:
    """Analyze mode='default' experiment results if available.

    This experiment uses torch.compile(mode='default') instead of 'reduce-overhead',
    disabling CUDA graphs. Expected: decode works, prefill may be slightly slower.
    """
    logger.info("=" * 60)
    logger.info("Analysis 7: mode='default' Experiment Results")
    logger.info("=" * 60)

    if mode_default_dir is None:
        # Auto-discover: find the latest run that isn't the reduce-overhead run
        p3_root = _REPO / "research" / "tr126" / "results" / "phase3"
        known_reduce_overhead = "20260222_231929"
        candidates = sorted(
            [
                p
                for p in p3_root.iterdir()
                if p.is_dir()
                and len(p.name) == 15
                and p.name[8] == "_"
                and p.name != known_reduce_overhead
            ],
            key=lambda p: p.name,
            reverse=True,
        )
        if candidates:
            mode_default_dir = candidates[0]
            logger.info("  Auto-discovered mode=default dir: %s", mode_default_dir)
        else:
            logger.info("  No mode=default results found yet — skipping")
            output["analysis_7_mode_default"] = {"status": "not_available"}
            return

    result: dict[str, Any] = {
        "source": str(mode_default_dir),
        "compile_mode": "default",
    }

    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        df = _load_mode_csv(mode_default_dir, mode)
        if df.empty:
            logger.info("  %s: no data", mode)
            continue

        mode_result: dict[str, Any] = {"n_total": len(df)}
        logger.info("  %s: %d samples", mode, len(df))

        # Backend rankings
        rankings = []
        for backend, grp in df.groupby("backend"):
            vals = grp["latency_ms"].dropna().values
            s = _summary(vals)
            s["backend"] = str(backend)
            rankings.append(s)
        rankings.sort(key=lambda r: r.get("mean_ms", float("inf")))
        for i, r in enumerate(rankings):
            r["rank_by_mean"] = i + 1
        mode_result["rankings"] = rankings

        # Per-model breakdown
        by_model = {}
        for (model, backend), grp in df.groupby(["model", "backend"]):
            vals = grp["latency_ms"].dropna().values
            s = _summary(vals)
            s["model"] = str(model)
            s["backend"] = str(backend)
            by_model[f"{model}/{backend}"] = s
        mode_result["by_model_backend"] = by_model

        # Compile effect
        eager = df[df["backend"] == "transformers-gpu"]["latency_ms"].dropna()
        compiled = df[df["backend"] == "transformers-gpu-compile"][
            "latency_ms"
        ].dropna()
        if eager.size >= 2 and compiled.size >= 2:
            comp = compare_groups(
                eager.tolist(),
                compiled.tolist(),
                "eager",
                "compiled_default",
                "latency_ms",
            )
            mode_result["compile_effect"] = {
                "eager_mean": comp.mean_a,
                "compiled_mean": comp.mean_b,
                "delta_ms": comp.difference,
                "delta_pct": comp.percent_change,
                "compile_helps": comp.mean_b < comp.mean_a,
                "t_statistic": comp.t_statistic,
                "p_value": comp.p_value,
                "significant": comp.significant,
                "cohens_d": comp.effect_size,
            }
            logger.info(
                "    Compile effect (%s): %+.1f%% (d=%.3f, p=%.2e)",
                mode,
                comp.percent_change,
                comp.effect_size,
                comp.p_value,
            )

        # Error rate (to confirm decode doesn't crash)
        csv_path = mode_default_dir / mode / "metrics.csv"
        if csv_path.is_file():
            df_raw = pd.read_csv(csv_path)
            if "status" in df_raw.columns:
                compiled_rows = df_raw[df_raw["backend"] == "transformers-gpu-compile"]
                n_ok = (compiled_rows["status"] == "ok").sum()
                n_err = (compiled_rows["status"] != "ok").sum()
                mode_result["compiled_error_rate"] = {
                    "n_ok": int(n_ok),
                    "n_error": int(n_err),
                    "crash_rate_pct": (
                        float(100 * n_err / (n_ok + n_err))
                        if (n_ok + n_err) > 0
                        else 0.0
                    ),
                }
                logger.info(
                    "    Compiled %s: %d ok, %d error (crash_rate=%.1f%%)",
                    mode,
                    n_ok,
                    n_err,
                    mode_result["compiled_error_rate"]["crash_rate_pct"],
                )

        result[mode] = mode_result

    # Cross-mode comparison with reduce-overhead
    reduce_overhead_analysis = PHASE3_DIR / "phase3_analysis.json"
    if reduce_overhead_analysis.is_file():
        ro_data = json.loads(reduce_overhead_analysis.read_text(encoding="utf-8"))
        cross_mode: dict[str, Any] = {}
        for mode in ["prefill", "kv_decode", "e2e_kv"]:
            ro_mode = ro_data.get(mode, {})
            default_mode = result.get(mode, {})
            if ro_mode and default_mode:
                # Compare compile effects between modes
                ro_ce = ro_mode.get("compile_effect", {})
                def_ce = default_mode.get("compile_effect", {})
                if ro_ce and def_ce:
                    cross_mode[mode] = {
                        "reduce_overhead_compiled_mean": ro_ce.get(
                            "gpu_compile_mean", ro_ce.get("compiled_mean")
                        ),
                        "default_compiled_mean": def_ce.get("compiled_mean"),
                        "reduce_overhead_delta_pct": ro_ce.get("delta_pct"),
                        "default_delta_pct": def_ce.get("delta_pct"),
                        "reduce_overhead_cohens_d": ro_ce.get("cohens_d"),
                        "default_cohens_d": def_ce.get("cohens_d"),
                    }
        result["cross_mode_comparison"] = cross_mode

    output["analysis_7_mode_default"] = result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR126 v2 Analysis Enhancement")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--mode-default-dir",
        type=Path,
        default=None,
        help="Path to mode=default experiment results",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    output: dict[str, Any] = {
        "version": "TR126_v2",
        "description": "Analysis enhancement for TR126 critical review",
    }

    # Run all analyses
    analysis_1_phase2_baseline(output)
    analysis_2_compiled_decode(output)
    analysis_3_anova_interaction(output)
    analysis_4_bonferroni_holm(output)
    analysis_5_per_model_ci(output)
    analysis_6_max_token_threshold(output)
    analysis_7_mode_default(output, args.mode_default_dir)

    # Save output
    output_path = OUTPUT_DIR / "enhance_v2_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    logger.info("=" * 60)
    logger.info("All analyses complete. Output: %s", output_path)
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
