#!/usr/bin/env python3
"""
TR120.A: Compile paradox analysis using TR117 Tier-3 artifacts.

Inputs:
  - results/tr117_tier3/metrics.csv (row-level latency/token metrics)

Outputs (under --out-dir):
  - processed/*.csv tables
  - processed/summary.json (key stats + deltas)
  - plots/*.png (CDF + quantile plots)

This script is intentionally artifact-first: it does not rerun benchmarks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats


def _percentiles(values: np.ndarray, ps: list[float]) -> dict[str, float]:
    if values.size == 0:
        return {f"p{int(p)}": float("nan") for p in ps}
    out: dict[str, float] = {}
    for p in ps:
        out[f"p{int(p)}"] = float(np.percentile(values, p))
    return out


def _summary(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {
            "n": 0,
            "mean_ms": float("nan"),
            "median_ms": float("nan"),
            "std_ms": float("nan"),
            "min_ms": float("nan"),
            "max_ms": float("nan"),
            **_percentiles(values, [90, 95, 99]),
        }
    return {
        "n": int(values.size),
        "mean_ms": float(values.mean()),
        "median_ms": float(np.median(values)),
        "std_ms": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "min_ms": float(values.min()),
        "max_ms": float(values.max()),
        **_percentiles(values, [90, 95, 99]),
    }


def _mann_whitney(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    if a.size == 0 or b.size == 0:
        return {"u_statistic": float("nan"), "p_value": float("nan")}
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"u_statistic": float(res.statistic), "p_value": float(res.pvalue)}


def _delta(a: float, b: float) -> dict[str, float]:
    # delta = b - a, pct = (b-a)/a
    if not np.isfinite(a) or not np.isfinite(b):
        return {"delta": float("nan"), "pct": float("nan")}
    d = b - a
    pct = (d / a) * 100.0 if a != 0 else float("nan")
    return {"delta": float(d), "pct": float(pct)}


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _save_plot(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=200)


def main() -> int:
    parser = argparse.ArgumentParser(description="TR120 compile paradox analysis (TR117 artifacts)")
    parser.add_argument(
        "--metrics-csv",
        default="results/tr117_tier3/metrics.csv",
        help="Path to TR117 Tier-3 metrics.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="scripts/tr120/results/tr120_compile_paradox",
        help="Output directory for TR120 artifacts",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional filter: model name (e.g., models/tiny-gpt2)",
    )
    parser.add_argument(
        "--backends",
        default="transformers-gpu,transformers-gpu-compile",
        help="Comma-separated backends to compare (exact strings from metrics.csv)",
    )
    parser.add_argument(
        "--quantizations",
        default=None,
        help="Optional comma-separated quantizations to include (e.g., fp32,fp16,int8)",
    )
    args = parser.parse_args()

    metrics_path = Path(args.metrics_csv)
    out_root = Path(args.out_dir)
    processed_dir = out_root / "processed"
    plots_dir = out_root / "plots"
    _ensure_dir(processed_dir)
    _ensure_dir(plots_dir)

    df = pd.read_csv(metrics_path)
    df = df[df["status"] == "ok"].copy()

    if args.model:
        df = df[df["model"] == str(args.model)].copy()

    backends = [b.strip() for b in str(args.backends).split(",") if b.strip()]
    df = df[df["backend"].isin(backends)].copy()

    if args.quantizations:
        quants = [q.strip() for q in str(args.quantizations).split(",") if q.strip()]
        df = df[df["quantization"].isin(quants)].copy()

    if df.empty:
        raise SystemExit("No rows after filtering; check --metrics-csv/filters.")

    # Core summaries
    percentiles = [50, 90, 95, 99]
    rows_overall: list[dict[str, Any]] = []
    rows_quant: list[dict[str, Any]] = []
    rows_scenario_quant: list[dict[str, Any]] = []

    for backend in backends:
        vals = df[df["backend"] == backend]["latency_ms"].dropna().to_numpy(dtype=float)
        s = _summary(vals)
        rows_overall.append({"backend": backend, **s})

    for (backend, quant), group in df.groupby(["backend", "quantization"]):
        if backend not in backends:
            continue
        vals = group["latency_ms"].dropna().to_numpy(dtype=float)
        s = _summary(vals)
        rows_quant.append({"backend": backend, "quantization": str(quant), **s})

    for (backend, quant, scenario), group in df.groupby(["backend", "quantization", "scenario"]):
        if backend not in backends:
            continue
        vals = group["latency_ms"].dropna().to_numpy(dtype=float)
        s = _summary(vals)
        rows_scenario_quant.append(
            {"backend": backend, "quantization": str(quant), "scenario": str(scenario), **s}
        )

    df_overall = pd.DataFrame(rows_overall).sort_values("mean_ms").reset_index(drop=True)
    df_quant = pd.DataFrame(rows_quant).sort_values(["quantization", "mean_ms"]).reset_index(drop=True)
    df_scenario_quant = (
        pd.DataFrame(rows_scenario_quant)
        .sort_values(["quantization", "scenario", "mean_ms"])
        .reset_index(drop=True)
    )

    df_overall.to_csv(processed_dir / "summary_overall.csv", index=False)
    df_quant.to_csv(processed_dir / "summary_by_quantization.csv", index=False)
    df_scenario_quant.to_csv(processed_dir / "summary_by_scenario_quantization.csv", index=False)

    # Pairwise comparisons (assume exactly two backends)
    comparisons: dict[str, Any] = {"overall": {}, "by_quantization": {}, "by_scenario_quantization": {}}
    if len(backends) == 2:
        a_name, b_name = backends[0], backends[1]

        def compare(sub_df: pd.DataFrame) -> dict[str, Any]:
            a = sub_df[sub_df["backend"] == a_name]["latency_ms"].dropna().to_numpy(dtype=float)
            b = sub_df[sub_df["backend"] == b_name]["latency_ms"].dropna().to_numpy(dtype=float)
            sa = _summary(a)
            sb = _summary(b)
            out: dict[str, Any] = {
                "backend_a": a_name,
                "backend_b": b_name,
                "n_a": sa["n"],
                "n_b": sb["n"],
                "mann_whitney": _mann_whitney(a, b),
                "mean_delta_ms": _delta(sa["mean_ms"], sb["mean_ms"]),
                "median_delta_ms": _delta(sa["median_ms"], sb["median_ms"]),
                "p95_delta_ms": _delta(sa["p95"], sb["p95"]),
                "p99_delta_ms": _delta(sa["p99"], sb["p99"]),
                "max_delta_ms": _delta(sa["max_ms"], sb["max_ms"]),
                "std_delta_ms": _delta(sa["std_ms"], sb["std_ms"]),
            }
            return out

        comparisons["overall"] = compare(df)

        for quant, group in df.groupby("quantization"):
            comparisons["by_quantization"][str(quant)] = compare(group)

        for (quant, scenario), group in df.groupby(["quantization", "scenario"]):
            comparisons["by_scenario_quantization"].setdefault(str(quant), {})[str(scenario)] = compare(group)

    # Cold-start / ordering effect (artifact-backed from run JSON arrays)
    #
    # In TR117 tier3, each {scenario, backend, quantization, model} has a single run_*.json file containing
    # multiple repeated measurements in `latencies_ms`. We treat the first element as a "first sample"
    # that can include one-time initialization effects within the timed boundary.
    run_paths = sorted(set(df["path"].dropna().astype(str).tolist()))
    by_file_rows: list[dict[str, Any]] = []
    backend_latencies: dict[str, list[np.ndarray]] = {b: [] for b in backends}
    backend_latencies_excl_first: dict[str, list[np.ndarray]] = {b: [] for b in backends}

    for run_path_str in run_paths:
        run_path = Path(run_path_str)
        if not run_path.exists():
            continue
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        spec = run.get("spec") or {}
        backend = str(spec.get("backend") or "")
        if backend not in backends:
            continue
        lat = np.array(run.get("latencies_ms") or [], dtype=float)
        if lat.size == 0:
            continue

        scenario = str(spec.get("scenario") or "")
        quantization = str(spec.get("quantization") or "")
        model_name = str(spec.get("model") or "")

        idx_max = int(np.argmax(lat))
        mean_excl_first = float(np.mean(lat[1:])) if lat.size > 1 else float("nan")
        median_rest = float(np.median(lat[1:])) if lat.size > 1 else float("nan")
        ratio_first_over_median_rest = (
            float(lat[0] / median_rest)
            if lat.size > 1 and np.isfinite(median_rest) and median_rest != 0.0
            else float("nan")
        )

        by_file_rows.append(
            {
                "backend": backend,
                "scenario": scenario,
                "quantization": quantization,
                "model": model_name,
                "n_samples": int(lat.size),
                "first_ms": float(lat[0]),
                "median_rest_ms": median_rest,
                "ratio_first_over_median_rest": ratio_first_over_median_rest,
                "first_over_2x_rest_median": bool(
                    np.isfinite(ratio_first_over_median_rest) and ratio_first_over_median_rest > 2.0
                ),
                "first_over_3x_rest_median": bool(
                    np.isfinite(ratio_first_over_median_rest) and ratio_first_over_median_rest > 3.0
                ),
                "mean_ms": float(np.mean(lat)),
                "median_ms": float(np.median(lat)),
                "p99_ms": float(np.percentile(lat, 99)),
                "max_ms": float(lat[idx_max]),
                "max_index": idx_max,
                "mean_excl_first_ms": mean_excl_first,
                "path": run_path_str,
            }
        )

        backend_latencies[backend].append(lat)
        if lat.size > 1:
            backend_latencies_excl_first[backend].append(lat[1:])

    df_by_file = pd.DataFrame(by_file_rows)
    if not df_by_file.empty:
        df_by_file = df_by_file.sort_values(["scenario", "quantization", "backend"]).reset_index(drop=True)
        df_by_file.to_csv(processed_dir / "cold_start_by_file.csv", index=False)

        cold_rows: list[dict[str, Any]] = []
        for backend in backends:
            lat_all = (
                np.concatenate(backend_latencies[backend]) if backend_latencies[backend] else np.array([])
            )
            lat_excl = (
                np.concatenate(backend_latencies_excl_first[backend])
                if backend_latencies_excl_first[backend]
                else np.array([])
            )
            s_all = _summary(lat_all)
            s_excl = _summary(lat_excl)

            frac_max_at_first = float(
                (df_by_file[df_by_file["backend"] == backend]["max_index"] == 0).mean()
            )
            frac_first_over_2x = float(
                df_by_file[df_by_file["backend"] == backend]["first_over_2x_rest_median"].mean()
            )
            frac_first_over_3x = float(
                df_by_file[df_by_file["backend"] == backend]["first_over_3x_rest_median"].mean()
            )

            cold_rows.append(
                {
                    "backend": backend,
                    "n_total_samples": s_all["n"],
                    "mean_ms": s_all["mean_ms"],
                    "median_ms": s_all["median_ms"],
                    "p99_ms": s_all["p99"],
                    "max_ms": s_all["max_ms"],
                    "n_excl_first_samples": s_excl["n"],
                    "mean_excl_first_ms": s_excl["mean_ms"],
                    "median_excl_first_ms": s_excl["median_ms"],
                    "p99_excl_first_ms": s_excl["p99"],
                    "max_excl_first_ms": s_excl["max_ms"],
                    "frac_max_at_first_sample_per_file": frac_max_at_first,
                    "frac_first_sample_over_2x_rest_median_per_file": frac_first_over_2x,
                    "frac_first_sample_over_3x_rest_median_per_file": frac_first_over_3x,
                }
            )

        df_cold = pd.DataFrame(cold_rows).sort_values("backend").reset_index(drop=True)
        df_cold.to_csv(processed_dir / "cold_start_effect_overall.csv", index=False)

        df_cold_scenario = (
            df_by_file.groupby(["scenario", "backend"], as_index=False)
            .agg(
                files=("path", "nunique"),
                max_ms=("max_ms", "max"),
                frac_max_at_first_sample=("max_index", lambda s: float((s == 0).mean())),
                mean_ms=("mean_ms", "mean"),
                mean_excl_first_ms=("mean_excl_first_ms", "mean"),
            )
            .sort_values(["scenario", "backend"])
            .reset_index(drop=True)
        )
        df_cold_scenario.to_csv(processed_dir / "cold_start_effect_by_scenario_backend.csv", index=False)

    # Plots
    import matplotlib.pyplot as plt  # type: ignore

    def plot_cdf(df_in: pd.DataFrame, title: str, path: Path) -> None:
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        for backend in backends:
            vals = (
                df_in[df_in["backend"] == backend]["latency_ms"].dropna().to_numpy(dtype=float)
            )
            if vals.size == 0:
                continue
            xs = np.sort(vals)
            ys = np.arange(1, xs.size + 1) / xs.size
            ax.plot(xs, ys, label=f"{backend} (n={xs.size})", linewidth=2)
        ax.set_title(title)
        ax.set_xlabel("Latency (ms)")
        ax.set_ylabel("CDF")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="lower right")
        _save_plot(fig, path)
        plt.close(fig)

    plot_cdf(df, "TR120.A: Latency CDF (overall; TR117 tier3)", plots_dir / "cdf_latency_overall.png")

    for quant, group in df.groupby("quantization"):
        plot_cdf(
            group,
            f"TR120.A: Latency CDF ({quant}; TR117 tier3)",
            plots_dir / f"cdf_latency_{quant}.png",
        )

    # Quantile comparison plot
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    qs = np.array([50, 90, 95, 99])
    for backend in backends:
        vals = df[df["backend"] == backend]["latency_ms"].dropna().to_numpy(dtype=float)
        if vals.size == 0:
            continue
        ax.plot(qs, np.percentile(vals, qs), marker="o", linewidth=2, label=backend)
    ax.set_title("TR120.A: Latency quantiles (overall; TR117 tier3)")
    ax.set_xlabel("Percentile")
    ax.set_ylabel("Latency (ms)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    _save_plot(fig, plots_dir / "quantiles_overall.png")
    plt.close(fig)

    # Write summary json
    meta = {
        "generated_at_unix": int(time.time()),
        "metrics_csv": str(metrics_path.as_posix()),
        "row_count": int(df.shape[0]),
        "backends": backends,
        "model_filter": args.model,
        "quantization_filter": args.quantizations,
    }
    out_json = {
        "metadata": meta,
        "summaries": {
            "overall": df_overall.to_dict(orient="records"),
            "by_quantization": df_quant.to_dict(orient="records"),
        },
        "comparisons": comparisons,
    }
    if not df_by_file.empty:
        out_json["cold_start"] = {
            "note": "Computed from TR117 run JSON arrays; 'first sample' is the first element of latencies_ms per run file.",
            "files_analyzed": int(df_by_file["path"].nunique()),
            "paths": {
                "by_file_csv": str((processed_dir / 'cold_start_by_file.csv').as_posix()),
                "overall_csv": str((processed_dir / 'cold_start_effect_overall.csv').as_posix()),
                "by_scenario_backend_csv": str(
                    (processed_dir / 'cold_start_effect_by_scenario_backend.csv').as_posix()
                ),
            },
        }
    _write_json(processed_dir / "summary.json", out_json)

    print(f"TR120 analysis written to: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
