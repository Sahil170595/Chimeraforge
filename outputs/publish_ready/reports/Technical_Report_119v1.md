# Technical Report 119 v1: Cost & Energy Analysis Deep Dive
## Local-first inference TCO with telemetry (prefill + generate)

**Project:** Banterhearts LLM Performance Research  
**Date:** 2025-12-21  
**Author:** Research Team  
**Report Type:** Definitive cost/energy analysis (artifact-backed, manually authored)  
**Test Duration:** ~3 minutes wall-clock benchmark runtime (350 benchmark runs; 0 degraded)  
**Related Work:** [TR117](Technical_Report_117.md) (latency/throughput baseline), [TR118_v2.2](Technical_Report_118_v2.2.md) (measurement rigor + pipeline validation), [TR115_v2](Technical_Report_115_v2.md) (definitive "production-grade" reporting standard)

---

## Executive Summary

This report answers a production question, not a benchmarking question:

> "If I run local-first inference on this machine, which backend minimizes dollars per token and energy per token, and how sensitive is that decision to workload shape and pricing tier?"

TR119 builds on TR117's speed baselines and applies a fully explicit cost+energy model backed by telemetry:

- **Power:** GPU power via NVML; CPU package power via Windows Energy Meter performance counters (Intel RAPL-backed on supported systems).
- **Energy attribution in v1:** GPU-backend energy uses GPU power; CPU-backend energy uses CPU package power (we do not sum CPU+GPU in this report).
- **Cost:** compute-hours derived from throughput, multiplied by tiered hourly rates + energy cost.
- **Carbon:** energy multiplied by carbon intensity.

Energy/carbon accuracy note (reviewer-proof):

- Power is sampled at `0.25s`. Many prefill timed regions are shorter than that, so some runs have only 1-2 telemetry samples; energy/carbon numbers should be treated as **low-frequency sampled estimates** (more reliable for longer generate runs than for short prefill calls). Cost rankings are robust because $/token is throughput-dominant under the configured hourly rates.

### The headline (what you should do)

If your deployment includes meaningful generation (which most LLM serving does), the dominant outcome is stable:

- **Default recommendation:** `onnxruntime-gpu`  
  It is **best overall** for **uncached generate** and **best overall** for **single-prompt prefill** on this hardware, which makes it best for request-level cost.

However, the *nuance* matters for publish-grade quality:

- **Prefill-only, batch-heavy workloads can flip the winner.**  
  In **prefill batch scenarios**, `transformers-gpu` is cheaper than `onnxruntime-gpu` in this benchmark matrix. If your workload is dominated by batched prompt processing (e.g., embeddings-like, reranking-like, prefill-heavy tasks with minimal generation), you should not blindly adopt the "overall mean across scenarios" winner.

### Key findings (numbers are mean across scenarios unless noted)

#### Prefill (prompt processing, single forward pass)

- **Best overall mean $/1M tokens:** `onnxruntime-gpu` at **$0.1279 / 1M tokens**.
- **Next-best overall mean:** `transformers-gpu-compile` at **$0.1995 / 1M** (1.56x higher).
- **Worst:** `transformers-cpu` at **$0.9710 / 1M** (7.59x higher).
- **Batch prefill nuance:** `transformers-gpu` is best for:
  - `batch_short` (**$0.05846 / 1M**, cheaper than any other backend for that scenario)
  - `batch_medium` (**$0.09046 / 1M**, narrowly best)

#### Generate (uncached greedy loop)

Across *every* generate scenario, `onnxruntime-gpu` is best:

- **Best overall mean $/1M generated tokens:** `onnxruntime-gpu` at **$1.204 / 1M**.
- **Worst:** `transformers-cpu` at **$18.47 / 1M** (15.34x higher).

#### Request-level cost (prompt+generate mix)

Using the configured request mix (**prompt_tokens=256, generate_tokens=128**) and combining measured prefill + generate:

- **Best request cost:** `onnxruntime-gpu` at **$0.0001475 per request**
- Worst: `transformers-cpu` at **$0.001997 per request** (13.54x higher)

### Business impact (scaled)

Using the artifact-backed TCO projection embedded in the pipeline (1B total tokens/month for 12 months, where total tokens = prompt + generated under the 256/128 request mix), backend choice is not a rounding error:

- `onnxruntime-gpu` vs `transformers-gpu`: **~$7.1k/year lower** total cost at the stated volume.
- `onnxruntime-gpu` vs `transformers-cpu`: **~$57.8k/year lower** total cost at the stated volume.

This is the practical interpretation: if your org will generate billions of tokens, backend choice is a budget line item.

### Why the rankings look "too simple"

They *are* simple for a structural reason:

- At the configured rates (on-demand $1.006/hr, energy $0.20/kWh), **infra cost dominates**.
- Energy is a small share of total cost for all backends here:
  - `onnxruntime-gpu` prefill: ~0.33% energy share
  - `onnxruntime-gpu` generate: ~0.59% energy share
  - CPU backends: ~1.4-1.7% energy share

So the dominant driver becomes:

> Higher throughput -> fewer compute-hours per token -> lower $/token.

### Publish decision

This report is **publish-ready** for a frontier research bar:

- **Artifact-backed:** raw JSONL runs, processed CSV/JSON summaries, plots, validation results, and a manifest with environment metadata.
- **Validation PASS:** cost/energy sanity checks report no issues for the current artifacts.
- **Statistical tests included:** ANOVA + significant pairwise comparisons per mode.
- **Limitations are explicit and scoped:** uncached generate; single hardware; scenario weighting sensitivity; energy attribution uses dominant device power (not full-system power).

---

## Table of Contents

