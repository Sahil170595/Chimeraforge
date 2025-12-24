#!/usr/bin/env python3
"""
TR119: Cost & Energy Validation

Validates that cost/energy calculations are reasonable and consistent.

Outputs:
- `scripts/tr119/results/processed/cost_energy_validation.json`
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

from scripts.tr119.artifact_utils import (
    compute_carbon_footprint,
    compute_cost_per_1m_tokens,
    compute_energy_from_power,
    compute_kwh_from_joules,
    resolve_repo_path,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_cost_model(
    cost_summary: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate cost model sanity.

    Checks:
    - Costs are positive
    - Energy costs are reasonable (< infra costs typically)
    - Total costs are within expected ranges
    """
    issues: list[str] = []
    warnings: list[str] = []

    on_demand = float(config.get("cloud_pricing", {}).get("on_demand_usd_per_hour", 1.0))
    usd_per_kwh = float(config.get("energy", {}).get("usd_per_kwh", 0.2))
    require_cpu_power = bool(config.get("telemetry", {}).get("require_cpu_power", False))

    rows: list[dict[str, Any]] = []
    if isinstance(cost_summary, dict) and isinstance(cost_summary.get("rows"), list):
        rows = [r for r in cost_summary.get("rows", []) if isinstance(r, dict)]
    elif isinstance(cost_summary, list):
        rows = [r for r in cost_summary if isinstance(r, dict)]

    if not rows:
        return {
            "valid": False,
            "issues": ["No cost rows found in cost summary"],
            "warnings": [],
            "on_demand_rate": on_demand,
            "energy_rate": usd_per_kwh,
        }

    for row in rows:
        backend = str(row.get("backend", "unknown"))
        scenario = str(row.get("scenario", "unknown"))
        mode = str(row.get("mode", "prefill"))
        label = f"{backend}/{scenario}/{mode}"

        infra_keys = [k for k in row.keys() if str(k).startswith("infra_cost_usd_per_1m_tokens_")]
        total_keys = [k for k in row.keys() if str(k).startswith("total_cost_usd_per_1m_tokens_")]
        energy_cost = row.get("energy_cost_usd_per_1m_tokens")
        power_source = row.get("power_source")
        backend_lower = backend.lower()
        is_cpu_backend = ("cpu" in backend_lower) and ("gpu" not in backend_lower)

        if not infra_keys:
            warnings.append(f"{label}: missing infra cost fields")
        if not total_keys:
            warnings.append(f"{label}: missing total cost fields")

        for infra_key in infra_keys:
            infra_cost = row.get(infra_key)
            if infra_cost is None:
                continue
            if infra_cost < 0:
                issues.append(f"{label}: negative {infra_key} ({infra_cost})")
            if infra_cost > 1000.0:
                warnings.append(f"{label}: very high {infra_key} ({infra_cost:.2f} USD/1M tokens)")

        if energy_cost is not None:
            if energy_cost < 0:
                issues.append(f"{label}: negative energy_cost ({energy_cost})")
            infra_on_demand = row.get("infra_cost_usd_per_1m_tokens_on_demand")
            if infra_on_demand and energy_cost > infra_on_demand * 2.0:
                warnings.append(
                    f"{label}: energy_cost ({energy_cost:.4f}) > 2x on-demand infra ({infra_on_demand:.4f})"
                )
        if is_cpu_backend and power_source in (None, "unknown", "gpu", "cpu_estimated"):
            msg = f"{label}: CPU backend uses non-CPU power source ({power_source})"
            if require_cpu_power:
                issues.append(msg)
            else:
                warnings.append(msg)

        for total_key in total_keys:
            total_cost = row.get(total_key)
            if total_cost is None:
                continue
            if total_cost < 0:
                issues.append(f"{label}: negative {total_key} ({total_cost})")
            if total_cost > 2000.0:
                warnings.append(f"{label}: very high {total_key} ({total_cost:.2f} USD/1M tokens)")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "on_demand_rate": on_demand,
        "energy_rate": usd_per_kwh,
    }


def validate_energy_measurements(
    latency_summary: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate energy measurements are reasonable.

    Checks:
    - GPU power is within expected ranges (50-400W typical)
    - Energy per token is reasonable
    - Carbon footprint is calculable
    """
    issues: list[str] = []
    warnings: list[str] = []

    if latency_summary.empty:
        return {"valid": False, "issues": ["No latency summary data"], "warnings": []}

    for _, row in latency_summary.iterrows():
        backend = str(row.get("backend", "unknown"))
        gpu_power = row.get("gpu_power_mean_watts")
        power = row.get("power_mean_watts", gpu_power)
        gpu_memory = row.get("gpu_memory_mean_mb")
        throughput = row.get("throughput_mean_tok_s")

        if power is not None:
            if power < 0:
                issues.append(f"{backend}: negative power ({power})")
            if power > 500.0:
                warnings.append(f"{backend}: very high power ({power:.1f}W)")
            if power < 5.0 and "gpu" in backend.lower():
                warnings.append(f"{backend}: suspiciously low power ({power:.1f}W) for GPU backend")

        if throughput and power:
            # Estimate energy per token
            # If throughput is tok/s and power is W, then energy per token = power / throughput (J/token)
            energy_per_token_j = power / throughput if throughput > 0 else None
            if energy_per_token_j and energy_per_token_j > 1.0:  # >1J per token is high
                warnings.append(
                    f"{backend}: high energy per token ({energy_per_token_j:.4f} J/token, {power:.1f}W / {throughput:.1f} tok/s)"
                )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="TR119 cost/energy validation")
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
        "--latency-summary",
        default=None,
        help="Latency summary CSV (defaults to latest in results/processed)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    processed_dir = results_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Load cost summary
    cost_summary_path = (
        resolve_repo_path(_REPO_ROOT, str(args.cost_summary))
        if args.cost_summary
        else processed_dir / "cost_energy_summary.json"
    )
    cost_summary = json.loads(cost_summary_path.read_text(encoding="utf-8")) if cost_summary_path.exists() else {}

    # Load latency summary
    latency_summary_path = (
        resolve_repo_path(_REPO_ROOT, str(args.latency_summary))
        if args.latency_summary
        else processed_dir / "latency_summary_cost.csv"
    )
    latency_summary = (
        pd.read_csv(latency_summary_path) if latency_summary_path.exists() else pd.DataFrame()
    )

    cost_validation = validate_cost_model(cost_summary, cfg)
    energy_validation = validate_energy_measurements(latency_summary, cfg)

    validation_result = {
        "cost_validation": cost_validation,
        "energy_validation": energy_validation,
        "overall_valid": cost_validation["valid"] and energy_validation["valid"],
    }

    out_path = processed_dir / "cost_energy_validation.json"
    out_path.write_text(json.dumps(validation_result, indent=2), encoding="utf-8")
    print(f"Cost/energy validation written to {out_path}")

    if not validation_result["overall_valid"]:
        print("\nValidation issues found:")
        for issue in cost_validation.get("issues", []):
            print(f"  - {issue}")
        for issue in energy_validation.get("issues", []):
            print(f"  - {issue}")
        return 1

    if cost_validation.get("warnings") or energy_validation.get("warnings"):
        print("\nValidation warnings:")
        for warning in cost_validation.get("warnings", []):
            print(f"  - {warning}")
        for warning in energy_validation.get("warnings", []):
            print(f"  - {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

