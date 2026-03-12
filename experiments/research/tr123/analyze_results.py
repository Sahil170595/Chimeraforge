#!/usr/bin/env python3
"""
TR123: KV-Cache Production Economics — Cost Analysis Pipeline.

Loads raw JSONL measurements from run_benchmark.py and computes:
- Phase-split $/1M tokens (prefill vs decode, per pricing tier)
- Phase-tagged energy attribution (J/tok per phase)
- Production-grade cost tables with statistical summaries
- TCO projections

Imports shared statistics from research/shared/ and cost functions from TR119.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
import sys
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from shared utilities
# ---------------------------------------------------------------------------

try:
    from research.shared.statistical_analysis import (
        bootstrap_confidence_interval,
        compute_summary,
        detect_outliers,
    )
except ImportError:
    # Minimal fallbacks
    def compute_summary(values):
        if not values:
            return {}
        import statistics

        return {
            "n": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }

    def bootstrap_confidence_interval(values, **kwargs):
        return None

    def detect_outliers(values, **kwargs):
        return []


try:
    from research.tr119.artifact_utils import (
        compute_carbon_footprint,
        compute_cost_per_1m_tokens,
        compute_energy_from_power,
        compute_kwh_from_joules,
        compute_tco,
    )
except ImportError:
    logger.warning("TR119 artifact_utils not available, using inline implementations")

    def compute_cost_per_1m_tokens(
        gpu_hours_per_1m_tokens,
        on_demand_usd_per_hour,
        energy_kwh_per_1m_tokens=None,
        usd_per_kwh=None,
    ):
        infra = gpu_hours_per_1m_tokens * on_demand_usd_per_hour
        energy = (energy_kwh_per_1m_tokens or 0) * (usd_per_kwh or 0)
        return {
            "infra_cost_usd_per_1m_tokens": infra,
            "energy_cost_usd_per_1m_tokens": energy if energy else None,
            "total_cost_usd_per_1m_tokens": infra + energy,
        }

    def compute_energy_from_power(power_watts, duration_seconds):
        return power_watts * duration_seconds

    def compute_kwh_from_joules(joules):
        return joules / 3.6e6

    def compute_carbon_footprint(energy_kwh, carbon_intensity=500.0):
        return energy_kwh * carbon_intensity

    def compute_tco(
        infra_cost_per_1m,
        energy_cost_per_1m,
        tokens_per_month,
        months=12,
        upfront_cost=0.0,
    ):
        cost_per_1m = infra_cost_per_1m + energy_cost_per_1m
        cost_per_month = (cost_per_1m / 1_000_000) * tokens_per_month
        total = upfront_cost + (cost_per_month * months)
        return {"total_cost_usd": total, "cost_per_month_usd": cost_per_month}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_results(jsonl_path: str | Path) -> list[dict[str, Any]]:
    """Load raw measurements from JSONL, filtering to status=ok rows."""
    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("status") == "ok":
                rows.append(row)
    logger.info(f"Loaded {len(rows)} ok rows from {jsonl_path}")
    return rows


# ---------------------------------------------------------------------------
# Phase-split cost computation
# ---------------------------------------------------------------------------


def compute_phase_cost(
    row: dict[str, Any],
    pricing_usd_per_hr: float,
    energy_cfg: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute $/1M tokens for prefill and decode phases separately.

    Args:
        row: Single measurement record with prefill_ms, decode_ms, prompt_tokens, gen_tokens
        pricing_usd_per_hr: GPU/server cost per hour
        energy_cfg: Optional {"usd_per_kwh": float, "carbon_intensity_gco2e_per_kwh": float}

    Returns:
        Dict with prefill and decode cost breakdowns
    """
    prefill_ms = row.get("prefill_ms") or row.get("prefill_cuda_ms")
    decode_ms = row.get("decode_ms") or row.get("decode_cuda_ms")
    prompt_tokens = row.get("prompt_tokens", 0)
    gen_tokens = row.get("gen_tokens", 0)

    if not prefill_ms or not decode_ms or not prompt_tokens or not gen_tokens:
        return {"status": "incomplete", "error": "missing timing or token counts"}

    # Throughput
    prefill_tok_per_s = prompt_tokens / (prefill_ms / 1000.0)
    decode_tok_per_s = gen_tokens / (decode_ms / 1000.0)

    # GPU-hours per 1M tokens
    prefill_gpu_hrs_per_1m = 1_000_000.0 / prefill_tok_per_s / 3600.0
    decode_gpu_hrs_per_1m = 1_000_000.0 / decode_tok_per_s / 3600.0

    # Cost per 1M tokens
    energy_kwh_per_1m_prefill = None
    energy_kwh_per_1m_decode = None

    # Phase-tagged energy from PhasePowerSampler (not whole-run average)
    phase_power = row.get("phase_power", {})
    prefill_power_w = (phase_power.get("prefill", {}) or {}).get("power_mean_w")
    decode_power_w = (phase_power.get("decode", {}) or {}).get("power_mean_w")

    if (
        prefill_power_w
        and prefill_power_w > 0
        and decode_power_w
        and decode_power_w > 0
    ):
        prefill_energy_j = prefill_power_w * (prefill_ms / 1000.0)
        decode_energy_j = decode_power_w * (decode_ms / 1000.0)

        prefill_j_per_tok = prefill_energy_j / prompt_tokens
        decode_j_per_tok = decode_energy_j / gen_tokens

        energy_kwh_per_1m_prefill = compute_kwh_from_joules(
            prefill_j_per_tok * 1_000_000
        )
        energy_kwh_per_1m_decode = compute_kwh_from_joules(decode_j_per_tok * 1_000_000)
    else:
        prefill_j_per_tok = None
        decode_j_per_tok = None

    usd_per_kwh = (energy_cfg or {}).get("usd_per_kwh")

    prefill_cost = compute_cost_per_1m_tokens(
        prefill_gpu_hrs_per_1m,
        pricing_usd_per_hr,
        energy_kwh_per_1m_prefill,
        usd_per_kwh,
    )
    decode_cost = compute_cost_per_1m_tokens(
        decode_gpu_hrs_per_1m,
        pricing_usd_per_hr,
        energy_kwh_per_1m_decode,
        usd_per_kwh,
    )

    return {
        "prefill_tok_per_s": round(prefill_tok_per_s, 1),
        "decode_tok_per_s": round(decode_tok_per_s, 1),
        "prefill_gpu_hrs_per_1m": prefill_gpu_hrs_per_1m,
        "decode_gpu_hrs_per_1m": decode_gpu_hrs_per_1m,
        "prefill_cost_per_1m": prefill_cost["total_cost_usd_per_1m_tokens"],
        "decode_cost_per_1m": decode_cost["total_cost_usd_per_1m_tokens"],
        "prefill_infra_cost_per_1m": prefill_cost["infra_cost_usd_per_1m_tokens"],
        "decode_infra_cost_per_1m": decode_cost["infra_cost_usd_per_1m_tokens"],
        "prefill_energy_cost_per_1m": prefill_cost.get("energy_cost_usd_per_1m_tokens"),
        "decode_energy_cost_per_1m": decode_cost.get("energy_cost_usd_per_1m_tokens"),
        "prefill_j_per_tok": prefill_j_per_tok,
        "decode_j_per_tok": decode_j_per_tok,
    }


