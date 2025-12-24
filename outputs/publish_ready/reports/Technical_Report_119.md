# Technical Report 119 v1.1: Cost & Energy Analysis
## Local-first inference TCO with telemetry (prefill + generate)


**Project:** Banterhearts LLM Performance Research
**Date:** 2025-12-20
**Author:** Research Team
**Report Type:** Frontier cost/energy deep dive
**Test Duration:** 2.0 hours
**Status:** Frontier Report (artifact-backed)
**Version:** 1.1
**Git SHA:** `fa75edf8367dce1e12e6762d23f3319ffd8e97b5`
**Related Work:** [TR117](Technical_Report_117.md), [TR118_v2.2](Technical_Report_118_v2.2.md)

---

## Abstract

TR119 converts benchmark latency/throughput and on-device telemetry into comparable
dollars, kWh, and carbon per 1M tokens. Using GPT-2 on the target hardware, we run
prefill (single forward pass) and uncached generate (repeated full forward passes
per token) across multiple backends and scenarios with repeated trials, then compute
compute-hours, energy, carbon footprint, and dollars per 1M tokens under multiple
pricing tiers. The outcome is a decision-ready ranking of backends by cost, latency,
energy efficiency, and carbon footprint, backed by artifacts, validation, and
statistical tests.

---

## Measurement Definitions

This report follows TR118-style explicit definitions. These definitions matter because they control comparability across backends.

### Prefill Mode

- **Latency (ms):** wall time for one forward pass (warmups excluded; tokenization excluded).
- **Throughput (tok/s):** `tokens_processed / latency_s`, where `tokens_processed = batch_size * seq_len` (padded length used in the forward pass).

### Generate Mode (Uncached)

- **Latency (ms):** total wall time for an uncached greedy decoding loop generating up to `max_new_tokens` new tokens.
- **Throughput (tok/s):** `tokens_generated / total_time_s` (tokens_generated may be < max_new_tokens if EOS appears).
- **Interpretation:** uncached generate is intentionally pessimistic; production KV-cache decoding should be materially faster.

### Energy, Cost, and Carbon

- **Power (W):** mean sampled power during the benchmark region (GPU for GPU backends; CPU package power for CPU backends).
- **Energy (kWh/1M tok):** `(power_w * seconds_per_1m) / 3.6e6` where `seconds_per_1m = 1e6 / throughput_tok_s`.
- **Infra cost (USD/1M tok):** `hours_per_1m * usd_per_hour` (tier-specific).
- **Total cost (USD/1M tok):** infra cost + energy cost.
- **Carbon (gCO2e/1M tok):** `energy_kwh_per_1m * carbon_intensity_gco2e_per_kwh`.

---

## Executive Summary

TR119 answers: which backend minimizes cost and energy for local-first inference once we include real telemetry and explicit pricing inputs?
Across this matrix (5 backends x 5 scenarios x 7 repetitions x 2 modes = 350 runs), the ranking is throughput-driven: the fastest stable backend is also the cheapest per token under time-based pricing.

### Key Findings

- Best-cost backend (prefill, mean across scenarios, on-demand): **onnxruntime-gpu** at ~**$0.1279 per 1M tokens**.
- Worst-cost backend (prefill): **transformers-cpu** at ~**$0.971 per 1M tokens**.
- Best spot pricing (prefill): **onnxruntime-gpu** at ~**$0.03868 per 1M tokens** (69.8% savings vs on-demand).
- Lowest carbon footprint (prefill): **onnxruntime-gpu** at ~**1.0 gCO2e per 1M tokens**.
- Best energy efficiency (prefill): **onnxruntime-gpu** at ~**503440295 tokens/kWh**.
- Lowest on-demand provider (prefill, mean across scenarios): **azure_nc_t4_v3/onnxruntime-gpu** at ~**$0.1144 per 1M tokens**.
- Best request-level cost: **onnxruntime-gpu** at ~**$0.0001475 per request**.
- Runs: **350** total, **0** degraded (0.0%).
- Best-latency backend (mean across scenarios): **onnxruntime-gpu** at ~**16.5 ms**.

### Key Decision

- If GPU is available, `onnxruntime-gpu` is the default recommendation on this hardware (best cost and best energy efficiency in this benchmark).
- If CPU-only, prefer `onnxruntime-cpu` over `transformers-cpu` for materially lower $/token and kWh/token.

---

