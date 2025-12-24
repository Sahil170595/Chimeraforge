#!/usr/bin/env python3
"""
TR118: Statistical analysis for benchmark results.

Reads run-level JSONL from results/raw and writes latency/throughput summaries
to results/processed. Uses TR117 statistical helpers for CI/ttest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr117.statistical_analysis import compare_groups, compute_summary
from scripts.tr118.artifact_utils import resolve_repo_path


def _load_raw(paths: list[Path]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            records.append(json.loads(line))
    df = pd.DataFrame(records)
    df["backend"] = df["spec"].apply(lambda s: s["backend"])
    df["scenario"] = df["spec"].apply(lambda s: s["scenario"])
    df["mode"] = df["spec"].apply(lambda s: s.get("mode", "prefill"))
    df["repetition"] = df["spec"].apply(lambda s: s.get("repetition", 0))
    df["batch_size"] = df["spec"].apply(lambda s: s.get("batch_size", 0))
    df["seq_len"] = df["spec"].apply(lambda s: s.get("seq_len", 0))
    df["run_mean_latency_ms"] = df["latencies_ms"].apply(
        lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
    )
    if "ttft_ms" in df.columns:
        df["run_mean_ttft_ms"] = df["ttft_ms"].apply(
            lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
        )
    else:
        df["run_mean_ttft_ms"] = None
    df["run_mean_throughput_tok_s"] = df["throughput_tok_s"].apply(
        lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
    )
    df["run_mean_warmup_latency_ms"] = df["warmup_latencies_ms"].apply(
        lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
    )
    df["degraded"] = df.apply(
        lambda r: bool(r.get("degraded_count", 0) > 0) or str(r.get("status", "")) != "ok",
        axis=1,
    )
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118 analysis")
    parser.add_argument(
        "--config",
        default="scripts/tr118/configs/baseline.yaml",
        help="TR118 config yaml",
    )
    parser.add_argument(
        "--mode",
        choices=["prefill", "generate"],
        default=None,
        help="Benchmark mode (defaults to config.benchmark.mode or prefill)",
    )
    parser.add_argument(
        "--raw",
        nargs="*",
        help="Raw jsonl files (defaults to latest in results/raw)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    mode = str(args.mode or cfg.get("benchmark", {}).get("mode", "prefill"))
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    raw_dir = results_dir / "raw"
    if args.raw:
        raw_files = [resolve_repo_path(_REPO_ROOT, str(p)) for p in args.raw]
    else:
        raw_files = sorted(raw_dir.glob(f"bench_{mode}_*.jsonl"), key=lambda p: p.stat().st_mtime)
        raw_files = [p for p in raw_files if p.exists() and p.stat().st_size > 0]
        if not raw_files:
            raw_files = sorted(raw_dir.glob("bench_*.jsonl"), key=lambda p: p.stat().st_mtime)
            raw_files = [p for p in raw_files if p.exists() and p.stat().st_size > 0]
        raw_files = raw_files[-1:] if raw_files else []
    if not raw_files:
        raise SystemExit("No raw results found")

    df = _load_raw(raw_files)
    df = df[df["mode"] == mode]
    df["degraded"] = df["degraded"].astype(bool)
    df_ok = df[(df["run_mean_latency_ms"].notna()) & (df["degraded"] == False)]  # noqa: E712

    totals = (
        df.groupby(["backend", "scenario"])["degraded"]
        .agg(n_total="count", n_degraded="sum")
        .reset_index()
    )
    totals["n_ok"] = totals["n_total"] - totals["n_degraded"]
    totals["degraded_rate"] = totals["n_degraded"] / totals["n_total"].where(totals["n_total"] > 0, 1)

    ok_groups = {(b, s): g for (b, s), g in df_ok.groupby(["backend", "scenario"])}

    rows: list[dict[str, Any]] = []
    for r in totals.to_dict(orient="records"):
        backend = str(r["backend"])
        scenario = str(r["scenario"])
        group = ok_groups.get((backend, scenario))

        values = [float(v) for v in group["run_mean_latency_ms"].tolist()] if group is not None else []
        summary = compute_summary(values) if values else None

        thr_values = (
            [float(v) for v in group["run_mean_throughput_tok_s"].dropna().tolist()] if group is not None else []
        )
        thr_summary = compute_summary(thr_values) if thr_values else None

        ttft_values = (
            [float(v) for v in group["run_mean_ttft_ms"].dropna().tolist()] if group is not None else []
        )
        ttft_summary = compute_summary(ttft_values) if ttft_values else None

        warm_values = (
            [float(v) for v in group["run_mean_warmup_latency_ms"].dropna().tolist()] if group is not None else []
        )
        warm_summary = compute_summary(warm_values) if warm_values else None

        row = {
            "backend": backend,
            "scenario": scenario,
            "n_total": int(r["n_total"]),
            "n_ok": int(r["n_ok"]),
            "n_degraded": int(r["n_degraded"]),
            "degraded_rate": float(r["degraded_rate"]),
            "throughput_mean_tok_s": thr_summary.mean if thr_summary else None,
            "throughput_median_tok_s": thr_summary.median if thr_summary else None,
            "ttft_mean_ms": ttft_summary.mean if ttft_summary else None,
            "ttft_median_ms": ttft_summary.median if ttft_summary else None,
            "warmup_mean_latency_ms": warm_summary.mean if warm_summary else None,
            "warmup_median_latency_ms": warm_summary.median if warm_summary else None,
        }
        if summary is not None:
            row |= summary.__dict__
        else:
            row |= {
                "mean": None,
                "median": None,
                "std": None,
                "min": None,
                "max": None,
                "q25": None,
                "q75": None,
                "ci_lower": None,
                "ci_upper": None,
                "n": 0,
            }
        rows.append(row)

    out_dir = results_dir / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / f"latency_summary_{mode}.csv"
    pd.DataFrame(rows).to_csv(summary_path, index=False)

    baseline_backend = str(cfg.get("baseline", {}).get("backend", "")).strip()
    comparisons = []
    comparisons_by_scenario = []
    throughput_comparisons = []
    ttft_comparisons = []
    if baseline_backend and baseline_backend in set(df_ok["backend"]):
        base_df = df_ok[df_ok["backend"] == baseline_backend]

        # Overall latency comparisons (aggregated across scenarios)
        base_vals_all = base_df["run_mean_latency_ms"].tolist()
        for backend, group in df_ok.groupby("backend"):
            if backend == baseline_backend:
                continue
            comp = compare_groups(
                [float(v) for v in base_vals_all],
                [float(v) for v in group["run_mean_latency_ms"].tolist()],
                baseline_backend,
                backend,
                "latency_ms",
            )
            comparisons.append(comp.__dict__)

        base_ttft_all = [float(v) for v in base_df["run_mean_ttft_ms"].dropna().tolist()]
        if base_ttft_all:
            for backend, group in df_ok.groupby("backend"):
                if backend == baseline_backend:
                    continue
                vals = [float(v) for v in group["run_mean_ttft_ms"].dropna().tolist()]
                if not vals:
                    continue
                comp = compare_groups(
                    base_ttft_all,
                    vals,
                    baseline_backend,
                    backend,
                    "ttft_ms",
                )
                ttft_comparisons.append(comp.__dict__)

        # Per-scenario latency + throughput comparisons
        for scenario in sorted(set(df_ok["scenario"].tolist())):
            base_s = base_df[base_df["scenario"] == scenario]
            if base_s.empty:
                continue
            base_latency = [float(v) for v in base_s["run_mean_latency_ms"].tolist()]
            base_thr = [float(v) for v in base_s["run_mean_throughput_tok_s"].dropna().tolist()]
            base_ttft = [float(v) for v in base_s["run_mean_ttft_ms"].dropna().tolist()]
            for backend, group in df_ok[df_ok["scenario"] == scenario].groupby("backend"):
                if backend == baseline_backend:
                    continue
                latency_vals = [float(v) for v in group["run_mean_latency_ms"].tolist()]
                comp = compare_groups(
                    base_latency,
                    latency_vals,
                    baseline_backend,
                    backend,
                    f"latency_ms::{scenario}",
                )
                comparisons_by_scenario.append(comp.__dict__)

                thr_vals = [float(v) for v in group["run_mean_throughput_tok_s"].dropna().tolist()]
                if base_thr and thr_vals:
                    thr_comp = compare_groups(
                        base_thr,
                        thr_vals,
                        baseline_backend,
                        backend,
                        f"throughput_tok_s::{scenario}",
                    )
                    throughput_comparisons.append(thr_comp.__dict__)

                ttft_vals = [float(v) for v in group["run_mean_ttft_ms"].dropna().tolist()]
                if base_ttft and ttft_vals:
                    ttft_comp = compare_groups(
                        base_ttft,
                        ttft_vals,
                        baseline_backend,
                        backend,
                        f"ttft_ms::{scenario}",
                    )
                    ttft_comparisons.append(ttft_comp.__dict__)

    (out_dir / f"statistical_analysis_{mode}.json").write_text(
        json.dumps(
            {
                "comparisons": comparisons,
                "comparisons_by_scenario": comparisons_by_scenario,
                "throughput_comparisons_by_scenario": throughput_comparisons,
                "ttft_comparisons": ttft_comparisons,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Latency summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