BLEND_RATIOS: dict[str, float] = {
    "rag_heavy": 0.95,  # RAG: long context, short answer
    "summarization": 0.85,  # Long input, short summary
    "chat": 0.67,  # Conversational (default)
    "balanced": 0.50,  # Equal input/output
    "code_gen": 0.25,  # Short prompt, long generation
}


def compute_production_cost(
    prefill_cost_per_1m: float,
    decode_cost_per_1m: float,
    input_ratio: float = 0.67,
) -> float:
    """Compute blended production cost given input/output token ratio."""
    output_ratio = 1.0 - input_ratio
    return (prefill_cost_per_1m * input_ratio) + (decode_cost_per_1m * output_ratio)


def compute_production_cost_sensitivity(
    prefill_cost_per_1m: float,
    decode_cost_per_1m: float,
) -> dict[str, float]:
    """Compute production cost across all standard workload blend ratios."""
    return {
        name: compute_production_cost(prefill_cost_per_1m, decode_cost_per_1m, ratio)
        for name, ratio in BLEND_RATIOS.items()
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_by_group(
    rows: list[dict[str, Any]],
    costs: list[dict[str, Any]],
    groupby: list[str],
) -> list[dict[str, Any]]:
    """Group measurements and compute statistical summaries."""
    from collections import defaultdict

    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)

    for row, cost in zip(rows, costs, strict=False):
        if "status" in cost and cost["status"] == "incomplete":
            continue
        key = tuple(row.get(k, "") for k in groupby)
        groups[key].append({**row, **cost})

    aggregated = []
    for key, items in groups.items():
        group_dict = dict(zip(groupby, key, strict=False))

        # Aggregate key metrics
        for metric in [
            "prefill_ms",
            "decode_ms",
            "total_ms",
            "prefill_tok_per_s",
            "decode_tok_per_s",
            "prefill_cost_per_1m",
            "decode_cost_per_1m",
            "prefill_j_per_tok",
            "decode_j_per_tok",
        ]:
            values = [x[metric] for x in items if x.get(metric) is not None]
            if values:
                summary = compute_summary(values)
                for stat_key, stat_val in vars(summary).items():
                    group_dict[f"{metric}_{stat_key}"] = stat_val

        # Production cost across all blend ratios
        for ratio_name, ratio_val in BLEND_RATIOS.items():
            prod_costs = []
            for item in items:
                pc = item.get("prefill_cost_per_1m")
                dc = item.get("decode_cost_per_1m")
                if pc is not None and dc is not None:
                    prod_costs.append(compute_production_cost(pc, dc, ratio_val))
            if prod_costs:
                summary = compute_summary(prod_costs)
                for stat_key, stat_val in vars(summary).items():
                    group_dict[f"cost_{ratio_name}_{stat_key}"] = stat_val

        # Default "production_cost" uses chat ratio for backward compat
        chat_costs = []
        for item in items:
            pc = item.get("prefill_cost_per_1m")
            dc = item.get("decode_cost_per_1m")
            if pc is not None and dc is not None:
                chat_costs.append(compute_production_cost(pc, dc, BLEND_RATIOS["chat"]))
        if chat_costs:
            summary = compute_summary(chat_costs)
            for stat_key, stat_val in vars(summary).items():
                group_dict[f"production_cost_per_1m_{stat_key}"] = stat_val

        group_dict["n_measurements"] = len(items)
        aggregated.append(group_dict)

    return aggregated