## Table of Contents

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Methodology & Experimental Design](#2-methodology--experimental-design)
3. [Environment & Artifacts](#3-environment--artifacts)
4. [Results & Analysis](#4-results--analysis)
5. [Statistical Analysis](#5-statistical-analysis)
6. [Synthesis & Decision Matrix](#6-synthesis--decision-matrix)
7. [Reproducibility](#7-reproducibility)

---

## 1. Introduction & Research Motivation

TR117 established baseline latency and throughput across multiple inference backends.
TR118 raised rigor: explicit measurement definitions, artifact pipelines, and reproducibility.
TR119 extends that foundation by translating speed into **$/token**, **kWh/token**, and **gCO2e/token** so backend selection becomes a cost-and-energy decision, not just a latency chart.

### 1.1 Research Questions

1. Which backend minimizes dollars per 1M tokens for **prefill** and for **generate**?
2. How large is the **pricing-tier lever** (on-demand vs spot vs reserved) relative to backend choice?
3. Does energy meaningfully change rankings, or is throughput the dominant driver?
4. What is request-level cost for a representative prompt+generate mix?

### 1.2 Scope

- Single target machine; results are hardware-specific.
- Model: GPT-2 (as configured).
- Generate mode is uncached (KV-cache disabled) to isolate raw compute; production decode will differ.

---

## 2. Methodology & Experimental Design

### Metrics
- Latency (ms), throughput (tokens/sec).
- GPU power (W), temperature (deg C), memory (MB); CPU package power (W).

### Benchmark Matrix
- Backends: transformers-gpu-compile, transformers-gpu, transformers-cpu, onnxruntime-gpu, onnxruntime-cpu
- Scenarios: single_short, single_medium, single_long, batch_short, batch_medium
- Repetitions: 7 per backend/scenario/mode
- Warmup runs: 2

### Cost & Energy Model
- GPU-hours per 1M tokens: `gpu_hours = 1_000_000 / (throughput_tok_s * 3600)`.
- Energy per 1M tokens (kWh): `energy_kwh = (power_w * seconds_per_1m) / 3.6e6`.
- Infra cost: `gpu_hours * price_per_hour` (per pricing tier).
- Energy cost: `energy_kwh * usd_per_kwh`.
- Total cost: infra cost + energy cost.
- Carbon footprint: `energy_kwh * carbon_intensity_gco2e_per_kwh`.

### Telemetry Collection
- GPU metrics sampled via ResourceMonitor at the configured interval.
- CPU package power captured from Windows Energy Meter (RAPL) counters when available.

### Pricing & Energy Inputs

- On-demand rate: $1.006/hour
- Spot rate: $0.302/hour
- Reserved 1yr rate: $0.704/hour
- Reserved 3yr rate: $0.503/hour
- Energy price: $0.2/kWh
- Carbon intensity: 500.0 gCO2e/kWh

### Request Token Mix

- prompt_tokens: 256
- generate_tokens: 128

## 3. Environment & Artifacts

- Config: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr119\configs\matrix.yaml`
- Results root: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr119\results\tr119_matrix`

### Telemetry

- Sample interval: 0.25 s
- GPU telemetry: True
- CPU telemetry: True

### Environment

- OS: Windows-11-10.0.26200-SP0
- Python: 3.13.1 (tags/v3.13.1:0671451, Dec  3 2024, 19:06:28) [MSC v.1942 64 bit (AMD64)]
- CPU: 13th Gen Intel(R) Core(TM) i9-13980HX
- Prompt config: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr117\configs\matrix_tier3.yaml`
- GPU: NVIDIA GeForce RTX 4080 Laptop GPU (12282 MB, CC 8.9)

- Modes observed: generate, prefill

## 4. Results & Analysis

This section summarizes observed performance, telemetry, and derived cost/energy metrics. Tables are artifact-backed.

### Latency & Throughput Summary (Mean Across Scenarios)

| Backend | Mode | lat_mean_ms | throughput_mean_tok_s | power_mean_w | degraded_rate | degraded_runs |
| --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | generate | 266.1 | 59.94 | 87.18 | 0 | 0/35 |
| onnxruntime-cpu | prefill | 26.21 | 1224 | 101.2 | 0 | 0/35 |
| onnxruntime-gpu | generate | 56.07 | 311.6 | 30.81 | 0 | 0/35 |
| onnxruntime-gpu | prefill | 16.54 | 2246 | 16.63 | 0 | 0/35 |
| transformers-cpu | generate | 815.4 | 20.11 | 74.87 | 0 | 0/35 |
| transformers-cpu | prefill | 88.82 | 377.5 | 64.24 | 0 | 0/35 |
| transformers-gpu | generate | 158 | 105.5 | 23.57 | 0 | 0/35 |
| transformers-gpu | prefill | 21.22 | 2071 | 16.37 | 0 | 0/35 |
| transformers-gpu-compile | generate | 166.2 | 116.8 | 30.71 | 0 | 0/35 |
| transformers-gpu-compile | prefill | 20.84 | 1817 | 20.39 | 0 | 0/35 |

#### Interpretation

- Prefill measures a single forward pass; uncached generate repeats full forward passes per token and therefore has substantially lower throughput.
- Under time-based pricing, higher throughput almost always implies lower $/token; power differences matter most when power varies dramatically at similar throughput.
- Treat CPU backends as fallbacks unless GPU is unavailable; the gap in throughput and cost per token is large in both modes.

### Latency, Throughput, and Telemetry (Per Backend/Scenario)

| Backend | Mode | Scenario | lat_mean_ms | lat_ci_lower | lat_ci_upper | throughput_mean_tok_s | power_mean_w | gpu_temp_mean_c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | generate | batch_medium | 436 | 427.8 | 444.3 | 73.44 | 1.738 | 50 |
| onnxruntime-cpu | prefill | batch_medium | 38.37 | 36.37 | 40.36 | 1987 | 1.955 | 48 |
| onnxruntime-cpu | generate | batch_short | 329.5 | 323.9 | 335.2 | 97.14 | 1.756 | 50 |
| onnxruntime-cpu | prefill | batch_short | 29.31 | 28.43 | 30.18 | 1504 | 1.924 | 48 |
| onnxruntime-cpu | generate | single_long | 213.1 | 208.9 | 217.3 | 37.55 | 1.755 | 50 |
| onnxruntime-cpu | prefill | single_long | 24.02 | 23.29 | 24.74 | 1125 | 2.691 | 48 |
| onnxruntime-cpu | generate | single_medium | 188.3 | 182 | 194.6 | 42.55 | 7.181 | 50 |
| onnxruntime-cpu | prefill | single_medium | 21.14 | 20.42 | 21.87 | 900 | 17.42 | 48 |
| onnxruntime-cpu | generate | single_short | 163.4 | 158.8 | 168 | 49.01 | 26.19 | 51.36 |
| onnxruntime-cpu | prefill | single_short | 18.23 | 17.54 | 18.93 | 604.3 | 18.98 | 48 |
| onnxruntime-gpu | generate | batch_medium | 63.12 | 60.8 | 65.44 | 508.7 | 36.3 | 52.43 |
| onnxruntime-gpu | prefill | batch_medium | 26.68 | 26.05 | 27.32 | 2850 | 14.61 | 48 |
| onnxruntime-gpu | generate | batch_short | 60.27 | 53.36 | 67.19 | 537.5 | 30.45 | 51.57 |
| onnxruntime-gpu | prefill | batch_short | 23.61 | 19.76 | 27.46 | 1940 | 15.94 | 48 |
| onnxruntime-gpu | generate | single_long | 47.04 | 44.73 | 49.35 | 170.6 | 27.64 | 51.29 |
| onnxruntime-gpu | prefill | single_long | 11.93 | 10.63 | 13.22 | 2292 | 16.81 | 48 |
| onnxruntime-gpu | generate | single_medium | 47.56 | 42.16 | 52.96 | 172.7 | 31.95 | 51.71 |
| onnxruntime-gpu | prefill | single_medium | 9.015 | 6.535 | 11.49 | 2315 | 23.32 | 48.43 |
| onnxruntime-gpu | generate | single_short | 62.38 | 23.51 | 101.2 | 168.4 | 27.69 | 51.14 |
| onnxruntime-gpu | prefill | single_short | 11.48 | -2.496 | 25.45 | 1832 | 12.49 | 48.57 |
| transformers-cpu | generate | batch_medium | 1021 | 970.3 | 1072 | 31.45 | 1.847 | 49.9 |
| transformers-cpu | prefill | batch_medium | 113.3 | 102.7 | 124 | 679 | 2.032 | 47 |
| transformers-cpu | generate | batch_short | 910.7 | 875.4 | 946 | 35.23 | 1.859 | 49.57 |
| transformers-cpu | prefill | batch_short | 92.59 | 83.45 | 101.7 | 485.4 | 2.038 | 47 |
| transformers-cpu | generate | single_long | 721.4 | 641.5 | 801.4 | 11.27 | 1.841 | 49 |
| transformers-cpu | prefill | single_long | 81.4 | 70.35 | 92.45 | 339.2 | 1.947 | 47 |
| transformers-cpu | generate | single_medium | 709.1 | 661 | 757.2 | 11.35 | 1.824 | 49 |
| transformers-cpu | prefill | single_medium | 86.59 | 80.63 | 92.55 | 221.4 | 2.618 | 47 |
| transformers-cpu | generate | single_short | 714.7 | 662.6 | 766.7 | 11.27 | 6.342 | 49.04 |
| transformers-cpu | prefill | single_short | 70.15 | 58.52 | 81.79 | 162.2 | 15.52 | 47 |
| transformers-gpu | generate | batch_medium | 177.5 | 166.7 | 188.2 | 181.4 | 27.18 | 50 |
| transformers-gpu | prefill | batch_medium | 25.32 | 21.9 | 28.74 | 3102 | 20.19 | 47.14 |
| transformers-gpu | generate | batch_short | 181.5 | 170 | 193 | 177.3 | 22.61 | 49.57 |
| transformers-gpu | prefill | batch_short | 11.34 | 6.077 | 16.6 | 4798 | 18.46 | 47.14 |
| transformers-gpu | generate | single_long | 154.2 | 140.2 | 168.2 | 52.32 | 20.42 | 49 |
| transformers-gpu | prefill | single_long | 23.61 | 22.71 | 24.5 | 1150 | 14.16 | 47 |
| transformers-gpu | generate | single_medium | 142.8 | 130.3 | 155.3 | 56.52 | 19.46 | 49 |
| transformers-gpu | prefill | single_medium | 23.57 | 22.96 | 24.19 | 810.6 | 14.05 | 47 |
| transformers-gpu | generate | single_short | 134.2 | 128.3 | 140 | 60.17 | 28.16 | 49.89 |
| transformers-gpu | prefill | single_short | 22.25 | 21.93 | 22.57 | 496.7 | 14.98 | 47 |
| transformers-gpu-compile | generate | batch_medium | 269.1 | 195.7 | 342.5 | 133.1 | 29 | 50.43 |
| transformers-gpu-compile | prefill | batch_medium | 25.56 | 22.54 | 28.57 | 3038 | 19.99 | 47.16 |
| transformers-gpu-compile | generate | batch_short | 183 | 128.7 | 237.4 | 196.4 | 33.58 | 50.47 |
| transformers-gpu-compile | prefill | batch_short | 21.62 | 8.448 | 34.79 | 2441 | 15.75 | 47.66 |
| transformers-gpu-compile | generate | single_long | 169.4 | 131.9 | 206.8 | 51.95 | 23.85 | 48.77 |
| transformers-gpu-compile | prefill | single_long | 26.47 | 25.48 | 27.46 | 1022 | 17.75 | 47 |
| transformers-gpu-compile | generate | single_medium | 154.2 | 107.4 | 201 | 57.62 | 22.32 | 49.22 |
| transformers-gpu-compile | prefill | single_medium | 24.44 | 23.68 | 25.19 | 778.3 | 16.11 | 47.14 |
| transformers-gpu-compile | generate | single_short | 55.44 | 52.73 | 58.14 | 144.7 | 44.79 | 51.29 |
| transformers-gpu-compile | prefill | single_short | 6.1 | 5.836 | 6.364 | 1808 | 32.36 | 48.42 |

### Cost & Energy Summary (Mean Across Scenarios)

| Backend | Mode | total_cost_usd_per_1M_tok | energy_cost_usd_per_1M_tok | energy_kwh_per_1M_tok | carbon_gco2e_per_1M_tok |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | generate | 5.37 | 0.09212 | 0.4606 | 230.3 |
| onnxruntime-cpu | prefill | 0.2748 | 0.005213 | 0.02607 | 13.03 |
| onnxruntime-gpu | generate | 1.204 | 0.007105 | 0.03553 | 17.76 |
| onnxruntime-gpu | prefill | 0.1279 | 0.0004174 | 0.002087 | 1.043 |
| transformers-cpu | generate | 18.47 | 0.2655 | 1.328 | 663.8 |
| transformers-cpu | prefill | 0.971 | 0.01186 | 0.05931 | 29.66 |
| transformers-gpu | generate | 3.626 | 0.01644 | 0.08222 | 41.11 |
| transformers-gpu | prefill | 0.2605 | 0.0007796 | 0.003898 | 1.949 |
| transformers-gpu-compile | generate | 3.154 | 0.01716 | 0.08582 | 42.91 |
| transformers-gpu-compile | prefill | 0.1995 | 0.0007668 | 0.003834 | 1.917 |

#### Interpretation

- Prefill and uncached generate operate in different cost regimes because generate throughput is far lower under repeated full forward passes.
- Energy and carbon scale linearly with mean power and runtime. At the configured rates, infra cost dominates total cost for all backends.

### Cost & Energy per 1M Tokens (On-Demand Pricing)

| Backend | Mode | Scenario | throughput_mean_tok_s | power_mean_w | gpu_hours_per_1M_tok | infra_cost_usd_per_1M_tok | energy_cost_usd_per_1M_tok | total_cost_usd_per_1M_tok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | generate | batch_medium | 73.44 | 82.13 | 3.782 | 3.805 | 0.06213 | 3.867 |
| onnxruntime-cpu | prefill | batch_medium | 1987 | 119.7 | 0.1398 | 0.1406 | 0.003347 | 0.144 |
| onnxruntime-cpu | generate | batch_short | 97.14 | 86.29 | 2.86 | 2.877 | 0.04935 | 2.926 |
| onnxruntime-cpu | prefill | batch_short | 1504 | 102.1 | 0.1847 | 0.1858 | 0.003772 | 0.1896 |
| onnxruntime-cpu | generate | single_long | 37.55 | 90.5 | 7.397 | 7.441 | 0.1339 | 7.575 |
| onnxruntime-cpu | prefill | single_long | 1125 | 94.11 | 0.2468 | 0.2483 | 0.004646 | 0.253 |
| onnxruntime-cpu | generate | single_medium | 42.55 | 85.19 | 6.528 | 6.567 | 0.1112 | 6.678 |
| onnxruntime-cpu | prefill | single_medium | 900 | 104.6 | 0.3087 | 0.3105 | 0.006457 | 0.317 |
| onnxruntime-cpu | generate | single_short | 49.01 | 91.76 | 5.668 | 5.702 | 0.104 | 5.806 |
| onnxruntime-cpu | prefill | single_short | 604.3 | 85.34 | 0.4597 | 0.4625 | 0.007846 | 0.4703 |
| onnxruntime-gpu | generate | batch_medium | 508.7 | 36.3 | 0.5461 | 0.5494 | 0.003964 | 0.5533 |
| onnxruntime-gpu | prefill | batch_medium | 2850 | 14.61 | 0.09745 | 0.09804 | 0.0002847 | 0.09832 |
| onnxruntime-gpu | generate | batch_short | 537.5 | 30.45 | 0.5168 | 0.5199 | 0.003148 | 0.523 |
| onnxruntime-gpu | prefill | batch_short | 1940 | 15.94 | 0.1432 | 0.144 | 0.0004563 | 0.1445 |
| onnxruntime-gpu | generate | single_long | 170.6 | 27.64 | 1.629 | 1.638 | 0.009003 | 1.647 |
| onnxruntime-gpu | prefill | single_long | 2292 | 16.81 | 0.1212 | 0.1219 | 0.0004074 | 0.1223 |
| onnxruntime-gpu | generate | single_medium | 172.7 | 31.95 | 1.608 | 1.618 | 0.01027 | 1.628 |
| onnxruntime-gpu | prefill | single_medium | 2315 | 23.32 | 0.12 | 0.1207 | 0.0005596 | 0.1212 |
| onnxruntime-gpu | generate | single_short | 168.4 | 27.69 | 1.65 | 1.66 | 0.009136 | 1.669 |
| onnxruntime-gpu | prefill | single_short | 1832 | 12.49 | 0.1516 | 0.1526 | 0.0003788 | 0.1529 |
| transformers-cpu | generate | batch_medium | 31.45 | 81.49 | 8.833 | 8.886 | 0.144 | 9.03 |
| transformers-cpu | prefill | batch_medium | 679 | 71.92 | 0.4091 | 0.4116 | 0.005884 | 0.4174 |
| transformers-cpu | generate | batch_short | 35.23 | 76.93 | 7.886 | 7.933 | 0.1213 | 8.054 |
| transformers-cpu | prefill | batch_short | 485.4 | 69.12 | 0.5723 | 0.5757 | 0.007911 | 0.5836 |
| transformers-cpu | generate | single_long | 11.27 | 73.08 | 24.65 | 24.8 | 0.3603 | 25.16 |
| transformers-cpu | prefill | single_long | 339.2 | 60.09 | 0.8189 | 0.8238 | 0.009842 | 0.8337 |
| transformers-cpu | generate | single_medium | 11.35 | 69.21 | 24.48 | 24.63 | 0.3388 | 24.96 |
| transformers-cpu | prefill | single_medium | 221.4 | 59.44 | 1.254 | 1.262 | 0.01491 | 1.277 |
| transformers-cpu | generate | single_short | 11.27 | 73.66 | 24.64 | 24.79 | 0.3631 | 25.15 |
| transformers-cpu | prefill | single_short | 162.2 | 60.63 | 1.712 | 1.723 | 0.02076 | 1.743 |
| transformers-gpu | generate | batch_medium | 181.4 | 27.18 | 1.531 | 1.54 | 0.008325 | 1.549 |
| transformers-gpu | prefill | batch_medium | 3102 | 20.19 | 0.08956 | 0.09009 | 0.0003617 | 0.09046 |
| transformers-gpu | generate | batch_short | 177.3 | 22.61 | 1.567 | 1.577 | 0.007088 | 1.584 |
| transformers-gpu | prefill | batch_short | 4798 | 18.46 | 0.0579 | 0.05824 | 0.0002137 | 0.05846 |
| transformers-gpu | generate | single_long | 52.32 | 20.42 | 5.309 | 5.341 | 0.02168 | 5.363 |
| transformers-gpu | prefill | single_long | 1150 | 14.16 | 0.2416 | 0.243 | 0.0006839 | 0.2437 |
| transformers-gpu | generate | single_medium | 56.52 | 19.46 | 4.914 | 4.944 | 0.01912 | 4.963 |
| transformers-gpu | prefill | single_medium | 810.6 | 14.05 | 0.3427 | 0.3447 | 0.000963 | 0.3457 |
| transformers-gpu | generate | single_short | 60.17 | 28.16 | 4.617 | 4.644 | 0.026 | 4.67 |
| transformers-gpu | prefill | single_short | 496.7 | 14.98 | 0.5592 | 0.5626 | 0.001676 | 0.5642 |
| transformers-gpu-compile | generate | batch_medium | 133.1 | 29 | 2.087 | 2.1 | 0.0121 | 2.112 |
| transformers-gpu-compile | prefill | batch_medium | 3038 | 19.99 | 0.09144 | 0.09199 | 0.0003657 | 0.09236 |
| transformers-gpu-compile | generate | batch_short | 196.4 | 33.58 | 1.414 | 1.423 | 0.0095 | 1.432 |
| transformers-gpu-compile | prefill | batch_short | 2441 | 15.75 | 0.1138 | 0.1145 | 0.0003586 | 0.1148 |
| transformers-gpu-compile | generate | single_long | 51.95 | 23.85 | 5.347 | 5.379 | 0.0255 | 5.404 |
| transformers-gpu-compile | prefill | single_long | 1022 | 17.75 | 0.2719 | 0.2735 | 0.0009651 | 0.2745 |
| transformers-gpu-compile | generate | single_medium | 57.62 | 22.32 | 4.821 | 4.85 | 0.02152 | 4.871 |
| transformers-gpu-compile | prefill | single_medium | 778.3 | 16.11 | 0.3569 | 0.359 | 0.00115 | 0.3602 |
| transformers-gpu-compile | generate | single_short | 144.7 | 44.79 | 1.919 | 1.931 | 0.01719 | 1.948 |
| transformers-gpu-compile | prefill | single_short | 1808 | 32.36 | 0.1537 | 0.1546 | 0.0009946 | 0.1556 |

### Multi-Tier Pricing Comparison (per 1M Tokens)

| Backend | Mode | Scenario | on_demand_usd | spot_usd | reserved_usd | reserved_1yr_usd | reserved_3yr_usd | on_prem_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | generate | batch_medium | 3.867 | 1.204 | 2.725 | 2.725 | 1.965 | 0.06213 |
| onnxruntime-cpu | prefill | batch_medium | 0.144 | 0.04557 | 0.1018 | 0.1018 | 0.07367 | 0.003347 |
| onnxruntime-cpu | generate | batch_short | 2.926 | 0.9129 | 2.062 | 2.062 | 1.488 | 0.04935 |
| onnxruntime-cpu | prefill | batch_short | 0.1896 | 0.05956 | 0.1338 | 0.1338 | 0.09668 | 0.003772 |
| onnxruntime-cpu | generate | single_long | 7.575 | 2.368 | 5.341 | 5.341 | 3.854 | 0.1339 |
| onnxruntime-cpu | prefill | single_long | 0.253 | 0.07919 | 0.1784 | 0.1784 | 0.1288 | 0.004646 |
| onnxruntime-cpu | generate | single_medium | 6.678 | 2.083 | 4.707 | 4.707 | 3.395 | 0.1112 |
| onnxruntime-cpu | prefill | single_medium | 0.317 | 0.09967 | 0.2238 | 0.2238 | 0.1617 | 0.006457 |
| onnxruntime-cpu | generate | single_short | 5.806 | 1.816 | 4.094 | 4.094 | 2.955 | 0.104 |
| onnxruntime-cpu | prefill | single_short | 0.4703 | 0.1467 | 0.3315 | 0.3315 | 0.2391 | 0.007846 |
| onnxruntime-gpu | generate | batch_medium | 0.5533 | 0.1689 | 0.3884 | 0.3884 | 0.2786 | 0.003964 |
| onnxruntime-gpu | prefill | batch_medium | 0.09832 | 0.02972 | 0.06889 | 0.06889 | 0.0493 | 0.0002847 |
| onnxruntime-gpu | generate | batch_short | 0.523 | 0.1592 | 0.367 | 0.367 | 0.2631 | 0.003148 |
| onnxruntime-gpu | prefill | batch_short | 0.1445 | 0.04369 | 0.1012 | 0.1012 | 0.07247 | 0.0004563 |
| onnxruntime-gpu | generate | single_long | 1.647 | 0.5009 | 1.156 | 1.156 | 0.8282 | 0.009003 |
| onnxruntime-gpu | prefill | single_long | 0.1223 | 0.03701 | 0.08574 | 0.08574 | 0.06138 | 0.0004074 |
| onnxruntime-gpu | generate | single_medium | 1.628 | 0.4959 | 1.142 | 1.142 | 0.8191 | 0.01027 |
| onnxruntime-gpu | prefill | single_medium | 0.1212 | 0.03679 | 0.08502 | 0.08502 | 0.0609 | 0.0005596 |
| onnxruntime-gpu | generate | single_short | 1.669 | 0.5074 | 1.171 | 1.171 | 0.839 | 0.009136 |
| onnxruntime-gpu | prefill | single_short | 0.1529 | 0.04618 | 0.1071 | 0.1071 | 0.07666 | 0.0003788 |
| transformers-cpu | generate | batch_medium | 9.03 | 2.811 | 6.362 | 6.362 | 4.587 | 0.144 |
| transformers-cpu | prefill | batch_medium | 0.4174 | 0.1294 | 0.2939 | 0.2939 | 0.2117 | 0.005884 |
| transformers-cpu | generate | batch_short | 8.054 | 2.503 | 5.673 | 5.673 | 4.088 | 0.1213 |
| transformers-cpu | prefill | batch_short | 0.5836 | 0.1807 | 0.4108 | 0.4108 | 0.2958 | 0.007911 |
| transformers-cpu | generate | single_long | 25.16 | 7.805 | 17.72 | 17.72 | 12.76 | 0.3603 |
| transformers-cpu | prefill | single_long | 0.8337 | 0.2572 | 0.5864 | 0.5864 | 0.4218 | 0.009842 |
| transformers-cpu | generate | single_medium | 24.96 | 7.731 | 17.57 | 17.57 | 12.65 | 0.3388 |
| transformers-cpu | prefill | single_medium | 1.277 | 0.3937 | 0.898 | 0.898 | 0.6459 | 0.01491 |
| transformers-cpu | generate | single_short | 25.15 | 7.805 | 17.71 | 17.71 | 12.76 | 0.3631 |
| transformers-cpu | prefill | single_short | 1.743 | 0.5379 | 1.226 | 1.226 | 0.8821 | 0.02076 |
| transformers-gpu | generate | batch_medium | 1.549 | 0.4707 | 1.086 | 1.086 | 0.7785 | 0.008325 |
| transformers-gpu | prefill | batch_medium | 0.09046 | 0.02741 | 0.06341 | 0.06341 | 0.04541 | 0.0003617 |
| transformers-gpu | generate | batch_short | 1.584 | 0.4804 | 1.11 | 1.11 | 0.7954 | 0.007088 |
| transformers-gpu | prefill | batch_short | 0.05846 | 0.0177 | 0.04097 | 0.04097 | 0.02934 | 0.0002137 |
| transformers-gpu | generate | single_long | 5.363 | 1.625 | 3.759 | 3.759 | 2.692 | 0.02168 |
| transformers-gpu | prefill | single_long | 0.2437 | 0.07364 | 0.1707 | 0.1707 | 0.1222 | 0.0006839 |
| transformers-gpu | generate | single_medium | 4.963 | 1.503 | 3.479 | 3.479 | 2.491 | 0.01912 |
| transformers-gpu | prefill | single_medium | 0.3457 | 0.1045 | 0.2422 | 0.2422 | 0.1733 | 0.000963 |
| transformers-gpu | generate | single_short | 4.67 | 1.42 | 3.276 | 3.276 | 2.348 | 0.026 |
| transformers-gpu | prefill | single_short | 0.5642 | 0.1706 | 0.3954 | 0.3954 | 0.283 | 0.001676 |
| transformers-gpu-compile | generate | batch_medium | 2.112 | 0.6424 | 1.481 | 1.481 | 1.062 | 0.0121 |
| transformers-gpu-compile | prefill | batch_medium | 0.09236 | 0.02798 | 0.06474 | 0.06474 | 0.04636 | 0.0003657 |
| transformers-gpu-compile | generate | batch_short | 1.432 | 0.4367 | 1.005 | 1.005 | 0.7209 | 0.0095 |
| transformers-gpu-compile | prefill | batch_short | 0.1148 | 0.03473 | 0.08048 | 0.08048 | 0.0576 | 0.0003586 |
| transformers-gpu-compile | generate | single_long | 5.404 | 1.64 | 3.79 | 3.79 | 2.715 | 0.0255 |
| transformers-gpu-compile | prefill | single_long | 0.2745 | 0.08308 | 0.1924 | 0.1924 | 0.1377 | 0.0009651 |
| transformers-gpu-compile | generate | single_medium | 4.871 | 1.477 | 3.415 | 3.415 | 2.446 | 0.02152 |
| transformers-gpu-compile | prefill | single_medium | 0.3602 | 0.1089 | 0.2524 | 0.2524 | 0.1807 | 0.00115 |
| transformers-gpu-compile | generate | single_short | 1.948 | 0.5968 | 1.368 | 1.368 | 0.9826 | 0.01719 |
| transformers-gpu-compile | prefill | single_short | 0.1556 | 0.0474 | 0.1092 | 0.1092 | 0.07828 | 0.0009946 |

### Cloud Provider Cost Comparison (Mean Across Scenarios)

| Provider | Backend | Mode | on_demand_usd | spot_usd | reserved_usd |
| --- | --- | --- | --- | --- | --- |
| aws_g5_xlarge | onnxruntime-cpu | generate | 5.37 | 1.677 | 3.786 |
| aws_g5_xlarge | onnxruntime-cpu | prefill | 0.2748 | 0.08613 | 0.1938 |
| aws_g5_xlarge | onnxruntime-gpu | generate | 1.204 | 0.3665 | 0.8448 |
| aws_g5_xlarge | onnxruntime-gpu | prefill | 0.1279 | 0.03868 | 0.08961 |
| aws_g5_xlarge | transformers-cpu | generate | 18.47 | 5.731 | 13.01 |
| aws_g5_xlarge | transformers-cpu | prefill | 0.971 | 0.2998 | 0.6831 |
| aws_g5_xlarge | transformers-gpu | generate | 3.626 | 1.1 | 2.542 |
| aws_g5_xlarge | transformers-gpu | prefill | 0.2605 | 0.07875 | 0.1825 |
| aws_g5_xlarge | transformers-gpu-compile | generate | 3.154 | 0.9587 | 2.212 |
| aws_g5_xlarge | transformers-gpu-compile | prefill | 0.1995 | 0.06042 | 0.1398 |
| azure_nc_t4_v3 | onnxruntime-cpu | generate | 4.814 | 1.509 | 3.24 |
| azure_nc_t4_v3 | onnxruntime-cpu | prefill | 0.2464 | 0.07756 | 0.166 |
| azure_nc_t4_v3 | onnxruntime-gpu | generate | 1.078 | 0.3284 | 0.721 |
| azure_nc_t4_v3 | onnxruntime-gpu | prefill | 0.1144 | 0.03462 | 0.07643 |
| azure_nc_t4_v3 | transformers-cpu | generate | 16.55 | 5.152 | 11.12 |
| azure_nc_t4_v3 | transformers-cpu | prefill | 0.8699 | 0.2693 | 0.5839 |
| azure_nc_t4_v3 | transformers-gpu | generate | 3.245 | 0.9851 | 2.169 |
| azure_nc_t4_v3 | transformers-gpu | prefill | 0.2331 | 0.07049 | 0.1557 |
| azure_nc_t4_v3 | transformers-gpu-compile | generate | 2.823 | 0.8589 | 1.888 |
| azure_nc_t4_v3 | transformers-gpu-compile | prefill | 0.1785 | 0.0541 | 0.1193 |
| gcp_a2_highgpu | onnxruntime-cpu | generate | 6.388 | 1.981 | 4.29 |
| gcp_a2_highgpu | onnxruntime-cpu | prefill | 0.3267 | 0.1017 | 0.2196 |
| gcp_a2_highgpu | onnxruntime-gpu | generate | 1.435 | 0.4355 | 0.959 |
| gcp_a2_highgpu | onnxruntime-gpu | prefill | 0.1524 | 0.04602 | 0.1018 |
| gcp_a2_highgpu | transformers-cpu | generate | 21.98 | 6.781 | 14.74 |
| gcp_a2_highgpu | transformers-cpu | prefill | 1.156 | 0.3551 | 0.7746 |
| gcp_a2_highgpu | transformers-gpu | generate | 4.322 | 1.308 | 2.887 |
| gcp_a2_highgpu | transformers-gpu | prefill | 0.3106 | 0.09373 | 0.2073 |
| gcp_a2_highgpu | transformers-gpu-compile | generate | 3.758 | 1.14 | 2.511 |
| gcp_a2_highgpu | transformers-gpu-compile | prefill | 0.2378 | 0.07188 | 0.1588 |

### Carbon Footprint per 1M Tokens

| Backend | Mode | Scenario | energy_kwh_per_1M_tok | carbon_gco2e_per_1M_tok |
| --- | --- | --- | --- | --- |
| onnxruntime-cpu | generate | batch_medium | 0.3107 | 155.3 |
| onnxruntime-cpu | prefill | batch_medium | 0.01674 | 8.368 |
| onnxruntime-cpu | generate | batch_short | 0.2468 | 123.4 |
| onnxruntime-cpu | prefill | batch_short | 0.01886 | 9.43 |
| onnxruntime-cpu | generate | single_long | 0.6694 | 334.7 |
| onnxruntime-cpu | prefill | single_long | 0.02323 | 11.61 |
| onnxruntime-cpu | generate | single_medium | 0.5561 | 278.1 |
| onnxruntime-cpu | prefill | single_medium | 0.03228 | 16.14 |
| onnxruntime-cpu | generate | single_short | 0.5201 | 260 |
| onnxruntime-cpu | prefill | single_short | 0.03923 | 19.61 |
| onnxruntime-gpu | generate | batch_medium | 0.01982 | 9.911 |
| onnxruntime-gpu | prefill | batch_medium | 0.001423 | 0.7117 |
| onnxruntime-gpu | generate | batch_short | 0.01574 | 7.869 |
| onnxruntime-gpu | prefill | batch_short | 0.002281 | 1.141 |
| onnxruntime-gpu | generate | single_long | 0.04502 | 22.51 |
| onnxruntime-gpu | prefill | single_long | 0.002037 | 1.019 |
| onnxruntime-gpu | generate | single_medium | 0.05137 | 25.69 |
| onnxruntime-gpu | prefill | single_medium | 0.002798 | 1.399 |
| onnxruntime-gpu | generate | single_short | 0.04568 | 22.84 |
| onnxruntime-gpu | prefill | single_short | 0.001894 | 0.9469 |
| transformers-cpu | generate | batch_medium | 0.7198 | 359.9 |
| transformers-cpu | prefill | batch_medium | 0.02942 | 14.71 |
| transformers-cpu | generate | batch_short | 0.6066 | 303.3 |
| transformers-cpu | prefill | batch_short | 0.03956 | 19.78 |
| transformers-cpu | generate | single_long | 1.802 | 900.8 |
| transformers-cpu | prefill | single_long | 0.04921 | 24.6 |
| transformers-cpu | generate | single_medium | 1.694 | 847.1 |
| transformers-cpu | prefill | single_medium | 0.07456 | 37.28 |
| transformers-cpu | generate | single_short | 1.815 | 907.7 |
| transformers-cpu | prefill | single_short | 0.1038 | 51.91 |
| transformers-gpu | generate | batch_medium | 0.04163 | 20.81 |
| transformers-gpu | prefill | batch_medium | 0.001808 | 0.9042 |
| transformers-gpu | generate | batch_short | 0.03544 | 17.72 |
| transformers-gpu | prefill | batch_short | 0.001069 | 0.5343 |
| transformers-gpu | generate | single_long | 0.1084 | 54.21 |
| transformers-gpu | prefill | single_long | 0.003419 | 1.71 |
| transformers-gpu | generate | single_medium | 0.09561 | 47.81 |
| transformers-gpu | prefill | single_medium | 0.004815 | 2.408 |
| transformers-gpu | generate | single_short | 0.13 | 65 |
| transformers-gpu | prefill | single_short | 0.008378 | 4.189 |
| transformers-gpu-compile | generate | batch_medium | 0.06052 | 30.26 |
| transformers-gpu-compile | prefill | batch_medium | 0.001828 | 0.9142 |
| transformers-gpu-compile | generate | batch_short | 0.0475 | 23.75 |
| transformers-gpu-compile | prefill | batch_short | 0.001793 | 0.8964 |
| transformers-gpu-compile | generate | single_long | 0.1275 | 63.76 |
| transformers-gpu-compile | prefill | single_long | 0.004826 | 2.413 |
| transformers-gpu-compile | generate | single_medium | 0.1076 | 53.8 |
| transformers-gpu-compile | prefill | single_medium | 0.005749 | 2.875 |
| transformers-gpu-compile | generate | single_short | 0.08596 | 42.98 |
| transformers-gpu-compile | prefill | single_short | 0.004973 | 2.486 |

### Prefill Deep Dive

Prefill is the prompt-processing phase. Under time-based pricing, the dominant driver of $/token is throughput (tokens/sec).

- Best prefill backend by cost: **onnxruntime-gpu** at **0.1279 USD/1M**.
- onnxruntime-gpu throughput: ~**2246 tok/s**; mean power: ~**16.6 W**; energy share: ~**0.33%**.
- Next-best: **transformers-gpu-compile** at **0.1995 USD/1M** (56.0% higher).

### Generate Deep Dive (Uncached)

Generate mode here is an uncached greedy decoding loop. Every step re-runs a full forward pass, so throughput collapses and cost per generated token rises.

- Best generate backend by cost: **onnxruntime-gpu** at **1.204 USD/1M**.
- onnxruntime-gpu throughput: ~**312 tok/s**; mean power: ~**30.8 W**.

### Figures

![mean_latency_tr119](../../scripts/tr119/results/tr119_matrix/plots/mean_latency_tr119.png)

![throughput_tr119](../../scripts/tr119/results/tr119_matrix/plots/throughput_tr119.png)

![total_cost_per_1m_tokens_tr119](../../scripts/tr119/results/tr119_matrix/plots/total_cost_per_1m_tokens_tr119.png)

![cost_tiers_tr119](../../scripts/tr119/results/tr119_matrix/plots/cost_tiers_tr119.png)

![energy_efficiency_tr119](../../scripts/tr119/results/tr119_matrix/plots/energy_efficiency_tr119.png)

![carbon_footprint_tr119](../../scripts/tr119/results/tr119_matrix/plots/carbon_footprint_tr119.png)

![cost_vs_throughput_tr119](../../scripts/tr119/results/tr119_matrix/plots/cost_vs_throughput_tr119.png)

![mean_latency_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/mean_latency_tr119_generate.png)

![throughput_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/throughput_tr119_generate.png)

![total_cost_per_1m_tokens_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/total_cost_per_1m_tokens_tr119_generate.png)

![cost_tiers_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/cost_tiers_tr119_generate.png)

![energy_efficiency_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/energy_efficiency_tr119_generate.png)

![carbon_footprint_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/carbon_footprint_tr119_generate.png)

![cost_vs_throughput_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/cost_vs_throughput_tr119_generate.png)

### Validation & Sanity Checks

- Validation status: **PASS**

### Cost & Energy Analysis

### Cost Breakdown (Infra vs Energy)

| Backend | infra_usd_per_1M | energy_usd_per_1M | total_usd_per_1M | infra_pct | energy_pct |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-gpu | 0.6622 | 0.003761 | 0.666 | 99.44 | 0.5647 |
| transformers-gpu-compile | 1.668 | 0.008965 | 1.677 | 99.47 | 0.5348 |
| transformers-gpu | 1.934 | 0.008612 | 1.943 | 99.56 | 0.4432 |
| onnxruntime-cpu | 2.774 | 0.04867 | 2.823 | 98.28 | 1.724 |
| transformers-cpu | 9.583 | 0.1387 | 9.722 | 98.57 | 1.426 |

### Energy Efficiency Ranking

Backends ranked by tokens per kWh (higher is better):

- **onnxruntime-gpu**: 269476245 tokens/kWh
- **transformers-gpu**: 218787639 tokens/kWh
- **transformers-gpu-compile**: 175331811 tokens/kWh
- **onnxruntime-cpu**: 22477886 tokens/kWh
- **transformers-cpu**: 10736929 tokens/kWh

### Carbon Footprint Comparison

- Lowest carbon: **onnxruntime-gpu** (9.4 gCO2e/1M tokens)
- Highest carbon: **transformers-cpu** (346.7 gCO2e/1M tokens)
- Range: 337.3 gCO2e/1M tokens

### ROI by Pricing Tier

Savings from switching to spot or reserved pricing:

- **transformers-gpu**: Spot saves 69.7%, Reserved saves 29.9%
- **transformers-gpu-compile**: Spot saves 69.6%, Reserved saves 29.9%
- **onnxruntime-gpu**: Spot saves 69.6%, Reserved saves 29.9%
- **transformers-cpu**: Spot saves 69.0%, Reserved saves 29.6%
- **onnxruntime-cpu**: Spot saves 68.8%, Reserved saves 29.5%

### Request-Level Cost (Prompt+Generate Mix)

Assumptions: prompt_tokens=256.0, generate_tokens=128.0.

| Backend | time_prefill_s | time_generate_s | energy_kwh_per_request | total_cost_usd_per_request |
| --- | --- | --- | --- | --- |
| onnxruntime-gpu | 0.114 | 0.4108 | 4.042e-06 | 0.0001475 |
| transformers-gpu-compile | 0.1409 | 1.096 | 1.015e-05 | 0.0003477 |
| transformers-gpu | 0.1236 | 1.213 | 8.502e-06 | 0.0003752 |
| onnxruntime-cpu | 0.2091 | 2.135 | 5.759e-05 | 0.0006667 |
| transformers-cpu | 0.6782 | 6.364 | 0.0001445 | 0.001997 |

### TCO Summary

Assumptions: 1000000000.0 tokens/month, 12 months, upfront $0.0.

| Backend | total_cost_usd | cost_per_month_usd | cost_per_1m_tokens_usd |
| --- | --- | --- | --- |
| onnxruntime-gpu | 7992 | 666 | 0.666 |
| transformers-gpu-compile | 2.012e+04 | 1677 | 1.677 |
| transformers-gpu | 2.332e+04 | 1943 | 1.943 |
| onnxruntime-cpu | 3.387e+04 | 2823 | 2.823 |
| transformers-cpu | 1.167e+05 | 9722 | 9.722 |

## 5. Statistical Analysis

We test whether observed cost differences are statistically significant across backends. Tests are run per mode when available.

### Generate Mode

#### Hypothesis Testing

- **ANOVA**: Significant differences detected across backends (F=12.85, p=0.0000)

#### Significant Pairwise Comparisons (p < 0.05)

- **onnxruntime-cpu vs onnxruntime-gpu**: $-4.1663 difference (-77.6%), p=0.0018, Cohen's d=-2.903
- **onnxruntime-cpu vs transformers-cpu**: $13.1022 difference (244.0%), p=0.0134, Cohen's d=1.997
- **onnxruntime-gpu vs transformers-cpu**: $17.2685 difference (1434.1%), p=0.0028, Cohen's d=2.686
- **onnxruntime-gpu vs transformers-gpu**: $2.4215 difference (201.1%), p=0.0263, Cohen's d=1.720
- **transformers-cpu vs transformers-gpu**: $-14.8470 difference (-80.4%), p=0.0072, Cohen's d=-2.265
- **transformers-cpu vs transformers-gpu-compile**: $-15.3191 difference (-82.9%), p=0.0060, Cohen's d=-2.340

### Prefill Mode

#### Hypothesis Testing

- **ANOVA**: Significant differences detected across backends (F=8.08, p=0.0005)

#### Significant Pairwise Comparisons (p < 0.05)

- **onnxruntime-cpu vs onnxruntime-gpu**: $-0.1469 difference (-53.5%), p=0.0345, Cohen's d=-1.609
- **onnxruntime-cpu vs transformers-cpu**: $0.6962 difference (253.4%), p=0.0230, Cohen's d=1.775
- **onnxruntime-gpu vs transformers-cpu**: $0.8431 difference (659.4%), p=0.0082, Cohen's d=2.207
- **transformers-cpu vs transformers-gpu**: $-0.7105 difference (-73.2%), p=0.0251, Cohen's d=-1.739
- **transformers-cpu vs transformers-gpu-compile**: $-0.7715 difference (-79.5%), p=0.0141, Cohen's d=-1.978

## 6. Synthesis & Decision Matrix

### 6.1 What matters most

- **Throughput dominates $/token** under the configured pricing inputs; small power differences rarely change rankings.
- **Pricing tier is a second lever**: spot/reserved can shift total cost by ~2-3x for the same backend.
- **Uncached generate is an upper bound**: production KV-cache decoding should reduce generate cost per token materially.

### 6.2 Deployment Recommendations (This Hardware)

- **Default GPU backend:** `onnxruntime-gpu` (best cost and best energy efficiency in this benchmark).
- **CPU-only fallback:** `onnxruntime-cpu` (better cost/energy than `transformers-cpu`).
- **Transformers backends:** keep when you need maximum feature parity; expect higher $/token.

### 6.3 Decision Matrix (On-Demand, Mean Across Scenarios)

| Backend | prefill_usd_per_1M | generate_usd_per_1M | generate/prefill |
| --- | --- | --- | --- |
| onnxruntime-cpu | 0.2748 | 5.37 | 19.55 |
| onnxruntime-gpu | 0.1279 | 1.204 | 9.417 |
| transformers-cpu | 0.971 | 18.47 | 19.02 |
| transformers-gpu | 0.2605 | 3.626 | 13.92 |
| transformers-gpu-compile | 0.1995 | 3.154 | 15.81 |

### 6.4 Operational Considerations

- `onnxruntime-gpu`: best efficiency here, but requires ONNX export + runtime integration (engineering overhead is moderate but stable).
- `transformers-gpu`: simplest integration path, but higher $/token in this benchmark.
- `transformers-gpu-compile`: can improve throughput for some models, but compilation overhead and variability can complicate deployment.
- CPU backends are viable for compatibility/fallback, not for cost-optimal throughput at scale.

### 6.5 Limitations & Next Steps

- Single hardware system; replicate on your production GPU/CPU to lock absolute costs.
- Generate results are **uncached** and intentionally pessimistic; repeat with KV-cache for production planning.
- Tokenization, batching overheads, and end-to-end serving stack are not included; integrate into TR123 for full-stack TCO.

---

## 7. Reproducibility

### 7.1 Run the pipeline

```bash
python scripts/tr119/run_experiment.py --config C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr119\configs\matrix.yaml --device cuda
```

### 7.2 Key artifacts

- Results root: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr119\results\tr119_matrix`
- Processed: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr119\results\tr119_matrix\processed`
- Report: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\reports\generated\Technical_Report_119.md`
- Manifest: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr119\results\tr119_matrix\processed\experiment_manifest_1766283570.json`
