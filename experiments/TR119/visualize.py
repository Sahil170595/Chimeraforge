#!/usr/bin/env python3
"""
TR119: Visualization helpers.

Creates basic plots from results/processed CSVs for:
  - latency vs backend
  - total cost per 1M tokens vs backend
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
    parser = argparse.ArgumentParser(description="TR119 visualization")
    parser.add_argument(
        "--config",
        default="scripts/tr119/configs/baseline.yaml",
        help="TR119 config yaml",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    proc_dir = results_dir / "processed"
    plots_dir = results_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    summary_path = proc_dir / "latency_summary_cost.csv"
    if not summary_path.exists():
        raise SystemExit(f"{summary_path.name} not found; run analyze_results.py first")
    df = pd.read_csv(summary_path)

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        print("matplotlib not installed; skipping TR119 plots")
        return 0

    modes = ["prefill"]
    if "mode" in df.columns:
        modes = sorted(df["mode"].dropna().unique())

    for mode in modes:
        df_mode = df[df["mode"] == mode] if "mode" in df.columns else df
        suffix = "" if mode == "prefill" else f"_{mode}"

        # Mean latency by backend (averaged across scenarios)
        means = df_mode.groupby("backend")["mean"].mean().sort_values()
        plt.figure(figsize=(10, 4))
        means.plot(kind="bar", color="steelblue")
        plt.ylabel("Mean latency (ms)")
        plt.title(f"TR119 mean latency by backend ({mode})")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        out_lat = plots_dir / f"mean_latency_tr119{suffix}.png"
        plt.savefig(out_lat, dpi=150)
        plt.close()
        print(f"Saved plot to {out_lat}")

        # Throughput by backend
        if "throughput_mean_tok_s" in df_mode.columns:
            thr = df_mode.groupby("backend")["throughput_mean_tok_s"].mean().sort_values(ascending=False)
            plt.figure(figsize=(10, 4))
            thr.plot(kind="bar", color="green")
            plt.ylabel("Tokens/sec (mean)")
            plt.title(f"TR119 throughput by backend ({mode})")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            out_thr = plots_dir / f"throughput_tr119{suffix}.png"
            plt.savefig(out_thr, dpi=150)
            plt.close()
            print(f"Saved plot to {out_thr}")

    # Cost/energy analysis plots
    cost_json = proc_dir / "cost_energy_summary.json"
    if cost_json.exists():
        import json

        data = json.loads(cost_json.read_text(encoding="utf-8"))
        rows = data.get("rows") or []
        if rows:
            cost_df = pd.DataFrame(rows)
            cost_modes = ["prefill"]
            if "mode" in cost_df.columns:
                cost_modes = sorted(cost_df["mode"].dropna().unique())
            
            for mode in cost_modes:
                cost_mode = cost_df[cost_df["mode"] == mode] if "mode" in cost_df.columns else cost_df
                suffix = "" if mode == "prefill" else f"_{mode}"

                # Total cost per 1M tokens (on-demand) by backend
                cost_means = cost_mode.groupby("backend")["total_cost_usd_per_1m_tokens_on_demand"].mean().sort_values()
                plt.figure(figsize=(10, 4))
                cost_means.plot(kind="bar", color="coral")
                plt.ylabel("USD per 1M tokens")
                plt.title(f"TR119 total cost per 1M tokens (on-demand) by backend ({mode})")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                out_cost = plots_dir / f"total_cost_per_1m_tokens_tr119{suffix}.png"
                plt.savefig(out_cost, dpi=150)
                plt.close()
                print(f"Saved plot to {out_cost}")

                # Multi-tier pricing comparison (dynamic tiers)
                tier_labels = {
                    "total_cost_usd_per_1m_tokens_on_demand": "On-demand",
                    "total_cost_usd_per_1m_tokens_spot": "Spot",
                    "total_cost_usd_per_1m_tokens_reserved": "Reserved",
                    "total_cost_usd_per_1m_tokens_reserved_1yr": "Reserved 1yr",
                    "total_cost_usd_per_1m_tokens_reserved_3yr": "Reserved 3yr",
                    "total_cost_usd_per_1m_tokens_on_prem": "On-prem",
                }
                tier_cols = [c for c in tier_labels.keys() if c in cost_mode.columns]
                if len(tier_cols) >= 2 and "total_cost_usd_per_1m_tokens_on_demand" in tier_cols:
                    cost_by_tier = cost_mode.groupby("backend")[tier_cols].mean().sort_values(
                        "total_cost_usd_per_1m_tokens_on_demand"
                    )
                    plt.figure(figsize=(12, 5))
                    cost_by_tier.plot(kind="bar")
                    plt.ylabel("USD per 1M tokens")
                    plt.title(f"TR119 cost comparison by pricing tier ({mode})")
                    plt.legend([tier_labels[c] for c in tier_cols])
                    plt.xticks(rotation=45, ha="right")
                    plt.tight_layout()
                    out_tier = plots_dir / f"cost_tiers_tr119{suffix}.png"
                    plt.savefig(out_tier, dpi=150)
                    plt.close()
                    print(f"Saved plot to {out_tier}")

                # Energy efficiency: tokens per kWh
                if "energy_kwh_per_1m_tokens" in cost_mode.columns:
                    eff_df = cost_mode[cost_mode["energy_kwh_per_1m_tokens"] > 0].copy()
                    if not eff_df.empty:
                        eff_df["tokens_per_kwh"] = 1_000_000.0 / eff_df["energy_kwh_per_1m_tokens"]
                        eff = eff_df.groupby("backend")["tokens_per_kwh"].mean().sort_values(ascending=False)
                        plt.figure(figsize=(10, 4))
                        eff.plot(kind="bar", color="purple")
                        plt.ylabel("Tokens per kWh")
                        plt.title(f"TR119 energy efficiency (tokens per kWh) by backend ({mode})")
                        plt.xticks(rotation=45, ha="right")
                        plt.tight_layout()
                        out_eff = plots_dir / f"energy_efficiency_tr119{suffix}.png"
                        plt.savefig(out_eff, dpi=150)
                        plt.close()
                        print(f"Saved plot to {out_eff}")

                # Carbon footprint per 1M tokens
                if "carbon_gco2e_per_1m_tokens" in cost_mode.columns:
                    carbon = cost_mode.groupby("backend")["carbon_gco2e_per_1m_tokens"].mean().sort_values()
                    plt.figure(figsize=(10, 4))
                    carbon.plot(kind="bar", color="darkgreen")
                    plt.ylabel("gCO2e per 1M tokens")
                    plt.title(f"TR119 carbon footprint per 1M tokens by backend ({mode})")
                    plt.xticks(rotation=45, ha="right")
                    plt.tight_layout()
                    out_carbon = plots_dir / f"carbon_footprint_tr119{suffix}.png"
                    plt.savefig(out_carbon, dpi=150)
                    plt.close()
                    print(f"Saved plot to {out_carbon}")

                # Cost vs throughput scatter
                if "throughput_mean_tok_s" in cost_mode.columns:
                    cost_scatter = cost_mode.groupby("backend")[
                        ["total_cost_usd_per_1m_tokens_on_demand", "throughput_mean_tok_s"]
                    ].mean()
                    plt.figure(figsize=(8, 6))
                    plt.scatter(
                        cost_scatter["throughput_mean_tok_s"],
                        cost_scatter["total_cost_usd_per_1m_tokens_on_demand"],
                        s=100,
                        alpha=0.6,
                    )
                    for backend in cost_scatter.index:
                        plt.annotate(
                            backend,
                            (
                                cost_scatter.loc[backend, "throughput_mean_tok_s"],
                                cost_scatter.loc[backend, "total_cost_usd_per_1m_tokens_on_demand"],
                            ),
                            fontsize=8,
                        )
                    plt.xlabel("Throughput (tokens/sec)")
                    plt.ylabel("Cost per 1M tokens (USD)")
                    plt.title(f"TR119 cost vs throughput trade-off ({mode})")
                    plt.grid(True, alpha=0.3)
                    plt.tight_layout()
                    out_scatter = plots_dir / f"cost_vs_throughput_tr119{suffix}.png"
                    plt.savefig(out_scatter, dpi=150)
                    plt.close()
                    print(f"Saved plot to {out_scatter}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


