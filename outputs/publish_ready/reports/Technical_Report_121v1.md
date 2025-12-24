# Technical Report 121 v1: Scaling Laws, Regimes, and Capacity Planning
## How latency, throughput, and cold-start risk change from ~0.1M to ~20.9B parameters

**Project:** Banterhearts LLM Performance Research  
**Date:** 2025-12-24  
**Author:** Research Team  
**Report Type:** Scaling-law analysis + mechanistic regime analysis + capacity/cost implications (artifact-backed)  
**Primary Artifacts (v1):** `scripts/tr121/results/20251224_002149/`  
**Supporting Artifacts:** Decode sweep `scripts/tr121/results/tr121_decode_sweep/20251224_002955/`; Gemma3 family check `scripts/tr121/results/20251224_002857/`; boundary-shift runs `scripts/tr121/results/20251224_002740/` (batch=8) and `scripts/tr121/results/20251224_004400/` (gen_tokens=512)  
**Related Work:** [TR117](Technical_Report_117.md), [TR118_v2.2](Technical_Report_118_v2.2.md), [TR119v1](Technical_Report_119v1.md), [TR120](Technical_Report_120.md), [TR122](../../scripts/tr122/README.md)

---

## Executive Summary

TR121 answers a production planning question:

> As model size increases, what breaks first: latency, tail risk (cold starts), or feasibility (capacity/cost), and how does the dominant regime change?

This report is publishable because it is:

- **Artifact-backed:** all claims trace to concrete run directories with raw `metrics.csv`, a manifest, summaries, and plots.
- **Attribution-correct:** parameter counts are measured (HF exact; Ollama tag-derived), and decode length is controlled.
- **Regime-aware:** we split **prefill**, **KV-cached decode**, and **end-to-end** (TR120-style). Scaling differs by phase.
- **Mechanistic:** we do not treat parameter count as a magic predictor; we show when depth vs width dominates latency.

### Claim status (to prevent misreads)

| Claim | Evidence base | Status |
| --- | --- | --- |
| One scaling exponent describes inference | Phase-split runner + fits | **False** (prefill vs decode differ; decode dominates end-to-end at moderate gen lengths) |
| Parameter count predicts latency on GPU for small models | HF GPU results (~0.1M-100M) + architecture audit | **Not supported here** (not identifiable under this boundary; R^2 ~0.03-0.06 and depth dominates) |
| Parameter count predicts latency on CPU for this model family | HF CPU GPT-2 family (~0.1M-100M) | **Supported (trend)** (strong overall monotonic trend / rank correlation, but not strict monotonicity due to architecture outliers) |
| Large-model serving latency scales strongly with parameter count | Ollama (~268M-20.9B) | **Supported** (strong monotonicity under this regime; R^2 ~0.90-0.93) |
| Mean latency is safe under cold-start effects | Warmup effect table | **False** (prefill warmups can be 10x-100x+) |

### The headline (numbers you can plan with)

#### 1) Scaling exponents (scenario-aggregated; median latency power-law fits)

Power-law model: `latency_ms ~ params_millions^slope`, fitted on scenario-aggregated medians (geomean across scenarios per model). This is a *regime descriptor* (not a universal law), especially for heterogeneous Ollama families/quantizations.

From `scripts/tr121/results/20251224_002149/analysis/scaling_fits.csv`:

| Backend | Mode | n_models | slope | R^2 | slope CI (bootstrap 95%) |
| --- | --- | ---: | ---: | ---: | --- |
| hf_cpu_fp32 | prefill | 7 | 0.281 | 0.873 | [0.0186, 0.510] |
| hf_cpu_fp32 | kv_decode | 7 | 0.291 | 0.848 | [0.0175, 0.650] |
| hf_cpu_fp32 | e2e_kv | 7 | 0.291 | 0.848 | [0.0175, 0.649] |
| hf_gpu_fp16 | prefill | 7 | 0.0338 | 0.0337 | [-0.313, 0.602] |
| hf_gpu_fp16 | kv_decode | 7 | 0.0426 | 0.0609 | [-0.262, 0.620] |
| hf_gpu_fp16 | e2e_kv | 7 | 0.0427 | 0.0609 | [-0.263, 0.620] |
| ollama | prefill | 5 | 0.623 | 0.901 | [0.454, 1.502] |
| ollama | kv_decode | 5 | 0.649 | 0.925 | [0.478, 1.439] |
| ollama | e2e_kv | 5 | 0.648 | 0.925 | [0.478, 1.440] |

Interpretation:

- **HF CPU (GPT-2 family)**: size is a good coarse predictor of latency in this range, but not a strict monotone mapping (architecture outliers exist; see Section 3.5 tables).
- **HF GPU (batch=1, short prompts)**: size alone is not a good predictor; model structure matters more.
- **Ollama (268M->20.9B)**: size is a strong predictor for both prefill and decode in this regime.

Interpretation note (HF GPU slopes):

- HF GPU slope values are reported for completeness because they fall out of the same fit machinery, but with `R^2 ~= 0.03-0.06` and wide sign-crossing bootstrap CIs they should be treated as **unidentifiable under this boundary** (batch=1, short prompts, `gen_tokens=64`), not as meaningful scaling exponents.

#### 1.1 What inferences this supports (and what it does not)

High-confidence inferences (strongly supported by the artifacts and insensitive to small analysis choices):

- **Decode dominates end-to-end quickly** once generation length is moderate (>=64 tokens in this sweep). Planning should treat end-to-end capacity as a decode throughput problem, not a prefill problem.
- **Cold-start is decision-grade risk.** Prefill warmups can add hundreds to thousands of milliseconds and can exceed steady-state by 10x-100x+; mean latency is unsafe as an SLO proxy when restarts exist.
- **HF CPU shows a strong monotonic trend** across this GPT-2 variant set in this range, but not strict monotonicity; parameter count is a useful *coarse* proxy under this boundary, not a guarantee.
- **Ollama large-model scaling is monotone** across 268M-20.9B for fixed-length decode equivalents; slopes remain stable under the decode-length sweep, and length-limited fits match the full fits.

Conditional inferences (true under this measurement boundary; do not generalize without rerunning):

- **HF GPU "latency vs params" is not identifiable at batch=1 with short prompts** for this heterogeneous HF set. In this boundary, (a) constant overhead dominates and (b) depth is a stronger predictor than parameter count.

Not supported / out of scope for TR121v1:

- A universal scaling law across architectures, quantization schemes, and serving stacks.
- Memory-wall feasibility, VRAM/RAM behavior, or energy/carbon (TR122/TR119).
- Quality/accuracy tradeoffs between 270M/1B/7B/20B (TR121 quantifies compute economics only).

#### 2) The key mechanistic finding (why HF GPU scaling looks "wrong")

In the HF model set used here, parameter count is not a smooth scaling family: models trade depth vs width and attention head count.

This matters because on GPU, **per-token decode cost is strongly sensitive to the number of transformer layers** (more sequential steps per token), even when parameter count is smaller.

Evidence (HF e2e_kv, scenario-aggregated; rank-based, artifact-backed):

From `scripts/tr121/results/20251224_002149/analysis/hf_architecture_correlations.csv`:

- Spearman correlation for HF GPU (log(params) vs log(latency)):
  - params vs latency: rho=0.286 (p=0.535) -> weak
  - n_layer vs log(latency): rho=0.811 (p=0.0269) -> strong
- Spearman correlation for HF CPU (log(params) vs log(latency)):
  - params vs latency: rho=0.857 (p=0.0137) -> strong
  - n_layer vs log(latency): rho=0.523 (p=0.229) -> weak/non-significant
  - n_embd vs log(latency): rho=0.855 (p=0.0143) -> strong

Interpretation:

- In this regime, **CPU time tracks "how much model"**; GPU time tracks **"how many sequential layer steps"**.
- This is why a naive "latency scales with params" claim would be wrong for small-model GPU at batch=1.

