"""TR127 — Statistical analysis of context-length sweep results.

Reads metrics.csv, computes scaling fits, VRAM cliffs, TTFT thresholds,
backend comparisons, outlier detection, and power analysis.

v2 additions:
  - Ollama cold-start detection and filtering (#19)
  - Two-regime decode analysis for HF models (#20)
  - KV cache cross-validation with theoretical predictions (#21)
  - Bonferroni/Holm multiple comparison correction (#22)
  - Two-way ANOVA for context_length x backend interaction (#22)
  - Trimmed-mean robustness analysis for scaling exponents (#22)
  - Distribution shape analysis (skewness, mean/median ratio) (#23)

Usage:
    python research/tr127/analyze.py -v
    python research/tr127/analyze.py --run-dir research/tr127/results/20260223_120000
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
from scipy import stats
from scipy.optimize import curve_fit

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.shared.statistical_analysis import (
    compare_groups,
    compute_summary,
    detect_outliers,
)
from research.tr127.shared.utils import (
    TR127_RESULTS,
    compute_percentiles,
    effect_label,
    find_latest_run,
    load_metrics_csv,
)

log = logging.getLogger("tr127.analyze")


# ── Scaling models ────────────────────────────────────────────────────


def _power_law(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """y = a * x^b"""
    return a * np.power(x, b)


def _linear(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """y = a * x + b"""
    return a * x + b


def _fit_scaling(
    ctx_lengths: np.ndarray, latencies: np.ndarray, gpu_vram_mb: float = 12288.0
) -> dict[str, Any]:
    """Fit both power-law and linear models, return best fit statistics.

    If VRAM data suggests thrashing (allocation >> physical VRAM), the fit
    is also run on the *clean* (pre-thrashing) subset to separate true
    computational scaling from memory-overflow artifacts.
    """
    result: dict[str, Any] = {"n_points": len(ctx_lengths)}

    if len(ctx_lengths) < 3:
        result["error"] = "too_few_points"
        return result

    def _do_fit(ctx: np.ndarray, lat: np.ndarray, tag: str = "") -> dict:
        """Fit power-law + linear on a (ctx, lat) pair."""
        out: dict[str, Any] = {"n_points": len(ctx)}
        r2_power = -1.0
        r2_lin = -1.0

        # Power-law fit: latency = a * ctx^b
        try:
            with np.errstate(over="ignore"):
                popt, _ = curve_fit(_power_law, ctx, lat, p0=[1e-3, 1.5], maxfev=5000)
            pred = _power_law(ctx, *popt)
            ss_res = np.sum((lat - pred) ** 2)
            ss_tot = np.sum((lat - np.mean(lat)) ** 2)
            r2_power = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            out["power_law"] = {
                "a": float(popt[0]),
                "b": float(popt[1]),
                "r_squared": float(r2_power),
            }
        except Exception as e:
            out["power_law"] = {"error": str(e)}

        # Linear fit: latency = a * ctx + b
        try:
            popt_lin, _ = curve_fit(_linear, ctx, lat, p0=[0.01, 10.0], maxfev=5000)
            pred_lin = _linear(ctx, *popt_lin)
            ss_res_lin = np.sum((lat - pred_lin) ** 2)
            ss_tot_lin = np.sum((lat - np.mean(lat)) ** 2)
            r2_lin = 1 - ss_res_lin / ss_tot_lin if ss_tot_lin > 0 else 0.0
            out["linear"] = {
                "a": float(popt_lin[0]),
                "b": float(popt_lin[1]),
                "r_squared": float(r2_lin),
            }
        except Exception as e:
            out["linear"] = {"error": str(e)}

        # Quadratic fit: latency = a * ctx^2 + b * ctx + c
        try:
            coeffs = np.polyfit(ctx, lat, 2)
            pred_q = np.polyval(coeffs, ctx)
            ss_res_q = np.sum((lat - pred_q) ** 2)
            ss_tot_q = np.sum((lat - np.mean(lat)) ** 2)
            r2_quad = 1 - ss_res_q / ss_tot_q if ss_tot_q > 0 else 0.0
            out["quadratic"] = {
                "a": float(coeffs[0]),
                "b": float(coeffs[1]),
                "c": float(coeffs[2]),
                "r_squared": float(r2_quad),
            }
        except Exception:
            pass

        out["better_fit"] = "power_law" if r2_power >= r2_lin else "linear"
        out["is_superlinear"] = (
            "b" in out.get("power_law", {}) and out["power_law"]["b"] > 1.2
        )
        return out

    # Full-range fit
    result.update(_do_fit(ctx_lengths, latencies))

    return result


def _fit_scaling_trimmed(
    ctx_lengths: np.ndarray,
    all_latencies: pd.DataFrame,
    trim_pcts: tuple[float, ...] = (0.05, 0.10),
) -> dict[str, Any]:
    """Fit scaling on trimmed means at each context length.

    For each trim percentage, compute scipy.stats.trim_mean per context
    length, then fit the power-law.  Returns exponent sensitivity.
    """
    result: dict[str, Any] = {}

    for pct in trim_pcts:
        trimmed_lats = []
        valid_ctx = []
        for ctx_val in sorted(ctx_lengths):
            vals = all_latencies[all_latencies["context_length"] == ctx_val][
                "latency_ms"
            ].values
            if len(vals) >= 3:
                trimmed_lats.append(float(stats.trim_mean(vals, pct)))
                valid_ctx.append(float(ctx_val))

        if len(valid_ctx) < 3:
            result[f"trim_{int(pct*100)}pct"] = {"error": "too_few_points"}
            continue

        ctx_arr = np.array(valid_ctx)
        lat_arr = np.array(trimmed_lats)

        try:
            with np.errstate(over="ignore"):
                popt, _ = curve_fit(
                    _power_law, ctx_arr, lat_arr, p0=[1e-3, 1.5], maxfev=5000
                )
            pred = _power_law(ctx_arr, *popt)
            ss_res = np.sum((lat_arr - pred) ** 2)
            ss_tot = np.sum((lat_arr - np.mean(lat_arr)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            result[f"trim_{int(pct*100)}pct"] = {
                "exponent_b": float(popt[1]),
                "a": float(popt[0]),
                "r_squared": float(r2),
                "n_points": len(valid_ctx),
            }
        except Exception as e:
            result[f"trim_{int(pct*100)}pct"] = {"error": str(e)}

    return result


def _full_summary(vals: list[float]) -> dict[str, Any]:
    """Compute mean, std, median, min, max, CI, p95, p99 for a list."""
    summary = compute_summary(vals)
    pcts = compute_percentiles(vals, [50, 95, 99])
    return {
        "mean": summary.mean,
        "median": summary.median,
        "std": summary.std,
        "min": summary.min,
        "max": summary.max,
        "ci_lower": summary.ci_lower,
        "ci_upper": summary.ci_upper,
        "p95": pcts["p95"],
        "p99": pcts["p99"],
        "n": summary.n,
    }


# ── Analysis sections ─────────────────────────────────────────────────


def _identify_thrashing_threshold(
    df_raw: pd.DataFrame,
    model: str,
    gpu_vram_mb: float = 12288.0,
) -> int | None:
    """Find the context length where CUDA allocation exceeds physical VRAM.

    Returns the first context_length where peak allocation > gpu_vram_mb,
    or None if all allocations fit in GPU.
    """
    hf = df_raw[
        (df_raw["model"] == model)
        & (df_raw["backend"] == "transformers-gpu")
        & (df_raw["status"] == "ok")
    ]
    if "vram_peak_mb" not in hf.columns:
        return None
    hf = hf.dropna(subset=["vram_peak_mb"])
    if hf.empty:
        return None

    agg = hf.groupby("context_length")["vram_peak_mb"].max().sort_index()
    for ctx, vram in agg.items():
        if vram > gpu_vram_mb:
            return int(ctx)
    return None


def analyze_cold_start(df: pd.DataFrame) -> dict[str, Any]:
    """Detect and characterize Ollama cold-start outliers (rep-0).

    Despite warmup repetitions, Ollama's first measured rep (rep-0) often
    shows 5-300x higher latency due to model loading, KV cache allocation,
    and GPU kernel compilation.  This function:

    1. Quantifies cold-start magnitude per model x context_length
    2. Computes trimmed means (excluding rep-0) vs full means
    3. Reports distribution shape (skewness, mean/median ratio)
    4. Recommends whether rep-0 should be filtered for each group
    """
    ollama = df[
        (df["backend"] == "ollama") & (df["status"] == "ok") & (df["mode"] == "prefill")
    ].dropna(subset=["latency_ms"])

    if ollama.empty:
        return {"note": "No Ollama prefill data available"}

    results: dict[str, Any] = {}
    total_cold_detected = 0
    total_groups = 0

    for model, model_grp in ollama.groupby("model"):
        model_results: dict[str, Any] = {}

        for cl, grp in model_grp.groupby("context_length"):
            total_groups += 1
            rep0 = grp[grp["rep"] == 0]["latency_ms"]
            rest = grp[grp["rep"] > 0]["latency_ms"]

            if rep0.empty or rest.empty:
                continue

            rep0_val = float(rep0.iloc[0])
            rest_median = float(rest.median())
            rest_mean = float(rest.mean())
            cold_ratio = rep0_val / rest_median if rest_median > 0 else 0

            is_cold = cold_ratio > 2.0  # >2x median = cold start
            if is_cold:
                total_cold_detected += 1

            # Full group stats
            all_vals = grp["latency_ms"].values
            clean_vals = rest.values

            all_mean = float(np.mean(all_vals))
            clean_mean = float(np.mean(clean_vals))
            mean_inflation = (
                (all_mean - clean_mean) / clean_mean * 100 if clean_mean > 0 else 0
            )

            model_results[int(cl)] = {
                "rep0_ms": round(rep0_val, 3),
                "rest_median_ms": round(rest_median, 3),
                "rest_mean_ms": round(rest_mean, 3),
                "cold_ratio": round(cold_ratio, 1),
                "is_cold_start": is_cold,
                "n_total": len(all_vals),
                "n_clean": len(clean_vals),
                "mean_with_rep0": round(all_mean, 3),
                "mean_without_rep0": round(clean_mean, 3),
                "mean_inflation_pct": round(mean_inflation, 1),
                "rest_cv_pct": (
                    round(100 * float(rest.std()) / rest_mean, 1)
                    if rest_mean > 0 and len(rest) > 1
                    else 0.0
                ),
            }

        results[model] = model_results

    results["_summary"] = {
        "total_groups": total_groups,
        "cold_starts_detected": total_cold_detected,
        "cold_start_pct": (
            round(100 * total_cold_detected / total_groups, 1)
            if total_groups > 0
            else 0.0
        ),
        "recommendation": (
            "Filter rep-0 from Ollama measurements. Cold-start inflates "
            "mean by 5-50% depending on context length. Median is robust "
            "but trimmed mean (excluding rep-0) is the preferred estimator."
        ),
    }

    return results


def analyze_prefill_scaling(
    df: pd.DataFrame,
    df_raw: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Fit prefill latency scaling for each model x backend.

    For HF models, also fits on pre-thrashing data only (context lengths
    where VRAM allocation stays within physical GPU memory).

    v2: Adds trimmed-mean robustness analysis for scaling exponents.
    """
    prefill = df[(df["mode"] == "prefill") & (df["status"] == "ok")]
    prefill = prefill.dropna(subset=["latency_ms"])
    results = {}

    for (model, backend), grp in prefill.groupby(["model", "backend"]):
        # Aggregate: median latency per context_length
        agg = grp.groupby("context_length")["latency_ms"].median().reset_index()
        ctx = agg["context_length"].values.astype(float)
        lat = agg["latency_ms"].values.astype(float)

        key = f"{model}__{backend}"
        results[key] = _fit_scaling(ctx, lat)

        # For HF backend, separate clean scaling from thrashing regime
        if backend == "transformers-gpu" and df_raw is not None:
            thresh = _identify_thrashing_threshold(df_raw, model)
            if thresh is not None:
                results[key]["thrashing_threshold"] = thresh
                # Fit on clean data only (before thrashing)
                mask = ctx < thresh
                if mask.sum() >= 3:
                    clean_fit = _fit_scaling(ctx[mask], lat[mask])
                    results[key]["clean_scaling"] = clean_fit
                    results[key]["clean_context_lengths"] = (
                        ctx[mask].astype(int).tolist()
                    )
                # Compute thrashing multiplier
                if mask.sum() >= 1 and (~mask).sum() >= 1:
                    last_clean = lat[mask][-1]
                    first_thrash = lat[~mask][0]
                    results[key]["thrashing_multiplier"] = round(
                        float(first_thrash / last_clean), 1
                    )

        # Trimmed-mean robustness for scaling exponent
        ctx_unique = grp["context_length"].unique()
        trimmed = _fit_scaling_trimmed(ctx_unique, grp)
        if trimmed:
            results[key]["trimmed_mean_fits"] = trimmed

        # Per-context-length full summaries
        per_ctx = {}
        for cl, subgrp in grp.groupby("context_length"):
            per_ctx[int(cl)] = _full_summary(subgrp["latency_ms"].tolist())
        results[key]["per_context_length"] = per_ctx

    return results


