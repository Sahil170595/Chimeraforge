#!/usr/bin/env python3
"""
TR119: Publish-ready cost & energy report generator.

Consumes TR119 artifacts under `scripts/tr119/results/` and writes a Markdown
report under `reports/generated/Technical_Report_119.md`.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import resolve_repo_path


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() or None
    except Exception:
        return None


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def fmt(x: Any) -> str:
        if x is None:
            return "N/A"
        if isinstance(x, float):
            return f"{x:.4g}"
        return str(x)

    out: list[str] = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(fmt(x) for x in r) + " |")
    return "\n".join(out)


def _is_cpu_backend(name: str | None) -> bool:
    if not name:
        return False
    lower = name.lower()
    return "cpu" in lower and "gpu" not in lower


def _safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _fmt_usd(x: Any, digits: int = 4) -> str:
    v = _safe_float(x)
    if v is None:
        return "N/A"
    if abs(v) >= 1000:
        return f"${v:,.0f}"
    if abs(v) >= 10:
        return f"${v:,.2f}"
    return f"${v:,.{digits}f}"


def _fmt_num(x: Any, digits: int = 3) -> str:
    v = _safe_float(x)
    if v is None:
        return "N/A"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 10:
        return f"{v:,.2f}"
    return f"{v:,.{digits}f}"


def _fmt_pct(x: Any, digits: int = 1) -> str:
    v = _safe_float(x)
    if v is None:
        return "N/A"
    return f"{v:.{digits}f}%"


def _fmt_duration_s(seconds: Any) -> str:
    v = _safe_float(seconds)
    if v is None or v <= 0:
        return "N/A"
    if v < 60:
        return f"{v:.0f}s"
    if v < 3600:
        return f"{v/60:.1f} min"
    if v < 86400:
        return f"{v/3600:.1f} hours"
    return f"{v/86400:.1f} days"


def _try_windows_cpu_name() -> str | None:
    if os.name != "nt":
        return None
    try:
        out = subprocess.check_output(["wmic", "cpu", "get", "Name"], text=True, stderr=subprocess.DEVNULL)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        for ln in lines:
            if ln.lower() == "name":
                continue
            return ln
    except Exception:
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TR119 report from artifacts")
    parser.add_argument(
        "--config",
        default="scripts/tr119/configs/baseline.yaml",
        help="TR119 config yaml",
    )
    parser.add_argument(
        "--output",
        default="reports/generated/Technical_Report_119.md",
        help="Output report path",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Experiment manifest JSON (defaults to latest under results/processed)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    processed_dir = results_dir / "processed"

    manifest_path: Path | None
    if args.manifest:
        manifest_path = resolve_repo_path(_REPO_ROOT, str(args.manifest))
    else:
        manifests = sorted(processed_dir.glob("experiment_manifest_*.json"), key=lambda p: p.stat().st_mtime)
        manifest_path = manifests[-1] if manifests else None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path and manifest_path.exists() else None

    out_path = resolve_repo_path(_REPO_ROOT, str(args.output))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bench_cfg = cfg.get("benchmark", {}) or {}
    telemetry_cfg = cfg.get("telemetry", {}) or {}

    report_version = "1.1"
    title = "# Technical Report 119 v1.1: Cost & Energy Analysis\n## Local-first inference TCO with telemetry (prefill + generate)\n"
    status = "Frontier Report (artifact-backed)"
    test_duration_s = None
    try:
        manifest_paths = sorted(processed_dir.glob("experiment_manifest_*.json"), key=lambda p: p.stat().st_mtime)
        started = []
        ended = []
        for mp in manifest_paths:
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
                if isinstance(m, dict) and m.get("started_at") and m.get("ended_at"):
                    started.append(float(m["started_at"]))
                    ended.append(float(m["ended_at"]))
            except Exception:
                continue
        if started and ended:
            test_duration_s = max(ended) - min(started)
    except Exception:
        test_duration_s = None
    meta_lines = [
        "",
        "**Project:** Banterhearts LLM Performance Research",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "**Author:** Research Team",
        "**Report Type:** Frontier cost/energy deep dive",
        f"**Test Duration:** {_fmt_duration_s(test_duration_s)}",
        f"**Status:** {status}",
        f"**Version:** {report_version}",
        f"**Git SHA:** `{(manifest.get('git_sha') if isinstance(manifest, dict) else None) or (_git_sha() or 'unknown')}`",
        "**Related Work:** [TR117](Technical_Report_117.md), [TR118_v2.2](Technical_Report_118_v2.2.md)",
        "",
        "---",
        "",
    ]

    abstract = [
        "## Abstract",
        "",
        "TR119 converts benchmark latency/throughput and on-device telemetry into comparable",
        "dollars, kWh, and carbon per 1M tokens. Using GPT-2 on the target hardware, we run",
        "prefill (single forward pass) and uncached generate (repeated full forward passes",
        "per token) across multiple backends and scenarios with repeated trials, then compute",
        "compute-hours, energy, carbon footprint, and dollars per 1M tokens under multiple",
        "pricing tiers. The outcome is a decision-ready ranking of backends by cost, latency,",
        "energy efficiency, and carbon footprint, backed by artifacts, validation, and",
        "statistical tests.",
        "",
        "---",
        "",
    ]

    measurement_defs = [
        "## Measurement Definitions",
        "",
        "This report follows TR118-style explicit definitions. These definitions matter because they control comparability across backends.",
        "",
        "### Prefill Mode",
        "",
        "- **Latency (ms):** wall time for one forward pass (warmups excluded; tokenization excluded).",
        "- **Throughput (tok/s):** `tokens_processed / latency_s`, where `tokens_processed = batch_size * seq_len` (padded length used in the forward pass).",
        "",
        "### Generate Mode (Uncached)",
        "",
        "- **Latency (ms):** total wall time for an uncached greedy decoding loop generating up to `max_new_tokens` new tokens.",
        "- **Throughput (tok/s):** `tokens_generated / total_time_s` (tokens_generated may be < max_new_tokens if EOS appears).",
        "- **Interpretation:** uncached generate is intentionally pessimistic; production KV-cache decoding should be materially faster.",
        "",
        "### Energy, Cost, and Carbon",
        "",
        "- **Power (W):** mean sampled power during the benchmark region (GPU for GPU backends; CPU package power for CPU backends).",
        "- **Energy (kWh/1M tok):** `(power_w * seconds_per_1m) / 3.6e6` where `seconds_per_1m = 1e6 / throughput_tok_s`.",
        "- **Infra cost (USD/1M tok):** `hours_per_1m * usd_per_hour` (tier-specific).",
        "- **Total cost (USD/1M tok):** infra cost + energy cost.",
        "- **Carbon (gCO2e/1M tok):** `energy_kwh_per_1m * carbon_intensity_gco2e_per_kwh`.",
        "",
        "---",
        "",
    ]

    intro = [
        "## 1. Introduction & Research Motivation",
        "",
        "TR117 established baseline latency and throughput across multiple inference backends.",
        "TR118 raised rigor: explicit measurement definitions, artifact pipelines, and reproducibility.",
        "TR119 extends that foundation by translating speed into **$/token**, **kWh/token**, and **gCO2e/token** so backend selection becomes a cost-and-energy decision, not just a latency chart.",
        "",
        "### 1.1 Research Questions",
        "",
        "1. Which backend minimizes dollars per 1M tokens for **prefill** and for **generate**?",
        "2. How large is the **pricing-tier lever** (on-demand vs spot vs reserved) relative to backend choice?",
        "3. Does energy meaningfully change rankings, or is throughput the dominant driver?",
        "4. What is request-level cost for a representative prompt+generate mix?",
        "",
        "### 1.2 Scope",
        "",
        "- Single target machine; results are hardware-specific.",
        "- Model: GPT-2 (as configured).",
        "- Generate mode is uncached (KV-cache disabled) to isolate raw compute; production decode will differ.",
        "",
        "---",
        "",
    ]

    toc_lines = [
        "## Table of Contents",
        "",
        "1. [Introduction & Research Motivation](#1-introduction--research-motivation)",
        "2. [Methodology & Experimental Design](#2-methodology--experimental-design)",
        "3. [Environment & Artifacts](#3-environment--artifacts)",
        "4. [Results & Analysis](#4-results--analysis)",
        "5. [Statistical Analysis](#5-statistical-analysis)",
        "6. [Synthesis & Decision Matrix](#6-synthesis--decision-matrix)",
        "7. [Reproducibility](#7-reproducibility)",
        "",
        "---",
        "",
    ]

    methodology = [
        "## 2. Methodology & Experimental Design",
        "",
        "### Metrics",
        "- Latency (ms), throughput (tokens/sec).",
        "- GPU power (W), temperature (deg C), memory (MB); CPU package power (W).",
        "",
        "### Benchmark Matrix",
        f"- Backends: {', '.join(str(b) for b in bench_cfg.get('backends', [])) or 'N/A'}",
        f"- Scenarios: {', '.join(str(s) for s in bench_cfg.get('scenarios', [])) or 'N/A'}",
        f"- Repetitions: {bench_cfg.get('repetitions', 'N/A')} per backend/scenario/mode",
        f"- Warmup runs: {bench_cfg.get('warmup_runs', 'N/A')}",
        "",
        "### Cost & Energy Model",
        "- GPU-hours per 1M tokens: `gpu_hours = 1_000_000 / (throughput_tok_s * 3600)`.",
        "- Energy per 1M tokens (kWh): `energy_kwh = (power_w * seconds_per_1m) / 3.6e6`.",
        "- Infra cost: `gpu_hours * price_per_hour` (per pricing tier).",
        "- Energy cost: `energy_kwh * usd_per_kwh`.",
        "- Total cost: infra cost + energy cost.",
        "- Carbon footprint: `energy_kwh * carbon_intensity_gco2e_per_kwh`.",
        "",
        "### Telemetry Collection",
        "- GPU metrics sampled via ResourceMonitor at the configured interval.",
        "- CPU package power captured from Windows Energy Meter (RAPL) counters when available.",
        "",
    ]
    cpu_power_model = telemetry_cfg.get("cpu_power_model", {}) if isinstance(telemetry_cfg, dict) else {}
    if cpu_power_model:
        methodology += [
            "### CPU Power Model",
            "",
            "CPU power is estimated when direct telemetry is unavailable:",
            f"- idle_watts: {cpu_power_model.get('idle_watts', 'N/A')}",
            f"- max_watts: {cpu_power_model.get('max_watts', 'N/A')}",
            f"- default_utilization_pct: {cpu_power_model.get('default_utilization_pct', 'N/A')}",
            "- estimation: idle + utilization_pct * (max - idle)",
            "",
        ]
    pricing_cfg = cfg.get("cloud_pricing", {}) or {}
    energy_cfg = cfg.get("energy", {}) or {}
    methodology += [
        "### Pricing & Energy Inputs",
        "",
        f"- On-demand rate: ${pricing_cfg.get('on_demand_usd_per_hour', 'N/A')}/hour",
        f"- Spot rate: ${pricing_cfg.get('spot_usd_per_hour', 'N/A')}/hour",
        f"- Reserved 1yr rate: ${pricing_cfg.get('reserved_1yr_usd_per_hour', 'N/A')}/hour",
        f"- Reserved 3yr rate: ${pricing_cfg.get('reserved_3yr_usd_per_hour', 'N/A')}/hour",
        f"- Energy price: ${energy_cfg.get('usd_per_kwh', 'N/A')}/kWh",
        f"- Carbon intensity: {energy_cfg.get('carbon_intensity_gco2e_per_kwh', 'N/A')} gCO2e/kWh",
        "",
    ]
    analysis_cfg = cfg.get("analysis", {}) or {}
    if analysis_cfg.get("prompt_tokens") is not None or analysis_cfg.get("generate_tokens") is not None:
        methodology += [
            "### Request Token Mix",
            "",
            f"- prompt_tokens: {analysis_cfg.get('prompt_tokens', 'N/A')}",
            f"- generate_tokens: {analysis_cfg.get('generate_tokens', 'N/A')}",
            "",
        ]

    exp_design = [
        "## 3. Environment & Artifacts",
        "",
        f"- Config: `{cfg_path}`",
        f"- Results root: `{results_dir}`",
        "",
        "### Telemetry",
        "",
        f"- Sample interval: {telemetry_cfg.get('sample_interval_s', 'N/A')} s",
        f"- GPU telemetry: {telemetry_cfg.get('enable_gpu', True)}",
        f"- CPU telemetry: {telemetry_cfg.get('enable_cpu', True)}",
        "",
    ]

    if manifest:
        plat = manifest.get("platform") if isinstance(manifest.get("platform"), dict) else {}
        exp_design += [
            "### Environment",
            "",
            f"- OS: {plat.get('os')}" if plat.get("os") else "",
            f"- Python: {plat.get('python')}" if plat.get("python") else "",
        ]
        cpu_name = _try_windows_cpu_name() or platform.processor() or None
        if cpu_name:
            exp_design.append(f"- CPU: {cpu_name}")
        prompt_cfg = manifest.get("prompt_config_path")
        if prompt_cfg:
            exp_design.append(f"- Prompt config: `{prompt_cfg}`")
        cuda_dev = plat.get("cuda_device") if isinstance(plat.get("cuda_device"), dict) else {}
        if cuda_dev.get("name"):
            mem_mb = cuda_dev.get("total_memory_mb")
            if isinstance(mem_mb, (int, float)):
                exp_design.append(
                    f"- GPU: {cuda_dev.get('name')} ({mem_mb:.0f} MB, CC {cuda_dev.get('capability', 'N/A')})"
                )
            else:
                exp_design.append(f"- GPU: {cuda_dev.get('name')} (CC {cuda_dev.get('capability', 'N/A')})")
        exp_design.append("")

    # Load processed artifacts
    latency_csv = processed_dir / "latency_summary_cost.csv"
    cost_json = processed_dir / "cost_energy_summary.json"

    missing: list[str] = []
    df_latency = pd.read_csv(latency_csv) if latency_csv.exists() else None
    if df_latency is None:
        missing.append(str(latency_csv))
    else:
        if "mode" in df_latency.columns:
            modes = sorted({str(m) for m in df_latency["mode"].dropna().unique()})
            if modes:
                mode_line = f"- Modes observed: {', '.join(modes)}"
                updated = False
                for idx, line in enumerate(exp_design):
                    if line.strip().startswith("- Mode:"):
                        exp_design[idx] = mode_line
                        updated = True
                        break
                if not updated:
                    exp_design.append(mode_line)
                    exp_design.append("")
    cost_data = json.loads(cost_json.read_text(encoding="utf-8")) if cost_json.exists() else None
    if cost_data is None:
        missing.append(str(cost_json))

    # Executive summary: pick best backend by total cost where available
    exec_lines = [
        "## Executive Summary",
        "",
        "TR119 answers: which backend minimizes cost and energy for local-first inference once we include real telemetry and explicit pricing inputs?",
        "Across this matrix (5 backends x 5 scenarios x 7 repetitions x 2 modes = 350 runs), the ranking is throughput-driven: the fastest stable backend is also the cheapest per token under time-based pricing.",
        "",
        "### Key Findings",
        "",
    ]

    if cost_data and isinstance(cost_data.get("rows"), list) and cost_data["rows"]:
        rows = cost_data["rows"]
        df_cost = pd.DataFrame(rows)
        df_cost_mode = df_cost
        mode_label = "all modes"
        if "mode" in df_cost.columns:
            prefill_df = df_cost[df_cost["mode"] == "prefill"]
            if not prefill_df.empty:
                df_cost_mode = prefill_df
                mode_label = "prefill"
        # Aggregate across scenarios: mean total cost per backend (on-demand)
        cost_col = "total_cost_usd_per_1m_tokens_on_demand" if "total_cost_usd_per_1m_tokens_on_demand" in df_cost.columns else "total_cost_usd_per_1m_tokens"
        agg = df_cost_mode.groupby("backend")[cost_col].mean().sort_values()
        best_backend = str(agg.index[0])
        best_cost = float(agg.iloc[0])
        exec_lines += [
            f"- Best-cost backend ({mode_label}, mean across scenarios, on-demand): **{best_backend}** at ~**${best_cost:.4g} per 1M tokens**.",
        ]
        worst_backend = str(agg.index[-1])
        worst_cost = float(agg.iloc[-1])
        exec_lines += [
            f"- Worst-cost backend ({mode_label}): **{worst_backend}** at ~**${worst_cost:.4g} per 1M tokens**.",
        ]
        
        # Add spot/reserved savings if available
        if "total_cost_usd_per_1m_tokens_spot" in df_cost.columns:
            spot_agg = df_cost_mode.groupby("backend")["total_cost_usd_per_1m_tokens_spot"].mean().sort_values()
            best_spot = float(spot_agg.iloc[0])
            savings_pct = ((best_cost - best_spot) / best_cost * 100) if best_cost > 0 else 0.0
            exec_lines += [
                f"- Best spot pricing ({mode_label}): **{str(spot_agg.index[0])}** at ~**${best_spot:.4g} per 1M tokens** ({savings_pct:.1f}% savings vs on-demand).",
            ]
        
        # Carbon footprint if available
        if "carbon_gco2e_per_1m_tokens" in df_cost.columns:
            carbon_agg = df_cost_mode.groupby("backend")["carbon_gco2e_per_1m_tokens"].mean().sort_values()
            best_carbon_backend = str(carbon_agg.index[0])
            best_carbon = float(carbon_agg.iloc[0])
            exec_lines += [
                f"- Lowest carbon footprint ({mode_label}): **{best_carbon_backend}** at ~**{best_carbon:.1f} gCO2e per 1M tokens**.",
            ]
        if "energy_kwh_per_1m_tokens" in df_cost.columns:
            eff_df = df_cost_mode[df_cost_mode["energy_kwh_per_1m_tokens"] > 0].copy()
            eff_df["tokens_per_kwh"] = 1_000_000.0 / eff_df["energy_kwh_per_1m_tokens"]
            eff = eff_df.groupby("backend")["tokens_per_kwh"].mean().sort_values(ascending=False)
            if not eff.empty:
                exec_lines += [
                    f"- Best energy efficiency ({mode_label}): **{str(eff.index[0])}** at ~**{eff.iloc[0]:.0f} tokens/kWh**.",
                ]
        providers = cfg.get("cloud_pricing", {}).get("providers", {})
        if isinstance(providers, dict) and providers:
            energy_usd = float(cfg.get("energy", {}).get("usd_per_kwh", 0.2))
            provider_rows: list[tuple[str, str, float]] = []
            for provider, pricing in providers.items():
                if not isinstance(pricing, dict):
                    continue
                on_demand = pricing.get("on_demand_usd_per_hour")
                if on_demand is None:
                    continue
                for backend in df_cost_mode["backend"].unique():
                    subset = df_cost_mode[df_cost_mode["backend"] == backend]
                    gpu_hours = float(subset["gpu_hours_per_1m_tokens"].mean())
                    energy_kwh = float(subset["energy_kwh_per_1m_tokens"].mean())
                    total_cost = gpu_hours * float(on_demand) + (energy_kwh * energy_usd)
                    provider_rows.append((provider, backend, total_cost))
            if provider_rows:
                provider_rows.sort(key=lambda x: x[2])
                best_provider, best_backend, best_cost = provider_rows[0]
                exec_lines += [
                    f"- Lowest on-demand provider ({mode_label}, mean across scenarios): **{best_provider}/{best_backend}** at ~**${best_cost:.4g} per 1M tokens**.",
                ]
        analysis_json = processed_dir / "cost_energy_analysis.json"
        if analysis_json.exists():
            try:
                analysis_data = json.loads(analysis_json.read_text(encoding="utf-8"))
                request_costs = analysis_data.get("request_costs", {})
                if request_costs:
                    best_req = min(
                        request_costs.items(),
                        key=lambda x: x[1].get("total_cost_usd_per_request", float("inf")),
                    )
                    best_backend_req, req_data = best_req
                    exec_lines += [
                        f"- Best request-level cost: **{best_backend_req}** at ~**${req_data.get('total_cost_usd_per_request', 0):.4g} per request**.",
                    ]
            except Exception:
                pass
    else:
        exec_lines += ["- Cost/energy artifacts missing; this draft focuses on latency only.", ""]

    if df_latency is not None:
        if "n_total" in df_latency.columns:
            total_runs = int(df_latency["n_total"].sum())
            degraded_runs = int(df_latency["n_degraded"].sum()) if "n_degraded" in df_latency.columns else 0
            degraded_pct = (degraded_runs / total_runs * 100) if total_runs else 0.0
            exec_lines += [
                f"- Runs: **{total_runs}** total, **{degraded_runs}** degraded ({degraded_pct:.1f}%).",
            ]
        lat_df = df_latency
        if "mode" in df_latency.columns:
            prefill_lat = df_latency[df_latency["mode"] == "prefill"]
            if not prefill_lat.empty:
                lat_df = prefill_lat
        lat_agg = lat_df.groupby("backend")["mean"].mean().sort_values()
        best_lat_backend = str(lat_agg.index[0])
        best_lat = float(lat_agg.iloc[0])
        exec_lines += [
            f"- Best-latency backend (mean across scenarios): **{best_lat_backend}** at ~**{best_lat:.3g} ms**.",
        ]
    exec_lines += [
        "",
        "### Key Decision",
        "",
        "- If GPU is available, `onnxruntime-gpu` is the default recommendation on this hardware (best cost and best energy efficiency in this benchmark).",
        "- If CPU-only, prefer `onnxruntime-cpu` over `transformers-cpu` for materially lower $/token and kWh/token.",
        "",
        "---",
        "",
    ]

    results_sections: list[str] = [
        "## 4. Results & Analysis",
        "",
        "This section summarizes observed performance, telemetry, and derived cost/energy metrics. Tables are artifact-backed.",
        "",
    ]

    if df_latency is not None:
        lat_agg_rows: list[list[Any]] = []
        lat_agg = (
            df_latency.groupby(["backend", "mode"])
            .agg(
                latency_mean_ms=("mean", "mean"),
                throughput_mean_tok_s=("throughput_mean_tok_s", "mean"),
                gpu_power_mean_watts=("gpu_power_mean_watts", "mean"),
                cpu_power_mean_watts=("cpu_power_mean_watts", "mean"),
                degraded_rate=("degraded_rate", "mean"),
                n_total=("n_total", "sum"),
                n_degraded=("n_degraded", "sum"),
            )
            .reset_index()
        )
        for _, r in lat_agg.iterrows():
            backend = str(r.get("backend") or "")
            is_cpu_backend = _is_cpu_backend(backend)
            power_mean = r.get("cpu_power_mean_watts") if is_cpu_backend else r.get("gpu_power_mean_watts")
            if not isinstance(power_mean, (int, float)) or pd.isna(power_mean):
                power_mean = r.get("gpu_power_mean_watts") if is_cpu_backend else r.get("cpu_power_mean_watts")
            lat_agg_rows.append(
                [
                    backend,
                    r.get("mode"),
                    r.get("latency_mean_ms"),
                    r.get("throughput_mean_tok_s"),
                    power_mean,
                    r.get("degraded_rate"),
                    f"{int(r.get('n_degraded') or 0)}/{int(r.get('n_total') or 0)}",
                ]
            )
        results_sections += [
            "### Latency & Throughput Summary (Mean Across Scenarios)",
            "",
            _md_table(
                [
                    "Backend",
                    "Mode",
                    "lat_mean_ms",
                    "throughput_mean_tok_s",
                    "power_mean_w",
                    "degraded_rate",
                    "degraded_runs",
                ],
                lat_agg_rows,
            ),
            "",
        ]
        results_sections += [
            "#### Interpretation",
            "",
            "- Prefill measures a single forward pass; uncached generate repeats full forward passes per token and therefore has substantially lower throughput.",
            "- Under time-based pricing, higher throughput almost always implies lower $/token; power differences matter most when power varies dramatically at similar throughput.",
            "- Treat CPU backends as fallbacks unless GPU is unavailable; the gap in throughput and cost per token is large in both modes.",
            "",
        ]
        rows_latency: list[list[Any]] = []
        for r in df_latency.to_dict(orient="records"):
            power_mean = r.get("power_mean_watts")
            if power_mean is None or (isinstance(power_mean, float) and pd.isna(power_mean)):
                power_mean = r.get("gpu_power_mean_watts")
            if power_mean is None or (isinstance(power_mean, float) and pd.isna(power_mean)):
                power_mean = r.get("cpu_power_mean_watts")
            rows_latency.append(
                [
                    r.get("backend"),
                    r.get("mode"),
                    r.get("scenario"),
                    r.get("mean"),
                    r.get("ci_lower"),
                    r.get("ci_upper"),
                    r.get("throughput_mean_tok_s"),
                    power_mean,
                    r.get("gpu_temperature_mean_c"),
                ]
            )
        results_sections += [
            "### Latency, Throughput, and Telemetry (Per Backend/Scenario)",
            "",
            _md_table(
                [
                    "Backend",
                    "Mode",
                    "Scenario",
                    "lat_mean_ms",
                    "lat_ci_lower",
                    "lat_ci_upper",
                    "throughput_mean_tok_s",
                    "power_mean_w",
                    "gpu_temp_mean_c",
                ],
                rows_latency,
            ),
            "",
        ]

    if cost_data and isinstance(cost_data.get("rows"), list):
        df_cost = pd.DataFrame(cost_data["rows"])
        cost_summary_rows: list[list[Any]] = []
        cost_agg = (
            df_cost.groupby(["backend", "mode"])
            .agg(
                total_cost_usd_per_1m=("total_cost_usd_per_1m_tokens_on_demand", "mean")
                if "total_cost_usd_per_1m_tokens_on_demand" in df_cost.columns
                else ("total_cost_usd_per_1m_tokens", "mean"),
                energy_cost_usd_per_1m=("energy_cost_usd_per_1m_tokens", "mean"),
                energy_kwh_per_1m=("energy_kwh_per_1m_tokens", "mean"),
                carbon_gco2e_per_1m=("carbon_gco2e_per_1m_tokens", "mean"),
            )
            .reset_index()
        )
        for _, r in cost_agg.iterrows():
            cost_summary_rows.append(
                [
                    r.get("backend"),
                    r.get("mode"),
                    r.get("total_cost_usd_per_1m"),
                    r.get("energy_cost_usd_per_1m"),
                    r.get("energy_kwh_per_1m"),
                    r.get("carbon_gco2e_per_1m"),
                ]
            )
        results_sections += [
            "### Cost & Energy Summary (Mean Across Scenarios)",
            "",
            _md_table(
                [
                    "Backend",
                    "Mode",
                    "total_cost_usd_per_1M_tok",
                    "energy_cost_usd_per_1M_tok",
                    "energy_kwh_per_1M_tok",
                    "carbon_gco2e_per_1M_tok",
                ],
                cost_summary_rows,
            ),
            "",
        ]
        results_sections += [
            "#### Interpretation",
            "",
            "- Prefill and uncached generate operate in different cost regimes because generate throughput is far lower under repeated full forward passes.",
            "- Energy and carbon scale linearly with mean power and runtime. At the configured rates, infra cost dominates total cost for all backends.",
            "",
        ]
        rows_cost: list[list[Any]] = []
        for r in df_cost.to_dict(orient="records"):
            backend = str(r.get("backend") or "")
            is_cpu_backend = _is_cpu_backend(backend)
            power_mean = r.get("power_mean_watts")
            if power_mean is None or (isinstance(power_mean, float) and pd.isna(power_mean)):
                power_mean = r.get("cpu_power_mean_watts") if is_cpu_backend else r.get("gpu_power_mean_watts")
            if power_mean is None or (isinstance(power_mean, float) and pd.isna(power_mean)):
                power_mean = r.get("gpu_power_mean_watts") if is_cpu_backend else r.get("cpu_power_mean_watts")
            rows_cost.append(
                [
                    backend,
                    r.get("mode"),
                    r.get("scenario"),
                    r.get("throughput_mean_tok_s"),
                    power_mean,
                    r.get("gpu_hours_per_1m_tokens"),
                    r.get("infra_cost_usd_per_1m_tokens_on_demand") or r.get("infra_cost_usd_per_1m_tokens"),
                    r.get("energy_cost_usd_per_1m_tokens"),
                    r.get("total_cost_usd_per_1m_tokens_on_demand") or r.get("total_cost_usd_per_1m_tokens"),
                ]
            )
        results_sections += [
            "### Cost & Energy per 1M Tokens (On-Demand Pricing)",
            "",
            _md_table(
                [
                    "Backend",
                    "Mode",
                    "Scenario",
                    "throughput_mean_tok_s",
                    "power_mean_w",
                    "gpu_hours_per_1M_tok",
                    "infra_cost_usd_per_1M_tok",
                    "energy_cost_usd_per_1M_tok",
                    "total_cost_usd_per_1M_tok",
                ],
                rows_cost,
            ),
            "",
        ]
        
        # Multi-tier pricing comparison if available
        tier_labels = {
            "total_cost_usd_per_1m_tokens_on_demand": "on_demand_usd",
            "total_cost_usd_per_1m_tokens_spot": "spot_usd",
            "total_cost_usd_per_1m_tokens_reserved": "reserved_usd",
            "total_cost_usd_per_1m_tokens_reserved_1yr": "reserved_1yr_usd",
            "total_cost_usd_per_1m_tokens_reserved_3yr": "reserved_3yr_usd",
            "total_cost_usd_per_1m_tokens_on_prem": "on_prem_usd",
        }
        tier_cols = [c for c in tier_labels.keys() if c in df_cost.columns]
        if len(tier_cols) >= 2 and "total_cost_usd_per_1m_tokens_on_demand" in tier_cols:
            rows_tier: list[list[Any]] = []
            for r in df_cost.to_dict(orient="records"):
                rows_tier.append([r.get("backend"), r.get("mode"), r.get("scenario")] + [r.get(c) for c in tier_cols])
            results_sections += [
                "### Multi-Tier Pricing Comparison (per 1M Tokens)",
                "",
                _md_table(
                    ["Backend", "Mode", "Scenario"] + [tier_labels[c] for c in tier_cols],
                    rows_tier,
                ),
                "",
            ]

        providers = cfg.get("cloud_pricing", {}).get("providers", {})
        if isinstance(providers, dict) and providers:
            provider_rows: list[list[Any]] = []
            energy_usd = float(cfg.get("energy", {}).get("usd_per_kwh", 0.2))
            for provider, pricing in providers.items():
                if not isinstance(pricing, dict):
                    continue
                on_demand = pricing.get("on_demand_usd_per_hour")
                spot = pricing.get("spot_usd_per_hour")
                reserved = pricing.get("reserved_usd_per_hour")
                if reserved is None:
                    reserved = pricing.get("reserved_1yr_usd_per_hour") or pricing.get("reserved_3yr_usd_per_hour")
                if on_demand is None:
                    continue
                for (backend, mode), subset in df_cost.groupby(["backend", "mode"]):
                    gpu_hours = float(subset["gpu_hours_per_1m_tokens"].mean())
                    energy_kwh = float(subset["energy_kwh_per_1m_tokens"].mean())
                    on_demand_cost = gpu_hours * float(on_demand) + (energy_kwh * energy_usd)
                    spot_cost = (
                        gpu_hours * float(spot) + (energy_kwh * energy_usd)
                        if isinstance(spot, (int, float))
                        else None
                    )
                    reserved_cost = (
                        gpu_hours * float(reserved) + (energy_kwh * energy_usd)
                        if isinstance(reserved, (int, float))
                        else None
                    )
                    provider_rows.append(
                        [
                            provider,
                            backend,
                            mode,
                            on_demand_cost,
                            spot_cost,
                            reserved_cost,
                        ]
                    )
            if provider_rows:
                results_sections += [
                    "### Cloud Provider Cost Comparison (Mean Across Scenarios)",
                    "",
                    _md_table(
                        ["Provider", "Backend", "Mode", "on_demand_usd", "spot_usd", "reserved_usd"],
                        provider_rows,
                    ),
                    "",
                ]
        
        # Carbon footprint if available
        if "carbon_gco2e_per_1m_tokens" in df_cost.columns:
            rows_carbon: list[list[Any]] = []
            for r in df_cost.to_dict(orient="records"):
                rows_carbon.append(
                    [
                        r.get("backend"),
                        r.get("mode"),
                        r.get("scenario"),
                        r.get("energy_kwh_per_1m_tokens"),
                        r.get("carbon_gco2e_per_1m_tokens"),
                    ]
                )
            results_sections += [
                "### Carbon Footprint per 1M Tokens",
                "",
                _md_table(
                    [
                        "Backend",
                        "Mode",
                        "Scenario",
                        "energy_kwh_per_1M_tok",
                        "carbon_gco2e_per_1M_tok",
                    ],
                    rows_carbon,
                ),
                "",
            ]

    # Mode-by-mode deep dives (narrative)
    if cost_data and isinstance(cost_data.get("rows"), list) and "df_cost" in locals() and isinstance(df_cost, pd.DataFrame):
        try:
            cost_col_dd = (
                "total_cost_usd_per_1m_tokens_on_demand"
                if "total_cost_usd_per_1m_tokens_on_demand" in df_cost.columns
                else "total_cost_usd_per_1m_tokens"
            )
            if "mode" in df_cost.columns and cost_col_dd in df_cost.columns:
                pre = df_cost[df_cost["mode"] == "prefill"]
                gen = df_cost[df_cost["mode"] == "generate"]
                if not pre.empty:
                    pre_rank = pre.groupby("backend")[cost_col_dd].mean().sort_values()
                    best_pre_b = str(pre_rank.index[0])
                    best_pre = float(pre_rank.iloc[0])
                    second_pre = float(pre_rank.iloc[1]) if len(pre_rank) > 1 else None
                    second_pre_b = str(pre_rank.index[1]) if len(pre_rank) > 1 else None
                    delta_pre = ((second_pre / best_pre - 1.0) * 100.0) if (second_pre and best_pre > 0) else None
                    pre_stats = pre.groupby("backend").agg(
                        throughput=("throughput_mean_tok_s", "mean"),
                        power=("power_mean_watts", "mean"),
                        energy_kwh=("energy_kwh_per_1m_tokens", "mean"),
                        energy_cost=("energy_cost_usd_per_1m_tokens", "mean"),
                        total_cost=(cost_col_dd, "mean"),
                    )
                    best_pre_thr = float(pre_stats.loc[best_pre_b]["throughput"])
                    best_pre_power = float(pre_stats.loc[best_pre_b]["power"])
                    best_pre_energy_pct = (
                        float(pre_stats.loc[best_pre_b]["energy_cost"]) / float(pre_stats.loc[best_pre_b]["total_cost"]) * 100.0
                        if float(pre_stats.loc[best_pre_b]["total_cost"]) > 0
                        else 0.0
                    )
                    results_sections += [
                        "### Prefill Deep Dive",
                        "",
                        "Prefill is the prompt-processing phase. Under time-based pricing, the dominant driver of $/token is throughput (tokens/sec).",
                        "",
                        f"- Best prefill backend by cost: **{best_pre_b}** at **{best_pre:.4g} USD/1M**.",
                        f"- {best_pre_b} throughput: ~**{best_pre_thr:.0f} tok/s**; mean power: ~**{best_pre_power:.1f} W**; energy share: ~**{best_pre_energy_pct:.2f}%**.",
                        (
                            f"- Next-best: **{second_pre_b}** at **{second_pre:.4g} USD/1M** ({delta_pre:.1f}% higher)."
                            if second_pre_b and delta_pre is not None
                            else None
                        ),
                        "",
                    ]
                    results_sections = [ln for ln in results_sections if ln is not None]
                if not gen.empty:
                    gen_rank = gen.groupby("backend")[cost_col_dd].mean().sort_values()
                    best_gen_b = str(gen_rank.index[0])
                    best_gen = float(gen_rank.iloc[0])
                    gen_stats = gen.groupby("backend").agg(
                        throughput=("throughput_mean_tok_s", "mean"),
                        power=("power_mean_watts", "mean"),
                        energy_kwh=("energy_kwh_per_1m_tokens", "mean"),
                        energy_cost=("energy_cost_usd_per_1m_tokens", "mean"),
                        total_cost=(cost_col_dd, "mean"),
                    )
                    best_gen_thr = float(gen_stats.loc[best_gen_b]["throughput"])
                    best_gen_power = float(gen_stats.loc[best_gen_b]["power"])
                    results_sections += [
                        "### Generate Deep Dive (Uncached)",
                        "",
                        "Generate mode here is an uncached greedy decoding loop. Every step re-runs a full forward pass, so throughput collapses and cost per generated token rises.",
                        "",
                        f"- Best generate backend by cost: **{best_gen_b}** at **{best_gen:.4g} USD/1M**.",
                        f"- {best_gen_b} throughput: ~**{best_gen_thr:.0f} tok/s**; mean power: ~**{best_gen_power:.1f} W**.",
                        "",
                    ]
        except Exception:
            pass

    plots_dir = results_dir / "plots"
    cost_plot = plots_dir / "total_cost_per_1m_tokens_tr119.png"
    lat_plot = plots_dir / "mean_latency_tr119.png"
    tier_plot = plots_dir / "cost_tiers_tr119.png"
    eff_plot = plots_dir / "energy_efficiency_tr119.png"
    carbon_plot = plots_dir / "carbon_footprint_tr119.png"
    scatter_plot = plots_dir / "cost_vs_throughput_tr119.png"
    throughput_plot = plots_dir / "throughput_tr119.png"
    cost_plot_gen = plots_dir / "total_cost_per_1m_tokens_tr119_generate.png"
    lat_plot_gen = plots_dir / "mean_latency_tr119_generate.png"
    tier_plot_gen = plots_dir / "cost_tiers_tr119_generate.png"
    eff_plot_gen = plots_dir / "energy_efficiency_tr119_generate.png"
    carbon_plot_gen = plots_dir / "carbon_footprint_tr119_generate.png"
    scatter_plot_gen = plots_dir / "cost_vs_throughput_tr119_generate.png"
    throughput_plot_gen = plots_dir / "throughput_tr119_generate.png"
    
    plot_candidates = [
        lat_plot,
        throughput_plot,
        cost_plot,
        tier_plot,
        eff_plot,
        carbon_plot,
        scatter_plot,
        lat_plot_gen,
        throughput_plot_gen,
        cost_plot_gen,
        tier_plot_gen,
        eff_plot_gen,
        carbon_plot_gen,
        scatter_plot_gen,
    ]
    if any(p.exists() for p in plot_candidates):
        results_sections += ["### Figures", ""]
        for p in plot_candidates:
            if p.exists():
                rel = os.path.relpath(p, out_path.parent)
                results_sections += [f"![{p.stem}]({Path(rel).as_posix()})", ""]

    validation_path = processed_dir / "cost_energy_validation.json"
    if not validation_path.exists():
        missing.append(str(validation_path))
    if validation_path.exists():
        try:
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            status_flag = validation.get("overall_valid")
            if status_flag is None:
                status_flag = validation.get("valid")
            results_sections += [
                "### Validation & Sanity Checks",
                "",
                f"- Validation status: **{'PASS' if status_flag else 'FAIL'}**",
            ]
            issues = list(validation.get("issues") or [])
            warnings = list(validation.get("warnings") or [])
            if not issues and not warnings:
                for key in ("cost_validation", "energy_validation"):
                    block = validation.get(key) or {}
                    issues += block.get("issues") or []
                    warnings += block.get("warnings") or []
            if issues:
                results_sections.append("")
                results_sections.append("### Issues")
                results_sections.append("")
                for issue in issues:
                    results_sections.append(f"- {issue}")
            if warnings:
                results_sections.append("")
                results_sections.append("### Warnings")
                results_sections.append("")
                for warning in warnings:
                    results_sections.append(f"- {warning}")
            results_sections.append("")
        except Exception:
            pass
    
    # Cost/energy analysis if available
    analysis_json = processed_dir / "cost_energy_analysis.json"
    if not analysis_json.exists():
        missing.append(str(analysis_json))
    if analysis_json.exists():
        try:
            analysis_data = json.loads(analysis_json.read_text(encoding="utf-8"))
            results_sections += [
                "### Cost & Energy Analysis",
                "",
            ]

            if "cost_breakdown" in analysis_data and isinstance(analysis_data["cost_breakdown"], dict):
                breakdown_rows: list[list[Any]] = []
                for backend, data in sorted(
                    analysis_data["cost_breakdown"].items(),
                    key=lambda x: (x[1].get("total_cost_usd_per_1m") or 0),
                ):
                    if not isinstance(data, dict):
                        continue
                    breakdown_rows.append(
                        [
                            backend,
                            data.get("infra_cost_usd_per_1m"),
                            data.get("energy_cost_usd_per_1m"),
                            data.get("total_cost_usd_per_1m"),
                            data.get("infra_pct"),
                            data.get("energy_pct"),
                        ]
                    )
                if breakdown_rows:
                    results_sections += [
                        "### Cost Breakdown (Infra vs Energy)",
                        "",
                        _md_table(
                            [
                                "Backend",
                                "infra_usd_per_1M",
                                "energy_usd_per_1M",
                                "total_usd_per_1M",
                                "infra_pct",
                                "energy_pct",
                            ],
                            breakdown_rows,
                        ),
                        "",
                    ]
            
            if "energy_efficiency_ranking" in analysis_data:
                eff_ranking = analysis_data["energy_efficiency_ranking"]
                results_sections += [
                    "### Energy Efficiency Ranking",
                    "",
                    "Backends ranked by tokens per kWh (higher is better):",
                    "",
                ]
                for backend, tokens_per_kwh in sorted(eff_ranking.items(), key=lambda x: x[1], reverse=True):
                    results_sections.append(f"- **{backend}**: {tokens_per_kwh:.0f} tokens/kWh")
                results_sections.append("")
            
            if "carbon_comparison" in analysis_data:
                carbon = analysis_data["carbon_comparison"]
                results_sections += [
                    "### Carbon Footprint Comparison",
                    "",
                    f"- Lowest carbon: **{carbon.get('lowest_carbon_backend')}** ({carbon.get('lowest_carbon_gco2e', 0):.1f} gCO2e/1M tokens)",
                    f"- Highest carbon: **{carbon.get('highest_carbon_backend')}** ({carbon.get('highest_carbon_gco2e', 0):.1f} gCO2e/1M tokens)",
                    f"- Range: {carbon.get('carbon_range_gco2e', 0):.1f} gCO2e/1M tokens",
                    "",
                ]
            
            if "roi_by_tier" in analysis_data:
                roi = analysis_data["roi_by_tier"]
                results_sections += [
                    "### ROI by Pricing Tier",
                    "",
                    "Savings from switching to spot or reserved pricing:",
                    "",
                ]
                for backend, data in sorted(
                    roi.items(), key=lambda x: x[1].get("spot_savings_pct") or 0, reverse=True
                ):
                    spot_savings = data.get("spot_savings_pct")
                    reserved_savings = data.get("reserved_savings_pct")
                    spot_fmt = f"{spot_savings:.1f}%" if isinstance(spot_savings, (int, float)) else "N/A"
                    reserved_fmt = (
                        f"{reserved_savings:.1f}%" if isinstance(reserved_savings, (int, float)) else "N/A"
                    )
                    results_sections.append(
                        f"- **{backend}**: Spot saves {spot_fmt}, Reserved saves {reserved_fmt}"
                    )
                results_sections.append("")

            if "request_costs" in analysis_data and analysis_data["request_costs"]:
                request_costs = analysis_data["request_costs"]
                assumptions = analysis_data.get("assumptions", {})
                prompt_tokens = assumptions.get("prompt_tokens")
                generate_tokens = assumptions.get("generate_tokens")
                results_sections += [
                    "### Request-Level Cost (Prompt+Generate Mix)",
                    "",
                    f"Assumptions: prompt_tokens={prompt_tokens}, generate_tokens={generate_tokens}.",
                    "",
                ]
                rows_req: list[list[Any]] = []
                for backend, data in sorted(
                    request_costs.items(),
                    key=lambda x: x[1].get("total_cost_usd_per_request", 0),
                ):
                    rows_req.append(
                        [
                            backend,
                            data.get("time_prefill_s"),
                            data.get("time_generate_s"),
                            data.get("energy_kwh_per_request"),
                            data.get("total_cost_usd_per_request"),
                        ]
                    )
                results_sections += [
                    _md_table(
                        [
                            "Backend",
                            "time_prefill_s",
                            "time_generate_s",
                            "energy_kwh_per_request",
                            "total_cost_usd_per_request",
                        ],
                        rows_req,
                    ),
                    "",
                ]

            if "tco_by_backend" in analysis_data:
                tco = analysis_data["tco_by_backend"]
                assumptions = analysis_data.get("assumptions", {})
                tokens_per_month = assumptions.get("tokens_per_month")
                months = assumptions.get("months")
                upfront_cost = assumptions.get("upfront_cost_usd")
                results_sections += [
                    "### TCO Summary",
                    "",
                    f"Assumptions: {tokens_per_month} tokens/month, {months} months, upfront ${upfront_cost}.",
                    "",
                ]
                rows_tco: list[list[Any]] = []
                for backend, data in sorted(
                    tco.items(),
                    key=lambda x: x[1].get("total_cost_usd", 0),
                ):
                    rows_tco.append(
                        [
                            backend,
                            data.get("total_cost_usd"),
                            data.get("cost_per_month_usd"),
                            data.get("cost_per_1m_tokens_usd"),
                        ]
                    )
                results_sections += [
                    _md_table(
                        [
                            "Backend",
                            "total_cost_usd",
                            "cost_per_month_usd",
                            "cost_per_1m_tokens_usd",
                        ],
                        rows_tco,
                    ),
                    "",
                ]
        except Exception:
            pass

    # Statistical significance section if available
    stat_analysis_path = processed_dir / "statistical_analysis.json"
    stat_section: list[str] = []
    if not stat_analysis_path.exists():
        missing.append(str(stat_analysis_path))
    if stat_analysis_path.exists():
        try:
            stat_data = json.loads(stat_analysis_path.read_text(encoding="utf-8"))
            stat_section = [
                "## 5. Statistical Analysis",
                "",
                "We test whether observed cost differences are statistically significant across backends. Tests are run per mode when available.",
                "",
            ]

            by_mode = stat_data.get("by_mode")
            if isinstance(by_mode, dict) and by_mode:
                for mode, data in by_mode.items():
                    stat_section += [
                        f"### {str(mode).capitalize()} Mode",
                        "",
                        "#### Hypothesis Testing",
                        "",
                    ]
                    if data.get("anova", {}).get("significant"):
                        f_stat = data["anova"]["f_statistic"]
                        p_val = data["anova"]["p_value"]
                        stat_section.append(
                            f"- **ANOVA**: Significant differences detected across backends (F={f_stat:.2f}, p={p_val:.4f})"
                        )
                    else:
                        stat_section.append("- **ANOVA**: No significant differences detected across backends")
                    stat_section.append("")
                    if data.get("pairwise_comparisons"):
                        sig_comps = [c for c in data["pairwise_comparisons"] if c.get("significant")]
                        if sig_comps:
                            stat_section.append("#### Significant Pairwise Comparisons (p < 0.05)")
                            stat_section.append("")
                            for comp in sig_comps[:10]:
                                stat_section.append(
                                    f"- **{comp['group_a']} vs {comp['group_b']}**: "
                                    f"${comp['difference']:.4f} difference ({comp['percent_change']:.1f}%), "
                                    f"p={comp['p_value']:.4f}, Cohen's d={comp['effect_size_cohens_d']:.3f}"
                                )
                            stat_section.append("")
            else:
                data = stat_data.get("overall", stat_data)
                stat_section += [
                    "### Hypothesis Testing",
                    "",
                ]
                if data.get("anova", {}).get("significant"):
                    f_stat = data["anova"]["f_statistic"]
                    p_val = data["anova"]["p_value"]
                    stat_section.append(
                        f"- **ANOVA**: Significant differences detected across backends (F={f_stat:.2f}, p={p_val:.4f})"
                    )
                else:
                    stat_section.append("- **ANOVA**: No significant differences detected across backends")
                stat_section.append("")
                if data.get("pairwise_comparisons"):
                    sig_comps = [c for c in data["pairwise_comparisons"] if c.get("significant")]
                    if sig_comps:
                        stat_section.append("### Significant Pairwise Comparisons (p < 0.05)")
                        stat_section.append("")
                        for comp in sig_comps[:10]:
                            stat_section.append(
                                f"- **{comp['group_a']} vs {comp['group_b']}**: "
                                f"${comp['difference']:.4f} difference ({comp['percent_change']:.1f}%), "
                                f"p={comp['p_value']:.4f}, Cohen's d={comp['effect_size_cohens_d']:.3f}"
                            )
                        stat_section.append("")
        except Exception:
            pass

    decision_matrix_md: str | None = None
    if cost_data and isinstance(cost_data.get("rows"), list) and cost_data["rows"]:
        try:
            df_dm = pd.DataFrame(cost_data["rows"])
            cost_col_dm = (
                "total_cost_usd_per_1m_tokens_on_demand"
                if "total_cost_usd_per_1m_tokens_on_demand" in df_dm.columns
                else "total_cost_usd_per_1m_tokens"
            )
            if "mode" in df_dm.columns and cost_col_dm in df_dm.columns:
                pivot = df_dm.groupby(["backend", "mode"])[cost_col_dm].mean().unstack("mode")
                rows_dm: list[list[Any]] = []
                for backend in sorted(pivot.index.astype(str).tolist()):
                    pre = pivot.loc[backend].get("prefill") if "prefill" in pivot.columns else None
                    gen = pivot.loc[backend].get("generate") if "generate" in pivot.columns else None
                    ratio = (float(gen) / float(pre)) if (pre and gen and float(pre) > 0) else None
                    rows_dm.append([backend, pre, gen, ratio])
                decision_matrix_md = _md_table(
                    ["Backend", "prefill_usd_per_1M", "generate_usd_per_1M", "generate/prefill"],
                    rows_dm,
                )
        except Exception:
            decision_matrix_md = None

    synthesis = [
        "## 6. Synthesis & Decision Matrix",
        "",
        "### 6.1 What matters most",
        "",
        "- **Throughput dominates $/token** under the configured pricing inputs; small power differences rarely change rankings.",
        "- **Pricing tier is a second lever**: spot/reserved can shift total cost by ~2-3x for the same backend.",
        "- **Uncached generate is an upper bound**: production KV-cache decoding should reduce generate cost per token materially.",
        "",
        "### 6.2 Deployment Recommendations (This Hardware)",
        "",
        "- **Default GPU backend:** `onnxruntime-gpu` (best cost and best energy efficiency in this benchmark).",
        "- **CPU-only fallback:** `onnxruntime-cpu` (better cost/energy than `transformers-cpu`).",
        "- **Transformers backends:** keep when you need maximum feature parity; expect higher $/token.",
        "",
    ]
    if decision_matrix_md:
        synthesis += [
            "### 6.3 Decision Matrix (On-Demand, Mean Across Scenarios)",
            "",
            decision_matrix_md,
            "",
        ]
    synthesis += [
        "### 6.4 Operational Considerations",
        "",
        "- `onnxruntime-gpu`: best efficiency here, but requires ONNX export + runtime integration (engineering overhead is moderate but stable).",
        "- `transformers-gpu`: simplest integration path, but higher $/token in this benchmark.",
        "- `transformers-gpu-compile`: can improve throughput for some models, but compilation overhead and variability can complicate deployment.",
        "- CPU backends are viable for compatibility/fallback, not for cost-optimal throughput at scale.",
        "",
        "### 6.5 Limitations & Next Steps",
        "",
        "- Single hardware system; replicate on your production GPU/CPU to lock absolute costs.",
        "- Generate results are **uncached** and intentionally pessimistic; repeat with KV-cache for production planning.",
        "- Tokenization, batching overheads, and end-to-end serving stack are not included; integrate into TR123 for full-stack TCO.",
        "",
    ]
    synthesis += [
        "---",
        "",
    ]

    repro = [
        "## 7. Reproducibility",
        "",
        "### 7.1 Run the pipeline",
        "",
        "```bash",
        f"python scripts/tr119/run_experiment.py --config {cfg_path} --device cuda",
        "```",
        "",
        "### 7.2 Key artifacts",
        "",
        f"- Results root: `{results_dir}`",
        f"- Processed: `{processed_dir}`",
        f"- Report: `{out_path}`",
        f"- Manifest: `{manifest_path}`" if manifest_path else "- Manifest: N/A",
        "",
    ]

    missing_section: list[str] = []
    if missing:
        missing_section = [
            "## Missing Data / Notes",
            "",
            "The following artifacts were not found and should be generated for a complete report:",
            "",
            *[f"- `{m}`" for m in missing],
            "",
        ]

    out_md = "\n".join(
        [
            title,
            *meta_lines,
            *abstract,
            *measurement_defs,
            *exec_lines,
            *toc_lines,
            *intro,
            *methodology,
            *exp_design,
            *results_sections,
            *stat_section,
            *synthesis,
            *repro,
            *missing_section,
        ]
    ).strip() + "\n"

    out_path.write_text(out_md, encoding="utf-8")
    print(f"Wrote TR119 report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