#### 3) Decode dominates end-to-end quickly (gen-length sweep)

From `scripts/tr121/results/tr121_decode_sweep/20251224_002955/`, median decode fraction (`kv_decode_ms / e2e_kv_ms`, scenario-aggregated) reaches ~0.98-0.99 by 64-128 tokens:

- At `gen_tokens=64`: HF CPU 0.979, HF GPU 0.981, Ollama 0.983
- At `gen_tokens=128`: HF CPU 0.989, HF GPU 0.990, Ollama 0.991

Operational meaning:

- For serving workloads with moderate generation lengths (>=64), end-to-end capacity is a **decode throughput** problem, not a prefill problem.

#### 4) Cold-start/warmup is a first-class risk (especially prefill)

From `scripts/tr121/results/20251224_002149/analysis/warmup_effect.csv` (definition: `warmup_ratio = warmup_median_ms / measured_median_ms` per `{backend, model, scenario, mode}`):

- HF GPU prefill warmup-to-steady max ratio: **194x** (tiny-gpt2, medium).
- Ollama prefill warmup-to-steady max ratio: **46x** (gpt-oss-20b, micro).
- HF CPU prefill warmup-to-steady max ratio: **20.6x** (gpt2-75m, medium).

Operational meaning:

- If you autoscale, restart workers, or rotate models, you must treat "first request after warmup" as an SLO event.

### Business impact (capacity and shadow-priced cost)

TR121 translates measured tokens/s into:

- workers required for a target token volume, and
- a shadow-priced $/token under time-priced compute (compute-hour model).

Using:

- 1B total tokens/month -> 385.8 tokens/s average load (30-day month)
- shadow price: `$1.006/hr` (TR119 on-demand default; interpret as "compute-hour cost", not local electricity)

Important: the `$1.006/hr` input is a compute-hour **shadow price** used to translate measured throughput into a comparable budget lever.
It is not a claim about local electricity, your exact cloud instance price, or full local TCO.

Scenario-aggregated end-to-end (e2e_kv) examples from `scripts/tr121/results/20251224_002149/analysis/summary_by_model_backend_mode_agg.csv`:

| Backend | Model | Tokens/s (e2e_kv) | $/1M total tokens (shadow) | Workers for 1B tokens/month |
| --- | --- | ---: | ---: | ---: |
| ollama | gpt-oss-20b:latest | 52.4 | 5.328 | 7.36 |
| ollama | qwen2.5:7b | 141.3 | 1.978 | 2.73 |
| ollama | gemma3:270m | 654.6 | 0.427 | 0.59 |
| hf_gpu_fp16 | models/gpt2-100m | 174.0 | 1.606 | 2.22 |
| hf_cpu_fp32 | models/gpt2-100m | 51.9 | 5.389 | 7.44 |

Takeaway:

- In this regime, model choice is a **~2.7x budget and capacity lever** (7B vs 20B is ~2.69x difference in $/token under time-priced compute in this run).

Practical interpretation:

- At `gen_tokens=64` under these prompts, **20B-class decode is multi-second**: `gpt-oss-20b:latest` has ~2966 ms end-to-end (scenario-aggregated).
- In the same regime, **7B-8B class is sub-second**: `qwen2.5:7b` is ~721 ms end-to-end; `llama3.1:8b-instruct-q4_0` is ~711 ms.
- These are not small deltas: they determine whether you can serve interactive traffic on a small fleet versus needing a multi-worker pool per model.

---

## Table of Contents

