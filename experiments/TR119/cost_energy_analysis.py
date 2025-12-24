#!/usr/bin/env python3
"""
TR119: Deep-dive cost & energy analysis scripts.

Provides analysis functions for:
- Cost breakdown by component (infra vs energy)
- ROI calculations for different pricing tiers
- Energy efficiency rankings
- Carbon footprint comparisons
- Cost amortization analysis
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

from scripts.tr118.artifact_utils import resolve_repo_path
from scripts.tr119.artifact_utils import (
    compute_carbon_footprint,
    compute_cost_per_1m_tokens,
    compute_roi_savings,
    compute_tco,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def analyze_cost_breakdown(cost_df: pd.DataFrame) -> dict[str, Any]:
    """Analyze cost breakdown: infra vs energy."""
    breakdown: dict[str, Any] = {}
    for backend in cost_df["backend"].unique():
        backend_data = cost_df[cost_df["backend"] == backend]
        infra_mean = float(backend_data["infra_cost_usd_per_1m_tokens_on_demand"].mean())
        energy_mean = float(backend_data["energy_cost_usd_per_1m_tokens"].mean())
        total_mean = float(backend_data["total_cost_usd_per_1m_tokens_on_demand"].mean())
        
        breakdown[backend] = {
            "infra_cost_usd_per_1m": infra_mean,
            "energy_cost_usd_per_1m": energy_mean,
            "total_cost_usd_per_1m": total_mean,
            "infra_pct": (infra_mean / total_mean * 100) if total_mean > 0 else 0.0,
            "energy_pct": (energy_mean / total_mean * 100) if total_mean > 0 else 0.0,
        }
    return breakdown


def analyze_roi_by_tier(
    cost_df: pd.DataFrame,
    tokens_per_month: float,
    months: int,
) -> dict[str, Any]:
    """Analyze ROI savings by switching pricing tiers."""
    roi: dict[str, Any] = {}
    for backend in cost_df["backend"].unique():
        backend_data = cost_df[cost_df["backend"] == backend]
        on_demand = float(backend_data["total_cost_usd_per_1m_tokens_on_demand"].mean())
        spot = (
            float(backend_data["total_cost_usd_per_1m_tokens_spot"].mean())
            if "total_cost_usd_per_1m_tokens_spot" in backend_data.columns
            else None
        )
        reserved = None
        if "total_cost_usd_per_1m_tokens_reserved" in backend_data.columns:
            reserved = float(backend_data["total_cost_usd_per_1m_tokens_reserved"].mean())
        elif "total_cost_usd_per_1m_tokens_reserved_1yr" in backend_data.columns:
            reserved = float(backend_data["total_cost_usd_per_1m_tokens_reserved_1yr"].mean())
        elif "total_cost_usd_per_1m_tokens_reserved_3yr" in backend_data.columns:
            reserved = float(backend_data["total_cost_usd_per_1m_tokens_reserved_3yr"].mean())

        spot_savings = (
            compute_roi_savings(on_demand, spot, tokens_per_month, months) if spot is not None else None
        )
        reserved_savings = (
            compute_roi_savings(on_demand, reserved, tokens_per_month, months)
            if reserved is not None
            else None
        )

        candidates = [
            ("spot", spot),
            ("reserved", reserved),
        ]
        candidates = [(name, cost) for name, cost in candidates if cost is not None]
        best_tier, best_cost = (min(candidates, key=lambda x: x[1]) if candidates else ("on_demand", on_demand))

        roi[backend] = {
            "on_demand_cost": on_demand,
            "spot_cost": spot,
            "reserved_cost": reserved,
            "spot_savings_pct": spot_savings["savings_pct"] if spot_savings else None,
            "spot_savings_usd": spot_savings["savings_usd"] if spot_savings else None,
            "reserved_savings_pct": reserved_savings["savings_pct"] if reserved_savings else None,
            "reserved_savings_usd": reserved_savings["savings_usd"] if reserved_savings else None,
            "best_tier": best_tier,
            "best_cost": best_cost,
        }
    return roi


def analyze_energy_efficiency(cost_df: pd.DataFrame) -> pd.DataFrame:
    """Rank backends by energy efficiency (tokens per kWh)."""
    cost_df = cost_df.copy()
    cost_df = cost_df[cost_df["energy_kwh_per_1m_tokens"] > 0]
    if cost_df.empty:
        return pd.Series(dtype=float)
    cost_df["tokens_per_kwh"] = 1_000_000.0 / cost_df["energy_kwh_per_1m_tokens"]
    efficiency = cost_df.groupby("backend")["tokens_per_kwh"].mean().sort_values(ascending=False)
    return efficiency


def analyze_carbon_comparison(cost_df: pd.DataFrame) -> dict[str, Any]:
    """Compare carbon footprints across backends."""
    carbon = cost_df.groupby("backend")["carbon_gco2e_per_1m_tokens"].mean().sort_values()
    return {
        "lowest_carbon_backend": str(carbon.index[0]),
        "lowest_carbon_gco2e": float(carbon.iloc[0]),
        "highest_carbon_backend": str(carbon.index[-1]),
        "highest_carbon_gco2e": float(carbon.iloc[-1]),
        "carbon_range_gco2e": float(carbon.iloc[-1] - carbon.iloc[0]),
        "by_backend": {str(k): float(v) for k, v in carbon.items()},
    }


def analyze_cost_amortization(
    cost_df: pd.DataFrame,
    upfront_cost_usd: float = 0.0,
    tokens_per_month: float = 1_000_000_000.0,  # 1B tokens/month
) -> dict[str, Any]:
    """Analyze cost amortization over time with upfront costs."""
    amortization: dict[str, Any] = {}
    months = [1, 3, 6, 12, 24]
    
    for backend in cost_df["backend"].unique():
        backend_data = cost_df[cost_df["backend"] == backend]
        cost_per_1m = float(backend_data["total_cost_usd_per_1m_tokens_on_demand"].mean())
        cost_per_month = (cost_per_1m / 1_000_000.0) * tokens_per_month
        
        amort: dict[str, Any] = {
            "cost_per_1m_tokens": cost_per_1m,
            "cost_per_month": cost_per_month,
            "upfront_cost": upfront_cost_usd,
            "break_even_months": None,
        }
        
        if upfront_cost_usd > 0:
            # Find break-even: when cumulative operational cost exceeds upfront
            cumulative = 0.0
            for m in months:
                cumulative += cost_per_month
                if cumulative >= upfront_cost_usd and amort["break_even_months"] is None:
                    amort["break_even_months"] = m
                amort[f"total_cost_month_{m}"] = upfront_cost_usd + (cost_per_month * m)
        else:
            for m in months:
                amort[f"total_cost_month_{m}"] = cost_per_month * m
        
        amortization[backend] = amort
    
    return amortization


def analyze_tco(
    cost_df: pd.DataFrame,
    tokens_per_month: float,
    months: int,
    upfront_cost_usd: float,
) -> dict[str, Any]:
    """Compute TCO by backend using on-demand infra + energy costs."""
    tco: dict[str, Any] = {}
    for backend in cost_df["backend"].unique():
        backend_data = cost_df[cost_df["backend"] == backend]
        if "infra_cost_usd_per_1m_tokens_on_demand" not in backend_data:
            continue
        infra_mean = float(backend_data["infra_cost_usd_per_1m_tokens_on_demand"].mean())
        energy_mean = float(backend_data["energy_cost_usd_per_1m_tokens"].mean())
        tco[backend] = compute_tco(
            infra_cost_per_1m=infra_mean,
            energy_cost_per_1m=energy_mean,
            tokens_per_month=tokens_per_month,
            months=months,
            upfront_cost=upfront_cost_usd,
        )
    return tco


def main() -> int:
    parser = argparse.ArgumentParser(description="TR119 cost/energy deep-dive analysis")
    parser.add_argument(
        "--config",
        default="scripts/tr119/configs/baseline.yaml",
        help="TR119 config yaml",
    )
    parser.add_argument(
        "--cost-summary",
        default=None,
        help="Cost summary JSON (defaults to latest in results/processed)",
    )
    parser.add_argument(
        "--tokens-per-month",
        type=float,
        default=None,
        help="Tokens per month for ROI/TCO calculations (default: config or 1e9)",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=None,
        help="Months for ROI/TCO calculations (default: config or 12)",
    )
    parser.add_argument(
        "--upfront-cost",
        type=float,
        default=None,
        help="Upfront cost in USD for amortization/TCO (default: config or 0)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    processed_dir = results_dir / "processed"

    cost_summary_path = (
        resolve_repo_path(_REPO_ROOT, str(args.cost_summary))
        if args.cost_summary
        else processed_dir / "cost_energy_summary.json"
    )
    
    if not cost_summary_path.exists():
        print(f"Cost summary not found: {cost_summary_path}")
        return 1
    
    cost_data = json.loads(cost_summary_path.read_text(encoding="utf-8"))
    cost_df = pd.DataFrame(cost_data.get("rows", []))

    if cost_df.empty:
        print("No cost data to analyze")
        return 1

    analysis_cfg = cfg.get("analysis", {}) or {}
    tokens_per_month = float(args.tokens_per_month or analysis_cfg.get("tokens_per_month", 1_000_000_000.0))
    months = int(args.months or analysis_cfg.get("months", 12))
    upfront_cost_usd = (
        float(args.upfront_cost)
        if args.upfront_cost is not None
        else float(analysis_cfg.get("upfront_cost_usd", 0.0))
    )
    prompt_tokens = analysis_cfg.get("prompt_tokens")
    generate_tokens = analysis_cfg.get("generate_tokens")
    prompt_tokens = float(prompt_tokens) if prompt_tokens is not None else None
    generate_tokens = float(generate_tokens) if generate_tokens is not None else None

    # Run analyses
    breakdown = analyze_cost_breakdown(cost_df)
    roi = analyze_roi_by_tier(cost_df, tokens_per_month, months)
    efficiency = analyze_energy_efficiency(cost_df)
    carbon = analyze_carbon_comparison(cost_df)
    amortization = analyze_cost_amortization(cost_df, upfront_cost_usd, tokens_per_month)
    tco = analyze_tco(cost_df, tokens_per_month, months, upfront_cost_usd)
    request_costs: dict[str, Any] = {}
    if prompt_tokens and generate_tokens:
        energy_usd_per_kwh = float(cfg.get("energy", {}).get("usd_per_kwh", 0.2))
        on_demand_rate = float(cfg.get("cloud_pricing", {}).get("on_demand_usd_per_hour", 1.0))
        for backend in cost_df["backend"].unique():
            prefill = cost_df[(cost_df["backend"] == backend) & (cost_df["mode"] == "prefill")]
            generate = cost_df[(cost_df["backend"] == backend) & (cost_df["mode"] == "generate")]
            if prefill.empty or generate.empty:
                continue
            prefill_thr = float(prefill["throughput_mean_tok_s"].mean())
            gen_thr = float(generate["throughput_mean_tok_s"].mean())
            prefill_power = float(prefill["power_mean_watts"].mean())
            gen_power = float(generate["power_mean_watts"].mean())
            if prefill_thr <= 0 or gen_thr <= 0 or prefill_power <= 0 or gen_power <= 0:
                continue
            prefill_time_s = prompt_tokens / prefill_thr
            gen_time_s = generate_tokens / gen_thr
            total_time_s = prefill_time_s + gen_time_s
            energy_kwh = (prefill_power * prefill_time_s + gen_power * gen_time_s) / 3.6e6
            infra_cost = (total_time_s / 3600.0) * on_demand_rate
            energy_cost = energy_kwh * energy_usd_per_kwh
            total_cost = infra_cost + energy_cost
            request_costs[str(backend)] = {
                "prompt_tokens": prompt_tokens,
                "generate_tokens": generate_tokens,
                "time_prefill_s": prefill_time_s,
                "time_generate_s": gen_time_s,
                "energy_kwh_per_request": energy_kwh,
                "infra_cost_usd_per_request": infra_cost,
                "energy_cost_usd_per_request": energy_cost,
                "total_cost_usd_per_request": total_cost,
            }

    analysis_result = {
        "cost_breakdown": breakdown,
        "roi_by_tier": roi,
        "energy_efficiency_ranking": {str(k): float(v) for k, v in efficiency.items()},
        "carbon_comparison": carbon,
        "cost_amortization": amortization,
        "tco_by_backend": tco,
        "request_costs": request_costs,
        "assumptions": {
            "tokens_per_month": tokens_per_month,
            "months": months,
            "upfront_cost_usd": upfront_cost_usd,
            "prompt_tokens": prompt_tokens,
            "generate_tokens": generate_tokens,
        },
    }

    out_path = processed_dir / "cost_energy_analysis.json"
    out_path.write_text(json.dumps(analysis_result, indent=2), encoding="utf-8")
    print(f"Cost/energy analysis written to {out_path}")

    # Print summary
    print("\n=== Cost Breakdown (Infra vs Energy) ===")
    for backend, data in sorted(breakdown.items(), key=lambda x: x[1]["total_cost_usd_per_1m"]):
        print(f"{backend}:")
        print(f"  Total: ${data['total_cost_usd_per_1m']:.4f}/1M tokens")
        print(f"  Infra: ${data['infra_cost_usd_per_1m']:.4f} ({data['infra_pct']:.1f}%)")
        print(f"  Energy: ${data['energy_cost_usd_per_1m']:.4f} ({data['energy_pct']:.1f}%)")

    print("\n=== Energy Efficiency Ranking ===")
    for backend, tokens_per_kwh in efficiency.items():
        print(f"{backend}: {tokens_per_kwh:.0f} tokens/kWh")

    print("\n=== Carbon Footprint ===")
    print(f"Lowest: {carbon['lowest_carbon_backend']} ({carbon['lowest_carbon_gco2e']:.1f} gCO2e/1M tokens)")
    print(f"Highest: {carbon['highest_carbon_backend']} ({carbon['highest_carbon_gco2e']:.1f} gCO2e/1M tokens)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

