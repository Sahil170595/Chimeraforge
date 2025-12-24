#!/usr/bin/env python3
"""
TR119: Statistical + cost/energy analysis for benchmark results.

Reads TR119 run-level JSONL from results/raw and writes:
  - latency_summary_cost.csv (per-backend/scenario latency/throughput/telemetry)
  - cost_energy_summary.json (derived cost/energy/TCO metrics)
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

from scripts.tr117.statistical_analysis import compute_summary
from scripts.tr118.artifact_utils import resolve_repo_path


def _load_raw(path: Path) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    df = pd.DataFrame(records)
    df["backend"] = df["spec"].apply(lambda s: s["backend"])
    df["scenario"] = df["spec"].apply(lambda s: s["scenario"])
    df["mode"] = df["spec"].apply(lambda s: s.get("mode", "prefill"))
    df["repetition"] = df["spec"].apply(lambda s: s.get("repetition", 0))
    df["run_mean_latency_ms"] = df["latencies_ms"].apply(
        lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
    )
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


def _mean_metric(metrics: list[dict[str, Any]], key: str) -> float | None:
    vals: list[float] = []
    for m in metrics:
        if not isinstance(m, dict):
            continue
        v = m.get(key)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _mode_from_file(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        spec = row.get("spec") if isinstance(row, dict) else None
        if isinstance(spec, dict):
            return str(spec.get("mode", "prefill"))
    return "prefill"


def main() -> int:
    parser = argparse.ArgumentParser(description="TR119 analysis (latency + cost/energy)")
    parser.add_argument(
        "--config",
        default="scripts/tr119/configs/baseline.yaml",
        help="TR119 config yaml",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    raw_dir = results_dir / "raw"

    raw_files = sorted(raw_dir.glob("bench_tr119_*.jsonl"), key=lambda p: p.stat().st_mtime)
    raw_files = [p for p in raw_files if p.exists() and p.stat().st_size > 0]
    if not raw_files:
        raise SystemExit("No TR119 raw results found")
    latest_by_mode: dict[str, Path] = {}
    for path in raw_files:
        mode = _mode_from_file(path)
        current = latest_by_mode.get(mode)
        if current is None or path.stat().st_mtime > current.stat().st_mtime:
            latest_by_mode[mode] = path
    dfs = [_load_raw(path) for path in latest_by_mode.values()]
    df = pd.concat(dfs, ignore_index=True) if dfs else _load_raw(raw_files[-1])
    df_ok = df[(df["run_mean_latency_ms"].notna()) & (df["degraded"] == False)]  # noqa: E712

    # Per-backend/scenario summary with telemetry means
    rows: list[dict[str, Any]] = []
    for (backend, scenario, mode), group_all in df.groupby(["backend", "scenario", "mode"]):
        group_ok = df_ok[
            (df_ok["backend"] == backend) & (df_ok["scenario"] == scenario) & (df_ok["mode"] == mode)
        ]
        metrics = [m for m in group_ok.get("resource_metrics", []).tolist() if isinstance(m, dict)]
        lat_vals = [float(v) for v in group_ok["run_mean_latency_ms"].dropna().tolist()]
        thr_vals = [float(v) for v in group_ok["run_mean_throughput_tok_s"].dropna().tolist()]
        lat_summary = compute_summary(lat_vals) if lat_vals else None
        thr_summary = compute_summary(thr_vals) if thr_vals else None
        row: dict[str, Any] = {
            "backend": backend,
            "scenario": scenario,
            "mode": mode,
            "n_total": int(group_all.shape[0]),
            "n_degraded": int(group_all["degraded"].astype(int).sum()),
            "degraded_rate": float(group_all["degraded"].astype(int).mean()),
            "throughput_mean_tok_s": thr_summary.mean if thr_summary else None,
            "throughput_median_tok_s": thr_summary.median if thr_summary else None,
            "gpu_power_mean_watts": _mean_metric(metrics, "gpu_power_mean_watts"),
            "gpu_memory_mean_mb": _mean_metric(metrics, "gpu_memory_mean_mb"),
            "gpu_temperature_mean_c": _mean_metric(metrics, "gpu_temperature_mean_c"),
            "cpu_power_mean_watts": _mean_metric(metrics, "cpu_power_mean_watts"),
            "cpu_utilization_mean_pct": _mean_metric(metrics, "cpu_utilization_mean_pct"),
        }
        if lat_summary is not None:
            row |= lat_summary.__dict__
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
    summary_path = out_dir / "latency_summary_cost.csv"
    pd.DataFrame(rows).to_csv(summary_path, index=False)
    print(f"TR119 latency+telemetry summary written to {summary_path}")

    # Comprehensive cost/energy derivation with multi-tier pricing and carbon footprint
    from scripts.tr119.artifact_utils import (
        compute_carbon_footprint,
        compute_cost_per_1m_tokens,
        compute_energy_from_power,
        compute_kwh_from_joules,
    )

    cloud_cfg = cfg.get("cloud_pricing", {}) or {}
    energy_cfg = cfg.get("energy", {}) or {}
    cpu_power_cfg = cfg.get("telemetry", {}).get("cpu_power_model", {}) or {}
    cpu_idle_watts = float(cpu_power_cfg.get("idle_watts", 10.0)) if cpu_power_cfg else 0.0
    cpu_max_watts = float(cpu_power_cfg.get("max_watts", 65.0)) if cpu_power_cfg else 0.0
    cpu_default_util = float(cpu_power_cfg.get("default_utilization_pct", 0.0)) if cpu_power_cfg else 0.0
    price_per_hour = float(cloud_cfg.get("on_demand_usd_per_hour", 1.0))
    spot_price_per_hour = float(cloud_cfg.get("spot_usd_per_hour", price_per_hour * 0.3))
    reserved_price_per_hour = cloud_cfg.get("reserved_usd_per_hour")
    reserved_1yr_price = cloud_cfg.get("reserved_1yr_usd_per_hour")
    reserved_3yr_price = cloud_cfg.get("reserved_3yr_usd_per_hour")
    on_prem_price = cloud_cfg.get("on_prem_usd_per_hour")

    if reserved_price_per_hour is None:
        reserved_price_per_hour = reserved_1yr_price
    if reserved_price_per_hour is None:
        reserved_price_per_hour = price_per_hour * 0.6
    reserved_price_per_hour = float(reserved_price_per_hour)

    pricing_tiers: dict[str, float] = {
        "on_demand": price_per_hour,
        "spot": float(spot_price_per_hour),
        "reserved": reserved_price_per_hour,
    }
    if reserved_1yr_price is not None:
        pricing_tiers["reserved_1yr"] = float(reserved_1yr_price)
    if reserved_3yr_price is not None:
        pricing_tiers["reserved_3yr"] = float(reserved_3yr_price)
    if on_prem_price is not None:
        pricing_tiers["on_prem"] = float(on_prem_price)
    energy_usd_per_kwh = float(energy_cfg.get("usd_per_kwh", 0.2))
    carbon_intensity = float(energy_cfg.get("carbon_intensity_gco2e_per_kwh", 500.0))

    # Approximate: power_mean_w * time_s / 3600 = kWh
    cost_rows: list[dict[str, Any]] = []
    for r in rows:
        thr = float(r.get("throughput_mean_tok_s") or 0.0)
        if thr <= 0:
            continue
        backend = str(r.get("backend") or "unknown")
        backend_lower = backend.lower()
        is_cpu_backend = ("cpu" in backend_lower) and ("gpu" not in backend_lower)
        gpu_power_w = float(r.get("gpu_power_mean_watts") or 0.0)
        cpu_power_raw = r.get("cpu_power_mean_watts")
        cpu_power_w = float(cpu_power_raw) if isinstance(cpu_power_raw, (int, float)) else None
        cpu_util = float(r.get("cpu_utilization_mean_pct") or 0.0)
        cpu_power_est = None
        if cpu_power_cfg and cpu_power_w is None and cpu_util > 0:
            cpu_power_est = cpu_idle_watts + (cpu_util / 100.0) * max(0.0, cpu_max_watts - cpu_idle_watts)

        if is_cpu_backend:
            if cpu_power_w is not None and cpu_power_w > 0:
                power_w = cpu_power_w
                power_source = "cpu"
            elif cpu_power_est is not None and cpu_power_est > 0:
                power_w = cpu_power_est
                power_source = "cpu_estimated"
            else:
                power_w = 0.0
                power_source = "unknown"
        else:
            if gpu_power_w > 0:
                power_w = gpu_power_w
                power_source = "gpu"
            elif cpu_power_w is not None and cpu_power_w > 0:
                power_w = cpu_power_w
                power_source = "cpu"
            elif cpu_power_est is not None and cpu_power_est > 0:
                power_w = cpu_power_est
                power_source = "cpu_estimated"
            else:
                power_w = 0.0
                power_source = "unknown"
        lat_mean_ms = float(r.get("mean") or 0.0)
        
        # tokens per hour at this throughput
        tok_per_hour = thr * 3600.0
        # GPU-hours per 1M tokens
        gpu_hours_per_1m = 1_000_000.0 / tok_per_hour if tok_per_hour > 0 else 0.0
        
        # Energy calculations
        seconds_per_1m = 1_000_000.0 / thr if thr > 0 else 0.0
        energy_j_per_1m = compute_energy_from_power(power_w, seconds_per_1m) if power_w > 0 else 0.0
        energy_j_per_token = energy_j_per_1m / 1_000_000.0 if energy_j_per_1m > 0 else 0.0
        energy_kwh_per_1m = compute_kwh_from_joules(energy_j_per_1m)
        
        # Cost calculations (multi-tier)
        tier_costs: dict[str, dict[str, Any]] = {}
        for tier_name, price in pricing_tiers.items():
            tier_costs[tier_name] = compute_cost_per_1m_tokens(
                gpu_hours_per_1m, float(price), energy_kwh_per_1m, energy_usd_per_kwh
            )
        
        # Carbon footprint
        carbon_gco2e_per_1m = compute_carbon_footprint(energy_kwh_per_1m, carbon_intensity)
        
        # Comprehensive cost metrics (frontier lab quality)
        # Cost per hour
        cost_per_hour: dict[str, float] = {}
        tokens_per_dollar: dict[str, float] = {}
        for tier_name, cost in tier_costs.items():
            total_cost = float(cost["total_cost_usd_per_1m_tokens"] or 0.0)
            per_hour = (total_cost / 1_000_000.0) * tok_per_hour
            cost_per_hour[tier_name] = per_hour
            tokens_per_dollar[tier_name] = tok_per_hour / per_hour if per_hour > 0 else 0.0
        
        # Efficiency metrics
        gpu_memory_mb = float(r.get("gpu_memory_mean_mb") or 0.0)
        memory_efficiency = thr / gpu_memory_mb if gpu_memory_mb > 0 else 0.0  # tokens/s per MB
        compute_efficiency = thr / lat_mean_ms if lat_mean_ms > 0 else 0.0  # tokens/s per ms

        row_cost: dict[str, Any] = {
            "backend": backend,
            "scenario": r["scenario"],
            "mode": r.get("mode", "prefill"),
            "throughput_mean_tok_s": thr,
            "gpu_power_mean_watts": gpu_power_w,
            "cpu_power_mean_watts": cpu_power_w if cpu_power_w and cpu_power_w > 0 else None,
            "cpu_power_estimated_watts": cpu_power_est,
            "power_mean_watts": power_w if power_w > 0 else None,
            "power_source": power_source,
            "latency_mean_ms": lat_mean_ms,
            "gpu_memory_mean_mb": gpu_memory_mb,
            "gpu_hours_per_1m_tokens": gpu_hours_per_1m,
            "energy_j_per_token": energy_j_per_token,
            "energy_kwh_per_1m_tokens": energy_kwh_per_1m,
            "energy_cost_usd_per_1m_tokens": tier_costs["on_demand"]["energy_cost_usd_per_1m_tokens"],
            "memory_efficiency_tokens_per_mb": memory_efficiency,
            "compute_efficiency_tokens_per_ms": compute_efficiency,
            "carbon_gco2e_per_1m_tokens": carbon_gco2e_per_1m,
        }

        for tier_name, cost in tier_costs.items():
            row_cost[f"infra_cost_usd_per_1m_tokens_{tier_name}"] = cost["infra_cost_usd_per_1m_tokens"]
            row_cost[f"total_cost_usd_per_1m_tokens_{tier_name}"] = cost["total_cost_usd_per_1m_tokens"]
            row_cost[f"cost_per_hour_usd_{tier_name}"] = cost_per_hour.get(tier_name)
            row_cost[f"tokens_per_dollar_{tier_name}"] = tokens_per_dollar.get(tier_name)

        cost_rows.append(row_cost)

    cost_summary_path = out_dir / "cost_energy_summary.json"
    cost_summary_path.write_text(json.dumps({"rows": cost_rows}, indent=2), encoding="utf-8")
    print(f"TR119 cost/energy summary written to {cost_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


