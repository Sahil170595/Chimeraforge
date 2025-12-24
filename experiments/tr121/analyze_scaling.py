#!/usr/bin/env python3
"""
TR121: Analyze scaling run artifacts.

Input:
  - <run_dir>/metrics.csv (from run_scaling.py)

Outputs (under <run_dir>/analysis):
  - summary_by_model_backend_mode.csv
  - summary_by_model_backend_mode_agg.csv
  - scaling_fits.csv
  - overhead_compute_fits.csv
  - cuda_event_gap_summary.csv (if cuda_event_ms exists)
  - warmup_effect.csv (if warmup rows exist)
  - ollama_warmup_breakdown.csv (if Ollama warmup rows exist)
  - ollama_early_stop_summary.csv (if Ollama rows exist)
  - ollama_decode_linearity.csv (if Ollama rows exist)
  - ollama_decode_projection_error.csv (if Ollama rows exist)
  - hf_multivariate_fits.csv (if HF arch data exists)
  - plots/*.png (if matplotlib is available)
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:  # Optional but available in the TR121 environment.
    from scipy.optimize import curve_fit  # type: ignore
    from scipy.stats import spearmanr, theilslopes  # type: ignore
except Exception:  # pragma: no cover
    curve_fit = None  # type: ignore
    spearmanr = None  # type: ignore
    theilslopes = None  # type: ignore

try:
    # NumPy changed where RankWarning is defined across versions.
    from numpy.polynomial.polyutils import RankWarning as _NpRankWarning  # type: ignore
except Exception:  # pragma: no cover
    _NpRankWarning = Warning  # type: ignore


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fit_power_law(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    # Fit log10(y) = a + b*log10(x)
    x = x.astype(float)
    y = y.astype(float)
    m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    x = x[m]
    y = y[m]
    if x.size < 2:
        return {"ok": False}
    lx = np.log10(x)
    ly = np.log10(y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", _NpRankWarning)
        b, a = np.polyfit(lx, ly, deg=1)
    yhat = a + b * lx
    ss_res = float(np.sum((ly - yhat) ** 2))
    ss_tot = float(np.sum((ly - float(np.mean(ly))) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {
        "ok": True,
        "log10_intercept": float(a),
        "slope": float(b),
        "r2": float(r2),
    }


def _bootstrap_power_law_ci(
    *,
    x: np.ndarray,
    y: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    x = x.astype(float)
    y = y.astype(float)
    m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    x = x[m]
    y = y[m]
    if x.size < 3 or n_boot <= 0:
        return {}

    rng = np.random.default_rng(seed)
    slopes: list[float] = []
    intercepts: list[float] = []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, x.size, size=x.size)
        fit = _fit_power_law(x[idx], y[idx])
        if not fit.get("ok"):
            continue
        slopes.append(float(fit["slope"]))
        intercepts.append(float(fit["log10_intercept"]))
    if len(slopes) < max(10, int(n_boot) // 10):
        return {}

    return {
        "slope_ci_low": float(np.quantile(np.asarray(slopes), 0.025)),
        "slope_ci_high": float(np.quantile(np.asarray(slopes), 0.975)),
        "log10_intercept_ci_low": float(np.quantile(np.asarray(intercepts), 0.025)),
        "log10_intercept_ci_high": float(np.quantile(np.asarray(intercepts), 0.975)),
        "boot_n_used": int(len(slopes)),
        "boot_n_requested": int(n_boot),
    }


def _geomean(arr: np.ndarray) -> float:
    arr = arr.astype(float)
    arr = arr[np.isfinite(arr) & (arr > 0)]
    if arr.size == 0:
        return float("nan")
    return float(np.exp(np.mean(np.log(arr))))


def _fit_linear(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    x = x.astype(float)
    y = y.astype(float)
    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]
    if x.size < 2:
        return {"ok": False}
    X = np.column_stack([np.ones_like(x), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    a = float(beta[0])
    b = float(beta[1])
    yhat = X @ beta
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {"ok": True, "a": a, "b": b, "r2": float(r2)}


def _fit_log_multivariate(
    *,
    x_params_m: np.ndarray,
    x_layers: np.ndarray,
    y_latency_ms: np.ndarray,
) -> dict[str, Any]:
    x_params_m = x_params_m.astype(float)
    x_layers = x_layers.astype(float)
    y_latency_ms = y_latency_ms.astype(float)
    m = (
        np.isfinite(x_params_m)
        & np.isfinite(x_layers)
        & np.isfinite(y_latency_ms)
        & (x_params_m > 0)
        & (x_layers > 0)
        & (y_latency_ms > 0)
    )
    x_params_m = x_params_m[m]
    x_layers = x_layers[m]
    y_latency_ms = y_latency_ms[m]
    if x_params_m.size < 3:
        return {"ok": False}

    X = np.column_stack([np.ones_like(x_params_m), np.log(x_params_m), np.log(x_layers)])
    y = np.log(y_latency_ms)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    yhat = X @ beta
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {
        "ok": True,
        "alpha": float(beta[0]),
        "beta_log_params": float(beta[1]),
        "gamma_log_layers": float(beta[2]),
        "r2": float(r2),
    }


def _fit_loglog_robust(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    x = x.astype(float)
    y = y.astype(float)
    m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    x = x[m]
    y = y[m]
    if x.size < 3:
        return {}

    lx = np.log10(x)
    ly = np.log10(y)
    out: dict[str, Any] = {}
    if spearmanr is not None:
        try:
            rho, p = spearmanr(lx, ly)
            out["spearman_rho_loglog"] = float(rho)
            out["spearman_p_loglog"] = float(p)
        except Exception:
            pass
    if theilslopes is not None:
        try:
            ts = theilslopes(ly, lx, 0.95)
            out["theilsen_slope"] = float(ts.slope)
            out["theilsen_log10_intercept"] = float(ts.intercept)
            out["theilsen_slope_ci_low"] = float(ts.low_slope)
            out["theilsen_slope_ci_high"] = float(ts.high_slope)
        except Exception:
            pass
    return out


def _fit_offset_linear(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    x = x.astype(float)
    y = y.astype(float)
    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]
    if x.size < 2:
        return {"ok": False}
    A = np.stack([np.ones_like(x), x], axis=1)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    a = float(coef[0])
    b = float(coef[1])
    yhat = a + b * x
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {"ok": True, "a_ms": a, "b_ms_per_million_params": b, "r2": r2}


def _fit_offset_power(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    x = x.astype(float)
    y = y.astype(float)
    m = np.isfinite(x) & np.isfinite(y) & (x > 0)
    x = x[m]
    y = y[m]
    if x.size < 3:
        return {"ok": False}

    def f(xx: np.ndarray, a: float, b: float, s: float) -> np.ndarray:
        return a + b * (xx**s)

    if curve_fit is None:
        return {"ok": False}

    try:
        popt, _pcov = curve_fit(
            f,
            x,
            y,
            p0=(float(np.min(y)) * 0.5, float(np.median(y)) / float(np.median(x)), 0.5),
            bounds=([0.0, 0.0, 0.0], [float("inf"), float("inf"), 2.0]),
            maxfev=20_000,
        )
        a, b, s = (float(popt[0]), float(popt[1]), float(popt[2]))
        yhat = f(x, a, b, s)
        ss_res = float(np.sum((y - yhat) ** 2))
        ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
        return {"ok": True, "a_ms": a, "b": b, "s": s, "r2": r2}
    except Exception:
        return {"ok": False}


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze TR121 scaling run")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--include-warmup", action="store_true", help="Include warmup rows in summaries and fits.")
    ap.add_argument("--bootstrap", type=int, default=1000, help="Bootstrap reps for slope CIs (>=3 models required).")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    analysis_dir = run_dir / "analysis"
    plots_dir = analysis_dir / "plots"
    _ensure_dir(analysis_dir)
    _ensure_dir(plots_dir)

    df_all = pd.read_csv(run_dir / "metrics.csv")
    df_all = df_all[df_all["status"] == "ok"].copy()

    if "is_warmup" in df_all.columns:
        df_all["is_warmup"] = df_all["is_warmup"].astype(bool)
    else:
        df_all["is_warmup"] = False

    # Numeric coercions
    for col in [
        "params_millions",
        "params_millions_config",
        "params_millions_measured",
        "latency_ms",
        "tokens_per_s",
        "tokens_total",
        "prompt_tokens",
        "prompt_tokens_raw",
        "prompt_tokens_compute",
        "gen_tokens",
        "gen_tokens_raw",
        "gen_tokens_equiv",
        "gen_tokens_target",
        "batch_size",
        "batch_size_config",
        "seq_len",
        "gpu_peak_mb",
        "ollama_load_ms",
        "hf_load_ms",
        "cuda_event_ms",
    ]:
        if col in df_all.columns:
            df_all[col] = pd.to_numeric(df_all[col], errors="coerce")
        else:
            # Make downstream aggregations robust to backend-specific columns.
            df_all[col] = np.nan

    # Prefer measured parameter counts when available (HF exact count; Ollama reported parameter_size).
    if "params_millions_measured" in df_all.columns:
        measured = pd.to_numeric(df_all["params_millions_measured"], errors="coerce")
        base = pd.to_numeric(df_all["params_millions"], errors="coerce")
        df_all["params_millions_effective"] = measured.where(np.isfinite(measured) & (measured > 0), base)
    else:
        df_all["params_millions_effective"] = pd.to_numeric(df_all["params_millions"], errors="coerce")

    # HF model architecture audit (depth/width confound check).
    hf_arch_rows: list[dict[str, Any]] = []
    if {"model_kind", "model"}.issubset(set(df_all.columns)):
        hf_models = sorted({str(m) for m in df_all[df_all["model_kind"].astype(str) == "hf"]["model"].unique()})
        for m in hf_models:
            model_dir = (_repo_root() / m).resolve()
            cfg_path = model_dir / "config.json"
            if not cfg_path.exists():
                continue
            try:
                cfg = _read_json(cfg_path)
                hf_arch_rows.append(
                    {
                        "model": m,
                        "config_path": str(cfg_path),
                        "n_layer": cfg.get("n_layer"),
                        "n_embd": cfg.get("n_embd"),
                        "n_head": cfg.get("n_head"),
                        "n_inner": cfg.get("n_inner"),
                        "vocab_size": cfg.get("vocab_size"),
                        "n_positions": cfg.get("n_positions"),
                    }
                )
            except Exception:
                continue
    hf_arch = pd.DataFrame(hf_arch_rows)
    hf_arch.to_csv(analysis_dir / "hf_model_architecture.csv", index=False)

    # Compute-token accounting (for padding/batching fairness analyses).
    # - prompt_tokens_raw: semantic tokens (attention_mask sum) if available
    # - prompt_tokens_compute: actual tokens processed by the model for prefill (batch_size * seq_len) when available
    # - tokens_total_compute: semantic in most cases, but uses compute tokens for HF prefill/e2e.
    bs = pd.to_numeric(df_all.get("batch_size"), errors="coerce").fillna(1.0)
    seq_len = pd.to_numeric(df_all.get("seq_len"), errors="coerce")
    df_all["prompt_tokens_compute"] = (bs * seq_len).where(np.isfinite(seq_len) & (seq_len > 0), np.nan)
    df_all["tokens_total_compute"] = pd.to_numeric(df_all.get("tokens_total"), errors="coerce")

    is_hf = df_all.get("backend_kind").astype(str) == "hf"
    is_prefill = df_all.get("mode").astype(str) == "prefill"
    is_e2e = df_all.get("mode").astype(str) == "e2e_kv"
    df_all.loc[is_hf & is_prefill, "tokens_total_compute"] = df_all.loc[is_hf & is_prefill, "prompt_tokens_compute"]
    df_all.loc[is_hf & is_e2e, "tokens_total_compute"] = (
        df_all.loc[is_hf & is_e2e, "prompt_tokens_compute"]
        + pd.to_numeric(df_all.loc[is_hf & is_e2e, "gen_tokens"], errors="coerce")
    )
    df_all["tokens_per_s_compute"] = df_all["tokens_total_compute"] / (df_all["latency_ms"] / 1000.0)

    # Warmup effect analysis (always computed from raw ok rows when warmup rows exist).
    if "is_warmup" in df_all.columns and bool(df_all["is_warmup"].any()):
        warm = df_all[df_all["is_warmup"] == True].copy()  # noqa: E712
        meas = df_all[df_all["is_warmup"] == False].copy()  # noqa: E712
        eff = (
            warm.groupby(["backend", "model", "scenario", "mode"], dropna=False)
            .agg(warmup_n=("latency_ms", "count"), warmup_median_ms=("latency_ms", "median"))
            .reset_index()
            .merge(
                meas.groupby(["backend", "model", "scenario", "mode"], dropna=False)
                .agg(measured_n=("latency_ms", "count"), measured_median_ms=("latency_ms", "median"))
                .reset_index(),
                on=["backend", "model", "scenario", "mode"],
                how="outer",
            )
        )
        eff["warmup_to_measured_ratio"] = eff["warmup_median_ms"] / eff["measured_median_ms"]
        eff["warmup_minus_measured_ms"] = eff["warmup_median_ms"] - eff["measured_median_ms"]
        eff.sort_values(["backend", "mode", "scenario", "model"]).to_csv(
            analysis_dir / "warmup_effect.csv", index=False
        )

        # Ollama warmup breakdown: load vs infer (prefill only).
        # This prevents apples-to-oranges interpretation when "warmup" includes model load (Ollama) vs
        # first-inference initialization (HF).
        if {"backend_kind", "mode", "prefill_ms", "ollama_load_ms"}.issubset(set(df_all.columns)):
            ow = warm[(warm["backend_kind"].astype(str) == "ollama") & (warm["mode"].astype(str) == "prefill")].copy()
            om = meas[(meas["backend_kind"].astype(str) == "ollama") & (meas["mode"].astype(str) == "prefill")].copy()
            if ow.shape[0] > 0 and om.shape[0] > 0:
                for d in (ow, om):
                    d["prefill_ms"] = pd.to_numeric(d["prefill_ms"], errors="coerce")
                    d["ollama_load_ms"] = pd.to_numeric(d["ollama_load_ms"], errors="coerce")
                    d["prefill_total_ms_including_load"] = d["prefill_ms"] + d["ollama_load_ms"]

                bw = (
                    ow.groupby(["backend", "model", "scenario"], dropna=False)
                    .agg(
                        warmup_prefill_infer_median_ms=("prefill_ms", "median"),
                        warmup_load_median_ms=("ollama_load_ms", "median"),
                        warmup_prefill_total_median_ms=("prefill_total_ms_including_load", "median"),
                        warmup_n=("prefill_ms", "count"),
                    )
                    .reset_index()
                )
                bm = (
                    om.groupby(["backend", "model", "scenario"], dropna=False)
                    .agg(
                        measured_prefill_infer_median_ms=("prefill_ms", "median"),
                        measured_load_median_ms=("ollama_load_ms", "median"),
                        measured_prefill_total_median_ms=("prefill_total_ms_including_load", "median"),
                        measured_n=("prefill_ms", "count"),
                    )
                    .reset_index()
                )
                bd = bw.merge(bm, on=["backend", "model", "scenario"], how="inner")
                bd["warmup_ratio_infer_only"] = (
                    bd["warmup_prefill_infer_median_ms"] / bd["measured_prefill_infer_median_ms"]
                )
                bd["warmup_ratio_total_including_load"] = (
                    bd["warmup_prefill_total_median_ms"] / bd["measured_prefill_total_median_ms"]
                )
                bd.sort_values(["model", "scenario"]).to_csv(
                    analysis_dir / "ollama_warmup_breakdown.csv", index=False
                )

    # Ollama early-stop sanity (kv_decode only; use raw eval_count vs configured target).
    # This matters because fixed-length equivalence can be biased if EOS happens early in a way that correlates with size.
    if {"backend_kind", "gen_tokens_raw", "gen_tokens_target", "mode"}.issubset(set(df_all.columns)):
        oll = df_all[
            (df_all["backend_kind"].astype(str) == "ollama")
            & (df_all["mode"].astype(str) == "kv_decode")
            & (df_all["is_warmup"] == False)  # noqa: E712
        ].copy()
        if oll.shape[0] > 0:
            if "ollama_done_reason" in oll.columns and "done_reason" not in oll.columns:
                oll["done_reason"] = oll["ollama_done_reason"]
            elif "done_reason" not in oll.columns:
                oll["done_reason"] = np.nan
            oll["early_stop"] = (
                pd.to_numeric(oll["gen_tokens_raw"], errors="coerce")
                < pd.to_numeric(oll["gen_tokens_target"], errors="coerce")
            )
            by = (
                oll.groupby(["backend", "model", "scenario"], dropna=False)
                .agg(
                    n=("latency_ms", "count"),
                    params_millions_effective_median=("params_millions_effective", "median"),
                    gen_tokens_target=("gen_tokens_target", "median"),
                    gen_tokens_raw_median=("gen_tokens_raw", "median"),
                    early_stop_rate=("early_stop", "mean"),
                    done_reason_mode=("done_reason", lambda s: s.mode(dropna=True).iloc[0] if s.notna().any() else None),
                )
                .reset_index()
                .sort_values(["model", "scenario"])
            )
            by.to_csv(analysis_dir / "ollama_early_stop_summary.csv", index=False)

    # Ollama decode linearity validation (duration vs eval_count) + projection error bounds.
    # This tests whether kv_decode_ms is approximately linear in gen_tokens_raw and whether the
    # fixed-length equivalence (proportional scaling) introduces material bias under early-stop.
    if {
        "backend_kind",
        "mode",
        "kv_decode_ms",
        "kv_decode_ms_equiv",
        "gen_tokens_raw",
        "gen_tokens_target",
        "is_warmup",
    }.issubset(set(df_all.columns)):
        od = df_all[
            (df_all["backend_kind"].astype(str) == "ollama")
            & (df_all["mode"].astype(str) == "kv_decode")
            & (df_all["is_warmup"] == False)  # noqa: E712
        ].copy()
        od["kv_decode_ms"] = pd.to_numeric(od["kv_decode_ms"], errors="coerce")
        od["kv_decode_ms_equiv"] = pd.to_numeric(od["kv_decode_ms_equiv"], errors="coerce")
        od["gen_tokens_raw"] = pd.to_numeric(od["gen_tokens_raw"], errors="coerce")
        od["gen_tokens_target"] = pd.to_numeric(od["gen_tokens_target"], errors="coerce")
        od = od[
            np.isfinite(od["kv_decode_ms"])
            & np.isfinite(od["gen_tokens_raw"])
            & (od["gen_tokens_raw"] > 0)
            & np.isfinite(od["gen_tokens_target"])
            & (od["gen_tokens_target"] > 0)
        ].copy()
        if od.shape[0] > 0:
            lin_rows: list[dict[str, Any]] = []
            err_rows: list[dict[str, Any]] = []
            for model, g in od.groupby("model", dropna=False):
                tgt = float(np.nanmedian(g["gen_tokens_target"].to_numpy()))
                fit = _fit_linear(g["gen_tokens_raw"].to_numpy(), g["kv_decode_ms"].to_numpy())
                if not fit.get("ok") or not np.isfinite(tgt) or tgt <= 0:
                    continue
                a = float(fit["a"])
                b = float(fit["b"])
                r2 = float(fit["r2"])
                affine_equiv = a + b * tgt

                prop_equiv = pd.to_numeric(g["kv_decode_ms_equiv"], errors="coerce").to_numpy(dtype=float)
                prop_err = prop_equiv - affine_equiv
                lin_rows.append(
                    {
                        "model": model,
                        "n": int(g.shape[0]),
                        "gen_tokens_target": float(tgt),
                        "a_ms": a,
                        "b_ms_per_token": b,
                        "r2": r2,
                        "affine_ms_at_target": float(affine_equiv),
                        "gen_tokens_raw_min": float(np.nanmin(g["gen_tokens_raw"].to_numpy())),
                        "gen_tokens_raw_median": float(np.nanmedian(g["gen_tokens_raw"].to_numpy())),
                        "gen_tokens_raw_max": float(np.nanmax(g["gen_tokens_raw"].to_numpy())),
                    }
                )
                err_rows.append(
                    {
                        "model": model,
                        "gen_tokens_target": float(tgt),
                        "n": int(np.isfinite(prop_err).sum()),
                        "prop_minus_affine_ms_median": float(np.nanmedian(prop_err)),
                        "prop_minus_affine_ms_p95": float(np.nanquantile(prop_err, 0.95)),
                        "prop_minus_affine_ms_min": float(np.nanmin(prop_err)),
                        "prop_minus_affine_ms_max": float(np.nanmax(prop_err)),
                    }
                )

            if lin_rows:
                pd.DataFrame(lin_rows).sort_values(["model"]).to_csv(
                    analysis_dir / "ollama_decode_linearity.csv", index=False
                )
            if err_rows:
                pd.DataFrame(err_rows).sort_values(["model"]).to_csv(
                    analysis_dir / "ollama_decode_projection_error.csv", index=False
                )

    # CUDA-event vs wall-clock gap (HF GPU only in this artifact set; still compute generically).
    # This is a defensibility check: if CUDA-event timing and wall-clock disagree wildly, the measured
    # region may be dominated by host-side overhead rather than GPU execution.
    if {"cuda_event_ms", "latency_ms"}.issubset(set(df_all.columns)):
        c = df_all[
            np.isfinite(df_all["cuda_event_ms"])
            & np.isfinite(df_all["latency_ms"])
            & (df_all["latency_ms"] > 0)
        ].copy()
        if c.shape[0] > 0:
            c["abs_gap_ms"] = (c["latency_ms"] - c["cuda_event_ms"]).abs()
            c["rel_gap"] = c["abs_gap_ms"] / c["latency_ms"]
            c.groupby(["backend", "backend_kind", "mode", "is_warmup"], dropna=False).agg(
                n=("rel_gap", "count"),
                rel_gap_median=("rel_gap", "median"),
                rel_gap_p95=("rel_gap", lambda s: float(np.quantile(s.to_numpy(), 0.95))),
                abs_gap_ms_median=("abs_gap_ms", "median"),
                abs_gap_ms_p95=("abs_gap_ms", lambda s: float(np.quantile(s.to_numpy(), 0.95))),
            ).reset_index().sort_values(["backend", "mode", "is_warmup"]).to_csv(
                analysis_dir / "cuda_event_gap_summary.csv", index=False
            )

    df = df_all
    if not args.include_warmup and "is_warmup" in df.columns:
        df = df[df["is_warmup"] == False].copy()  # noqa: E712

    group_cols = [
        "backend",
        "backend_kind",
        "batch_size",
        "model",
        "model_kind",
        "params_millions_effective",
        "scenario",
        "mode",
    ]
    agg = (
        df.groupby(group_cols, dropna=False)
        .agg(
            n=("latency_ms", "count"),
            latency_mean_ms=("latency_ms", "mean"),
            latency_median_ms=("latency_ms", "median"),
            latency_p95_ms=("latency_ms", lambda s: float(np.quantile(s.to_numpy(dtype=float), 0.95))),
            latency_p99_ms=("latency_ms", lambda s: float(np.quantile(s.to_numpy(dtype=float), 0.99))),
            tokens_per_s_median=("tokens_per_s", "median"),
            tokens_per_s_compute_median=("tokens_per_s_compute", "median"),
            tokens_total_median=("tokens_total", "median"),
            tokens_total_compute_median=("tokens_total_compute", "median"),
            prompt_tokens_median=("prompt_tokens", "median"),
            prompt_tokens_raw_median=("prompt_tokens_raw", "median"),
            prompt_tokens_compute_median=("prompt_tokens_compute", "median"),
            gen_tokens_median=("gen_tokens", "median"),
            gen_tokens_raw_median=("gen_tokens_raw", "median"),
            gen_tokens_target_median=("gen_tokens_target", "median"),
            cuda_event_median_ms=("cuda_event_ms", "median"),
            gpu_peak_mb_median=("gpu_peak_mb", "median"),
            ollama_load_ms_median=("ollama_load_ms", "median"),
            params_millions_config_median=("params_millions_config", "median"),
            params_millions_measured_median=("params_millions_measured", "median"),
        )
        .reset_index()
        .sort_values(["backend", "mode", "scenario", "params_millions_effective"])
    )
    agg.to_csv(analysis_dir / "summary_by_model_backend_mode.csv", index=False)

    # Scenario-aggregated (geometric mean across scenarios per model/backend/mode).
    by_model_mode = (
        agg.groupby(
            ["backend", "backend_kind", "batch_size", "model", "model_kind", "params_millions_effective", "mode"],
            dropna=False,
        )
        .agg(
            n_scenarios=("scenario", "count"),
            latency_geomean_ms=("latency_median_ms", lambda s: _geomean(s.to_numpy(dtype=float))),
            latency_median_of_medians_ms=("latency_median_ms", "median"),
            tokens_per_s_geomean=("tokens_per_s_median", lambda s: _geomean(s.to_numpy(dtype=float))),
            tokens_per_s_compute_geomean=("tokens_per_s_compute_median", lambda s: _geomean(s.to_numpy(dtype=float))),
            gpu_peak_mb_median=("gpu_peak_mb_median", "median"),
            ollama_load_ms_median=("ollama_load_ms_median", "median"),
            params_millions_config_median=("params_millions_config_median", "median"),
            params_millions_measured_median=("params_millions_measured_median", "median"),
        )
        .reset_index()
        .sort_values(["backend", "mode", "params_millions_effective"])
    )
    by_model_mode.to_csv(analysis_dir / "summary_by_model_backend_mode_agg.csv", index=False)

    # HF multivariate fits (scenario-aggregated): log(latency) ~ log(params) + log(n_layer).
    # Purpose: tighten the "depth vs params" mechanism beyond rank correlations.
    if not hf_arch.empty:
        mv = by_model_mode[by_model_mode["backend_kind"].astype(str) == "hf"].merge(
            hf_arch[["model", "n_layer"]],
            on="model",
            how="inner",
        )
        mv["params_millions_effective"] = pd.to_numeric(mv["params_millions_effective"], errors="coerce")
        mv["latency_geomean_ms"] = pd.to_numeric(mv["latency_geomean_ms"], errors="coerce")
        mv["n_layer"] = pd.to_numeric(mv["n_layer"], errors="coerce")
        mv = mv[
            np.isfinite(mv["params_millions_effective"])
            & np.isfinite(mv["latency_geomean_ms"])
            & np.isfinite(mv["n_layer"])
        ].copy()

        mv_rows: list[dict[str, Any]] = []
        rng = np.random.default_rng(int(args.seed))
        n_boot = int(args.bootstrap)
        for (backend, batch_size, mode), g in mv.groupby(["backend", "batch_size", "mode"], dropna=False):
            x_p = g["params_millions_effective"].to_numpy(dtype=float)
            x_l = g["n_layer"].to_numpy(dtype=float)
            y = g["latency_geomean_ms"].to_numpy(dtype=float)
            fit = _fit_log_multivariate(x_params_m=x_p, x_layers=x_l, y_latency_ms=y)
            if not fit.get("ok"):
                continue

            boot_betas: list[float] = []
            boot_gammas: list[float] = []
            boot_r2: list[float] = []
            n = int(x_p.size)
            if n >= 3 and n_boot > 0:
                for _ in range(n_boot):
                    idx = rng.integers(0, n, size=n)
                    bf = _fit_log_multivariate(
                        x_params_m=x_p[idx],
                        x_layers=x_l[idx],
                        y_latency_ms=y[idx],
                    )
                    if not bf.get("ok"):
                        continue
                    boot_betas.append(float(bf["beta_log_params"]))
                    boot_gammas.append(float(bf["gamma_log_layers"]))
                    boot_r2.append(float(bf["r2"]))

            row: dict[str, Any] = {
                "backend": backend,
                "backend_kind": "hf",
                "batch_size": batch_size,
                "mode": mode,
                "n_models": int(n),
                "beta_log_params": float(fit["beta_log_params"]),
                "gamma_log_layers": float(fit["gamma_log_layers"]),
                "r2": float(fit["r2"]),
            }
            if boot_betas:
                row.update(
                    {
                        "beta_ci_low": float(np.quantile(np.asarray(boot_betas), 0.025)),
                        "beta_ci_high": float(np.quantile(np.asarray(boot_betas), 0.975)),
                        "gamma_ci_low": float(np.quantile(np.asarray(boot_gammas), 0.025)),
                        "gamma_ci_high": float(np.quantile(np.asarray(boot_gammas), 0.975)),
                        "r2_ci_low": float(np.quantile(np.asarray(boot_r2), 0.025)),
                        "r2_ci_high": float(np.quantile(np.asarray(boot_r2), 0.975)),
                        "boot_n_used": int(len(boot_betas)),
                        "boot_n_requested": int(n_boot),
                    }
                )
            mv_rows.append(row)

        if mv_rows:
            pd.DataFrame(mv_rows).sort_values(["backend", "mode"]).to_csv(
                analysis_dir / "hf_multivariate_fits.csv", index=False
            )

    # HF architecture correlation summary (uses scenario-aggregated medians).
    # This is intentionally rank-based: we want to know what predicts latency under this boundary, not fit a universal law.
    if not hf_arch.empty and spearmanr is not None:
        hm = by_model_mode[by_model_mode["backend_kind"].astype(str) == "hf"].merge(hf_arch, on="model", how="left")
        corr_rows: list[dict[str, Any]] = []
        for (backend, batch_size, mode), g in hm.groupby(["backend", "batch_size", "mode"], dropna=False):
            if g["n_layer"].isna().all():
                continue
            y = pd.to_numeric(g["latency_geomean_ms"], errors="coerce")
            pm = pd.to_numeric(g["params_millions_effective"], errors="coerce")
            n_layer = pd.to_numeric(g["n_layer"], errors="coerce")
            n_embd = pd.to_numeric(g["n_embd"], errors="coerce")
            m = y.notna() & pm.notna()
            if int(m.sum()) < 3:
                continue
            ylog = np.log10(y[m].to_numpy(dtype=float))
            pmlog = np.log10(pm[m].to_numpy(dtype=float))
            rho_p, p_p = spearmanr(pmlog, ylog)
            row: dict[str, Any] = {
                "backend": backend,
                "batch_size": batch_size,
                "mode": mode,
                "n_models": int(m.sum()),
                "spearman_rho_loglog_params": float(rho_p),
                "spearman_p_loglog_params": float(p_p),
            }
            if n_layer.notna().any():
                m2 = m & n_layer.notna()
                if int(m2.sum()) >= 3:
                    ylog2 = np.log10(y[m2].to_numpy(dtype=float))
                    rho_l, p_l = spearmanr(n_layer[m2].to_numpy(dtype=float), ylog2)
                    row["spearman_rho_n_layer_vs_log_latency"] = float(rho_l)
                    row["spearman_p_n_layer_vs_log_latency"] = float(p_l)
            if n_embd.notna().any():
                m3 = m & n_embd.notna()
                if int(m3.sum()) >= 3:
                    ylog3 = np.log10(y[m3].to_numpy(dtype=float))
                    rho_e, p_e = spearmanr(n_embd[m3].to_numpy(dtype=float), ylog3)
                    row["spearman_rho_n_embd_vs_log_latency"] = float(rho_e)
                    row["spearman_p_n_embd_vs_log_latency"] = float(p_e)
            corr_rows.append(row)
        pd.DataFrame(corr_rows).sort_values(["backend", "mode"]).to_csv(
            analysis_dir / "hf_architecture_correlations.csv", index=False
        )

    # Scaling fits per backend_kind/backend/mode/scenario
    fit_rows: list[dict[str, Any]] = []
    for (backend, backend_kind, mode, scenario), g in agg.groupby(
        ["backend", "backend_kind", "mode", "scenario"], dropna=False
    ):
        x = g["params_millions_effective"].to_numpy(dtype=float)
        y = g["latency_median_ms"].to_numpy(dtype=float)
        fit = _fit_power_law(x, y)
        robust = _fit_loglog_robust(x, y)
        ci = _bootstrap_power_law_ci(x=x, y=y, n_boot=int(args.bootstrap), seed=int(args.seed))
        fit_rows.append(
            {
                "backend": backend,
                "backend_kind": backend_kind,
                "batch_size": float(g["batch_size"].iloc[0]) if "batch_size" in g.columns and g.shape[0] else float("nan"),
                "mode": mode,
                "scenario": scenario,
                "aggregation": "scenario",
                "n_models": int(g.shape[0]),
                **fit,
                **robust,
                **ci,
            }
        )

    # Scenario-aggregated fit (geomean across scenarios per model).
    for (backend, backend_kind, batch_size, mode), g in by_model_mode.groupby(
        ["backend", "backend_kind", "batch_size", "mode"], dropna=False
    ):
        x = g["params_millions_effective"].to_numpy(dtype=float)
        y = g["latency_geomean_ms"].to_numpy(dtype=float)
        fit = _fit_power_law(x, y)
        robust = _fit_loglog_robust(x, y)
        ci = _bootstrap_power_law_ci(x=x, y=y, n_boot=int(args.bootstrap), seed=int(args.seed))
        fit_rows.append(
            {
                "backend": backend,
                "backend_kind": backend_kind,
                "batch_size": batch_size,
                "mode": mode,
                "scenario": "__all__",
                "aggregation": "geomean_across_scenarios",
                "n_models": int(g.shape[0]),
                **fit,
                **robust,
                **ci,
            }
        )
    fits = pd.DataFrame(fit_rows).sort_values(["backend", "mode", "scenario"])
    fits.to_csv(analysis_dir / "scaling_fits.csv", index=False)

    # Optional: length-limited decode fits for Ollama (guards against EOS/stop bias).
    # If a model stops early (done_reason != "length"), the fixed-length equivalence can distort scaling if early-stop
    # frequency correlates with size. This file computes the same fits after excluding early-stop decode/e2e rows.
    if {"backend_kind", "gen_tokens_raw", "gen_tokens_target", "mode"}.issubset(set(df.columns)):
        df_len = df.copy()
        is_ollama = df_len["backend_kind"].astype(str) == "ollama"
        is_decode_mode = df_len["mode"].astype(str).isin(["kv_decode", "e2e_kv"])
        gen_raw = pd.to_numeric(df_len["gen_tokens_raw"], errors="coerce")
        gen_tgt = pd.to_numeric(df_len["gen_tokens_target"], errors="coerce")
        is_length_limited = gen_raw >= gen_tgt
        df_len = df_len[~(is_ollama & is_decode_mode) | is_length_limited].copy()

        agg_len = (
            df_len.groupby(group_cols, dropna=False)
            .agg(latency_median_ms=("latency_ms", "median"))
            .reset_index()
        )
        by_model_mode_len = (
            agg_len.groupby(
                ["backend", "backend_kind", "batch_size", "model", "model_kind", "params_millions_effective", "mode"],
                dropna=False,
            )
            .agg(latency_geomean_ms=("latency_median_ms", lambda s: _geomean(s.to_numpy(dtype=float))))
            .reset_index()
        )
        fit_len_rows: list[dict[str, Any]] = []
        for (backend, backend_kind, batch_size, mode), g in by_model_mode_len.groupby(
            ["backend", "backend_kind", "batch_size", "mode"], dropna=False
        ):
            if str(backend_kind) != "ollama":
                continue
            x = g["params_millions_effective"].to_numpy(dtype=float)
            y = g["latency_geomean_ms"].to_numpy(dtype=float)
            fit = _fit_power_law(x, y)
            robust = _fit_loglog_robust(x, y)
            ci = _bootstrap_power_law_ci(x=x, y=y, n_boot=int(args.bootstrap), seed=int(args.seed))
            fit_len_rows.append(
                {
                    "backend": backend,
                    "backend_kind": backend_kind,
                    "batch_size": batch_size,
                    "mode": mode,
                    "scenario": "__all__",
                    "aggregation": "geomean_across_scenarios",
                    "filter": "length_limited_decode_only",
                    "n_models": int(g.shape[0]),
                    **fit,
                    **robust,
                    **ci,
                }
            )
        out_len = analysis_dir / "scaling_fits_length_limited.csv"
        if fit_len_rows:
            pd.DataFrame(fit_len_rows).sort_values(["backend", "mode"]).to_csv(out_len, index=False)
        else:
            out_len.write_text("", encoding="utf-8")

    # Overhead + compute fits (latency_ms = a + b*P or a + b*P^s).
    overhead_rows: list[dict[str, Any]] = []
    for (backend, backend_kind, batch_size, mode), g in by_model_mode.groupby(
        ["backend", "backend_kind", "batch_size", "mode"], dropna=False
    ):
        x = g["params_millions_effective"].to_numpy(dtype=float)
        y = g["latency_geomean_ms"].to_numpy(dtype=float)
        lin = _fit_offset_linear(x, y)
        if lin.get("ok"):
            x_min = float(np.nanmin(x))
            x_max = float(np.nanmax(x))
            overhead_rows.append(
                {
                    "backend": backend,
                    "backend_kind": backend_kind,
                    "batch_size": batch_size,
                    "mode": mode,
                    "aggregation": "geomean_across_scenarios",
                    "fit": "lat = a + b*P",
                    "n_models": int(g.shape[0]),
                    **lin,
                    "overhead_fraction_at_min_model": float(
                        lin["a_ms"] / (lin["a_ms"] + lin["b_ms_per_million_params"] * x_min)
                    )
                    if (lin["a_ms"] + lin["b_ms_per_million_params"] * x_min) > 0
                    else float("nan"),
                    "overhead_fraction_at_max_model": float(
                        lin["a_ms"] / (lin["a_ms"] + lin["b_ms_per_million_params"] * x_max)
                    )
                    if (lin["a_ms"] + lin["b_ms_per_million_params"] * x_max) > 0
                    else float("nan"),
                }
            )
        powfit = _fit_offset_power(x, y)
        if powfit.get("ok"):
            x_min = float(np.nanmin(x))
            x_max = float(np.nanmax(x))
            a = float(powfit["a_ms"])
            b = float(powfit["b"])
            s = float(powfit["s"])
            overhead_rows.append(
                {
                    "backend": backend,
                    "backend_kind": backend_kind,
                    "batch_size": batch_size,
                    "mode": mode,
                    "aggregation": "geomean_across_scenarios",
                    "fit": "lat = a + b*P^s",
                    "n_models": int(g.shape[0]),
                    **powfit,
                    "overhead_fraction_at_min_model": float(a / (a + b * (x_min**s))) if (a + b * (x_min**s)) > 0 else float("nan"),
                    "overhead_fraction_at_max_model": float(a / (a + b * (x_max**s))) if (a + b * (x_max**s)) > 0 else float("nan"),
                }
            )
    pd.DataFrame(overhead_rows).sort_values(["backend", "mode", "fit"]).to_csv(
        analysis_dir / "overhead_compute_fits.csv", index=False
    )

    # Plots (best-effort)
    try:
        import matplotlib.pyplot as plt  # type: ignore

        for (backend, backend_kind, mode, scenario), g in agg.groupby(
            ["backend", "backend_kind", "mode", "scenario"], dropna=False
        ):
            if g.shape[0] < 2:
                continue
            xs = g["params_millions_effective"].to_numpy(dtype=float)
            ys = g["latency_median_ms"].to_numpy(dtype=float)
            fit = _fit_power_law(xs, ys)
            plt.figure(figsize=(6.8, 4.0))
            plt.plot(xs, ys, marker="o")
            if fit.get("ok"):
                xline = np.logspace(np.log10(float(np.min(xs))), np.log10(float(np.max(xs))), 100)
                yline = (10 ** float(fit["log10_intercept"])) * (xline ** float(fit["slope"]))
                plt.plot(xline, yline, linestyle="--", linewidth=1.5, alpha=0.85)
            plt.xscale("log")
            plt.yscale("log")
            plt.grid(True, alpha=0.25)
            plt.xlabel("Parameters (millions)")
            plt.ylabel("Median latency (ms)")
            title = f"TR121 scaling: {backend} | {mode} | {scenario}"
            if fit.get("ok"):
                title += f" | slope={float(fit['slope']):.3f} r2={float(fit['r2']):.3f}"
            plt.title(title)
            out = plots_dir / f"scaling_{backend}_{mode}_{scenario}.png"
            plt.tight_layout()
            plt.savefig(out, dpi=200)
            plt.close()

        # Scenario-aggregated plot
        for (backend, backend_kind, batch_size, mode), g in by_model_mode.groupby(
            ["backend", "backend_kind", "batch_size", "mode"], dropna=False
        ):
            if g.shape[0] < 2:
                continue
            xs = g["params_millions_effective"].to_numpy(dtype=float)
            ys = g["latency_geomean_ms"].to_numpy(dtype=float)
            fit = _fit_power_law(xs, ys)
            plt.figure(figsize=(6.8, 4.0))
            plt.plot(xs, ys, marker="o")
            if fit.get("ok"):
                xline = np.logspace(np.log10(float(np.min(xs))), np.log10(float(np.max(xs))), 100)
                yline = (10 ** float(fit["log10_intercept"])) * (xline ** float(fit["slope"]))
                plt.plot(xline, yline, linestyle="--", linewidth=1.5, alpha=0.85)
            plt.xscale("log")
            plt.yscale("log")
            plt.grid(True, alpha=0.25)
            plt.xlabel("Parameters (millions)")
            plt.ylabel("Geomean median latency across scenarios (ms)")
            title = f"TR121 scaling (agg): {backend} | {mode} | bs={int(batch_size) if pd.notna(batch_size) else 'na'}"
            if fit.get("ok"):
                title += f" | slope={float(fit['slope']):.3f} r2={float(fit['r2']):.3f}"
            plt.title(title)
            bs_tag = f"bs{int(batch_size)}" if pd.notna(batch_size) else "bsna"
            out = plots_dir / f"scaling_{backend}_{mode}__all__{bs_tag}.png"
            plt.tight_layout()
            plt.savefig(out, dpi=200)
            plt.close()

        # Ollama early-stop sanity plot (gen_tokens_raw vs params)
        early_csv = analysis_dir / "ollama_early_stop_summary.csv"
        if early_csv.exists():
            e = pd.read_csv(early_csv)
            if {"gen_tokens_raw_median", "params_millions_effective_median", "model"}.issubset(set(e.columns)) and e.shape[0] > 0:
                plt.figure(figsize=(7.2, 4.0))
                e2 = (
                    e.groupby(["model"], dropna=False)
                    .agg(
                        params_millions_effective_median=("params_millions_effective_median", "median"),
                        gen_tokens_raw_median=("gen_tokens_raw_median", "median"),
                    )
                    .reset_index()
                )
                plt.plot(
                    e2["params_millions_effective_median"].to_numpy(dtype=float),
                    e2["gen_tokens_raw_median"].to_numpy(dtype=float),
                    marker="o",
                )
                plt.xscale("log")
                plt.grid(True, alpha=0.25)
                plt.xlabel("Parameters (millions; measured)")
                plt.ylabel("Median raw generated tokens (kv_decode)")
                plt.title("TR121: Ollama early-stop sanity (raw eval_count)")
                plt.tight_layout()
                plt.savefig(plots_dir / "ollama_early_stop_sanity.png", dpi=200)
                plt.close()
    except Exception:
        pass

    print(f"TR121 analysis written to: {analysis_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