def analyze_decode_scaling(
    df: pd.DataFrame,
    df_raw: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Fit decode latency and throughput scaling.

    v2: Adds two-regime analysis for HF models (pre/post VRAM spillover)
    and trimmed-mean robustness for scaling exponents.
    """
    decode = df[(df["mode"] == "decode") & (df["status"] == "ok")]
    decode = decode.dropna(subset=["latency_ms"])
    results = {}

    for (model, backend), grp in decode.groupby(["model", "backend"]):
        agg = grp.groupby("context_length")["latency_ms"].median().reset_index()
        ctx = agg["context_length"].values.astype(float)
        lat = agg["latency_ms"].values.astype(float)

        key = f"{model}__{backend}"
        results[key] = _fit_scaling(ctx, lat)

        # Two-regime decode analysis for HF backend
        if backend == "transformers-gpu" and df_raw is not None:
            thresh = _identify_thrashing_threshold(df_raw, model)
            if thresh is not None:
                results[key]["thrashing_threshold"] = thresh
                mask = ctx < thresh
                if mask.sum() >= 3:
                    clean_fit = _fit_scaling(ctx[mask], lat[mask])
                    results[key]["clean_scaling"] = clean_fit
                    results[key]["clean_context_lengths"] = (
                        ctx[mask].astype(int).tolist()
                    )
                # Decode thrashing multiplier
                if mask.sum() >= 1 and (~mask).sum() >= 1:
                    last_clean = lat[mask][-1]
                    first_thrash = lat[~mask][0]
                    results[key]["thrashing_multiplier"] = round(
                        float(first_thrash / last_clean), 1
                    )

        # Trimmed-mean robustness for decode scaling exponent
        ctx_unique = grp["context_length"].unique()
        trimmed = _fit_scaling_trimmed(ctx_unique, grp)
        if trimmed:
            results[key]["trimmed_mean_fits"] = trimmed

        # Throughput + latency per context length with full stats
        per_ctx = {}
        for cl, subgrp in grp.groupby("context_length"):
            lat_vals = subgrp["latency_ms"].tolist()
            tps_vals = subgrp["tokens_per_s"].tolist()
            lat_stats = _full_summary(lat_vals)
            tps_stats = _full_summary(tps_vals)
            per_ctx[int(cl)] = {
                "latency_mean": lat_stats["mean"],
                "latency_median": lat_stats["median"],
                "latency_std": lat_stats["std"],
                "latency_ci_lower": lat_stats["ci_lower"],
                "latency_ci_upper": lat_stats["ci_upper"],
                "latency_p95": lat_stats["p95"],
                "latency_p99": lat_stats["p99"],
                "throughput_mean": tps_stats["mean"],
                "throughput_median": tps_stats["median"],
                "throughput_std": tps_stats["std"],
                "throughput_p95": tps_stats["p95"],
                "n": lat_stats["n"],
            }
        results[key]["per_context_length"] = per_ctx

    return results


def analyze_vram_scaling(
    df: pd.DataFrame, gpu_vram_mb: float = 12288.0
) -> dict[str, Any]:
    """VRAM peak vs context length, cliff detection, spillover analysis.

    Note: ``vram_peak_mb`` is ``torch.cuda.max_memory_allocated()`` which
    includes CUDA Unified Memory spillover to system RAM.  Values exceeding
    ``gpu_vram_mb`` indicate system-memory paging, not physical GPU usage.
    """
    hf = df[(df["backend"] == "transformers-gpu") & (df["status"] == "ok")]
    hf = hf.dropna(subset=["vram_peak_mb"])
    results = {}

    for model, grp in hf.groupby("model"):
        agg = grp.groupby("context_length")["vram_peak_mb"].max().reset_index()
        ctx = agg["context_length"].values.astype(float)
        vram = agg["vram_peak_mb"].values.astype(float)

        fit = {}
        if len(ctx) >= 2:
            slope, intercept, r, p, _se = stats.linregress(ctx, vram)
            fit = {
                "slope_mb_per_token": float(slope),
                "intercept_mb": float(intercept),
                "r_squared": float(r**2),
                "p_value": float(p),
            }

        # OOM cliff: find shortest context_length with OOM
        oom_rows = df[
            (df["model"] == model)
            & (df["backend"] == "transformers-gpu")
            & (df["status"].isin(["oom", "exceeds_max_context"]))
        ]
        oom_cliff = int(oom_rows["context_length"].min()) if len(oom_rows) > 0 else None

        # Physical VRAM threshold (11.5 GB)
        vram_cliff = None
        for cl, v in zip(ctx, vram, strict=False):
            if v > 11500:
                vram_cliff = int(cl)
                break

        # Spillover detection: where allocation exceeds physical GPU
        spillover_threshold = None
        spillover_ratio = None
        for cl, v in zip(ctx, vram, strict=False):
            if v > gpu_vram_mb:
                spillover_threshold = int(cl)
                spillover_ratio = round(float(v / gpu_vram_mb), 2)
                break

        per_ctx = {}
        for cl, subgrp in grp.groupby("context_length"):
            vals = subgrp["vram_peak_mb"].tolist()
            peak = float(max(vals))
            per_ctx[int(cl)] = {
                "max_mb": peak,
                "mean_mb": float(np.mean(vals)),
                "min_mb": float(min(vals)),
                "in_gpu": peak <= gpu_vram_mb,
                "spillover_gb": round(max(0, (peak - gpu_vram_mb)) / 1024, 2),
            }

        # KV cache per-token cost estimate (from VRAM growth)
        kv_cost_bytes_per_token = None
        if len(ctx) >= 2:
            # Use adjacent in-GPU points for clean estimate
            in_gpu_mask = vram <= gpu_vram_mb
            if in_gpu_mask.sum() >= 2:
                in_ctx = ctx[in_gpu_mask]
                in_vram = vram[in_gpu_mask]
                # MB per token from regression on clean data
                slope_clean, _, _, _, _ = stats.linregress(in_ctx, in_vram)
                kv_cost_bytes_per_token = round(slope_clean * 1024 * 1024, 0)

        results[model] = {
            "linear_fit": fit,
            "oom_cliff": oom_cliff,
            "vram_cliff_11_5gb": vram_cliff,
            "spillover_threshold": spillover_threshold,
            "spillover_ratio": spillover_ratio,
            "kv_cache_bytes_per_token": kv_cost_bytes_per_token,
            "gpu_vram_mb": gpu_vram_mb,
            "per_context_length": per_ctx,
            "note": (
                "vram_peak_mb is torch.cuda.max_memory_allocated() which "
                "includes CUDA Unified Memory spillover to system RAM. "
                "Values exceeding GPU physical VRAM indicate paging."
            ),
        }

    return results


def analyze_kv_cross_validation(
    vram_scaling: dict[str, Any],
) -> dict[str, Any]:
    """Cross-validate empirical KV cache costs with theoretical predictions.

    Theoretical KV cost per token = n_layers * n_kv_heads * head_dim * 2
    (keys + values) * precision_bytes (2 for FP16).

    Model architectures (from config.json):
      qwen2.5-0.5b: 24 layers, 2 kv_heads, 64 head_dim
      qwen2.5-1.5b: 28 layers, 2 kv_heads, 128 head_dim
      qwen2.5-3b:   36 layers, 2 kv_heads, 128 head_dim
    """
    # Theoretical KV cost per token per layer-head:
    #   per_head_per_layer = head_dim * 2_bytes (FP16) * 2 (K+V)
    model_arch = {
        "qwen2.5-0.5b": {
            "n_layers": 24,
            "n_kv_heads": 2,
            "head_dim": 64,
            "precision_bytes": 2,
        },
        "qwen2.5-1.5b": {
            "n_layers": 28,
            "n_kv_heads": 2,
            "head_dim": 128,
            "precision_bytes": 2,
        },
        "qwen2.5-3b": {
            "n_layers": 36,
            "n_kv_heads": 2,
            "head_dim": 128,
            "precision_bytes": 2,
        },
    }

    results: dict[str, Any] = {}

    for model_name, arch in model_arch.items():
        theoretical_bytes = (
            arch["n_layers"]
            * arch["n_kv_heads"]
            * arch["head_dim"]
            * 2  # K + V tensors
            * arch["precision_bytes"]
        )

        vram_info = vram_scaling.get(model_name, {})
        empirical_bytes = vram_info.get("kv_cache_bytes_per_token")

        if empirical_bytes is not None:
            overhead_ratio = empirical_bytes / theoretical_bytes
            overhead_pct = (overhead_ratio - 1) * 100
        else:
            overhead_ratio = None
            overhead_pct = None

        results[model_name] = {
            "architecture": arch,
            "theoretical_kv_bytes_per_token": theoretical_bytes,
            "empirical_kv_bytes_per_token": empirical_bytes,
            "overhead_ratio": (
                round(overhead_ratio, 2) if overhead_ratio is not None else None
            ),
            "overhead_pct": (
                round(overhead_pct, 1) if overhead_pct is not None else None
            ),
            "note": (
                "Overhead includes CUDA allocator fragmentation, "
                "activation memory, and attention workspace. "
                f"Theoretical: {theoretical_bytes:,} B/token = "
                f"{arch['n_layers']}L x {arch['n_kv_heads']}KV x "
                f"{arch['head_dim']}d x 2(K+V) x "
                f"{arch['precision_bytes']}B(FP16)"
            ),
        }

    return results


def analyze_ttft(df: pd.DataFrame) -> dict[str, Any]:
    """TTFT = prefill latency analysis with threshold identification."""
    prefill = df[(df["mode"] == "prefill") & (df["status"] == "ok")]
    prefill = prefill.dropna(subset=["latency_ms"])
    results = {}
    thresholds_ms = [1000, 5000, 10000]  # 1s, 5s, 10s

    for (model, backend), grp in prefill.groupby(["model", "backend"]):
        key = f"{model}__{backend}"
        per_ctx = {}
        threshold_crossings = dict.fromkeys(thresholds_ms)

        for cl in sorted(grp["context_length"].unique()):
            vals = grp[grp["context_length"] == cl]["latency_ms"].tolist()
            s = _full_summary(vals)
            per_ctx[int(cl)] = {
                "mean_ms": s["mean"],
                "median_ms": s["median"],
                "ci_lower": s["ci_lower"],
                "ci_upper": s["ci_upper"],
                "std": s["std"],
                "p95": s["p95"],
                "p99": s["p99"],
                "n": s["n"],
            }
            # Check thresholds
            for t in thresholds_ms:
                if threshold_crossings[t] is None and s["mean"] >= t:
                    threshold_crossings[t] = int(cl)

        results[key] = {
            "per_context_length": per_ctx,
            "threshold_crossings": {
                f">{t}ms": threshold_crossings[t] for t in thresholds_ms
            },
        }

    return results


def analyze_backend_comparison(df: pd.DataFrame) -> dict[str, Any]:
    """Compare HF vs Ollama at each context length for shared models."""
    results = {}
    ok = df[df["status"] == "ok"]

    for mode in ["prefill", "decode", "e2e"]:
        mode_df = ok[ok["mode"] == mode]
        mode_results = {}

        # Find models present on both backends
        models_per_backend = mode_df.groupby("backend")["model"].unique()
        if (
            "transformers-gpu" not in models_per_backend.index
            or "ollama" not in models_per_backend.index
        ):
            continue
        shared_models = set(models_per_backend["transformers-gpu"]) & set(
            models_per_backend["ollama"]
        )

        for model in shared_models:
            model_results = {}
            for cl in sorted(mode_df["context_length"].unique()):
                hf_vals = mode_df[
                    (mode_df["model"] == model)
                    & (mode_df["backend"] == "transformers-gpu")
                    & (mode_df["context_length"] == cl)
                ]["latency_ms"].tolist()
                ol_vals = mode_df[
                    (mode_df["model"] == model)
                    & (mode_df["backend"] == "ollama")
                    & (mode_df["context_length"] == cl)
                ]["latency_ms"].tolist()

                if len(hf_vals) >= 2 and len(ol_vals) >= 2:
                    cmp = compare_groups(
                        hf_vals,
                        ol_vals,
                        "transformers-gpu",
                        "ollama",
                        f"latency_ms@{cl}",
                    )
                    model_results[int(cl)] = {
                        "hf_mean": cmp.mean_a,
                        "ollama_mean": cmp.mean_b,
                        "difference_ms": cmp.difference,
                        "percent_change": cmp.percent_change,
                        "p_value": cmp.p_value,
                        "significant": cmp.significant,
                        "cohens_d": cmp.effect_size,
                        "effect_label": effect_label(cmp.effect_size),
                    }

            if model_results:
                model_results = dict(sorted(model_results.items()))
            mode_results[model] = model_results

        results[mode] = mode_results

    return results


def analyze_multiple_comparisons(backend_comparison: dict[str, Any]) -> dict[str, Any]:
    """Apply Bonferroni and Holm-Bonferroni corrections to backend comparisons.

    Collects all p-values from pairwise t-tests, applies family-wise error
    rate corrections, and reports which results survive.
    """
    # Collect all p-values with labels
    all_tests: list[dict[str, Any]] = []

    for mode, models in backend_comparison.items():
        for model, per_ctx in models.items():
            for cl, test_data in per_ctx.items():
                all_tests.append(
                    {
                        "mode": mode,
                        "model": model,
                        "context_length": cl,
                        "p_value": test_data["p_value"],
                        "cohens_d": test_data["cohens_d"],
                        "uncorrected_significant": test_data["significant"],
                    }
                )

    n_tests = len(all_tests)
    if n_tests == 0:
        return {"note": "No pairwise tests to correct"}

    alpha = 0.05

    # Bonferroni correction: reject if p < alpha / n_tests
    bonferroni_threshold = alpha / n_tests
    for t in all_tests:
        t["bonferroni_significant"] = t["p_value"] < bonferroni_threshold

    # Holm-Bonferroni (step-down): sort by p-value, reject p_i < alpha/(n-i)
    sorted_tests = sorted(all_tests, key=lambda x: x["p_value"])
    for i, t in enumerate(sorted_tests):
        holm_threshold = alpha / (n_tests - i)
        t["holm_rank"] = i + 1
        t["holm_threshold"] = round(holm_threshold, 6)
        # Holm: reject if all previous (smaller p) were rejected
        if i == 0:
            t["holm_significant"] = t["p_value"] < holm_threshold
        else:
            prev_rejected = sorted_tests[i - 1]["holm_significant"]
            t["holm_significant"] = prev_rejected and t["p_value"] < holm_threshold

    # Summary counts
    n_uncorrected_sig = sum(1 for t in all_tests if t["uncorrected_significant"])
    n_bonferroni_sig = sum(1 for t in all_tests if t["bonferroni_significant"])
    n_holm_sig = sum(1 for t in all_tests if t["holm_significant"])

    return {
        "n_tests": n_tests,
        "alpha": alpha,
        "bonferroni_threshold": round(bonferroni_threshold, 6),
        "uncorrected_significant": n_uncorrected_sig,
        "bonferroni_significant": n_bonferroni_sig,
        "holm_significant": n_holm_sig,
        "tests": sorted_tests,
        "interpretation": (
            f"Of {n_tests} pairwise tests, {n_uncorrected_sig} significant "
            f"at p<0.05 uncorrected. After Bonferroni correction "
            f"(threshold={bonferroni_threshold:.4f}), {n_bonferroni_sig} "
            f"survive. After Holm-Bonferroni (less conservative), "
            f"{n_holm_sig} survive."
        ),
    }


def analyze_anova_interaction(df: pd.DataFrame) -> dict[str, Any]:
    """Two-way ANOVA: context_length x backend interaction for shared models.

    Tests whether the effect of backend depends on context length (interaction).
    Uses Type II SS via manual sum-of-squares decomposition since we only have
    two backends (no need for statsmodels).
    """
    ok = df[(df["status"] == "ok") & (df["mode"].isin(["prefill", "decode"]))]
    ok = ok.dropna(subset=["latency_ms"])
    results: dict[str, Any] = {}

    for mode in ["prefill", "decode"]:
        mode_df = ok[ok["mode"] == mode]
        mode_results: dict[str, Any] = {}

        # Find shared models
        models_per_backend = mode_df.groupby("backend")["model"].unique()
        if (
            "transformers-gpu" not in models_per_backend.index
            or "ollama" not in models_per_backend.index
        ):
            continue
        shared_models = set(models_per_backend["transformers-gpu"]) & set(
            models_per_backend["ollama"]
        )

        for model in shared_models:
            model_df = mode_df[mode_df["model"] == model]

            # One-way ANOVA: backend effect (collapsing across contexts)
            groups_backend = {}
            for backend, bgrp in model_df.groupby("backend"):
                groups_backend[backend] = bgrp["latency_ms"].values

            if len(groups_backend) < 2:
                continue

            try:
                f_backend, p_backend = stats.f_oneway(*groups_backend.values())
            except Exception:
                continue

            # One-way ANOVA: context_length effect
            groups_ctx = {}
            for cl, cgrp in model_df.groupby("context_length"):
                groups_ctx[int(cl)] = cgrp["latency_ms"].values

            try:
                f_ctx, p_ctx = stats.f_oneway(*groups_ctx.values())
            except Exception:
                f_ctx, p_ctx = 0.0, 1.0

            # Interaction test: within each context, test backend effect
            # Report per-context F-statistics to show interaction pattern
            per_ctx_backend_f: dict[int, dict] = {}
            for cl in sorted(model_df["context_length"].unique()):
                cl_df = model_df[model_df["context_length"] == cl]
                hf_vals = cl_df[cl_df["backend"] == "transformers-gpu"][
                    "latency_ms"
                ].values
                ol_vals = cl_df[cl_df["backend"] == "ollama"]["latency_ms"].values

                if len(hf_vals) >= 2 and len(ol_vals) >= 2:
                    t_stat, p_val = stats.ttest_ind(hf_vals, ol_vals)
                    per_ctx_backend_f[int(cl)] = {
                        "t_statistic": round(float(t_stat), 3),
                        "p_value": round(float(p_val), 6),
                        "significant": float(p_val) < 0.05,
                        "hf_mean": round(float(np.mean(hf_vals)), 2),
                        "ollama_mean": round(float(np.mean(ol_vals)), 2),
                    }

            # Interaction evidence: does the direction/magnitude of backend
            # effect change across context lengths?
            sig_at = [cl for cl, v in per_ctx_backend_f.items() if v["significant"]]
            nonsig_at = [
                cl for cl, v in per_ctx_backend_f.items() if not v["significant"]
            ]

            interaction_evidence = "none"
            if sig_at and nonsig_at:
                interaction_evidence = "moderate"
            elif len(sig_at) == len(per_ctx_backend_f) and len(sig_at) > 0:
                # Check if effect size changes direction or magnitude
                effects = [
                    v["hf_mean"] - v["ollama_mean"] for v in per_ctx_backend_f.values()
                ]
                if effects:
                    signs = [1 if e > 0 else -1 for e in effects]
                    if len(set(signs)) > 1:
                        interaction_evidence = "strong (direction reversal)"
                    else:
                        ratio = max(abs(e) for e in effects) / (
                            min(abs(e) for e in effects) + 1e-6
                        )
                        interaction_evidence = (
                            "strong (magnitude change)" if ratio > 5 else "weak"
                        )

            mode_results[model] = {
                "backend_effect": {
                    "f_statistic": round(float(f_backend), 3),
                    "p_value": round(float(p_backend), 6),
                    "significant": float(p_backend) < 0.05,
                },
                "context_length_effect": {
                    "f_statistic": round(float(f_ctx), 3),
                    "p_value": round(float(p_ctx), 6),
                    "significant": float(p_ctx) < 0.05,
                },
                "per_context_backend_test": per_ctx_backend_f,
                "interaction_evidence": interaction_evidence,
                "significant_at_contexts": sig_at,
                "nonsignificant_at_contexts": nonsig_at,
            }

        results[mode] = mode_results

    return results


def analyze_distribution_shape(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze distribution shape per model x backend x mode.

    Reports skewness, kurtosis, mean/median ratio (>1 indicates right skew),
    and Shapiro-Wilk normality test.
    """
    ok = df[df["status"] == "ok"].dropna(subset=["latency_ms"])
    results: dict[str, Any] = {}

    for (model, backend, mode), grp in ok.groupby(["model", "backend", "mode"]):
        key = f"{model}__{backend}__{mode}"
        per_ctx: dict[int, dict] = {}

        for cl, subgrp in grp.groupby("context_length"):
            vals = subgrp["latency_ms"].values
            n = len(vals)

            if n < 3:
                continue

            mean_val = float(np.mean(vals))
            median_val = float(np.median(vals))
            mm_ratio = mean_val / median_val if median_val > 0 else 0

            skew = float(stats.skew(vals)) if n >= 8 else None
            kurt = float(stats.kurtosis(vals)) if n >= 8 else None

            # Shapiro-Wilk (only meaningful for n >= 3)
            try:
                sw_stat, sw_p = stats.shapiro(vals)
                shapiro = {
                    "statistic": round(float(sw_stat), 4),
                    "p_value": round(float(sw_p), 4),
                    "normal": float(sw_p) >= 0.05,
                }
            except Exception:
                shapiro = None

            per_ctx[int(cl)] = {
                "n": n,
                "mean_median_ratio": round(mm_ratio, 4),
                "skewness": round(skew, 4) if skew is not None else None,
                "kurtosis": round(kurt, 4) if kurt is not None else None,
                "shapiro_wilk": shapiro,
            }

        # Group-level shape (pooled across context lengths — less meaningful
        # but useful for quick overview)
        all_vals = grp["latency_ms"].values
        if len(all_vals) >= 8:
            group_skew = float(stats.skew(all_vals))
            group_mm = float(np.mean(all_vals) / np.median(all_vals))
        else:
            group_skew = None
            group_mm = None

        results[key] = {
            "pooled_skewness": (
                round(group_skew, 4) if group_skew is not None else None
            ),
            "pooled_mean_median_ratio": (
                round(group_mm, 4) if group_mm is not None else None
            ),
            "per_context_length": per_ctx,
        }

    return results


def analyze_cross_model(df: pd.DataFrame) -> dict[str, Any]:
    """Rank models at each context length by latency."""
    ok = df[df["status"] == "ok"]
    results = {}

    for mode in ["prefill", "decode"]:
        mode_df = ok[ok["mode"] == mode]
        rankings = {}

        for cl in sorted(mode_df["context_length"].unique()):
            cl_df = mode_df[mode_df["context_length"] == cl]
            ranking = (
                cl_df.groupby(["model", "backend"])["latency_ms"]
                .mean()
                .sort_values()
                .reset_index()
            )
            rankings[int(cl)] = [
                {
                    "model": row["model"],
                    "backend": row["backend"],
                    "mean_latency_ms": round(row["latency_ms"], 2),
                }
                for _, row in ranking.iterrows()
            ]

        results[mode] = rankings

    return results


def analyze_outliers(df: pd.DataFrame) -> dict[str, Any]:
    """Detect outliers per model x backend x mode x context_length.

    Per-context-length detection avoids false positives from pooling
    heterogeneous measurement regimes (e.g. 50ms at 512 tokens vs
    470,000ms at 16K tokens).
    """
    ok = df[df["status"] == "ok"].dropna(subset=["latency_ms"])
    results = {}
    total_measured = 0
    total_outliers = 0

    for (model, backend, mode), grp in ok.groupby(["model", "backend", "mode"]):
        key = f"{model}__{backend}__{mode}"
        per_ctx_outliers = {}
        group_total = 0
        group_outliers = 0

        for cl, subgrp in grp.groupby("context_length"):
            vals = subgrp["latency_ms"].tolist()
            group_total += len(vals)
            if len(vals) < 4:
                continue
            det = detect_outliers(vals, method="iqr")
            if det["count"] > 0:
                per_ctx_outliers[int(cl)] = {
                    "n": len(vals),
                    "n_outliers": det["count"],
                    "outlier_values": [round(v, 2) for v in det["outliers"]],
                }
                group_outliers += det["count"]

        total_measured += group_total
        total_outliers += group_outliers
        results[key] = {
            "n_total": group_total,
            "n_outliers": group_outliers,
            "outlier_pct": (
                round(100.0 * group_outliers / group_total, 1)
                if group_total > 0
                else 0.0
            ),
            "per_context_length": per_ctx_outliers,
        }

    results["_summary"] = {
        "total_measured": total_measured,
        "total_outliers": total_outliers,
        "overall_outlier_pct": (
            round(100.0 * total_outliers / total_measured, 2)
            if total_measured > 0
            else 0.0
        ),
        "method": "IQR per context_length (not pooled)",
    }

    return results


def analyze_power(df: pd.DataFrame, repetitions: int = 5) -> dict[str, Any]:
    """Power analysis — stratified by model x backend for meaningful results.

    Reports per-stratum detectable effect sizes instead of a single pooled
    number that mixes heterogeneous measurement regimes.
    """
    n = repetitions
    alpha = 0.05
    power = 0.80

    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    min_d = (z_alpha + z_beta) * np.sqrt(2 / n)

    t_crit = stats.t.ppf(1 - alpha / 2, df=2 * n - 2)
    min_d_t = t_crit * np.sqrt(2 / n)

    # Classify sensitivity
    if min_d < 0.5:
        sensitivity = "small effects"
    elif min_d < 0.8:
        sensitivity = "medium effects"
    else:
        sensitivity = "large effects only"

    # Stratified analysis per model x backend
    ok = df[(df["status"] == "ok") & (df["mode"] == "prefill")]
    ok = ok.dropna(subset=["latency_ms"])

    strata = {}
    for (model, backend), grp in ok.groupby(["model", "backend"]):
        stratum_std = float(grp["latency_ms"].std()) if len(grp) > 1 else 0.0
        stratum_mean = float(grp["latency_ms"].mean())
        min_det_ms = min_d * stratum_std
        key = f"{model}__{backend}"

        # Per-context-length std (more meaningful — within-group variation)
        per_ctx_stds = {}
        for cl, subgrp in grp.groupby("context_length"):
            if len(subgrp) > 1:
                ctx_std = float(subgrp["latency_ms"].std())
                per_ctx_stds[int(cl)] = {
                    "std_ms": round(ctx_std, 2),
                    "min_detectable_ms": round(min_d * ctx_std, 2),
                    "cv_pct": (
                        round(100 * ctx_std / subgrp["latency_ms"].mean(), 1)
                        if subgrp["latency_ms"].mean() > 0
                        else 0.0
                    ),
                }

        strata[key] = {
            "pooled_std_ms": round(stratum_std, 2),
            "mean_ms": round(stratum_mean, 2),
            "min_detectable_ms": round(min_det_ms, 2),
            "n_measurements": len(grp),
            "per_context_length": per_ctx_stds,
        }

    # Also compute overall pooled for reference
    pooled_std = float(ok["latency_ms"].std()) if len(ok) > 1 else 0.0

    return {
        "repetitions": n,
        "alpha": alpha,
        "power": power,
        "min_cohens_d_z": round(float(min_d), 3),
        "min_cohens_d_t": round(float(min_d_t), 3),
        "sensitivity": sensitivity,
        "overall_pooled_std_ms": round(pooled_std, 2),
        "note": (
            "Overall pooled std mixes heterogeneous regimes (8ms Ollama "
            "to 533,000ms HF-thrashing). Per-stratum and per-context-length "
            "values are the meaningful power indicators."
        ),
        "strata": strata,
        "interpretation": (
            f"At N={n} reps (power={power:.0%}, alpha={alpha}), the minimum "
            f"detectable Cohen's d is {min_d:.2f} ({sensitivity}). "
            f"See per-stratum breakdown for meaningful detectable differences."
        ),
    }


# ── main ──────────────────────────────────────────────────────────────


def run_analysis(run_dir: Path) -> Path:
    """Run all analyses and save analysis.json.  Returns output path."""
    metrics_path = run_dir / "metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"No metrics.csv in {run_dir}")

    # Load raw (all rows) for summary + VRAM cliff detection (needs OOM rows)
    df_raw = load_metrics_csv(metrics_path, filter_ok=False)
    # Load filtered (ok only) for statistical analyses
    df = load_metrics_csv(metrics_path, filter_ok=True)
    log.info("Loaded %d total rows (%d ok) from %s", len(df_raw), len(df), metrics_path)

    # Read repetitions from manifest if available
    reps = 10
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open() as f:
            manifest = json.load(f)
        reps = manifest.get("config", {}).get("repetitions", 10)

    # Core analyses
    backend_cmp = analyze_backend_comparison(df)
    vram_scaling = analyze_vram_scaling(df_raw)

    analysis = {
        "summary": {
            "total_rows": len(df_raw),
            "ok_rows": len(df),
            "models": sorted(df_raw["model"].unique().tolist()),
            "backends": sorted(df_raw["backend"].unique().tolist()),
            "context_lengths": sorted(
                int(x) for x in df_raw["context_length"].unique()
            ),
            "status_counts": df_raw["status"].value_counts().to_dict(),
        },
        "cold_start_analysis": analyze_cold_start(df),
        "prefill_scaling": analyze_prefill_scaling(df, df_raw=df_raw),
        "decode_scaling": analyze_decode_scaling(df, df_raw=df_raw),
        "vram_scaling": vram_scaling,
        "kv_cross_validation": analyze_kv_cross_validation(vram_scaling),
        "ttft_analysis": analyze_ttft(df),
        "backend_comparison": backend_cmp,
        "multiple_comparisons": analyze_multiple_comparisons(backend_cmp),
        "anova_interaction": analyze_anova_interaction(df),
        "distribution_shape": analyze_distribution_shape(df),
        "cross_model_ranking": analyze_cross_model(df),
        "outlier_analysis": analyze_outliers(df),
        "power_analysis": analyze_power(df, repetitions=reps),
    }

    out_path = run_dir / "analysis.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)
    log.info("Analysis -> %s", out_path)

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR127 analysis")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Specific run directory (default: latest)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    run_dir = args.run_dir or find_latest_run(TR127_RESULTS)
    if run_dir is None:
        log.error("No run directory found in %s", TR127_RESULTS)
        return 1

    run_analysis(Path(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