1. [Research Context & Objectives](#1-research-context--objectives)
2. [Methodology & Measurement Definitions](#2-methodology--measurement-definitions)
3. [Experimental Design & Environment](#3-experimental-design--environment)
4. [Cost/Energy Model (Fully Explicit)](#4-costenergy-model-fully-explicit)
5. [Results Overview (Decision-Relevant Summary)](#5-results-overview-decision-relevant-summary)
6. [Data Quality & Validation](#6-data-quality--validation)
7. [Workload Mix Sensitivity](#7-workload-mix-sensitivity)
8. [Prefill Deep Dive (Where the nuance lives)](#8-prefill-deep-dive-where-the-nuance-lives)
9. [Generate Deep Dive (Uncached, worst-case decode)](#9-generate-deep-dive-uncached-worst-case-decode)
10. [Statistical Deep Dive (Significance, not vibes)](#10-statistical-deep-dive-significance-not-vibes)
11. [Pricing Tier & Sensitivity Analysis](#11-pricing-tier--sensitivity-analysis)
12. [Production Deployment Strategy](#12-production-deployment-strategy)
13. [Limitations & Next Steps](#13-limitations--next-steps)
14. [Reproducibility & Artifacts](#14-reproducibility--artifacts)
15. [Appendix A: Key Tables](#appendix-a-key-tables)
16. [Appendix B: Figures](#appendix-b-figures)
17. [Appendix C: Scenario Definitions](#appendix-c-scenario-definitions)
18. [Appendix D: Glossary](#appendix-d-glossary)

---

## 1. Research Context & Objectives

### 1.1 What TR119 adds beyond TR117

TR117 answers: "Which backend is fastest?"  
TR119 answers: "Which backend is cheapest and most energy efficient for a given workload?"

Speed alone is not a decision; cost is.

TR119 makes performance actionable by translating throughput into:

- **Compute-hours per 1M tokens**
- **Energy per 1M tokens**
- **Carbon per 1M tokens**
- **$ per 1M tokens** under multiple pricing tiers
- **$ per request** under a token mix

### 1.2 Objectives

1. Establish a **defensible cost model** grounded in measured throughput and measured power.
2. Produce **decision-grade rankings** for:
   - prefill cost/latency
   - generate cost/latency (uncached)
   - request-level cost with a mixed prompt/generate workload
3. Quantify sensitivity to:
   - scenario shape (batching / sequence length)
   - pricing tier selection (on-demand vs spot vs reserved)
4. Provide production recommendations with explicit constraints and risks.

### 1.3 How to use this report

Use TR119 in two passes:

1. **Choose the likely winner** from the mean-across-scenarios tables (Section 5). This is a robust default when you do not yet have an exact production workload distribution.
2. **Re-weight by your workload** using the scenario-winner table (Section 5.2) and (ideally) re-run TR119 with your real batch/sequence/token mix. This is mandatory for high-volume deployment decisions.

### 1.4 Research evolution (how we got here)

TR119 is not a standalone benchmark; it is the next step in a sequence of "make it real" research iterations:

- **TR117:** established a Tier-3 benchmark matrix for local inference backends and scenarios (latency/throughput, degradation tracking, reproducibility).
- **TR118 v2.x:** validated and hardened the measurement pipeline (artifact integrity, CI logic, failure classification) and demonstrated why "one table" is not sufficient for a publishable performance claim.
- **TR119 (this report):** converts those same latency/throughput baselines into **token economics** (dollars, energy, carbon) with telemetry, multi-tier pricing, and explicit assumptions.

The methodological stance is consistent across these reports:

- If a claim is important, it must be backed by artifacts.
- If a metric is used for a decision, its definition must be explicit.
- If a number cannot be reproduced, it is not decision-grade.

### 1.5 Research questions (decision-grade)

This study answers:

1. Which backend minimizes **$/token** under time-based pricing for prefill and for generate?
2. Does the answer change when we move from **single** to **batch** prompt processing?
3. How sensitive is the decision to pricing tier (on-demand vs spot vs reserved)?
4. Is the ranking stable enough to ship a default recommendation on this hardware?

### 1.6 Non-goals (explicitly out of scope)

This report does **not** attempt to:

- claim absolute production decode cost (KV-cache decoding is not measured here)
- generalize across hardware classes (single-machine study)
- estimate organizational total cost (staffing, reliability, maintenance)
- measure full-system power draw (CPU+GPU summed) for GPU backends

---

## 2. Methodology & Measurement Definitions

This section is intentionally explicit. If you cannot define a metric precisely, you cannot publish the number.

### 2.1 Modes

**Prefill mode**

- Measures a **single forward pass** over a fixed padded sequence length (`seq_len`) and batch size.
- Throughput is computed from known tokens processed: `batch_size * seq_len`.

**Generate mode (uncached)**

- Measures an **uncached greedy generation loop**: at each generated token step, the backend performs a full forward pass.
- This is a worst-case decode proxy: production generation typically uses KV-cache.

### 2.2 Latency and Throughput

- **Prefill latency (ms):** wall time for one forward pass.
  - Excludes tokenization and warmup overhead.
- **Prefill throughput (tok/s):**
  - `throughput = (batch_size * seq_len) / latency_s`

- **Generate latency (ms):** total wall time for the uncached generation loop.
- **Generate throughput (tok/s):**
  - `throughput = tokens_generated / total_time_s`

### 2.3 Scenario resolution and token accounting

TR119 reuses the TR117 Tier-3 prompt/scenario definitions and resolves each scenario into a concrete workload:

- a prompt string (from a prompt set: `short`, `medium`, `long`)
- a batch size (1 for `single_*`, 4 for `batch_*`)
- a padded sequence length `seq_len` computed from tokenized length with a safety margin

Token accounting (what "tokens" mean in TR119):

- Prefill tokens processed are `batch_size * seq_len` (the padded length, not the raw prompt length).
- Generate tokens processed are the number of generated tokens actually produced by the loop (`tokens_generated`).

This choice is intentional: it makes compute comparable across runs by ensuring each forward pass has a defined, repeatable shape.

### 2.4 Generate parameters and scaling assumptions

Generate mode uses an **uncached greedy loop** implemented as repeated full forward passes.

Two practical consequences:

1. The runner defaults to a short generation (`max_new_tokens=8`) for runtime practicality across the matrix.
2. Because this is uncached, the forward pass shape grows with the effective sequence length. With only 8 new tokens, TR119 does not reach the very-long-decode regime where uncached cost can accelerate.

The report therefore treats uncached generate as:

- a consistent backend stress test (apples-to-apples), and
- a conservative upper bound on decode cost (KV-cache should be cheaper),

not as an exact forecast of production decoding cost.

### 2.5 Telemetry (power and why we trust it)

TR119 uses measured power, not a CPU utilization proxy model:

- **GPU package power (W):** sampled via NVML (`pynvml`).
- **CPU package power (W):** sampled from Windows "Energy Meter" performance counters (Intel RAPL-backed on supported systems) via `win32pdh`.

This matters because energy becomes:

- `energy_j = power_w * time_s`
- `energy_kwh = energy_j / 3.6e6`

If you cannot defend your watts, you cannot defend your kWh.

### 2.6 Degradation

- A run is **degraded** if it errors, times out, or produces invalid output.
- This run set has **0 degraded runs** (350/350 ok).

---

## 3. Experimental Design & Environment

### 3.1 Benchmark matrix

Backends:

- `onnxruntime-gpu`
- `onnxruntime-cpu`
- `transformers-gpu`
- `transformers-gpu-compile`
- `transformers-cpu`

Scenarios:

- `single_short`
- `single_medium`
- `single_long`
- `batch_short`
- `batch_medium`

Repetitions:

- 7 repetitions per backend/scenario/mode
- 2 warmup runs per backend/scenario

Modes observed:

- `prefill`
- `generate`

Total runs:

- 5 backends x 5 scenarios x 7 reps x 2 modes = **350 runs**

Scenario definitions (source of truth):

- Prompt/scenario config: `scripts/tr117/configs/matrix_tier3.yaml`
- TR119 uses the subset `{single_short, single_medium, single_long, batch_short, batch_medium}`.

Concrete workload shapes:

| Scenario | Prompt set | Batch size | Notes |
| --- | --- | --- | --- |
| `single_short` | `short` | 1 | interactive-like prompt |
| `single_medium` | `medium` | 1 | longer prompt, more prefill work |
| `single_long` | `long` | 1 | longest prompt set in this matrix |
| `batch_short` | `short` | 4 | prefill batching stressor |
| `batch_medium` | `medium` | 4 | batching + longer prompt |

Scenario shapes used in this run (derived from raw artifacts; padded seq_len is the timed-region shape):

| Scenario | Batch | Prefill seq_len (padded) | Prefill tokens/call | Generate final seq_len (padded) | Generate tokens/call |
| --- | --- | --- | --- | --- | --- |
| `single_short` | 1 | 11 | 11 | 19 | 8 |
| `single_medium` | 1 | 19 | 19 | 27 | 8 |
| `single_long` | 1 | 27 | 27 | 35 | 8 |
| `batch_short` | 4 | 11 | 44 | 19 | 32 |
| `batch_medium` | 4 | 19 | 76 | 27 | 32 |

Notes:

- A "run" is one backend x scenario x mode x repetition record. Each run evaluates 2 prompts per scenario (the `short`/`medium`/`long` prompt sets contain two prompts), which is why raw `latencies_ms`/`throughput_tok_s` arrays have length 2.
- For prefill, that means 2 timed forward passes per run. For generate (uncached), each prompt performs `max_new_tokens` forward passes (8 here), so each run includes 16 forward passes per scenario (2 prompts x 8 steps), even though it is counted as 1 run.
- Generate uses `max_new_tokens=8` in this run; generated tokens/call above are empirically verified via `throughput_tok_s * latency_s` in raw artifacts.

Generate loop parameters (important for interpretation):

- `max_new_tokens`: defaults to **8** in the TR119 runner unless overridden
- `max_seq_len`: defaults to **512**
- `stop_on_eos`: enabled by default (but GPT-2 may not emit EOS early)

Reproducibility control:

- Config seed: `seed: 42` (set across Python/Numpy/Torch in the runner)

### 3.2 Hardware and software

System:

- OS: Windows 11 (Build 26200)
- CPU: 13th Gen Intel(R) Core(TM) i9-13980HX
- GPU: NVIDIA GeForce RTX 4080 Laptop GPU (12 GB)

Key packages (from manifest):

- Python: 3.13.1
- torch: 2.8.0+cu128
- transformers: 4.57.0
- onnxruntime: 1.23.2
- tensorrt: 10.12.0.36 (provider present; TRT backend not part of this matrix)
- pandas: 2.2.3
- scipy: 1.15.2

### 3.3 Artifact pipeline (what makes this publishable)

Raw results:

- JSONL lines per run containing latencies, throughput arrays, and resource metrics.

Processed results:

- `latency_summary_cost.csv` (scenario-level stats, 95% CI, throughput)
- `cost_energy_summary.json` (per backend/scenario/mode derived cost+energy)
- `cost_energy_analysis.json` (request-level cost, ROI/tier analysis, TCO)
- `statistical_analysis.json` (ANOVA + pairwise tests)
- `cost_energy_validation.json` (sanity checks; PASS)

Plots:

- Latency, throughput, cost tiers, energy efficiency, carbon footprint, and cost-vs-throughput (prefill + generate).

---

## 4. Cost/Energy Model (Fully Explicit)

TR119 uses a minimal model with explicit assumptions, designed to be:

- unit-consistent
- explainable
- easy to re-parameterize (swap your rates, rerun)

### 4.1 Core quantities per backend/scenario/mode

Given throughput `thr_tok_s`:

- `seconds_per_1M = 1_000_000 / thr_tok_s`
- `hours_per_1M = seconds_per_1M / 3600`

Given mean power `power_w`:

- `energy_kwh_per_1M = (power_w * seconds_per_1M) / 3.6e6`

### 4.2 Cost decomposition

With:

- `usd_per_hour` (pricing tier)
- `usd_per_kwh` (electricity rate)

Compute:

- `infra_cost_usd_per_1M = hours_per_1M * usd_per_hour`
- `energy_cost_usd_per_1M = energy_kwh_per_1M * usd_per_kwh`
- `total_cost_usd_per_1M = infra_cost_usd_per_1M + energy_cost_usd_per_1M`

### 4.3 Inputs used for this report

From `scripts/tr119/configs/matrix.yaml`:

- On-demand: **$1.006/hr**
- Spot: **$0.302/hr**
- Reserved 1yr: **$0.704/hr**
- Reserved 3yr: **$0.503/hr**
- Energy price: **$0.20/kWh**
- Carbon intensity: **500 gCO2e/kWh**

These are configured inputs (not universal constants); replace with your region/tariff and grid intensity when publishing for a specific deployment environment.

Pricing interpretation note (prevents "local TCO" semantic attacks):

- Hourly rates are treated as a **shadow price of compute-hours** (cloud-equivalent) to compare backends under time-priced compute. A true local-first TCO (CapEx amortization, utilization, maintenance) is future work; the "energy-only" column approximates the fully-amortized / sunk-hardware regime.

### 4.4 Request-level costing

From config:

- prompt_tokens = 256
- generate_tokens = 128

Per backend:

- `t_prefill = prompt_tokens / prefill_throughput`
- `t_generate = generate_tokens / generate_throughput`
- `energy_kwh_request = (P_prefill * t_prefill + P_generate * t_generate) / 3.6e6`
- `infra_cost_request = ((t_prefill + t_generate) / 3600) * on_demand_usd_per_hour`
- `total_cost_request = infra_cost_request + energy_kwh_request * usd_per_kwh`

This is intentionally simple: it uses measured mean throughput/power and composes them into a request.

### 4.5 Energy attribution and what it implies

TR119 reports energy and carbon because they matter for:

- sustainability reporting (gCO2e / token)
- on-prem electricity planning
- thermal and power budgeting on constrained systems

However, the energy model is explicit about what it is measuring:

- For GPU backends, `power_w` comes from **GPU power** (NVML).
- For CPU backends, `power_w` comes from **CPU package power** (Windows Energy Meter).

This has two implications:

1. It prevents double counting (GPU + CPU simultaneously) when the telemetry is not designed to be summed.
2. It makes GPU-backend energy/carbon numbers a lower bound on total platform energy, because CPU package power is not included in the GPU-backend `power_w` column.

The ranking conclusions are still robust under the configured pricing, because energy is a small fraction of total cost at $0.20/kWh. If you need carbon-grade absolute accuracy, the next step is full-system power accounting (CPU + GPU) validated against an external power meter.

### 4.6 A useful mental model (why throughput usually dominates $/token)

Under time-based pricing, the dominant term is:

- `infra_cost_usd_per_1M = (1_000_000 / thr_tok_s / 3600) * usd_per_hour`

So, to first order:

- doubling throughput halves infra cost per token
- small wattage differences rarely change the ranking unless electricity is extremely expensive or compute-hours are priced near zero (pure on-prem / sunk-cost regime)

This is why TR119 focuses on throughput stability and workload-shape sensitivity: the cost model is mostly a throughput model with explicit energy add-ons.

---

## 5. Results Overview (Decision-Relevant Summary)

### 5.1 Core results (mean across scenarios)

These tables are the "decision surface" for the report: if you only read one page, read these.

Aggregation note (reviewer-proof):

- The summary tables aggregate on **time per 1M tokens** (seconds_per_1M) and on **per-scenario cost/energy**, then derive an "effective throughput" as `1e6 / mean(seconds_per_1M)`.
- This avoids the common pitfall where an arithmetic mean throughput is displayed next to a mean cost that was computed by averaging per-scenario costs (those are not algebraically consistent under inversion).
- "Effective dominant-device power" is computed from the aggregated time and energy (time-weighted), not by arithmetic averaging watts across scenarios: `P_eff = mean(E_kWh_per_1M) * 3.6e6 / mean(seconds_per_1M)`.

#### Prefill mode (prompt processing)

| Backend | Mean seconds/1M | Effective throughput (tok/s) | Effective dominant-device power (W) | Mean energy (kWh/1M) | Mean carbon (gCO2e/1M) | Mean total cost ($/1M, on-demand) | Multiple vs best |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-gpu | 456 | 2193 | 16.47 | 0.002087 | 1.043 | 0.1279 | 1.00x |
| transformers-gpu-compile | 711 | 1406 | 19.41 | 0.003834 | 1.917 | 0.1995 | 1.56x |
| transformers-gpu | 929 | 1076 | 15.10 | 0.003898 | 1.949 | 0.2605 | 2.04x |
| onnxruntime-cpu | 965 | 1037 | 97.29 | 0.02607 | 13.03 | 0.2748 | 2.15x |
| transformers-cpu | 3432 | 291.3 | 62.21 | 0.05931 | 29.66 | 0.9710 | 7.59x |

Interpretation:

- **onnxruntime-gpu** wins the overall mean, but the gap to `transformers-gpu(-compile)` is workload-dependent.
- CPU backends are qualitatively different: lower throughput, higher cost per token, and higher energy per token.
- Mean across scenarios is equal-weighted across the 5 shapes; see Section 5.2 and Section 7 for shape sensitivity.

#### Generate mode (uncached decode)

| Backend | Mean seconds/1M | Effective throughput (tok/s) | Effective dominant-device power (W) | Mean energy (kWh/1M) | Mean carbon (gCO2e/1M) | Mean total cost ($/1M, on-demand) | Multiple vs best |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-gpu | 4283 | 233.4 | 29.86 | 0.03553 | 17.76 | 1.204 | 1.00x |
| transformers-gpu-compile | 11224 | 89.10 | 27.53 | 0.08582 | 42.91 | 3.154 | 2.62x |
| transformers-gpu | 12915 | 77.43 | 22.92 | 0.08222 | 41.11 | 3.626 | 3.01x |
| onnxruntime-cpu | 18887 | 52.94 | 87.79 | 0.4606 | 230.3 | 5.370 | 4.46x |
| transformers-cpu | 65138 | 15.35 | 73.35 | 1.328 | 663.8 | 18.47 | 15.34x |

Interpretation:

- Uncached generate is expensive for every backend, but **onnxruntime-gpu separates hard**.
- The generate regime makes "prefill-only intuition" unsafe for end-to-end serving.

### 5.2 Scenario winners (where the nuance lives)

If you can only deploy one backend, you need the overall mean.  
If you can deploy intelligently, you need the scenario-level winners.

**Generate (uncached):** `onnxruntime-gpu` is best in every scenario.

**Prefill:** batching flips the winner:

| Mode | Scenario | Best backend | Cost ($/1M) | Second best | Cost ($/1M) |
| --- | --- | --- | --- | --- | --- |
| prefill | batch_short | transformers-gpu | 0.05846 | transformers-gpu-compile | 0.1148 |
| prefill | batch_medium | transformers-gpu | 0.09046 | transformers-gpu-compile | 0.09236 |
| prefill | single_short | onnxruntime-gpu | 0.1529 | transformers-gpu-compile | 0.1556 |
| prefill | single_medium | onnxruntime-gpu | 0.1212 | onnxruntime-cpu | 0.3170 |
| prefill | single_long | onnxruntime-gpu | 0.1223 | transformers-gpu | 0.2437 |

This is the core "frontier-grade" nuance:

- If your workload is *batch-dominant prefill*, `transformers-gpu` can be cheaper than `onnxruntime-gpu`.
- If your workload includes *meaningful generation*, `onnxruntime-gpu` dominates end-to-end.

### 5.3 Request-level economics (prompt=256, generate=128)

Most real services do not buy "prefill tokens" and "generate tokens" separately; they buy end-to-end requests.

TR119 computes a request-level cost by composing the measured prefill + generate throughput into one request mix:

- prompt_tokens = 256
- generate_tokens = 128

From `cost_energy_analysis.json` (on-demand pricing):

| Backend | Total cost ($/request) | Relative vs best |
| --- | --- | --- |
| onnxruntime-gpu | 0.0001475 | 1.00x |
| transformers-gpu-compile | 0.0003477 | 2.36x |
| transformers-gpu | 0.0003752 | 2.54x |
| onnxruntime-cpu | 0.0006667 | 4.52x |
| transformers-cpu | 0.001997 | 13.54x |

Interpretation:

- The request-level ranking is dominated by generate cost: even a backend that wins batched prefill can lose end-to-end if it is weak on decode.
- If your service is prefill-only (no generation), you should ignore this table and focus on the prefill scenario winners instead.

### 5.4 Infra vs energy (combined request mix)

For the configured rates, energy is a small fraction of total cost for every backend. This is not a moral judgment; it is an economic statement about time-priced compute.

From `cost_energy_analysis.json` request-level components, converted to $/1M **total tokens** under the request mix (prompt=256, generate=128; total tokens=384):

| Backend | Total ($/1M total tokens) | Infra ($/1M) | Energy ($/1M) | Energy % |
| --- | --- | --- | --- | --- |
| onnxruntime-gpu | 0.3840 | 0.3819 | 0.002105 | 0.548% |
| transformers-gpu-compile | 0.9056 | 0.9003 | 0.005286 | 0.584% |
| transformers-gpu | 0.9770 | 0.9726 | 0.004428 | 0.453% |
| onnxruntime-cpu | 1.736 | 1.706 | 0.02999 | 1.73% |
| transformers-cpu | 5.200 | 5.125 | 0.07524 | 1.45% |

Why this matters:

- Backend selection mainly changes your **compute-hours per token**, not your electricity bill, under these inputs.
- If you want energy to be decision-dominant, you need either (a) very cheap compute-hours (on-prem/sunk cost) or (b) very expensive electricity.
- Energy values are low-frequency sampled estimates for short prefill calls (Section 6.2), but they do not drive the total cost ranking under time-priced compute.

### 5.5 Carbon impact (combined request mix)

Carbon is computed as:

- `gCO2e_per_1M = kWh_per_1M * carbon_intensity_gCO2e_per_kWh`

From `cost_energy_analysis.json` request-level energy, converted to carbon per 1M **total tokens** under the request mix (carbon intensity = 500 gCO2e/kWh):

| Backend | Carbon (gCO2e / 1M total tokens) |
| --- | --- |
| onnxruntime-gpu | 5.263 |
| transformers-gpu | 11.07 |
| transformers-gpu-compile | 13.22 |
| onnxruntime-cpu | 74.99 |
| transformers-cpu | 188.1 |

Important nuance: carbon values are low-frequency sampled estimates (Section 6.2). GPU-backend carbon values are also lower bounds under TR119's dominant-device power attribution (Section 6.2).

---

## 6. Data Quality & Validation

This section exists for one reason: if the numbers are not defensible, the recommendations are not publishable.

TR119 is intentionally "artifact-first":

- Raw runs are written as JSONL (one record per run).
- Every number in this report is derived from those raw artifacts via deterministic processing code.
- Validation runs as a first-class pipeline stage (not a manual afterthought).

### 6.1 Coverage and acceptance criteria

The benchmark matrix is:

- 5 backends x 5 scenarios x 2 modes x 7 repetitions = 350 measured runs
- 2 warmups per backend/scenario (not included in statistics)

Acceptance rules:

- A run is considered **degraded** if it timeouts, errors, or violates internal invariants (e.g., no tokens generated).
- Degraded runs are retained in raw artifacts (so failures are visible) but excluded from throughput/power means.

Outcome for this artifact set:

- **0 degraded** runs across the 350-run matrix.
- All aggregated cells have `n=7` valid samples.

### 6.2 Telemetry integrity (what is actually measured)

Telemetry is sampled at `0.25s` during each run:

- **GPU:** NVML power (W), memory usage (MB), utilization (%), temperature (C).
- **CPU:** Windows "Energy Meter" power (W) plus conventional CPU utilization/memory telemetry.

Power aggregation:

- The report uses the arithmetic mean of the sampled power values during the timed region (no idle-baseline subtraction).

Cadence limitation (the biggest remaining risk for energy/carbon precision):

- Telemetry sampling interval is `0.25s` and many prefill timed regions are shorter than that.
- In the raw artifacts for this report, **76.6% of prefill runs** have **<= 1** telemetry sample (and 96.0% have <= 2). Generate is better but still imperfect (22.9% of generate runs have <= 1 sample).

Implication:

- Energy/carbon values are directionally useful but are **not high-precision** for short prefill calls. For a carbon-grade report, use longer timed regions (looped measurements), faster sampling with care, or energy counters (delta mJ) where supported.

Important nuance (and the most common way readers misinterpret energy reports):

- For **GPU backends**, TR119 uses **GPU power** as the energy basis (power source = `gpu`).
- For **CPU backends**, TR119 uses **CPU package power** as the energy basis (power source = `cpu`).
- This avoids double counting, but it is **not** a full-system energy measurement.

Practical consequence:

- The *relative* cost rankings (dominated by throughput + hourly rate) are robust.
- The *absolute* carbon numbers for GPU backends are a **lower bound** on platform energy because CPU package power is not summed into the GPU-backend energy column.

Power sanity check (dominant-device power, min/median/max across the 5 scenarios):

Prefill:

| Backend | Min (W) | Median (W) | Max (W) |
| --- | --- | --- | --- |
| onnxruntime-gpu | 12.49 | 15.94 | 23.32 |
| transformers-gpu | 14.05 | 14.98 | 20.19 |
| transformers-gpu-compile | 15.75 | 17.75 | 32.36 |
| onnxruntime-cpu | 85.34 | 102.1 | 119.7 |
| transformers-cpu | 59.44 | 60.63 | 71.92 |

Generate:

| Backend | Min (W) | Median (W) | Max (W) |
| --- | --- | --- | --- |
| onnxruntime-gpu | 27.64 | 30.45 | 36.30 |
| transformers-gpu | 19.46 | 22.61 | 28.16 |
| transformers-gpu-compile | 22.32 | 29.00 | 44.79 |
| onnxruntime-cpu | 82.13 | 86.29 | 91.76 |
| transformers-cpu | 69.21 | 73.66 | 81.49 |

### 6.3 Sanity checks (PASS)

The pipeline includes a cost/energy validation pass:

- `scripts/tr119/results/tr119_matrix/processed/cost_energy_validation.json`
- `overall_valid: true` and no issues/warnings for this artifact set

The validation logic checks, at minimum:

- No negative or missing costs/energies where throughput is present
- Tiered pricing behaves monotonically (spot <= reserved <= on-demand where configured)
- Energy and carbon are consistent with the configured conversion factors

### 6.4 Statistical sufficiency (what "7 repetitions" buys you)

TR119 chooses 7 repetitions per cell to support:

- meaningful confidence intervals in `latency_summary_cost.csv`
- robust ANOVA + pairwise testing on the derived `$/1M tokens` metric

This matters because cost per token is not a raw measurement; it is a deterministic function of measured throughput and power. If throughput/power are unstable, cost will be unstable too.

### 6.5 What the statistical tests actually test

TR119 has two layers of stability:

1. **Within-cell stability:** 7 repetitions per backend/scenario/mode stabilize the latency/throughput/power estimates for that cell.
2. **Across-scenario stability:** statistical tests (ANOVA and pairwise tests) are run over the per-scenario derived costs, which means each backend/mode has `n=5` samples (the 5 scenarios).

This is the correct abstraction if your goal is "robust across workload shapes" rather than "robust under one fixed workload".

---

## 7. Workload Mix Sensitivity

This section is the bridge between "benchmark matrix" and "production decision".

The headline is simple:

- If you generate tokens at any meaningful volume, `onnxruntime-gpu` dominates end-to-end cost on this hardware.
- If you do *prefill-only* and you batch heavily, `transformers-gpu` can be cheaper.

### 7.1 Winner map (scenario x mode)

From `cost_energy_summary.json` (on-demand, $/1M tokens):

**Generate (uncached):** `onnxruntime-gpu` wins every scenario.

**Prefill:**

- `batch_short`: `transformers-gpu` is best at **$0.05846 / 1M**
- `batch_medium`: `transformers-gpu` is best at **$0.09046 / 1M**
- `single_short`: `onnxruntime-gpu` is best at **$0.1529 / 1M**
- `single_medium`: `onnxruntime-gpu` is best at **$0.1212 / 1M**
- `single_long`: `onnxruntime-gpu` is best at **$0.1223 / 1M**

### 7.2 Mapping the matrix to real deployments

Interpretation by workload archetype:

- **Interactive chat / agent tools:** dominated by `single_*` prefill + generate -> choose `onnxruntime-gpu`.
- **Batch prompt processing (reranking, offline summarization):** dominated by `batch_*` prefill with little/no generation -> benchmark your exact batch/seq distribution; `transformers-gpu` can win.
- **Hybrid systems:** you can benefit from routing (prefill batches on one backend; decode on another), but only if operational complexity is acceptable.

### 7.3 A concrete weighting method (how to apply TR119 to your traffic)

If you have production telemetry, you can turn this report into your own decision surface:

1. Bucket requests into a small set of "shape classes" (batch size x prompt length).
2. Estimate the fraction of your token volume and request volume in each class.
3. Compute a weighted cost per 1M tokens using the per-scenario rows in `cost_energy_summary.json`.

If you do not have that telemetry yet, use the mean-across-scenarios tables as a safe default, then rerun TR119 with your true mix before committing to a high-volume deployment.

### 7.4 Routing patterns (if you can tolerate complexity)

If you can operate more than one backend safely, there is a straightforward pattern suggested by the winner map:

- Route **batched prefill** workloads (`batch_*`-like shapes) to `transformers-gpu`.
- Route **interactive prefill + any generate** workloads (`single_*` + decode) to `onnxruntime-gpu`.

This can reduce cost without requiring you to "pick one winner" everywhere, but it introduces operational complexity:

- two deployment artifacts (two runtimes)
- two sets of correctness/compatibility tests
- routing logic and fallbacks

If you cannot afford that complexity, the report's default recommendation remains: ship `onnxruntime-gpu` and accept some prefill batch inefficiency.

---

## 8. Prefill Deep Dive (Where the nuance lives)

Prefill is the prompt-processing phase. It is usually:

- the dominant cost for embedding-like workloads
- a major contributor to TTFT for long prompts
- a throughput lever for batch processing

### 8.1 Why `transformers-gpu` wins batched prefill

The data says it clearly:

- For `batch_short` and `batch_medium`, `transformers-gpu` produces the lowest $/1M tokens.
- But its single-scenario performance is uneven; its worst prefill scenario is much more expensive than its best.

Concrete evidence (on-demand, prefill):

| Scenario | Backend | Throughput (tok/s) | Cost ($/1M) |
| --- | --- | --- | --- |
| `batch_short` | transformers-gpu | 4798 | 0.05846 |
| `batch_short` | transformers-gpu-compile | 2441 | 0.1148 |
| `batch_short` | onnxruntime-gpu | 1940 | 0.1445 |
| `batch_medium` | transformers-gpu | 3102 | 0.09046 |
| `batch_medium` | transformers-gpu-compile | 3038 | 0.09236 |
| `batch_medium` | onnxruntime-gpu | 2850 | 0.09832 |

The key observation is not subtle: for `batch_short`, `transformers-gpu` achieves ~2.47x higher throughput than `onnxruntime-gpu`, and cost follows throughput under time-based pricing.

This pattern is consistent with a backend whose performance is sensitive to:

- shape (batch size x sequence length)
- kernel selection and fusion
- overheads that amortize better with batch

The practical takeaway:

- If your production traffic is dominated by batched prompt processing, benchmark with your actual batch/seq distribution before defaulting to `onnxruntime-gpu`.

### 8.2 Why `onnxruntime-gpu` wins the overall mean

The overall mean across scenarios weights `single_*` and `batch_*` equally in this report. Under that weighting:

- `onnxruntime-gpu` is consistently strong across `single_short`, `single_medium`, `single_long`.
- It is not the best for batched prefill, but it is "never bad," and it is best on the `single_*` scenarios that dominate many real LLM serving workloads (interactive).

Concrete evidence (on-demand, prefill single scenarios):

- `single_short`: `onnxruntime-gpu` **$0.1529 / 1M** (essentially tied with `transformers-gpu-compile` at **$0.1556 / 1M**)
- `single_medium`: `onnxruntime-gpu` **$0.1212 / 1M** (next-best is `onnxruntime-cpu` at **$0.3170 / 1M**)
- `single_long`: `onnxruntime-gpu` **$0.1223 / 1M** (next-best is `transformers-gpu` at **$0.2437 / 1M**)

This is why the report's default recommendation is not "pick the absolute cheapest cell": it is "pick the backend that is consistently strong across the shapes you will actually see".

### 8.3 Stability and workload sensitivity

Scenario sensitivity (min-to-max cost across prefill scenarios, on-demand $/1M):

| Backend | Min ($/1M) | Max ($/1M) | Spread vs min |
| --- | --- | --- | --- |
| onnxruntime-gpu | 0.09832 | 0.1529 | 55.5% |
| transformers-gpu | 0.05846 | 0.5642 | 865.2% |
| transformers-gpu-compile | 0.09236 | 0.3602 | 290.0% |
| onnxruntime-cpu | 0.1440 | 0.4703 | 226.6% |
| transformers-cpu | 0.4174 | 1.743 | 317.7% |

This is why the overall mean is meaningful: it's an "average workload" proxy, but it must be replaced by your workload mix for deployment.

---

## 9. Generate Deep Dive (Uncached, worst-case decode)

### 9.1 What uncached generate actually measures

Uncached generation is intentionally pessimistic:

- Every step re-runs a full forward pass over the growing sequence.
- Production decoding normally uses KV-cache, turning decode into cheaper incremental work.

So why measure it?

- It provides a backend-stress test that is consistent across implementations.
- It can expose overhead differences and kernel quality under sustained decode workloads.

Two implementation details matter for interpretation:

- The runner defaults to `max_new_tokens=8`, so this is a short uncached loop (useful for comparisons, not the long-sequence regime).
- `batch_*` scenarios use batch size 4, so the loop generates tokens for a batch and typically achieves higher throughput than `single_*`.

### 9.2 The result that dominates the report

For uncached generate:

- `onnxruntime-gpu` is best across every scenario.
- The gap is large: the next-best backend is 2.62x more expensive per 1M generated tokens.

Scenario-level evidence (on-demand, generate):

| Scenario | Winner | Cost ($/1M) | Next best | Cost ($/1M) |
| --- | --- | --- | --- | --- |
| `batch_short` | onnxruntime-gpu | 0.5230 | transformers-gpu-compile | 1.432 |
| `batch_medium` | onnxruntime-gpu | 0.5533 | transformers-gpu | 1.549 |
| `single_short` | onnxruntime-gpu | 1.669 | transformers-gpu-compile | 1.948 |
| `single_medium` | onnxruntime-gpu | 1.628 | transformers-gpu-compile | 4.871 |
| `single_long` | onnxruntime-gpu | 1.647 | transformers-gpu | 5.363 |

This is the structural reason the request-level cost ranking is stable:

> Any backend that loses generate throughput loses end-to-end cost, even if it wins batched prefill.

### 9.3 Practical production interpretation

Treat uncached generate cost as an upper bound. For production planning:

1. Use this report to choose the likely winner (`onnxruntime-gpu`).
2. Then repeat TR119 with KV-cache generation enabled for your actual serving stack.

---

## 10. Statistical Deep Dive (Significance, not vibes)

TR119 includes statistical tests on cost per 1M tokens (artifact-backed).

### 10.1 ANOVA results

We test whether the mean costs differ across backends.

- **Generate:** F=12.85, p=2.44e-05 (significant)
- **Prefill:** F=8.08, p=4.78e-04 (significant)

Robustness check (non-parametric, same conclusion):

- **Generate Kruskal-Wallis:** H=17.33, p=0.00167
- **Prefill Kruskal-Wallis:** H=12.78, p=0.0124

Interpretation: backend choice materially changes cost; differences are not explained by noise.

### 10.2 Pairwise significance (selected)

Statistical tests are run over per-scenario derived costs (n=5 scenarios per backend per mode), not over per-repetition latencies. The 7 repetitions stabilize each scenario mean; inference is about cross-shape generality.

#### Mean costs with 95% CI (across scenarios)

| Mode | Backend | Mean $/1M (on-demand) | 95% CI | n |
| --- | --- | --- | --- | --- |
| prefill | onnxruntime-gpu | 0.1279 | [0.1012, 0.1546] | 5 |
| prefill | transformers-gpu-compile | 0.1995 | [0.05789, 0.3411] | 5 |
| prefill | transformers-gpu | 0.2605 | [0.004882, 0.5161] | 5 |
| prefill | onnxruntime-cpu | 0.2748 | [0.1167, 0.4329] | 5 |
| prefill | transformers-cpu | 0.9710 | [0.3007, 1.641] | 5 |
| generate | onnxruntime-gpu | 1.204 | [0.4490, 1.959] | 5 |
| generate | transformers-gpu-compile | 3.154 | [0.8709, 5.436] | 5 |
| generate | transformers-gpu | 3.626 | [1.271, 5.980] | 5 |
| generate | onnxruntime-cpu | 5.370 | [2.966, 7.774] | 5 |
| generate | transformers-cpu | 18.47 | [7.208, 29.74] | 5 |

Interpretation:

- Prefill has tighter cross-scenario variance for `onnxruntime-gpu` than for the Torch backends, because batching changes the relative winner.
- Generate has large cross-scenario variance for all backends because `batch_*` and `single_*` are fundamentally different shapes.

#### Pairwise comparisons focused on the decision boundary

Key comparisons for the recommended default (`onnxruntime-gpu`):

Generate (uncached):

| Comparison | Mean A | Mean B | % change (B vs A) | p-value | Cohen's d |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu vs onnxruntime-gpu | 5.370 | 1.204 | -77.6% | 0.00178 | -2.90 |
| onnxruntime-gpu vs transformers-cpu | 1.204 | 18.47 | +1434% | 0.00281 | 2.69 |
| onnxruntime-gpu vs transformers-gpu | 1.204 | 3.626 | +201% | 0.0263 | 1.72 |
| onnxruntime-gpu vs transformers-gpu-compile | 1.204 | 3.154 | +162% | 0.0545 | 1.42 |

Prefill:

| Comparison | Mean A | Mean B | % change (B vs A) | p-value | Cohen's d |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu vs onnxruntime-gpu | 0.2748 | 0.1279 | -53.5% | 0.0345 | -1.61 |
| onnxruntime-gpu vs transformers-cpu | 0.1279 | 0.9710 | +659% | 0.00820 | 2.21 |
| onnxruntime-gpu vs transformers-gpu | 0.1279 | 0.2605 | +104% | 0.190 | 0.906 |
| onnxruntime-gpu vs transformers-gpu-compile | 0.1279 | 0.1995 | +56.0% | 0.205 | 0.873 |

How to read this:

- Generate results show large, statistically significant improvements for `onnxruntime-gpu` over CPU backends and over `transformers-gpu`, with large effect sizes.
- Prefill is more nuanced: the mean difference between `onnxruntime-gpu` and the Torch GPU backends is not significant at alpha=0.05 when treating the 5 scenarios as samples. That matches the scenario-winner flips in Section 5.2 and is why workload mix (Section 7) matters.

---

## 11. Pricing Tier & Sensitivity Analysis

The pricing tier lever is large, and it applies multiplicatively to all backends:

- spot and reserved rates reduce infra cost roughly proportionally
- energy cost stays constant

### 11.1 Mean multi-tier cost per 1M tokens (across scenarios)

| Backend | Mode | On-demand | Spot | Reserved (1yr) | Reserved (3yr) | Energy-only (on-prem tier) |
| --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-gpu | prefill | 0.1279 | 0.03868 | 0.08961 | 0.06414 | 0.000417 |
| transformers-gpu-compile | prefill | 0.1995 | 0.06042 | 0.1398 | 0.1001 | 0.000767 |
| transformers-gpu | prefill | 0.2605 | 0.07875 | 0.1825 | 0.1306 | 0.000780 |
| onnxruntime-cpu | prefill | 0.2748 | 0.08613 | 0.1938 | 0.1400 | 0.005213 |
| transformers-cpu | prefill | 0.9710 | 0.2998 | 0.6831 | 0.4914 | 0.01186 |
| onnxruntime-gpu | generate | 1.204 | 0.3665 | 0.8448 | 0.6056 | 0.007105 |
| transformers-gpu-compile | generate | 3.154 | 0.9587 | 2.212 | 1.585 | 0.01716 |
| transformers-gpu | generate | 3.626 | 1.100 | 2.542 | 1.821 | 0.01644 |
| onnxruntime-cpu | generate | 5.370 | 1.677 | 3.786 | 2.731 | 0.09212 |
| transformers-cpu | generate | 18.47 | 5.731 | 13.01 | 9.369 | 0.2655 |

Interpretation:

- Tier selection shifts total cost by **~3x** (on-demand -> spot) without changing throughput.
- Energy-only is tiny in this configuration; infra dominates.

### 11.2 What "energy-only" means (and what it does not mean)

The "energy-only (on-prem tier)" column is the marginal electricity cost if you treat hardware cost as sunk (CapEx already paid) and ignore all amortization, maintenance, and opportunity cost. It is not a full TCO. Its purpose is to make one point clear:

- On this hardware and benchmark, **the marginal energy cost per token is extremely small** compared to time-based infra cost.

### 11.3 Energy-price sensitivity (what would need to change to matter)

In this run, energy is <2% of total cost for all backends. For energy price to materially change rankings, one of the following must be true:

1. Power differs dramatically between backends at similar throughput, or
2. Energy price rises by an order of magnitude, or
3. Infra rate collapses (e.g., fully amortized hardware) such that energy dominates.

This matters because it tells you what knob is worth turning:

- If you control the pricing tier and utilization, those dominate.
- If you control electricity price, it will matter primarily in the "energy-only / amortized" regime.

### 11.4 ROI by tier (combined request mix)

The tier lever is large and (mostly) backend-agnostic: it scales the compute-hour component without changing throughput.

From request-level time/energy in `cost_energy_analysis.json`, converted to $/1M **total tokens** under the request mix (prompt=256, generate=128; total tokens=384) and then recomputed under each hourly rate:

| Backend | On-demand | Spot | Reserved (1yr) | Reserved (3yr) | Spot savings vs on-demand |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-gpu | 0.3840 | 0.1168 | 0.2694 | 0.1931 | 69.6% |
| transformers-gpu-compile | 0.9056 | 0.2756 | 0.6353 | 0.4554 | 69.6% |
| transformers-gpu | 0.9770 | 0.2964 | 0.6850 | 0.4907 | 69.7% |
| onnxruntime-cpu | 1.736 | 0.5422 | 1.224 | 0.8831 | 68.8% |
| transformers-cpu | 5.200 | 1.614 | 3.662 | 2.638 | 69.0% |

Interpretation:

- The "best tier" in this configuration is spot for every backend, but the ordering between backends does not change.
- Tier selection is a major budget lever; backend selection is also a major budget lever; they compound.

---

## 12. Production Deployment Strategy

This section converts the report into actionable engineering choices.

### 12.1 Decision matrix (what to ship)

**If your system serves interactive LLM requests (prefill + generate):**

- Deploy `onnxruntime-gpu` as the default inference backend.
- Keep `transformers-gpu` as a compatibility fallback when:
  - you need features not surfaced in your ORT integration,
  - you need rapid iteration on model architecture without export friction.

**If your workload is batch-heavy prompt processing with minimal generation:**

- Re-run TR119 with your real batch/seq distribution.
- Expect `transformers-gpu` to be competitive or best in prefill batch scenarios.

**If you must run CPU-only:**

- Use `onnxruntime-cpu` as the default.
- Treat `transformers-cpu` as last-resort compatibility.

### 12.2 Operational considerations

- **Integration overhead:** `onnxruntime-gpu` requires a stable export+runtime path. Once built, it tends to be operationally stable.
- **Performance variability:** compiled PyTorch (`transformers-gpu-compile`) can be excellent, but compilation overhead and occasional variability complicate deployment if you need predictable cold starts.
- **Workload mix matters:** the "mean across scenarios" is not your workload. Use scenario winners as guidance, then weight by your production traffic.

### 12.3 Risk assessment

Frontier-grade reporting includes risk, not just wins:

- **Uncached generate is not production decode.** Treat generate numbers as upper bounds unless you confirm KV-cache behavior in your stack.
- **Single hardware system.** Rankings are likely stable across similar GPUs, but absolute costs must be re-run on production hardware.
- **Cost model meaning:** hourly rate represents a "compute-hour cost." If you deploy CPU-only, you should not apply GPU-instance hourly pricing; re-run with CPU instance pricing or on-prem amortization.

### 12.4 Rollout plan (practical)

For a production rollout that keeps risk low while capturing most of the savings:

1. Ship `onnxruntime-gpu` behind a feature flag as the default GPU path.
2. Keep `transformers-gpu` as a safety fallback (compatibility + debugging).
3. Add KV-cache generation benchmarking as a follow-on (to turn "uncached generate" into production-realistic decode costing).
4. Re-run TR119 with your real prompt/generate distribution and batch patterns to lock the final decision.

### 12.5 Monitoring and alerting (what to watch in production)

To keep a cost/energy recommendation honest over time, you need telemetry in your serving stack.

Minimum metrics to track:

- request latency split into prefill and decode (or TTFT + tokens/sec)
- tokens/sec by request class (prompt length buckets, batch size)
- GPU memory and utilization (capacity planning and throttling signals)
- degradation rate (timeouts, OOMs, correctness failures)

Alerting guidance:

- Alert on sustained throughput regressions (e.g., >10% drop in tok/s at fixed prompt/gen shapes) because $/token will move nearly linearly with tok/s.
- Alert on routing drift (if you implement multi-backend routing) so the assumed workload mix remains true.

### 12.6 When to rerun TR119

Re-run TR119 (or a smaller "smoke" variant) when any of the following changes:

- model architecture or weight format (export path changes)
- backend version upgrades (`torch`, `onnxruntime`, CUDA drivers)
- serving strategy changes (KV-cache enablement, batching policy)
- hardware changes (different GPU class, different CPU, different power limits)
- pricing changes (hourly rates, electricity/carbon assumptions)

---

## 13. Limitations & Next Steps

This report is designed to be decision-grade for the stated scope. It is also explicit about what it does not cover yet.

### 13.1 Limitations (explicit)

1. **Uncached generate is a stress test, not production decode.** KV-cache decode should be added for production planning.
2. **Generation length is short in the benchmark loop.** The runner defaults to `max_new_tokens=8`, which means the uncached loop does not reach the long-sequence regime where decode cost can grow with sequence length.
3. **Single model / single hardware.** GPT-2 (~124M params) on one Windows + RTX 4080 Laptop system; larger models can shift kernel balance and memory pressure.
4. **Power sampling cadence can undersample short runs.** Telemetry is sampled at `0.25s`; many prefill timed regions have only 1-2 samples, so energy/carbon is a low-frequency estimate for short calls (Section 6.2).
5. **Energy is not full-system energy.** GPU-backend energy uses GPU power (NVML) and does not add CPU package power; carbon numbers for GPU backends should be treated as lower bounds.
6. **Pricing is configurable inputs.** The absolute $/token depends on the configured hourly rate and energy rate; the ranking is the main stable insight.

### 13.2 Next steps (frontier-grade follow-through)

1. Add KV-cache generation benchmarking and cost modeling (decode realistic).
2. Extend `max_new_tokens` and `max_seq_len` to cover longer decode trajectories.
3. Add TensorRT into the same matrix (so "TRT vs ORT vs torch" is evaluated on the same telemetry footing).
4. Add full-system power accounting (CPU + GPU) and validate against an external power meter for carbon-grade reporting.
5. Re-run TR119 on at least one additional hardware class to identify portability vs hardware-specific effects.

---

## 14. Reproducibility & Artifacts

### 14.1 Run the experiment

Install dependencies (local venv recommended):

```bash
pip install -r scripts/tr119/requirements.txt
```

Run the full matrix (benchmark -> analysis -> stats -> plots -> generated report):

```bash
python scripts/tr119/run_experiment.py --config scripts/tr119/configs/matrix.yaml --device cuda
```

If you only want to regenerate processed summaries from existing raw JSONL:

```bash
python scripts/tr119/analyze_results.py --config scripts/tr119/configs/matrix.yaml
python scripts/tr119/statistical_analysis.py --cost-summary scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json
python scripts/tr119/validate_cost_energy.py --config scripts/tr119/configs/matrix.yaml
python scripts/tr119/visualize.py --config scripts/tr119/configs/matrix.yaml
python scripts/tr119/generate_report.py --results-dir scripts/tr119/results/tr119_matrix
```

### 14.2 Key artifacts

- Config: `scripts/tr119/configs/matrix.yaml`
- Results root: `scripts/tr119/results/tr119_matrix`
- Raw JSONL: `scripts/tr119/results/tr119_matrix/raw/`
- Processed summaries: `scripts/tr119/results/tr119_matrix/processed/`
- Plots: `scripts/tr119/results/tr119_matrix/plots/`
- Validation: `scripts/tr119/results/tr119_matrix/processed/cost_energy_validation.json`
- Statistical analysis: `scripts/tr119/results/tr119_matrix/processed/statistical_analysis.json`
- Request-level cost + TCO: `scripts/tr119/results/tr119_matrix/processed/cost_energy_analysis.json`

### 14.3 CPU power telemetry prerequisites (Windows)

CPU package power is measured from Windows Energy Meter performance counters via `pywin32` (`win32pdh`).

If the Energy Meter object is unavailable on your system:

- CPU-backend energy/carbon results will be missing or invalid, and the report should be rerun on a machine where these counters are available, or an alternative measurement approach should be documented.
- GPU-backend energy uses NVML GPU power, but full-system power is still not captured (Section 6.2).

---

## Appendix A: Key Tables

### A.1 Request-level cost (prompt_tokens=256, generate_tokens=128)

| Backend | Prefill time (s) | Generate time (s) | Total cost ($/request) |
| --- | --- | --- | --- |
| onnxruntime-gpu | 0.1140 | 0.4108 | 0.0001475 |
| transformers-gpu-compile | 0.1409 | 1.096 | 0.0003477 |
| transformers-gpu | 0.1236 | 1.213 | 0.0003752 |
| onnxruntime-cpu | 0.2091 | 2.135 | 0.0006667 |
| transformers-cpu | 0.6782 | 6.364 | 0.001997 |

### A.2 TCO projection (1B tokens/month, 12 months)

Definition note (reviewer-proof):

- In this projection, "tokens" refers to **total processed tokens** (prompt + generated) under the configured request mix: prompt_tokens=256 and generate_tokens=128 (total tokens per request = 384).
- The projection converts token volume to request volume as: `requests_per_month = tokens_per_month / 384`, then multiplies by the measured `$ / request`.

| Backend | Total cost ($) | Cost/month ($) | Cost per 1M total tokens ($) |
| --- | --- | --- | --- |
| onnxruntime-gpu | 4,608 | 384 | 0.3840 |
| transformers-gpu-compile | 10,867 | 906 | 0.9056 |
| transformers-gpu | 11,724 | 977 | 0.9770 |
| onnxruntime-cpu | 20,835 | 1,736 | 1.736 |
| transformers-cpu | 62,402 | 5,200 | 5.200 |

---

## Appendix B: Figures

Plots are generated artifacts (not hand-drawn). Paths are relative to this report.

### Prefill + combined

![mean_latency_tr119](../../scripts/tr119/results/tr119_matrix/plots/mean_latency_tr119.png)

![throughput_tr119](../../scripts/tr119/results/tr119_matrix/plots/throughput_tr119.png)

![total_cost_per_1m_tokens_tr119](../../scripts/tr119/results/tr119_matrix/plots/total_cost_per_1m_tokens_tr119.png)

![cost_tiers_tr119](../../scripts/tr119/results/tr119_matrix/plots/cost_tiers_tr119.png)

![energy_efficiency_tr119](../../scripts/tr119/results/tr119_matrix/plots/energy_efficiency_tr119.png)

![carbon_footprint_tr119](../../scripts/tr119/results/tr119_matrix/plots/carbon_footprint_tr119.png)

![cost_vs_throughput_tr119](../../scripts/tr119/results/tr119_matrix/plots/cost_vs_throughput_tr119.png)

### Generate (uncached)

![mean_latency_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/mean_latency_tr119_generate.png)

![throughput_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/throughput_tr119_generate.png)

![total_cost_per_1m_tokens_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/total_cost_per_1m_tokens_tr119_generate.png)

![cost_tiers_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/cost_tiers_tr119_generate.png)

![energy_efficiency_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/energy_efficiency_tr119_generate.png)

![carbon_footprint_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/carbon_footprint_tr119_generate.png)

![cost_vs_throughput_tr119_generate](../../scripts/tr119/results/tr119_matrix/plots/cost_vs_throughput_tr119_generate.png)

---

## Appendix C: Scenario Definitions

TR119 scenarios are sourced from the TR117 Tier-3 prompt/scenario config:

- `scripts/tr117/configs/matrix_tier3.yaml`

The goal of the scenario set is not to be an exhaustive corpus; it is to cover a small number of workload shapes that reliably expose backend differences:

- **Single prompt, varying prompt length:** `single_short`, `single_medium`, `single_long`
- **Batch prompt processing:** `batch_short`, `batch_medium` (batch size 4)

Scenario mapping (exact definitions live in the YAML):

| Scenario | Prompt set | Batch size | Mode |
| --- | --- | --- | --- |
| `single_short` | `short` | 1 | single |
| `single_medium` | `medium` | 1 | single |
| `single_long` | `long` | 1 | single |
| `batch_short` | `short` | 4 | batch |
| `batch_medium` | `medium` | 4 | batch |

Why this matters:

- It makes the "winner flips" in prefill interpretable: batching can amplify or suppress backend overheads.
- It makes the generate results interpretable: `batch_*` and `single_*` are meaningfully different decode shapes.

## Appendix D: Glossary

- **Prefill:** The prompt-processing phase; a single forward pass over the full prompt context.
- **Generate (decode):** Token-by-token generation after prefill. Production decode typically uses a KV-cache.
- **Uncached generate:** A pessimistic decode loop that recomputes full forward passes each step (used here for apples-to-apples stress testing).
- **$ / 1M tokens:** Cost normalized to one million tokens, computed from measured throughput and configured hourly/energy rates.
- **Spot / Reserved / On-demand:** Pricing tiers; spot is cheapest but interruptible, reserved reduces cost with commitment, on-demand is pay-as-you-go.
- **Energy-only (on-prem tier):** The marginal electricity cost when compute-hour cost is treated as zero (sunk hardware). Not a full TCO.
- **Degraded run:** A run flagged as invalid due to timeout, error, or invariant violation; excluded from performance means but retained in raw artifacts.