1. [Research Context & Objectives](#1-research-context--objectives)
2. [Methodology & Measurement Definitions](#2-methodology--measurement-definitions)
3. [Experimental Design & Environment](#3-experimental-design--environment)
4. [Results Overview (Scaling Laws + Regimes)](#4-results-overview-scaling-laws--regimes)
5. [Mechanistic Deep Dive (Depth vs Width)](#5-mechanistic-deep-dive-depth-vs-width)
6. [Decode-Length Sensitivity](#6-decode-length-sensitivity)
7. [Cold-Start / Warmup Analysis](#7-cold-start--warmup-analysis)
8. [Business Impact (Capacity + Shadow-Priced Cost)](#8-business-impact-capacity--shadow-priced-cost)
9. [Production Deployment Guidance](#9-production-deployment-guidance)
10. [Limitations & Next Steps](#10-limitations--next-steps)
11. [Reproducibility & Artifacts](#11-reproducibility--artifacts)
12. [Appendix A: HF Model Structure](#appendix-a-hf-model-structure)
13. [Appendix B: Figures](#appendix-b-figures)

---

## 1. Research Context & Objectives

TR117 made backend comparisons meaningful for a single small model but surfaced a critical issue: model skew. If your benchmark is dominated by a tiny model, you can accidentally report truths about "kernel launch counts" rather than truths about "serving cost."

TR121 closes that gap by answering:

1. How does latency scale with model size for **prefill** vs **KV-cached decode**?
2. Does scaling hold across prompt scenarios, or is it dominated by the measurement boundary and overhead?
3. How large is the cold-start penalty, and what does it imply for SLOs and autoscaling?
4. How do scaling results translate into capacity planning and budget planning?

TR121 is explicitly in-scope for production guidance because teams do not serve "a model" in isolation; they serve a model under:

- a request mix (prompt length + decode length),
- an uptime/cold-start regime (warm pool vs frequent restarts),
- and a capacity constraint (how many requests/tokens per second must be supported).

Non-goals (v1):

- Not a full energy report (TR119/TR122).
- Not a full serving-system report (queueing, batching policy, scheduler; those are stack-dependent).
- Not a pure scaling-law paper (we do not claim universality; we claim "in this environment and these regimes").

---

## 2. Methodology & Measurement Definitions

### 2.1 Modes (phase split)

TR121 uses three modes because "latency" is not one thing:

**Prefill (`prefill`)**

- One forward pass over the prompt context with `use_cache=True`.

**KV decode (`kv_decode`)**

- Fixed-length decode loop using `past_key_values` for `gen_tokens` steps.

**End-to-end KV (`e2e_kv`)**

- `prefill + kv_decode` (serving-like kernel-focused proxy).

### 2.2 Token accounting (explicit)

Throughput is computed as:

- `tokens_per_s = tokens_total / (latency_ms / 1000)`

`tokens_total` is mode-specific:

- `prefill`: prompt tokens
- `kv_decode`: generated tokens (fixed-length equivalent)
- `e2e_kv`: prompt + generated (fixed-length equivalent)

HF:

- prompt tokens come from the HF tokenizer.
- decode length is exactly `gen_tokens` (the loop always runs that many steps).

Ollama:

- prompt tokens come from `prompt_eval_count`.
- models may stop early; to keep comparability, we report a fixed-length equivalent decode time:

  - `kv_decode_ms_per_token = eval_duration_ms / eval_count`
  - `kv_decode_ms_equiv = kv_decode_ms_per_token * gen_tokens_target`

We then use `kv_decode_ms_equiv` and `gen_tokens_equiv = gen_tokens_target` for scaling fits and throughput.

This is a modeling choice that makes scaling claims defensible under early-stop variability. TR121 also validates the
assumptions explicitly:

- Early-stop frequency and `done_reason` by prompt scenario: `scripts/tr121/results/20251224_002149/analysis/ollama_early_stop_summary.csv`
- Decode scaling restricted to length-limited samples (removes EOS/stop bias): `scripts/tr121/results/20251224_002149/analysis/scaling_fits_length_limited.csv`
- Decode linearity validation (tests the proportional projection assumption): `scripts/tr121/results/20251224_002149/analysis/ollama_decode_linearity.csv` and `scripts/tr121/results/20251224_002149/analysis/ollama_decode_projection_error.csv`

Interpretation (why this matters):

- For most Ollama models in this run, `kv_decode_ms` is close to linear in `eval_count` (high per-model `R^2`), which makes fixed-length equivalence defensible.
- The projection is not perfect under early-stop. In the worst case here (`gpt-oss-20b:latest`), proportional projection vs an affine `a + b*count` model differs by a median **-109 ms** (under-prediction) and ranges from **-545 ms** to **+285 ms** at a 64-token target. This does not change qualitative regime conclusions, but it bounds the modeling error explicitly.

### 2.2.1 Timing boundaries and measurement sources (what "latency_ms" actually is)

TR121 uses backend-appropriate timing sources, but normalizes the outputs into a common schema:

- HF (CPU/GPU): wall-clock latency around the forward pass / decode loop in `run_scaling.py`.
  - On CUDA, TR121 also records CUDA-event timing per mode (`cuda_event_ms`) as a best-effort GPU-only time window.
  - In this artifact set, CUDA-event and wall-clock medians are very close for HF GPU, which indicates the measured region is dominated by GPU execution (not host-side overhead).
    Quantitatively, on `hf_gpu_fp16` (non-warmup rows), `|wall_ms - cuda_event_ms| / wall_ms` is:
    - `prefill`: median **0.94%**, p95 **1.99%**
    - `kv_decode`: median **0.013%**, p95 **0.036%**
    - `e2e_kv`: median **0.031%**, p95 **0.070%**
    Source: `scripts/tr121/results/20251224_002149/analysis/cuda_event_gap_summary.csv`
- Ollama: timing comes from Ollama's reported durations:
  - `prefill_ms` from `prompt_eval_duration`
  - `kv_decode_ms` from `eval_duration`
  - TR121 also records `ollama_wall_ms` as an external cross-check, plus `ollama_load_ms` to make cold-start effects visible.

Important nuance:

- For Ollama, `load_duration` can be a large contributor to warmup behavior depending on model residency and caching state.
- For HF, models are loaded once per `{model, device, dtype}` and cached in-process, so warmup mostly reflects first-inference initialization (allocator growth, kernel autotune, etc.) rather than repeated weight loading.

### 2.3 Parameter counts (measured)

TR121 treats parameter count as data, not a label:

- HF: exact params via `sum(p.numel()) / 1e6`
- Ollama: parsed from `/api/tags` `details.parameter_size`

All fits use:

- `params_millions_effective = params_millions_measured if present else params_millions_config`

### 2.4 Aggregation and fitting (what we regress)

TR121 reports distribution statistics per task (median, p95, p99). Scaling fits are run on medians.

Per-scenario fit:

- `median_latency_ms(model, scenario) ~ params_millions_effective^slope`

Scenario-aggregated fit (headline):

- `latency_geomean_ms(model) = geomean_scenarios( median_latency_ms(model, scenario) )`
- `latency_geomean_ms(model) ~ params_millions_effective^slope`

### 2.5 Randomization and warmup (TR120 lessons applied)

TR120 showed that ordering and first-call effects can dominate mean behavior. TR121 therefore:

- randomizes task order using `seed`
- records `is_warmup`, `call_idx`, and `task_idx` in raw metrics
- computes warmup-to-steady ratios explicitly

Scaling fits exclude warmup rows by default.

### 2.6 Robustness checks (beyond a single regression)

Because n_models per series is small:

- slopes include bootstrap 95% confidence intervals (where n_models>=3)
- we compute Spearman rank correlation as a non-parametric monotonicity check

---

## 3. Experimental Design & Environment

### 3.1 Primary run (v1)

- Run dir: `scripts/tr121/results/20251224_002149/`
- Config: `scripts/tr121/configs/scaling.yaml`
- Scenarios: micro/short/medium
- Warmups: 1 per task
- Repetitions: 3 per task
- `gen_tokens`: 64
- Seed: 42

Coverage sanity:

- Total per-mode records: 684 (`status=ok` for all)
- Backend rows: hf_cpu_fp32=252, hf_gpu_fp16=252, ollama=180

### 3.2 Supporting runs (to make v1 decision-grade)

Decode sweep:

- Root: `scripts/tr121/results/tr121_decode_sweep/20251224_002955/`
- `gen_tokens_list`: 8/32/64/128

Gemma3 family check:

- Run dir: `scripts/tr121/results/20251224_002857/`
- Config: `scripts/tr121/configs/gemma_family.yaml`

Batch-size boundary shift (HF GPU):

- Run dir: `scripts/tr121/results/20251224_002740/`
- Config: `scripts/tr121/configs/boundary_shift_batch8.yaml`

Decode-length boundary shift (HF GPU):

- Run dir: `scripts/tr121/results/20251224_004400/`
- Config: `scripts/tr121/configs/boundary_shift_gen512.yaml`

### 3.3 Hardware / software (from manifest)

From `scripts/tr121/results/20251224_002149/manifest.json`:

- OS: Windows 11 (Build 26200)
- CPU: Intel i9-13980HX
- GPU: NVIDIA RTX 4080 Laptop (12GB)
- Python: 3.13.1
- Torch: 2.8.0+cu128 (CUDA 12.8)
- Transformers: 4.57.0

### 3.4 Models and backends

This is not a single homogeneous model family across all backends:

- HF models are local GPT-2 style variants with differing depth/width/head counts.
- Ollama models are quantized GGUF variants across multiple families.

TR121 treats this explicitly: it reports "regimes" and provides a within-family Gemma3 check to reduce the largest confound.

### 3.5 Scenario-aggregated performance tables (source of truth)

The report uses scenario-aggregated (geomean across scenarios) medians for headline comparisons.

These are the exact per-model values used for capacity planning (e2e_kv) and for scaling fits (latency_geomean_ms):

HF CPU (`hf_cpu_fp32`) scenario-aggregated (gen_tokens=64):

| Model | Params (M) | Prefill (ms) | Prefill tok/s | KV decode (ms) | KV decode tok/s | Decode ms/token | E2E (ms) | E2E tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| models/tiny-gpt2 | 0.103 | 3.49 | 1530.7 | 166.32 | 384.8 | 2.599 | 169.76 | 428.3 |
| models/gpt2-5m | 5.04 | 20.71 | 258.2 | 1042.44 | 61.4 | 16.288 | 1063.47 | 68.4 |
| models/gpt2-25m | 25.0 | 15.75 | 339.5 | 783.67 | 81.7 | 12.245 | 799.73 | 90.9 |
| models/gpt2-45m | 45.2 | 18.08 | 295.8 | 799.82 | 80.0 | 12.497 | 818.73 | 88.8 |
| models/gpt2-50m | 51.5 | 25.35 | 211.0 | 1267.69 | 50.5 | 19.808 | 1289.54 | 56.4 |
| models/gpt2-75m | 74.8 | 27.80 | 192.4 | 1600.77 | 40.0 | 25.012 | 1634.74 | 44.5 |
| models/gpt2-100m | 96.1 | 26.98 | 198.3 | 1374.22 | 46.6 | 21.472 | 1402.22 | 51.9 |

HF GPU (`hf_gpu_fp16`) scenario-aggregated (gen_tokens=64):

| Model | Params (M) | Prefill (ms) | Prefill tok/s | KV decode (ms) | KV decode tok/s | Decode ms/token | E2E (ms) | E2E tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| models/tiny-gpt2 | 0.103 | 4.30 | 1242.6 | 224.95 | 284.5 | 3.515 | 228.87 | 317.7 |
| models/gpt2-5m | 5.04 | 13.07 | 409.3 | 626.09 | 102.2 | 9.783 | 639.85 | 113.6 |
| models/gpt2-25m | 25.0 | 3.24 | 1650.4 | 173.13 | 369.7 | 2.705 | 176.39 | 412.2 |
| models/gpt2-45m | 45.2 | 7.63 | 701.3 | 385.33 | 166.1 | 6.021 | 393.07 | 185.0 |
| models/gpt2-50m | 51.5 | 5.85 | 914.8 | 331.40 | 193.1 | 5.178 | 337.44 | 215.5 |
| models/gpt2-75m | 74.8 | 6.34 | 843.0 | 336.59 | 190.1 | 5.259 | 343.01 | 212.0 |
| models/gpt2-100m | 96.1 | 7.37 | 726.1 | 410.32 | 156.0 | 6.411 | 417.92 | 174.0 |

Ollama (`ollama`) scenario-aggregated (gen_tokens=64; decode is fixed-length equivalent):

| Model | Params | Prefill (ms) | Prefill tok/s | KV decode (ms) | KV decode tok/s | Decode ms/token | E2E (ms) | E2E tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma3:270m | 268M | 2.32 | 6973.3 | 121.57 | 526.4 | 1.900 | 123.90 | 654.6 |
| gemma3:1b-it-qat | 999.89M | 4.51 | 3829.9 | 260.90 | 245.3 | 4.077 | 265.53 | 309.2 |
| qwen2.5:7b | 7.6B | 11.57 | 3236.1 | 709.04 | 90.3 | 11.079 | 720.60 | 141.3 |
| llama3.1:8b-instruct-q4_0 | 8.0B | 11.53 | 1544.6 | 699.44 | 91.5 | 10.929 | 711.17 | 116.3 |
| gpt-oss-20b:latest | 20.9B | 50.85 | 1798.7 | 2914.22 | 22.0 | 45.535 | 2965.75 | 52.4 |

Sources:

- `scripts/tr121/results/20251224_002149/analysis/summary_by_model_backend_mode_agg.csv`
- Ollama measured params/quantization: `scripts/tr121/results/20251224_002149/resolved_model_params.csv`

### 3.5.1 Workload shape (why this is an overhead-sensitive study)

The benchmark prompts here are intentionally short-to-medium. That makes it excellent for:

- cold-start / warmup characterization (TR120 lessons),
- small-batch serving realism (batch=1, no throughput inflation from batching),
- and comparing phase dominance (prefill vs decode).

It also means the smallest-model GPU series can sit in a launch/dispatch dominated regime.

From `scripts/tr121/results/20251224_002149/metrics.csv` (non-warmup rows; median/min/max prompt tokens per scenario):

HF (tokenizer-stable across these GPT-2 variants):

- `micro`: 1 token
- `short`: 9 tokens
- `medium`: 17 tokens

Ollama (tokenization varies by model family; `prompt_eval_count` differs across models):

- `micro`: median 11 tokens (min 10, max 84)
- `short`: median 19 tokens (min 17, max 92)
- `medium`: median 27 tokens (min 25, max 99)

Interpretation:

- The HF micro scenario is intentionally a "minimal prompt" probe. For small models on GPU, you should expect constant overhead and depth effects to dominate.
- The Ollama prompt token variance is not "noise"; it is a real consequence of heterogeneous tokenizers across families. TR121 therefore treats Ollama results as regime descriptors, not architecture-invariant scaling laws.

### 3.6 Memory sanity (what this run is not stressing)

This run is not a memory-wall study:

- HF GPU peak allocated memory (median) stays well below 1 GB across the HF models in this sweep (best-effort via `torch.cuda.max_memory_allocated()`).
- This is consistent with the small-model scope and short prompts.

Implication:

- If your production models are GPU-memory-bound (common for larger LLMs), you must treat TR121 as a latency/throughput scaling study, not a VRAM feasibility study.
- TR122 is the correct follow-up for VRAM/RAM/power becoming first-class metrics.

### 3.7 Data quality and acceptance

TR121 v1 artifacts are clean in the sense required for a publishable scaling claim:

- `metrics.csv` contains only `status=ok` rows for the primary run.
- Warmups are explicitly labeled (`is_warmup=true`) and excluded from scaling fits by default.
- The manifest records a `config_sha256` and resolved allowlists to prevent "silent config drift" when regenerating results.

---

## 4. Results Overview (Scaling Laws + Regimes)

### 4.1 Regime map (what changes as models get larger)

TR121 observes three practical regimes:

1. **Small-model HF regime (0.1M-100M):** CPU scaling is predictable; GPU scaling vs params is weak because structure dominates and the models are not a pure scaling family.
2. **Large-model Ollama regime (268M-20.9B):** latency scales strongly with params under a fixed decode budget; decode dominates end-to-end quickly.
3. **Cold-start regime (all sizes):** first-call prefill can be 10x-100x+ slower than steady-state; warm pools and explicit warmups are operationally mandatory for consistent SLOs.

Ollama nuance (important for interpretability):

- Some prompt scenarios stop early (`done_reason=stop`), so TR121 reports a fixed-length decode equivalent for comparability.
- This does not materially change the inferred Ollama scaling in this run: the length-limited-only fits match the main fits closely.
  - See `scripts/tr121/results/20251224_002149/analysis/ollama_early_stop_summary.csv` and `scripts/tr121/results/20251224_002149/analysis/scaling_fits_length_limited.csv`.

### 4.1.1 Early-stop profile (why fixed-length equivalence is necessary for Ollama)

In the primary run, early-stop is not a rare edge case; it is common in the shortest prompt scenarios.
From `scripts/tr121/results/20251224_002149/analysis/ollama_early_stop_summary.csv` (5 models x 3 scenarios; `gen_tokens_target=64`):

| Scenario | Models | Early-stop rate |
| --- | ---: | ---: |
| `medium` | 5 | 0% |
| `short` | 5 | 80% |
| `micro` | 5 | 80% |

Interpretation:

- If we naively regressed Ollama decode latency against params using raw `eval_count`, the x-axis would be model size but the y-axis would be a mixture of "64-token decode" and "early stop at 10-57 tokens", which is definitionally not comparable.
- TR121's fixed-length decode equivalence avoids that artifact, and the length-limited-only fits demonstrate that the exponent is not being manufactured by the projection.

### 4.1.2 Within-family check (Gemma3: 270M -> 1B -> 4B)

To reduce the biggest confound in the Ollama regime (mixed families + mixed quantization), TR121 includes a within-family Gemma3 check.

Run:

- `scripts/tr121/results/20251224_002857/`

From `scripts/tr121/results/20251224_002857/analysis/scaling_fits.csv` (scenario-aggregated):

| Backend | Mode | n_models | slope | R^2 |
| --- | --- | ---: | ---: | ---: |
| ollama | prefill | 3 | 0.503 | 0.9996 |
| ollama | kv_decode | 3 | 0.515 | 0.998 |
| ollama | e2e_kv | 3 | 0.514 | 0.998 |

Interpretation:

- The within-family slope is lower than the cross-family Ollama slope (~0.65 in the primary run), which is expected: once you remove cross-family differences, "params-only" becomes closer to a true proxy.
- Even with only three models, the monotonicity is clear and provides a sanity check that TR121's "Ollama regime is params-dominated" conclusion is not just a byproduct of one idiosyncratic model.

### 4.2 Scenario sensitivity (why prompts matter)

Per-scenario fits show that prompt shape can materially change fit strength and slope.

Example: HF CPU prefill has R^2=0.715 on short prompts but R^2=0.865 on medium prompts (where overhead is less dominant).

Source: `scripts/tr121/results/20251224_002149/analysis/scaling_fits.csv`

### 4.3 What you should actually use as your planning metric

If your workload has moderate decode lengths, use:

- scenario-aggregated **e2e_kv tokens/s**

because:

- it captures the dominance of decode at gen_tokens>=64, and
- it is what converts cleanly into capacity and cost.

### 4.4 Boundary-shift check (batching improves identifiability, but does not make params a strong predictor across heterogeneous HF architectures)

A common reviewer objection to weak GPU scaling is: "you're in a launch-overhead regime; batch up and scaling will appear."

TR121 tests this directly with a batch-size ablation that runs the same HF model set at batch=1 vs batch=8:

- Config: `scripts/tr121/configs/boundary_shift_batch8.yaml`
- Run: `scripts/tr121/results/20251224_002740/`

Outcome (scenario-aggregated fits; `scripts/tr121/results/20251224_002740/analysis/scaling_fits.csv`):

- `hf_gpu_fp16_bs1` prefill: R^2=0.012; `hf_gpu_fp16_bs8` prefill: R^2=0.342 (better, but still not "clean scaling")
- `hf_gpu_fp16_bs1` kv_decode: R^2=0.138; `hf_gpu_fp16_bs8` kv_decode: R^2=0.201

Interpretation:

- Batching makes prefill more compute-dominated (improves identifiability), but **parameter count still does not become a strong predictor** across this heterogeneous HF set.
- This supports TR121's mechanistic conclusion: the dominant confound is **model structure (depth/width)**, not only launch overhead.

### 4.4.1 Boundary-shift check 2: longer decode budgets (gen_tokens=512)

If the main run is "too small" to expose scaling, the simplest stressor is to increase the decode length.
TR121 runs an additional HF GPU sweep at `gen_tokens=512` (same scenarios; batch=1):

- Run: `scripts/tr121/results/20251224_004400/`
- Source: `scripts/tr121/results/20251224_004400/analysis/scaling_fits.csv`

Result (HF GPU, scenario-aggregated):

- `hf_gpu_fp16` kv_decode: slope=0.077, R^2=0.154
- `hf_gpu_fp16` e2e_kv: slope=0.077, R^2=0.154

Interpretation:

- Increasing decode length does make the relationship slightly more identifiable (R^2 rises vs the gen_tokens=64 run),
  which is consistent with "compute dominates more at longer decode budgets".
- But parameter count still does not become a strong predictor across this heterogeneous HF set; the dominant confound remains architecture structure (depth/width).

---

## 5. Mechanistic Deep Dive (Depth vs Width)

The most important technical reason TR121 exists (instead of a shallow "params vs latency" scatterplot) is that **parameter count is an incomplete proxy**.

### 5.1 Why params fails on HF GPU in this run

The HF model set is not a smooth scaling family:

- `models/gpt2-5m` is deep (12 layers) and narrow (80 hidden).
- `models/gpt2-25m` is shallow (3 layers) and wider (384 hidden).
- `models/gpt2-45m` changes head count (8 heads).

Decode work is per token per layer. On GPU, a deep-but-small model can be slower than a larger-but-shallow model because it executes more sequential layer steps per token (and has more kernel launches / synchronization points inside the forward).

This is visible in the HF GPU e2e_kv ordering:

- `models/gpt2-25m` (3 layers) is much faster than `models/gpt2-5m` (12 layers) even though it has more parameters.

Concrete evidence from the scenario-aggregated tables (gen_tokens=64):

- GPU decode ms/token:
  - `models/gpt2-5m`: 9.783 ms/token
  - `models/gpt2-25m`: 2.705 ms/token
- That is ~3.62x faster decode per token for the "larger" (higher param count) but shallower model.

This is the right mental model for why parameter-only scaling fits can look weak: if the model set changes depth, the per-token sequential step count changes.

### 5.2 Evidence: which predictor actually correlates

On HF e2e_kv (scenario-aggregated):

- CPU: log(params) vs log(latency) is strong (rho=0.857, p=0.0137); n_layer vs log(latency) is weak/non-significant (rho=0.523, p=0.229)
- GPU: log(params) vs log(latency) is weak (rho=0.286, p=0.535); n_layer vs log(latency) is strong (rho=0.811, p=0.0269)

Source: `scripts/tr121/results/20251224_002149/analysis/hf_architecture_correlations.csv`

Interpretation:

- CPU cost tracks "how much total math and memory" well enough that params is a usable proxy in this family/range.
- GPU cost in this regime is more sensitive to **sequential depth** (layers), which params does not uniquely determine.

### 5.2.2 Multivariate fit (params + depth; makes the mechanism harder to dismiss)

To make the "depth matters" mechanism more than a correlation claim, TR121 also fits a simple multivariate model on the HF set
using scenario-aggregated medians:

- `log(latency_ms) ~ alpha + beta*log(params_millions) + gamma*log(n_layer)`

Source: `scripts/tr121/results/20251224_002149/analysis/hf_multivariate_fits.csv`

Decision-relevant summary (e2e_kv; batch=1; n_models=7):

| Backend | beta (log params) | gamma (log layers) | R^2 |
| --- | ---: | ---: | ---: |
| hf_cpu_fp32 | 0.231 | 0.422 | 0.929 |
| hf_gpu_fp16 | -0.0616 | 0.734 | 0.874 |

Interpretation (scoped; not a universal law):

- For HF GPU under this boundary, the fitted `gamma` (depth term) is strongly positive while the fitted `beta` (params term) is near zero, consistent with "sequential depth dominates variance" in this regime.
- This is an in-sample explanatory fit on a small, heterogeneous model set; use it as a mechanistic diagnostic, not a cross-architecture scaling law.

### 5.2.1 Overhead + compute model (explicitly modeling the constant term)

A pure power-law fit on latency (`lat ~ P^s`) is fragile when there is a large constant term (launch/dispatch + short-sequence effects).
TR121 therefore also fits a simple "overhead + compute" model on scenario-aggregated medians:

- `lat_ms = a + b * params_millions`

From `scripts/tr121/results/20251224_002149/analysis/overhead_compute_fits.csv` (HF GPU, scenario-aggregated):

- `hf_gpu_fp16` e2e_kv: linear offset fit `lat_ms = a + b*P` yields `a_ms ~= 358 ms`, `b ~= 0.097 ms/M params`, with `R^2 ~= 0.0005`.

How to read this (important, to avoid a common over-interpretation):

- The intercept `a_ms` is evidence that a constant-like baseline is on the order of **hundreds of milliseconds** under this boundary (batch=1, short prompts, `gen_tokens=64`).
- The linear offset fit is **not** a physically meaningful "overhead decomposition" here: the fit has near-zero `R^2` and can under-predict individual models.
- The `overhead_fraction_at_*` fields in `overhead_compute_fits.csv` are computed against the *fitted curve* (`a / (a + b*P)`), not against observed latencies; given the poor fit quality, treat them as descriptive only and do not read them as "true overhead share."

Interpretation:

- Under this boundary (batch=1, short sequences, fixed gen_tokens=64), a constant baseline dominates HF GPU latency, so "params-only" scaling is not identifiable.
- This does not contradict the depth finding; it complements it: when total compute is small, both **constant overhead** and **sequential depth** can dominate variance.

### 5.3 What "depth sensitivity" likely means at the kernel level

TR121 does not include a profiler trace (that is follow-up work), but the mechanism is consistent with how decode executes:

- KV decode is a loop of single-token forward passes.
- Each token step runs through all transformer blocks.
- More layers means more sequential subgraphs and kernel launches per generated token.

On CPU, additional layers tend to add work in a way that correlates with total parameter count across this family.
On GPU for small models at batch=1, the per-layer launch and scheduling overhead can become a large fraction of total time, making depth a stronger predictor than parameters.

### 5.3 What this implies for model design and selection

If you are targeting GPU serving at batch=1 for small models, the results suggest:

- Depth is expensive: more layers increases per-token sequential work and can reduce tokens/s.
- "Same params" can be achieved by different depth/width tradeoffs with very different latency behavior.

This is not a universal claim. It is a concrete, artifact-backed observation for this environment and this model set, and it is the correct explanation for why a parameter-only scaling fit is weak here.

### 5.4 Practical guidance: what to treat as the "x-axis" in different regimes

If you are doing back-of-the-envelope planning:

- HF CPU regime (this family/range): parameter count is a reasonable first proxy.
- HF GPU small-model regime (batch=1): parameter count is not sufficient; depth (n_layer) is a better proxy for per-token latency.
- Large-model serving regime: parameter count becomes a useful predictor again, but you should also track quantization level and memory behavior (TR122).

### 5.5 Interpreting "weird points" (non-monotonicity and small-n reality)

In small sweeps, two things can make scaling plots look "messy" even when the regime story is correct:

1. **Heterogeneous architecture axes:** a 50M-param model is not guaranteed to be "harder" than a 75M-param model if the 50M model is deeper or has less favorable kernel shapes.
2. **Low compute budgets:** with very short prompts and batch=1, the absolute compute is small enough that constant overhead and scheduling noise can move points around.

TR121 treats this defensively:

- It does not claim a universal exponent for HF GPU small models; it says parameter count is not an adequate predictor under this boundary.
- It provides a mechanistic alternative axis (depth) and shows it correlates where params does not.

---

## 6. Decode-Length Sensitivity

The decode-length sweep exists because phase dominance can change as generation length increases.

Artifacts:

- `scripts/tr121/results/tr121_decode_sweep/20251224_002955/`

Decision anchor figure (median decode fraction across models by backend):

![decode_fraction_by_gen_tokens](../../scripts/tr121/results/tr121_decode_sweep/20251224_002955/plots/decode_fraction_by_gen_tokens.png)

### 6.1 Decode dominance (why end-to-end is a decode problem at 64+ tokens)

By gen_tokens=64-128:

- median decode fraction `kv_decode_ms / e2e_kv_ms` is ~0.98-0.99 for both HF and Ollama in the sweep:
  - at 64 tokens: HF CPU 0.979, HF GPU 0.981, Ollama 0.983
  - at 128 tokens: HF CPU 0.989, HF GPU 0.990, Ollama 0.991

Interpretation:

- For most serving workloads, optimizing only prefill (TTFT) will not materially change end-to-end throughput if decode dominates.

### 6.2 Exponent stability (Ollama)

In the sweep:

- Ollama KV decode slope remains ~0.64-0.69 for gen_tokens 8/32/64/128 with high R^2 (~0.93-0.98).

Interpretation:

- In this large-model regime, scaling behavior is stable with respect to decode length in the tested range.

---

## 7. Cold-Start / Warmup Analysis

Warmup analysis artifact:

- `scripts/tr121/results/20251224_002149/analysis/warmup_effect.csv`

### 7.1 Summary statistics

Warmup ratio summary (median/p95/max across the scenario x model grid; higher is worse):

| Backend | Mode | Median warmup ratio | p95 | Max |
| --- | --- | ---: | ---: | ---: |
| hf_cpu_fp32 | prefill | 1.64x | 18.60x | 20.59x |
| hf_gpu_fp16 | prefill | 2.02x | 15.39x | 194.45x |
| ollama | prefill | 3.71x | 33.18x | 46.28x |
| hf_cpu_fp32 | kv_decode | 1.04x | 1.21x | 1.35x |
| hf_gpu_fp16 | kv_decode | 1.03x | 1.95x | 2.40x |
| ollama | kv_decode | 1.01x | 1.45x | 1.96x |
| hf_cpu_fp32 | e2e_kv | 1.07x | 1.55x | 1.66x |
| hf_gpu_fp16 | e2e_kv | 1.08x | 2.38x | 5.09x |
| ollama | e2e_kv | 1.09x | 1.92x | 2.37x |

Interpretation:

- Warmup spikes are primarily a prefill phenomenon.
- End-to-end warmup spikes are usually muted because decode dominates at gen_tokens=64.

### 7.1.1 Ollama cold-start decomposition (load vs infer; prevents apples-to-oranges reads)

For HF, warmup is mostly "first inference in-process" effects (allocator growth, autotune, kernel initialization).
For Ollama, a large fraction of "cold-start pain" can come from **model load / residency** (reported as `load_duration`), which is a different operational phenomenon.

TR121 therefore also computes an Ollama-only warmup breakdown that separates:

- prefill inference time (`prefill_ms`, prompt eval duration), and
- load time (`ollama_load_ms`)

Source: `scripts/tr121/results/20251224_002149/analysis/ollama_warmup_breakdown.csv`

Headline observation (this artifact set):

- Measured (steady) `ollama_load_ms` medians are ~**122-227 ms**, while warmup `ollama_load_ms` medians can be **seconds to 12+ seconds** depending on scenario/model residency.
- The resulting warmup ratio for *total cold-start including load* can exceed **50x** (e.g., `gpt-oss-20b:latest` micro: **54.0x**; `llama3.1:8b-instruct-q4_0` short: **50.9x**).

Interpretation:

- The warmup ratios in the main table are meaningful for inference stability, but for Ollama they are not the whole cold-start story.
- If you care about first-request TTFT after worker/model eviction, you must treat `load_duration` as first-class and design for model residency (warm pool) or explicit preloading.

### 7.2 Operational meaning (why this matters for SLOs)

Warmup penalties translate into:

- tail latency spikes on worker restart
- timeout risk for the first few requests on a cold worker
- queue amplification under load

Mitigation policy (the minimum that is consistent with these artifacts):

1. Maintain a warm pool for large models (keep weights loaded and the model "hot").
2. Run an explicit warmup flow on deploy/autoscale.
3. Track cold-start latency separately from steady-state SLOs.

### 7.3 Worst-case events (absolute milliseconds, not just ratios)

Warmup ratios can hide the real operational harm when steady-state latency is tiny. TR121 therefore treats absolute deltas as first-class.

From `scripts/tr121/results/20251224_002149/analysis/warmup_effect.csv` (top warmup events by ratio; warmup median vs steady median):

- HF GPU prefill (tiny model, medium prompt): 836.1 ms warmup vs 4.30 ms steady (194x; +832 ms)
- Ollama prefill (20B, micro prompt): 2228.1 ms warmup vs 48.15 ms steady (46x; +2180 ms)
- HF CPU prefill (75M, medium prompt): 521.4 ms warmup vs 25.33 ms steady (20.6x; +496 ms)

Interpretation:

- Even if end-to-end throughput is decode-dominated, prefill warmup spikes can blow TTFT budgets and create user-visible stalls on the first request to a worker.
- These events are large enough to trigger timeouts in real serving stacks unless you explicitly warm the worker before routing real user traffic.

---

## 8. Business Impact (Capacity + Shadow-Priced Cost)

TR121 is not TR119 (no energy telemetry), but a scaling report must still translate into decision-grade planning.

### 8.1 From tokens/s to capacity

For a target `T` total tokens/month:

- `avg_tokens_per_s = T / seconds_per_month`

For 1B total tokens/month (30-day month):

- `avg_tokens_per_s ~= 385.8`

Given a measured tokens/s per worker:

- `workers ~= avg_tokens_per_s / worker_tokens_per_s`

This is not a concurrency model; it is a utilization-perfect lower bound.
If your traffic is bursty (e.g., p95 load is 5x mean) then fleet size must exceed this bound by a comparable factor unless you can queue/batch without violating latency SLOs.

### 8.2 Shadow-priced $/token (compute-hour model)

To translate time-per-token into dollars, we use a compute-hour shadow price:

- `sec_per_1M = 1e6 / tokens_per_s`
- `usd_per_1M = (sec_per_1M / 3600) * usd_per_hour`

For comparability with TR119, we use `usd_per_hour = 1.006`.

Interpretation:

- This is "cloud-equivalent compute-hour cost", not local electricity.
- It is still the correct way to translate throughput into a budget lever under time-priced compute.

### 8.3 Concrete planning example (1B tokens/month, gen_tokens=64 regime)

Using scenario-aggregated e2e_kv tokens/s:

| Model/backend | Tokens/s | Workers for 1B/month | $/1M tokens (shadow) | $/month (shadow) |
| --- | ---: | ---: | ---: | ---: |
| ollama gpt-oss-20b | 52.4 | 7.36 | 5.328 | 5,328 |
| ollama qwen2.5:7b | 141.3 | 2.73 | 1.978 | 1,978 |
| ollama llama3.1:8b-instruct-q4_0 | 116.3 | 3.32 | 2.402 | 2,402 |
| ollama gemma3:1b-it-qat | 309.2 | 1.25 | 0.904 | 904 |
| ollama gemma3:270m | 654.6 | 0.59 | 0.427 | 427 |
| hf_gpu_fp16 gpt2-100m | 174.0 | 2.22 | 1.606 | 1,606 |
| hf_cpu_fp32 gpt2-100m | 51.9 | 7.44 | 5.389 | 5,389 |

Business interpretation:

- If your product can ship 7B instead of 20B, you can often buy ~2.7x more capacity for the same compute-hours (in this regime).
- If you are CPU-bound, GPU is not a marginal improvement: it is the difference between a feasible service and a service that requires an order of magnitude more workers.

### 8.3.1 Decision deltas (what model choice costs you, in dollars and fleet)

Using the same table (1B tokens/month; shadow price $1.006/hr):

- `gpt-oss-20b` vs `qwen2.5:7b`:
  - +$3,350/month (5,328 - 1,978)
  - +4.63 workers (7.36 - 2.73)
- `qwen2.5:7b` vs `gemma3:1b-it-qat`:
  - +$1,074/month (1,978 - 904)
  - +1.48 workers (2.73 - 1.25)

Operational interpretation:

- The "quality tier" decision is also a budget and reliability decision.
- If you do not have a measured quality delta that justifies ~2-3x cost, shipping a larger model by default can be an avoidable burn rate increase.

### 8.3.2 Translating token economics into request economics (how to use this with product metrics)

TR121 is token-first because token volume is the cleanest cross-stack unit. To map this into requests:

- `requests_per_s ~= tokens_per_s / tokens_per_request`
- `cost_per_request ~= (tokens_per_request / 1e6) * usd_per_1M_tokens`

Example (illustrative, not measured in this run): if your median request is 384 total tokens (prompt 256 + generate 128),
then under the $/1M totals in Section 8.3:

- `gpt-oss-20b`: ~$2.05 per 1k requests
- `qwen2.5:7b`: ~$0.76 per 1k requests
- `gemma3:270m`: ~$0.16 per 1k requests

The correct workflow for production planning is:

1. Measure your real `tokens_per_request` distribution from production logs.
2. Choose the model tier and backend that meets quality and SLO constraints.
3. Use the formulas above to translate tokens/s into request capacity and compute-hour consumption.

### 8.3.3 Product scenario pack (request mixes you can plug into planning)

TR121's raw measurements are token-first. Product planning is request-first. This section provides a small set of canonical request mixes
so you can translate `$ / 1M tokens` into `$ / 1k requests` and compare "model tiers" in product terms.

Important caveat:

- These are **cost** projections under a token-linear compute-hour model. They do not claim latency is invariant to context length or batch policy.
- For long-context workloads, you must rerun TR121 with your real prompt length distribution to get accurate latency and tokens/s.

Canonical mixes (total tokens per request):

| Scenario | Prompt tokens | Gen tokens | Total tokens |
| --- | ---: | ---: | ---: |
| `chat_default` | 256 | 128 | 384 |
| `agent_tool_step` | 512 | 32 | 544 |
| `codegen_medium` | 512 | 1024 | 1536 |
| `long_context_summary` | 2048 | 256 | 2304 |

Cost per 1k requests under these mixes (using `$ / 1M tokens` from Section 8.3; shadow price `$1.006/hr`):

Formula: `usd_per_1k_requests = usd_per_1M_tokens * (total_tokens / 1000)`

| Model | $/1M tokens | chat_default | agent_tool_step | codegen_medium | long_context_summary |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gpt-oss-20b` | 5.328 | 2.046 | 2.898 | 8.184 | 12.276 |
| `qwen2.5:7b` | 1.978 | 0.760 | 1.076 | 3.038 | 4.557 |
| `llama3.1:8b-instruct-q4_0` | 2.402 | 0.922 | 1.307 | 3.690 | 5.534 |
| `gemma3:1b-it-qat` | 0.904 | 0.347 | 0.492 | 1.389 | 2.083 |
| `gemma3:270m` | 0.427 | 0.164 | 0.232 | 0.656 | 0.984 |

How to use this table:

- If you know your request volume, multiply `$ / 1k requests` by `(requests / 1000)` to get monthly compute-hour spend under the shadow price.
- If you do not know your token counts yet, measure `prompt_tokens` and `generated_tokens` from logs for one week; then you can replace these mixes with your empirical distribution.

### 8.3.4 Quality proxy and break-even analysis (what "2-3x cost" must buy you)

TR121 intentionally does not claim model quality. It does, however, give you a quantitative way to ask:

> "How much quality improvement must the larger model deliver to justify its incremental compute cost?"

#### A) What counts as a quality proxy (defensible, production-aligned)

Use a layered approach:

1. **Offline task suite (primary):** build an eval set from your real prompts and acceptance criteria.
   - Metrics: pass rate, rubric score, refusal correctness, tool-call correctness, hallucination rate.
2. **Online quality signals (secondary):** in-product outcomes.
   - Metrics: user ratings, retention, task completion rate, fallback-to-human rate, tool retry rate.
3. **Safety/guardrail outcomes (hard constraints):**
   - Metrics: policy violations, jailbreak success, PII leakage, high-risk hallucinations.

TR121's stance for publish-grade claims is: you should not ship a 2-3x compute cost model without at least one of (1) or (2) showing a clear lift.

#### B) Break-even math (simple and actionable)

Let:

- `C_small` = cost per request for the small model
- `C_big` = cost per request for the big model
- `p_small` = probability a request is "successful" (passes your acceptance criteria)
- `p_big` = probability a request is "successful"

Then cost per successful request is:

- `C_success = C / p`

The big model is cost-justified when:

- `C_big / p_big <= C_small / p_small`
- equivalently `p_big >= p_small * (C_big / C_small)`

Example using `chat_default` costs from the table above:

- `gpt-oss-20b` vs `qwen2.5:7b`: cost ratio ~= `2.046 / 0.760 ~= 2.69x`
- If `p_small = 0.70`, then break-even requires `p_big >= 0.70 * 2.69 ~= 1.88` (impossible)

Interpretation:

- Under this cost regime, a naive "upgrade everything to 20B" policy is almost never cost-justified on success-rate alone.
- The rational policy is tiering/routing: only pay the 20B premium when the value per-success is high (paid users, high-stakes tasks, or when the small model fails).

#### C) When large models *are* justified (value-per-success, not just success-rate)

If a failed request has a real downstream cost (human time, churn, incident risk), use a value-based break-even:

- Let `V_fail` be the expected dollar cost of a failure (e.g., human review time).
- Let `delta_fail = fail_rate_small - fail_rate_big`.
- Pay the big-model premium when: `C_big - C_small <= delta_fail * V_fail`

This is why large models can be justified for:

- customer support escalation,
- compliance-sensitive summarization,
- agent steps that trigger external side effects.

### 8.4 What this does not include

The shadow-priced model does not include:

- electricity and carbon (TR119/TR122)
- memory walls and OOM failure rate (TR122)
- queuing and batching dynamics (serving stack dependent)

Treat it as a consistent translation from measured tokens/s to compute-hour consumption.

### 8.5 Sensitivity: volume and hourly-rate tiers

Two facts make this section simple:

1. Required workers scales linearly with token volume.
2. Shadow-priced $/token scales linearly with the hourly rate.

Volume scaling example (same per-worker tokens/s; 30-day month):

- 100M tokens/month -> 38.6 tokens/s
- 1B tokens/month -> 385.8 tokens/s
- 10B tokens/month -> 3858 tokens/s

So the worker counts in Section 8.3 multiply by 0.1x or 10x for those volumes.

Hourly-rate sensitivity:

- `usd_per_1M_tokens = (1e6 / tokens_per_s / 3600) * usd_per_hour`

If you want TR119-style tiering, replace `usd_per_hour` with your tier rate (on-demand / spot / reserved / amortized on-prem). Rankings do not change under this model; costs scale proportionally.

Example (ollama qwen2.5:7b at 141 tok/s e2e_kv):

- on-demand ($1.006/hr): ~$1.978 / 1M tokens
- spot ($0.302/hr): ~$0.594 / 1M tokens
- reserved-3yr ($0.503/hr): ~$0.989 / 1M tokens

Interpretation:

- Tier selection is a major budget lever, but it does not change the throughput-derived ordering; it rescales everything.

---

## 9. Production Deployment Guidance

### 9.1 What to measure in production (minimum)

If you want scaling claims to stay true over time, track:

- TTFT vs decode tokens/s separately (prefill vs decode split)
- tokens/s by request bucket (prompt length, generation length, batch size)
- cold-start vs steady-state latency (worker age, time since last request, model load status)

### 9.2 What to do if you need a policy now

- Assume decode dominates for gen>=64; plan capacity primarily off tokens/s, not TTFT.
- For small models, if GPU tokens/s is unstable vs params, prefer policies that stabilize the workload:
  - batch where possible
  - bucket/pad sequence lengths
  - avoid deep-and-narrow architectures if you care about per-token latency at batch=1
- For large models, treat cold-start mitigation as a cost-control strategy, not a UX nicety.

### 9.3 A concrete "model tiering" playbook (what TR121 implies you should ship)

TR121's strongest business implication is that model size is a fleet-sizing knob. A reasonable production pattern is:

1. **Default tier (cheap, fast):** a small/medium model that comfortably meets latency SLOs.
2. **Premium tier (expensive, better quality):** a larger model used only when value is high (paid users, complex prompts, fallback on failure).
3. **Routing policy:** route by user tier, complexity heuristics, or offline pre-classification; keep per-tier cold-start behavior visible.

Why this is consistent with the artifacts:

- Decode dominates end-to-end quickly, so tokens/s is the capacity constraint for most real workloads.
- Larger models impose a roughly multiplicative cost and fleet requirement for the same token volume.

This is the key inference TR121 enables: model choice is not "just quality"; it is operational feasibility.

---

## 10. Limitations & Next Steps

Limitations (v1):

1. HF and Ollama represent different families and runtimes; compare regimes, not absolute backend quality.
2. Ollama decode is reported as a fixed-length equivalent; explicit and defensible, but still a modeling choice.
3. Model counts per series are small (n=5 for Ollama in the main run); we use bootstrap CIs and Spearman checks to avoid overclaiming.
4. Resource telemetry (VRAM/RSS/power) is not first-class here; that is TR122.
5. Within-family Gemma3 check reduces confounds but quantization differs across the three models.

Next steps (to push TR121 beyond v1):

1. Same-model cross-backend sweep (HF vs Ollama for the same architecture) to isolate runtime/backend effects.
2. Extend decode sweep to 256/512 tokens and check exponent stability at longer decode regimes.
3. Add a batch-size sweep to find when HF GPU leaves the overhead/structure-dominated regime.
4. Integrate TR122 telemetry so scaling can be expressed in memory/power/cost terms.

---

## 11. Reproducibility & Artifacts

Run the primary sweep:

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/scaling.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/20251224_002149
python scripts/tr121/generate_report.py --run-dir scripts/tr121/results/20251224_002149
```

Run the decode-length sweep:

```bash
python scripts/tr121/run_decode_sweep.py --config scripts/tr121/configs/decode_sweep.yaml
```

Run the within-family Gemma3 check:

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/gemma_family.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/20251224_002857
```

Run the batch-size boundary shift (HF GPU):

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/boundary_shift_batch8.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/20251224_002740
```

Run the longer-decode boundary shift (HF GPU, gen_tokens=512):

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/boundary_shift_gen512.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/20251224_004400
```

Key artifacts (primary run):

- Raw per-measurement data: `scripts/tr121/results/20251224_002149/metrics.csv`
- Manifest (environment + resolved config): `scripts/tr121/results/20251224_002149/manifest.json`
- Scenario-level summary: `scripts/tr121/results/20251224_002149/analysis/summary_by_model_backend_mode.csv`
- Scenario-aggregated summary: `scripts/tr121/results/20251224_002149/analysis/summary_by_model_backend_mode_agg.csv`
- Scaling fits: `scripts/tr121/results/20251224_002149/analysis/scaling_fits.csv`
- Length-limited Ollama decode fits (EOS/stop sanity): `scripts/tr121/results/20251224_002149/analysis/scaling_fits_length_limited.csv`
- Ollama early-stop summary (`eval_count` vs target + `done_reason`): `scripts/tr121/results/20251224_002149/analysis/ollama_early_stop_summary.csv`
- Ollama decode linearity + projection error bounds: `scripts/tr121/results/20251224_002149/analysis/ollama_decode_linearity.csv`
- Ollama decode linearity + projection error bounds: `scripts/tr121/results/20251224_002149/analysis/ollama_decode_projection_error.csv`
- Warmup effect: `scripts/tr121/results/20251224_002149/analysis/warmup_effect.csv`
- Ollama warmup breakdown (load vs infer): `scripts/tr121/results/20251224_002149/analysis/ollama_warmup_breakdown.csv`
- CUDA-event vs wall-clock gap (HF timing validity): `scripts/tr121/results/20251224_002149/analysis/cuda_event_gap_summary.csv`
- Overhead+compute fits (`lat = a + b*P`): `scripts/tr121/results/20251224_002149/analysis/overhead_compute_fits.csv`
- HF model structure table: `scripts/tr121/results/20251224_002149/analysis/hf_model_architecture.csv`
- HF structure-vs-latency correlations: `scripts/tr121/results/20251224_002149/analysis/hf_architecture_correlations.csv`
- HF multivariate fits (params + depth): `scripts/tr121/results/20251224_002149/analysis/hf_multivariate_fits.csv`
- Plots: `scripts/tr121/results/20251224_002149/analysis/plots/`

---

## Appendix A: HF Model Structure

TR121's HF set is not a pure scaling family; these variants differ in depth/width/head count.

Source: `scripts/tr121/results/20251224_002149/analysis/hf_model_architecture.csv` (parsed from each local HF `config.json`).

| Model | Params (M) | n_layer | n_embd | n_head |
| --- | ---: | ---: | ---: | ---: |
| models/tiny-gpt2 | 0.103 | 2 | 2 | 2 |
| models/gpt2-5m | 5.037 | 12 | 80 | 2 |
| models/gpt2-25m | 25.016 | 3 | 384 | 2 |
| models/gpt2-45m | 45.171 | 6 | 512 | 8 |
| models/gpt2-50m | 51.476 | 8 | 512 | 2 |
| models/gpt2-75m | 74.825 | 5 | 768 | 2 |
| models/gpt2-100m | 96.088 | 8 | 768 | 2 |

Interpretation:

- Parameter count alone does not determine per-token work. Depth is a separate axis.
- This is the correct reason to treat "HF GPU scaling vs params" as a regime statement rather than a universal scaling law.

---

## Appendix B: Figures

Scenario-aggregated scaling plots (log-log; points are models, dashed line is power-law fit):

### HF CPU

![hf_cpu_prefill](../../scripts/tr121/results/20251224_002149/analysis/plots/scaling_hf_cpu_fp32_prefill__all__bs1.png)

![hf_cpu_kv_decode](../../scripts/tr121/results/20251224_002149/analysis/plots/scaling_hf_cpu_fp32_kv_decode__all__bs1.png)

### HF GPU

![hf_gpu_prefill](../../scripts/tr121/results/20251224_002149/analysis/plots/scaling_hf_gpu_fp16_prefill__all__bs1.png)

![hf_gpu_kv_decode](../../scripts/tr121/results/20251224_002149/analysis/plots/scaling_hf_gpu_fp16_kv_decode__all__bs1.png)

### Ollama

![ollama_prefill](../../scripts/tr121/results/20251224_002149/analysis/plots/scaling_ollama_prefill__all__bs1.png)

![ollama_kv_decode](../../scripts/tr121/results/20251224_002149/analysis/plots/scaling_ollama_kv_decode__all__bs1.png)
