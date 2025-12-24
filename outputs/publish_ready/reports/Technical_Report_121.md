# Technical Report 121 (Superseded Draft): Model Scaling Study
## How inference behavior changes from ~5M to ~20B parameters (HF + Ollama)

**Project:** Banterhearts LLM Performance Research  
**Date:** 2025-12-23  
**Author:** Research Team  
**Report Type:** Scaling-law analysis + bottleneck characterization (artifact-backed)  
**Related Work:** [TR117](Technical_Report_117.md) (backend matrix), [TR118_v2.2](Technical_Report_118_v2.2.md) (pipeline rigor), [TR120](Technical_Report_120.md) (compile paradox), [TR122](../../scripts/tr122/README.md) (planned resource profiling deep dive)

---

## Status (read this first)

This document is retained as the original TR121 pipeline draft. It is **superseded** by the publish-ready report:

- `PublishReady/reports/Technical_Report_121v1.md`

If you are looking for the definitive TR121 analysis (methodology + results + business impact + artifacts), use `PublishReady/reports/Technical_Report_121v1.md`.

## Executive Summary (v1)

TR121 answers a production planning question:

> As model size increases, what changes first: latency, tail risk, or feasibility (memory wall), and which runtime regime dominates?

This report **builds the TR121 experimentation pipeline** and establishes a first, reproducible scaling harness that:

- measures **prefill** and **KV-cached decode** separately (TR120-style), and
- spans model sizes from **~5M (local HF GPT-2 variants)** to **~20B (Ollama models)** on the same machine.

### Status and publishing posture

TR121 v1 is **pipeline-complete and ready for a full sweep**, but it is **not yet publish-ready** as a definitive scaling claim until:

1. the full matrix run is executed (not a smoke subset), and
2. the report is updated with the resulting tables/plots + conclusions.

The purpose of this v1 document is to:

- make the harness and artifact structure stable,
- define scaling metrics precisely,
- and make the follow-on "full sweep -> publishable TR121" straightforward.

---

## Table of Contents

1. [Research Context & Objectives](#1-research-context--objectives)
2. [Methodology (What Is Measured)](#2-methodology-what-is-measured)
3. [Experiment Design](#3-experiment-design)
4. [Artifact Structure & Reproducibility](#4-artifact-structure--reproducibility)
5. [Analysis (Scaling Fits)](#5-analysis-scaling-fits)
6. [Limitations & Next Steps](#6-limitations--next-steps)

---

## 1. Research Context & Objectives

TR117 established backend rankings on a single small model, with a known model skew. TR121 exists to answer:

- Are those rankings stable as model size grows?
- At what size does the system move from "launch/overhead dominated" to "kernel/throughput dominated" to "memory wall dominated"?
- When do "policy decisions" (quantization, batching, routing, compilation) become mandatory rather than optional?

### 1.1 Scope of v1

TR121 is explicitly a two-family scaling study:

- **HF local models (5M-124M)** measured via a controlled PyTorch harness.
- **Ollama models (270M-20B)** measured via Ollama's `/api/generate` counters.

These are not identical runtimes; TR121 v1 focuses on:

1. consistent **phase definitions** (prefill vs decode),
2. a consistent **decode token budget** (`gen_tokens`),
3. artifact-backed measurements that can be extended.

---

## 2. Methodology (What Is Measured)

TR121 adopts TR120's phase split:

- **Prefill:** a single forward pass over the prompt with `use_cache=True`.
- **KV decode:** a fixed-length decode loop using KV cache (`past_key_values`) for `gen_tokens` steps.
- **End-to-end KV:** prefill + KV decode.

### 2.1 HF (local) measurement

HF models are measured by running the model directly in eval/no-grad mode:

- Prefill: `model(input_ids, attention_mask, use_cache=True)`
- KV decode: repeated single-token steps using `past_key_values`

For CUDA devices, both wall-clock and CUDA-event timing are recorded.

### 2.2 Ollama measurement

Ollama models are measured by calling:

- `POST /api/generate` with `options.num_predict = gen_tokens`

The response includes:

- `prompt_eval_count`, `prompt_eval_duration` (prefill analog)
- `eval_count`, `eval_duration` (decode analog)
- `load_duration` (model load / cold-start component)

TR121 treats these counters as the phase source-of-truth for Ollama runs.

### 2.3 Throughput definition

TR121 reports `tokens_per_s` as:

- `tokens_total / latency_s` for each mode.

This is valid within each runtime family (HF vs Ollama) given consistent token accounting.

---

## 3. Experiment Design

### 3.1 Config (source of truth)

Default config:

- `scripts/tr121/configs/scaling.yaml`

Contains:

- scenarios (prompt strings)
- decode token budget (`gen_tokens`)
- repetitions and warmups
- HF model list (local paths) with `params_millions`
- Ollama model list with `params_millions`

### 3.2 Output structure

Each run writes:

- `manifest.json` (environment + run config)
- `runs.jsonl` (one JSON record per measurement)
- `metrics.csv` (flat table of all records)
- `analysis/*` (generated by `scripts/tr121/analyze_scaling.py`)

---

## 4. Artifact Structure & Reproducibility

### 4.1 Run the sweep

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/scaling.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/<RUN_ID>
python scripts/tr121/generate_report.py --run-dir scripts/tr121/results/<RUN_ID>
```

### 4.2 Key artifacts

- Runner: `scripts/tr121/run_scaling.py`
- Analysis: `scripts/tr121/analyze_scaling.py`
- Generated report draft: `scripts/tr121/generate_report.py`
- Config: `scripts/tr121/configs/scaling.yaml`

---

## 5. Analysis (Scaling Fits)

TR121 fits a log-log power law per `{backend, mode, scenario}`:

- `log10(latency_ms) = a + b * log10(params_millions)`

The analysis outputs:

- `analysis/summary_by_model_backend_mode.csv`
- `analysis/scaling_fits.csv`
- `analysis/plots/scaling_*.png`

Interpretation rule:

- Slope `b` approximates the scaling exponent for the measured regime (prompt length + token budget + runtime).
- R^2 indicates how well a simple power law explains observed behavior.

---

## 6. Limitations & Next Steps

### 6.1 Limitations (v1)

1. TR121 v1 is a **pipeline + definitions** milestone; it does not yet embed a full "publishable" sweep in this report.
2. HF and Ollama use different runtimes; cross-family comparisons must be framed as "regime behavior," not apples-to-apples backend ranking.
3. Resource profiling (VRAM, RSS, power) is not yet first-class in TR121; it is planned as TR122.

### 6.2 Next steps (to make TR121 publish-ready)

1. Run the full matrix in `scripts/tr121/configs/scaling.yaml` (or an expanded config).
2. Add a model-family coherence sweep (e.g., Gemma family on HF and Ollama) if weights are available locally.
3. Add memory wall evidence (peak VRAM, paging) and correlate with latency inflections.
4. Add a decode-length sweep (8/32/64/128/256) for at least one family to show scaling stability vs token budget.
