#!/usr/bin/env python3
"""
TR118: Visualization helpers.

Creates basic plots from results/processed CSVs when matplotlib is available.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import resolve_repo_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118 visualization")
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
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    mode = str(args.mode or cfg.get("benchmark", {}).get("mode", "prefill"))
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    proc_dir = results_dir / "processed"
    plots_dir = results_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    summary_path = proc_dir / f"latency_summary_{mode}.csv"
    if not summary_path.exists():
        raise SystemExit(f"{summary_path.name} not found; run analyze_results.py first")

    df = pd.read_csv(summary_path)
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        print("matplotlib not installed; skipping plots")
        return 0

    # Mean latency per backend (averaged over scenarios, ignoring missing)
    means = df.groupby("backend")["mean"].mean().sort_values()
    plt.figure(figsize=(10, 4))
    means.plot(kind="bar")
    plt.ylabel("Mean latency (ms)")
    plt.title(f"TR118 {mode} mean latency by backend")
    plt.tight_layout()
    out_path = plots_dir / f"mean_latency_{mode}.png"
    plt.savefig(out_path)
    print(f"Saved plot to {out_path}")

    if "throughput_mean_tok_s" in df.columns:
        thr = df.groupby("backend")["throughput_mean_tok_s"].mean().sort_values(ascending=False)
        plt.figure(figsize=(10, 4))
        thr.plot(kind="bar")
        plt.ylabel("Tokens/sec (mean)")
        plt.title(f"TR118 {mode} throughput by backend")
        plt.tight_layout()
        out_thr = plots_dir / f"mean_throughput_tok_s_{mode}.png"
        plt.savefig(out_thr)
        print(f"Saved plot to {out_thr}")

    if "degraded_rate" in df.columns:
        degr = df.groupby("backend")["degraded_rate"].mean().sort_values(ascending=False)
        plt.figure(figsize=(10, 4))
        degr.plot(kind="bar")
        plt.ylabel("Degraded rate")
        plt.title(f"TR118 {mode} degraded rate by backend (mean across scenarios)")
        plt.tight_layout()
        out_degr = plots_dir / f"degraded_rate_{mode}.png"
        plt.savefig(out_degr)
        print(f"Saved plot to {out_degr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