# ---------------------------------------------------------------------------
# Cost table builder
# ---------------------------------------------------------------------------


def build_cost_table(
    rows: list[dict[str, Any]],
    pricing_tiers: dict[str, dict[str, float]],
    energy_cfg: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Build full cost table across all pricing tiers."""
    table = []

    for tier_name, tier_prices in pricing_tiers.items():
        # Get the hourly rate (try common keys)
        hourly = (
            tier_prices.get("on_demand")
            or tier_prices.get("effective_hourly")
            or tier_prices.get("on_demand_usd_per_hour")
            or 0.0
        )
        if hourly <= 0:
            continue

        costs = [compute_phase_cost(row, hourly, energy_cfg) for row in rows]
        agg = aggregate_by_group(
            rows,
            costs,
            groupby=["model", "backend", "scenario"],
        )

        for group in agg:
            group["pricing_tier"] = tier_name
            group["hourly_rate"] = hourly
            table.append(group)

    return table


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(results_dir: str | Path, config_path: str | Path | None = None):
    """Run the full analysis pipeline on a results directory."""
    results_dir = Path(results_dir)
    jsonl_path = results_dir / "raw_measurements.jsonl"

    if not jsonl_path.exists():
        logger.error(f"No raw_measurements.jsonl found in {results_dir}")
        sys.exit(1)

    # Load config for pricing
    if config_path is None:
        config_path = Path(__file__).parent / "configs" / "matrix.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    pricing_tiers = cfg.get("cloud_pricing", {})
    energy_cfg = cfg.get("energy", {})

    rows = load_results(jsonl_path)
    if not rows:
        logger.error("No valid measurements found")
        sys.exit(1)

    # Compute costs for consumer tier as the default detailed output
    consumer_hourly = pricing_tiers.get("consumer_rtx4080", {}).get(
        "effective_hourly", 0.046
    )
    costs = [compute_phase_cost(row, consumer_hourly, energy_cfg) for row in rows]

    # Per-row detailed output
    detailed_path = results_dir / "cost_per_measurement.csv"
    detailed_rows = []
    for row, cost in zip(rows, costs, strict=False):
        phase_power = row.get("phase_power", {})
        detail = {
            "model": row.get("model"),
            "backend": row.get("backend"),
            "scenario": row.get("scenario"),
            "rep": row.get("rep"),
            "prompt_tokens": row.get("prompt_tokens"),
            "gen_tokens": row.get("gen_tokens"),
            "prefill_ms": row.get("prefill_ms"),
            "decode_ms": row.get("decode_ms"),
            "total_ms": row.get("total_ms"),
            "gpu_clock_mhz": row.get("gpu_clock_mhz"),
            "gpu_temp_c": row.get("gpu_temp_c"),
            "prefill_power_w": (phase_power.get("prefill", {}) or {}).get(
                "power_mean_w"
            ),
            "decode_power_w": (phase_power.get("decode", {}) or {}).get("power_mean_w"),
            "thermal_throttled": any(
                (phase_power.get(p, {}) or {}).get("thermal_throttled", False)
                for p in ("prefill", "decode")
            ),
            **{k: v for k, v in cost.items() if k != "status"},
        }
        # Add multi-ratio production costs
        pc = cost.get("prefill_cost_per_1m")
        dc = cost.get("decode_cost_per_1m")
        if pc is not None and dc is not None:
            for rname, rval in BLEND_RATIOS.items():
                detail[f"cost_{rname}"] = compute_production_cost(pc, dc, rval)
        detailed_rows.append(detail)

    if detailed_rows:
        with open(detailed_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=detailed_rows[0].keys())
            w.writeheader()
            w.writerows(detailed_rows)
        logger.info(f"Wrote {len(detailed_rows)} rows → {detailed_path}")

    # Aggregated summary
    agg = aggregate_by_group(
        rows,
        costs,
        groupby=["model", "backend", "scenario"],
    )
    summary_path = results_dir / "summary_stats.csv"
    if agg:
        # Collect all keys across all rows (some groups may have extra fields)
        all_keys: list[str] = []
        for row in agg:
            for k in row:
                if k not in all_keys:
                    all_keys.append(k)
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=all_keys)
            w.writeheader()
            w.writerows(agg)
        logger.info(f"Wrote {len(agg)} groups → {summary_path}")

    # Multi-tier cost table
    cost_table = build_cost_table(rows, pricing_tiers, energy_cfg)
    cost_table_path = results_dir / "cost_table_all_tiers.csv"
    if cost_table:
        # Collect all keys
        all_keys: list[str] = []
        for row in cost_table:
            for k in row:
                if k not in all_keys:
                    all_keys.append(k)
        with open(cost_table_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=all_keys)
            w.writeheader()
            w.writerows(cost_table)
        logger.info(f"Wrote {len(cost_table)} tier-groups → {cost_table_path}")

    logger.info("Analysis complete.")
    return results_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TR123: Cost Analysis Pipeline")
    parser.add_argument(
        "results_dir", help="Path to results directory with raw_measurements.jsonl"
    )
    parser.add_argument("--config", default=None, help="Path to matrix.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    main(args.results_dir, args.config)
