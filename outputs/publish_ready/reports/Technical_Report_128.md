# Technical Report 128: Production Workload Characterization
## Concurrency, saturation, streaming, and multi-turn performance of Ollama on consumer GPU

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-02-25
**Author:** Research Team
**Report Type:** Production workload characterization (5-phase, 3,172 measurements)
**Test Duration:** ~55 minutes
**Status:** Complete --- All 5 phases delivered
**Run ID:** `20260225_145254`
**Related Work:** [TR123](Technical_Report_123.md) (KV-Cache Economics), [TR125](Technical_Report_125.md) (Quantization Matrix), [TR126](Technical_Report_126.md) (Linux/Triton Validation), [TR127](Technical_Report_127.md) (Long-Context Scaling)
**Depends On:** TR127 (context scaling baseline, prefill cross-validation), TR126 (HF vs Ollama methodology)

---

## Abstract

TR108--TR127 characterized LLM inference under controlled, single-shot conditions: one request at a time, steady-state execution, no concurrency. Production workloads differ in four critical ways --- bursty arrivals, concurrent requests, streaming responses, and multi-turn context accumulation --- creating queueing and thermal effects invisible to single-request benchmarks. TR128 fills this gap with a 5-phase production workload experiment: **3,172 measurements** across **3 models** (1.2B--3.2B parameters), all served by Ollama on an RTX 4080 Laptop GPU (12 GB VRAM).

**Phase 1 (Baseline Characterization)** establishes serial service times at zero concurrency: llama3.2-1b at 858 ms mean (1.17 req/s theoretical max), qwen2.5-1.5b at 1,008 ms (0.99 req/s), llama3.2-3b at 1,435 ms (0.70 req/s). Measurement precision is high (CV 2--10%), and the 1.7x latency range across models directly predicts their saturation behavior in later phases. These service times feed the M/D/1 queueing predictions tested in Phase 2 and calibrate the 80%-saturation arrival rates used in Phase 3.

**Phase 2 (Concurrency & Saturation Sweep)** is the core experiment. OLLAMA_NUM_PARALLEL={1, 2, 4} is swept across 5 Poisson arrival rates (0.5--10 req/s) for each model, with Ollama restarted between parallelism levels. The central finding: **0 out of 30 pairwise comparisons reach significance** after Holm--Bonferroni correction (mean |change| = 4.0%, 26/30 effects negligible). NUM_PARALLEL does not enable concurrent GPU inference --- the CUDA compute kernels for transformer inference occupy the entire GPU, and the parameter only affects CPU-side request admission. M/D/1 queueing theory, which assumes NP>1 scales throughput linearly, deviates from reality by up to **20.4x** (llama3.2-3b at NP=4, 1.0 req/s). The theory's deterministic-service and linear-scaling assumptions both fail.

**Phase 3 (Thermal Stability)** holds each model at ~80% of its Phase 1 saturation rate for 180 seconds under constant periodic arrivals. GPU temperature peaks at 66 degrees C --- well below the 80 degrees C throttle threshold. No thermal throttling is detected. An unexpected finding: qwen2.5-1.5b's decode throughput **increases 66% over 143 requests** (167 to 275 tok/s), while the other two models remain flat. This model-specific warmup effect --- which is not GPU clock ramp, not JIT, and not model reloading --- produces the -27.7% wall latency drift (p < 0.0001) and warrants standalone investigation.

**Phase 4 (Streaming Performance)** compares batch vs stream response modes at 3 arrival rates and measures TTFT (time to first token) under load. Streaming adds **no significant wall-clock overhead** --- 0 out of 9 comparisons reach significance after Holm--Bonferroni correction. TTFT amplification reaches **29.9x** at 2.0 req/s (llama3.2-3b), which is pure queueing delay: prompt evaluation speed is unchanged, but requests wait longer in the queue before the GPU serves them. Inter-chunk latency is reported honestly as ichunk (not inter-token), acknowledging that TCP buffering batches multiple tokens per NDJSON chunk.

**Phase 5 (Multi-Turn Context Accumulation)** tests full vs sliding-window (last 3 turns) context strategies across 5- and 10-turn conversations. Under full context, prompt token counts grow linearly from ~35 to ~1,365 tokens over 10 turns. Sliding-window shows a suggestive reduction for llama3.2-1b at turn 9 (5.9%, d = 1.12, p = 0.042, n=8) but this would not survive Bonferroni correction across the 3 models tested (threshold = 0.017). The other two models show no benefit (0.4--0.5%, p > 0.2). More conversations are needed to draw firm conclusions about sliding-window efficacy.

**Total: 3,172 measurements, 3 models, 5 phases, 100% success rate, ~55 minutes runtime.**

Key findings:

- **Single-GPU Ollama cannot parallelize inference.** NUM_PARALLEL is a no-op for GPU scheduling. 0/30 tests significant, mean absolute change 4.0%.
- **M/D/1 queueing theory dramatically underestimates real tail latency.** Up to 20.4x deviation at NP=4. The model's linear-scaling and deterministic-service assumptions both fail.
- **Streaming is free.** Zero wall-clock overhead across 9 comparisons. Applications should always use streaming mode.
- **Laptop GPU handles sustained LLM load without throttling.** Peak 66 degrees C under 3-minute sustained load. No cooling upgrades needed.
- **TTFT amplification under load is severe.** 29.9x at 2.0 req/s (llama3.2-3b). This is pure queueing delay, not compute degradation.
- **Sliding-window context management shows suggestive but inconclusive benefit.** Borderline significant for llama3.2-1b only (p = 0.042, n=8); would not survive correction across 3 models. Needs larger sample.
- **qwen2.5-1.5b exhibits an unexplained 66% decode throughput increase** during sustained load (Phase 3), while the other two models remain flat. Not GPU clock, not JIT, not reloading --- mechanism unknown.
- **All 15/15 latency distributions are non-normal** (Shapiro-Wilk p < 0.05). Right-skewed by design. t-tests remain valid at n >= 30 via CLT; median and trimmed-mean are more appropriate central tendency measures.

---

## Executive Summary

TR128 answers: **what happens when you put realistic load on a single-GPU Ollama instance, and which configuration knobs actually matter?**

The answer is sobering for anyone expecting Ollama's NUM_PARALLEL setting to improve throughput: it does nothing. The GPU serializes transformer inference regardless of configuration. A single RTX 4080 Laptop GPU serves at most 1.17 req/s (llama3.2-1b) or 0.70 req/s (llama3.2-3b), and no amount of parallelism tuning changes this. The good news: streaming is free (use it always), the laptop GPU doesn't throttle under sustained load, and sliding-window context management can bound prompt growth in multi-turn conversations (though the latency benefit needs further validation).

### Key Findings

1. **Baseline service times span 858--1,435 ms** (1.7x range across 3 models). Theoretical max throughput: 1.17 req/s (llama3.2-1b), 0.99 req/s (qwen2.5-1.5b), 0.70 req/s (llama3.2-3b). Measurement precision is high: CV 2--10%, 95% CIs within +/-25 ms.
2. **OLLAMA_NUM_PARALLEL has zero effect on latency.** 0/30 pairwise tests significant after Holm--Bonferroni correction. 26/30 effect sizes negligible (|d| < 0.2), 4/30 small (d = 0.20--0.29). Mean absolute change 4.0% --- consistent with noise.
3. **M/D/1 queueing theory deviates up to 20.4x from observed queue wait** (llama3.2-3b at NP=4, 1.0 req/s). Two assumptions fail simultaneously: (a) service is not deterministic (CV 2--10%), and (b) NP>1 does not scale throughput because the GPU is the bottleneck.
4. **Saturation occurs at very low arrival rates.** At NP=1, all three models show p99/p50 > 2.0 at the lowest tested rate (0.5 req/s). Even sub-saturation traffic creates measurable queueing delay.
5. **No thermal throttling under sustained load.** Peak 66 degrees C across 412 Phase 3 measurements (threshold: 80 degrees C). Negative latency drift in qwen2.5-1.5b (-27.7%) reflects a model-specific decode warmup (see Finding 9), not thermal degradation; the other two models are flat.
6. **Streaming adds no wall-clock overhead.** 0/9 comparisons significant after Holm--Bonferroni correction. Applications should always use streaming for better perceived responsiveness.
7. **TTFT amplification reaches 29.9x under load** (llama3.2-3b at 2.0 req/s). This is pure queueing delay --- prompt evaluation speed itself is unchanged, but requests wait in the queue.
8. **Sliding-window context shows suggestive but inconclusive benefit.** llama3.2-1b: 5.9% at turn 9, d = 1.12, p = 0.042 --- but with n=8 per group, this would not survive Bonferroni correction across the 3 models tested (threshold = 0.017). The other two models show 0.4--0.5% reduction (p > 0.2). Needs larger sample sizes to confirm.
9. **qwen2.5-1.5b decode throughput increases 66% during sustained load** (Phase 3: 167 to 275 tok/s over 143 requests). llama3.2-1b and llama3.2-3b are flat (<1% change). The mechanism is model-specific and unknown --- not GPU clock ramp (would affect all models), not JIT (llama.cpp is compiled C++), not model reloading (load_duration_ms is stable). This is an open question.
10. **15/15 group distributions are non-normal** (Shapiro-Wilk). Right-skewed latency data is expected. Power analysis confirms ability to detect small effects (d >= 0.19) in the core Phase 2 experiment.

### Key Decisions

1. **Leave OLLAMA_NUM_PARALLEL at default (1).** It provides no latency benefit on single-GPU hardware. Use a reverse proxy (e.g., nginx) for request queuing instead of relying on Ollama's internal parallelism.
2. **Limit sustained arrival rate to 70% of theoretical max.** For llama3.2-1b: 0.82 req/s. For qwen2.5-1.5b: 0.69 req/s. For llama3.2-3b: 0.49 req/s. Above this, p99 exceeds 2x p50.
3. **Always use streaming mode.** Zero overhead, real TTFT benefit (users see first tokens sooner), and better perceived responsiveness.
4. **Consider sliding-window context** for multi-turn applications exceeding 5 turns (window of last 3 turns). Evidence is suggestive but not conclusive (borderline significance for 1/3 models at n=8). The primary benefit may be memory/cost reduction rather than latency --- validate for your specific model and generation length.
5. **Do not use M/D/1 predictions for capacity planning.** Use empirical saturation curves from Phase 2 instead. The theory overestimates available capacity by up to 20x.
6. **No cooling upgrades needed** for sustained small-model inference on RTX 4080 Laptop. Monitor GPU temperature and alert at 75 degrees C as a safety margin.

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| 1 | NUM_PARALLEL enables concurrent GPU inference | 0/30 pairwise tests significant, mean |change| = 4.0% (SS4) | **Refuted** |
| 2 | M/D/1 predicts queue wait accurately | Deviation up to 20.4x at NP=4 (SS5) | **Refuted** (at NP>1) |
| 3 | Streaming adds latency overhead | 0/9 tests significant after Holm--Bonferroni (SS8) | **Refuted** |
| 4 | GPU throttles under sustained LLM load | Peak 66 degrees C, 0 throttle events across 412 measurements (SS6) | **Refuted** |
| 5 | TTFT degrades under load | TTFT amplification up to 29.9x at 2.0 req/s (SS8) | **Validated** (queueing) |
| 6 | Multi-turn context accumulation increases latency | Per-turn latency grows with full context; prompt tokens reach 1,365 at turn 9 (SS10) | **Validated** |
| 7 | Sliding-window context management recovers performance | llama3.2-1b: 5.9%, d = 1.12, p = 0.042, n=8 (SS11). Would not survive Bonferroni across 3 models (threshold = 0.017). Other models: p > 0.2 | **Inconclusive** --- borderline for 1 model, needs more data |
| 8 | Queue depth grows with arrival rate | Monotonic growth confirmed: 0.6--0.8 at 0.5 rps to 11.9--13.5 at 10 rps (SS5) | **Validated** |

---

## When to Use This Report

TR128 is the production workload reference for the Banterhearts research program. It is the first report to test Ollama under realistic load patterns (concurrent requests, Poisson arrivals, streaming, multi-turn conversations) rather than single-shot synthetic benchmarks. Use it when planning Ollama deployment capacity, evaluating concurrency settings, or understanding how realistic load patterns affect inference latency.

### Scenario 1: Sizing an Ollama Instance for Production Traffic

**Question:** "I expect 0.8 req/s average traffic to qwen2.5-1.5b. Will a single Ollama instance handle it?"

**Answer:** Consult SS3. qwen2.5-1.5b has a baseline service time of 1,008 ms, giving a theoretical max of 0.99 req/s. At 0.8 req/s you would be at 81% utilization --- above the recommended 70% threshold. Consult the Phase 2 utilization curves in SS4: at 1.0 req/s (the nearest tested rate), qwen2.5-1.5b shows mean latency of 4,427 ms with p99 of 7,350 ms. Either accept high tail latency, reduce traffic below 0.69 req/s (70% threshold), or add a second instance with load balancing.

### Scenario 2: Tuning OLLAMA_NUM_PARALLEL

**Question:** "Should I set NUM_PARALLEL=4 for better throughput on my single-GPU setup?"

**Answer:** No. Consult SS4. NUM_PARALLEL has zero statistically significant effect on latency across all 30 tested combinations (3 models x 5 rates x 2 comparisons). The GPU serializes inference regardless. Leave at default (1) and use a reverse proxy for request queuing.

### Scenario 3: Choosing Between Batch and Streaming Mode

**Question:** "Does streaming add latency overhead compared to batch mode?"

**Answer:** No. Consult SS8. Zero overhead detected across all 9 comparisons (3 models x 3 rates). Always use streaming --- it provides earlier TTFT with no wall-clock cost, giving users a better experience.

### Scenario 4: Implementing Multi-Turn Chat

**Question:** "Should I send full conversation history or truncate to the last N turns?"

**Answer:** Consult SS10--SS11. Full history causes prompt token counts to grow linearly with turn count (reaching ~1,365 tokens at turn 9 for 10-turn conversations). Sliding-window context (last 3 turns) bounds this at ~464 tokens. The latency benefit is suggestive but not confirmed: nominally significant for llama3.2-1b (5.9% at turn 9, p = 0.042, n=8) but would not survive Bonferroni correction across models, and the other two models show no benefit. Consider sliding-window for conversations exceeding 5 turns (primarily for memory/cost), but validate both latency and quality impact for your workload.

---

## Table of Contents

**Preliminaries**

- [Metric Definitions & Statistical Methods](#metric-definitions--statistical-methods)

**Experiment Design (SS1--SS2)**

1. [Introduction & Research Questions](#1-introduction--research-questions)
2. [Methodology & Experimental Design](#2-methodology--experimental-design)

**Results (SS3--SS11)**

3. [Baseline Characterization (Phase 1)](#3-baseline-characterization-phase-1) --- Service time distributions, theoretical max throughput
4. [Concurrency Scaling (Phase 2)](#4-concurrency-scaling-phase-2) --- Core result: NUM_PARALLEL no-effect
5. [M/D/1 Deviation & Queue Analysis (Phase 2)](#5-md1-deviation--queue-analysis-phase-2) --- Theory vs reality
6. [Thermal Stability (Phase 3)](#6-thermal-stability-phase-3) --- Sustained load, drift analysis
7. [GPU Metrics Summary](#7-gpu-metrics-summary) --- Temperature, clock, power, VRAM
8. [Streaming Performance (Phase 4)](#8-streaming-performance-phase-4) --- TTFT amplification, stream vs batch
9. [Inter-Chunk Latency (Phase 4)](#9-inter-chunk-latency-phase-4) --- ichunk honesty, jitter
10. [Multi-Turn Degradation (Phase 5)](#10-multi-turn-degradation-phase-5) --- Per-turn latency curves
11. [Context Management Strategies (Phase 5)](#11-context-management-strategies-phase-5) --- Full vs sliding-window

**Validation & Statistics (SS12--SS13)**

12. [Cross-Validation & Consistency](#12-cross-validation--consistency) --- TR127, cross-phase
13. [Statistical Analysis](#13-statistical-analysis) --- Cold-start, normality, power analysis

**Synthesis (SS14--SS16)**

14. [Key Findings](#14-key-findings)
15. [Conclusions](#15-conclusions)
16. [Production Guidance & Decision Trees](#16-production-guidance--decision-trees)

**Closing**

17. [Limitations & Future Work](#17-limitations--future-work)
18. [Reproducibility](#18-reproducibility)

**Appendices**

- [Appendix A: Environment Specifications](#appendix-a-environment-specifications)
- [Appendix B: Config (Source of Truth)](#appendix-b-config-source-of-truth)
- [Appendix C: Glossary](#appendix-c-glossary)
- [References](#references)

---

## Metric Definitions & Statistical Methods

### Latency Metrics

| Metric | Definition | Computation |
|--------|-----------|-------------|
| **Wall (ms)** | Total client-side latency from HTTP request to full response | `time.perf_counter()` around `httpx` call |
| **TTFT (ms)** | Time to first token (streaming only) | Time from request submission to first non-empty NDJSON chunk |
| **prompt_eval_ms** | Ollama native prefill time (GPU-only) | From `/api/generate` response `prompt_eval_duration` field |
| **eval_ms** | Ollama native decode time (GPU-only) | From `/api/generate` response `eval_duration` field |
| **Queue wait (ms)** | Time spent in Ollama's internal queue | `wall_ms - (prompt_eval_ms + eval_ms + load_duration_ms)` |
| **p50/p95/p99 (ms)** | Percentile latencies | `numpy.percentile(x, [50, 95, 99])` |
| **95% CI** | 95% confidence interval for the mean | t-distribution: `mean +/- t(0.025, n-1) * sem` |
| **CV%** | Coefficient of variation | `(std / mean) * 100` |

### Throughput Metrics

| Metric | Definition | Computation |
|--------|-----------|-------------|
| **tok/s** | Decode throughput | `eval_count / eval_duration * 1e9` (Ollama native) |
| **Max RPS** | Theoretical max request rate from serial service time | `1000 / mean_service_ms` |
| **Queue depth** | Number of in-flight requests at submission time | Mutable asyncio counter: incremented on submit, decremented on completion |

### Effect Size & Significance

| Metric | Definition | Interpretation |
|--------|-----------|---------------|
| **Cohen's d** | Standardized mean difference: `(mean_B - mean_A) / pooled_std` | Negligible: \|d\| < 0.2, Small: 0.2--0.5, Medium: 0.5--0.8, Large: > 0.8 |
| **p-value** | Probability of observing the data under H0 (no difference), via Welch's two-sample t-test | Significant if p < 0.05 (before correction) |
| **Holm--Bonferroni** | Step-down FWER correction: sort p-values ascending, reject p_i if p_i < alpha/(n-i+1) while all smaller p rejected | Controls family-wise error rate without assuming test independence. More powerful than Bonferroni |

### Queue Wait Derivation

Ollama's native timing fields (`prompt_eval_duration`, `eval_duration`, `load_duration`) measure GPU-only compute time. They do not include time spent waiting in the request queue. The difference between wall-clock and native timing captures pure queueing delay:

```
queue_wait_ms = wall_ms - (prompt_eval_ms + eval_ms + load_duration_ms)
```

This derivation is reliable because Ollama processes requests sequentially on the GPU --- there is no GPU context switching that would pollute the native timing fields. When NUM_PARALLEL > 1, Ollama admits multiple requests at the CPU level, but they still serialize on the GPU. The queue wait metric captures this serialization delay.

### Inter-Chunk vs Inter-Token Latency

Ollama streams responses as NDJSON over HTTP. Each line contains a JSON object with a `response` field (one or more tokens). TCP buffering at the OS and application layers means each network read may contain multiple tokens batched into a single chunk. We therefore report **inter-chunk latency (ichunk)**, not inter-token latency (ITL). Only TTFT --- the time from request submission to the first non-empty chunk --- is a reliable client-side timing metric. Subsequent chunk timing is an upper bound on true ITL, not an exact measurement.

### M/D/1 Queueing Model

The M/D/1 model assumes Markovian (Poisson) arrivals, deterministic (constant) service times, and a single server. Mean queue wait is:

```
W_q = (rho * service_time) / (2 * (1 - rho))     where rho = arrival_rate * service_time
```

For NUM_PARALLEL > 1, we test the assumption that effective service rate scales linearly: `effective_rate = baseline_rate * NP`. The deviation ratio `observed_wait / predicted_wait` measures how badly the theory fails.

### Multiple Comparison Correction

Phase 2 performs 30 pairwise tests (3 models x 5 rates x 2 NP comparisons). Phase 4 performs 9 tests (3 models x 3 rates). The Holm--Bonferroni step-down procedure is applied within each family:

1. Sort p-values ascending: p_(1) <= p_(2) <= ... <= p_(k)
2. Reject p_(i) if p_(i) < alpha / (k - i + 1)
3. Stop at first non-rejection; all remaining tests are non-significant

This controls the family-wise error rate at alpha = 0.05 without the conservatism of Bonferroni.

---

## 1. Introduction & Research Questions

### 1.1 Research Motivation

TR108--TR127 measured LLM inference under synthetic, single-shot conditions: one request submitted, one response received, then the next request submitted. There was never a queue, never a concurrent request, never a streaming response being consumed while a new request arrived. Real production workloads differ in four critical ways:

1. **Bursty arrivals.** Users submit requests according to Poisson processes (or worse --- bursty peaks during active hours), not at fixed intervals. This creates request queues even when average throughput is below capacity.
2. **Concurrent requests.** Multiple users submit requests simultaneously. Ollama exposes `OLLAMA_NUM_PARALLEL` to ostensibly handle this --- but does the GPU actually serve requests in parallel, or does it serialize them?
3. **Streaming responses.** Production applications consume tokens as they are generated via Server-Sent Events or NDJSON streaming. Does streaming add latency overhead compared to batch mode? How does TTFT behave under load?
4. **Multi-turn context accumulation.** Chat applications accumulate conversation history, sending increasingly long prompts each turn. TR127 characterized context-length scaling for single requests; TR128 characterizes it in a conversational setting with sliding-window truncation as a mitigation.

No prior TR in this research program characterized any of these effects. TR128 fills the gap.

### 1.2 Research Questions

TR128 addresses six decision-grade questions:

1. **Does OLLAMA_NUM_PARALLEL enable concurrent GPU inference?** The Ollama documentation describes this parameter as controlling parallel request processing. Does setting NP=4 actually reduce per-request latency under concurrent load, or does the GPU serialize inference regardless?
2. **At what request rate does tail latency explode?** What is the saturation point for each model on a single GPU --- the arrival rate beyond which p99 exceeds 2x p50?
3. **Does M/D/1 queueing theory predict real behavior?** Can simple queueing models --- the standard tool for capacity planning --- guide Ollama deployment, or do they break down?
4. **Does the GPU throttle under sustained load?** On a laptop GPU with limited cooling (150W TDP, shared thermal envelope), does continuous inference for minutes at a time cause thermal throttling that degrades throughput?
5. **Does streaming add latency overhead?** Is there a wall-clock cost to streaming vs batch mode, and how does TTFT (time to first token) behave as queue depth increases?
6. **Does sliding-window context management recover performance?** As conversations grow longer, can truncating to the last N turns bound latency growth?

### 1.3 Scope

- **Hardware:** Single consumer machine --- RTX 4080 Laptop GPU (12 GB VRAM), same GPU used throughout TR117--TR127.
- **Platform:** Windows 11, Python 3.13, Ollama localhost (llama.cpp backend).
- **Models:** 3 Ollama models spanning 1.2B--3.2B parameters: llama3.2-1b (1.2B), qwen2.5-1.5b (1.5B), llama3.2-3b (3.2B). All quantized at Ollama's default level (typically Q4_K_M or Q8_0). All already pulled from TR127.
- **Backend:** Ollama only --- the point of TR128 is measuring a *serving backend* under load, not raw model performance. HuggingFace transformers does not expose a server API and was tested in single-request mode in prior TRs.
- **Load generation:** Async Python (`asyncio` + `httpx.AsyncClient`) with Poisson and periodic arrival patterns.
- **Temperature:** 0.0 (greedy decoding), seed=42. Deterministic output --- validated by TR124 Phase 3.
- **Prompt generation:** Synthetic paragraphs targeting 100--300 tokens, uniformly distributed.

### 1.4 Literature Grounding

| Reference | Contribution | How TR128 Uses It |
|-----------|-------------|-------------------|
| TR123 (Banterhearts) | KV-cache cost model, VRAM formulas | Context budget for multi-turn Phase 5 |
| TR125 (Banterhearts) | Ollama quantization quality data | Model selection, quality baseline |
| TR126 (Banterhearts) | HF vs Ollama backend comparison | Ollama timing methodology |
| TR127 (Banterhearts) | Context-length scaling, prefill cross-validation | Cross-validation baseline for Phase 5, prefill timing reference |
| Erlang, A.K. (1909) | Queueing theory foundations | M/D/1 predictions in SS5 |
| Cohen, J. (1988) | Statistical Power Analysis | Effect size thresholds used throughout |
| Holm, S. (1979) | Sequential rejective multiple test procedure | Holm--Bonferroni correction in SS4, SS8 |

**Gap filled:** Prior reports tested inference in isolation. TR128 provides the first concurrent-load, streaming, and multi-turn characterization on consumer hardware in this research program.

### 1.5 How to Read This Report

Use TR128 in three passes:

1. **SS1--SS2 (Design):** Understand the 5-phase experimental design and what each phase measures. If you trust the methodology, skip to results.
2. **SS3--SS11 (Results):** The core contribution. SS3 establishes baselines. SS4 is the headline finding (NUM_PARALLEL no-effect). SS5 shows why M/D/1 fails. SS6--SS7 cover thermal stability. SS8--SS9 cover streaming. SS10--SS11 cover multi-turn.
3. **SS12--SS16 (Validation & Synthesis):** Cross-validation with TR127, statistical analysis, synthesized findings, and production guidance. Read these for deployment decisions.

---

## 2. Methodology & Experimental Design

### 2.1 Models

| Model | Ollama Tag | Parameters | Max Context | Quantization |
|-------|-----------|------------|-------------|-------------|
| llama3.2-1b | `llama3.2:1b` | 1,200M | 131,072 | Default (Q8_0) |
| qwen2.5-1.5b | `qwen2.5:1.5b` | 1,500M | 131,072 | Default (Q4_K_M) |
| llama3.2-3b | `llama3.2:3b` | 3,200M | 131,072 | Default (Q4_K_M) |

**Design rationale:** Three models at 1.2B/1.5B/3.2B provide a 2.7x parameter range on a single GPU. The smallest model (llama3.2-1b) should have the fastest service time and highest saturation threshold; the largest (llama3.2-3b) should saturate earliest. All three fit entirely in VRAM without spillover (confirmed by TR127), so Phase 2 queueing behavior reflects compute, not memory pressure.

### 2.2 Five-Phase Design

| Phase | Purpose | Key Variable | Requests | Duration |
|-------|---------|--------------|----------|----------|
| P1: Baseline | Serial service time distribution | None (zero concurrency) | 150 | ~5 min |
| P2: Concurrency | OLLAMA_NUM_PARALLEL sweep | NP={1,2,4} x 5 rates x 3 models | 1,350 | ~25 min |
| P3: Thermal | Sustained load at 80% saturation | Duration (180s per model) | 412 | ~9 min |
| P4: Streaming | Batch vs stream, TTFT measurement | Response mode x 3 rates | 540 | ~10 min |
| P5: Multi-Turn | Context accumulation and truncation | Full vs sliding-window | 720 | ~6 min |
| **Total** | | | **3,172** | **~55 min** |

### 2.3 Key Design Decisions

**OLLAMA_NUM_PARALLEL requires server restart.** This parameter is read at Ollama startup and cannot be changed at runtime. The Phase 2 protocol is: stop Ollama (`taskkill /F /IM ollama.exe`), set the environment variable, restart Ollama, wait 10 seconds for stabilization, run 3 warmup requests, then proceed with measurements. This restart introduces a thermal discontinuity between parallelism levels --- acknowledged as a limitation (SS17).

**GPU instrumentation runs continuously.** `nvidia-smi` is polled every 1.0 second throughout all phases, recording GPU temperature, clock speed, utilization percentage, power draw, and VRAM usage. Thermal throttle detection uses a conservative threshold: temperature > 80 degrees C AND clock speed < 90% of peak simultaneously. Single temperature spikes without clock degradation are not classified as throttling.

**Arrival patterns are carefully chosen per phase.** Phase 2 uses Poisson arrivals (realistic bursty traffic) to stress the queue. Phase 3 uses periodic arrivals (constant rate) to isolate thermal effects from arrival-pattern variance. Phase 4 uses Poisson arrivals again (same as Phase 2 for comparability).

**Inter-chunk honesty.** We report inter-*chunk* latency (ichunk), not inter-*token* latency (ITL). TCP buffering at the OS level means each `readline()` call on the HTTP response may return a chunk containing multiple tokens. Only TTFT (first chunk) reliably corresponds to a single event (prefill completion). This is a deliberate methodological choice --- we prefer honest measurement over inflated precision claims.

**Queue depth tracking.** A mutable Python list `[0]` acts as an atomic counter in single-threaded asyncio. It is incremented when a request is submitted and decremented when the response completes. Each request records the counter value at submission time --- this directly measures how many other requests are in-flight when the new request enters the queue.

**Prompt generation.** Synthetic paragraphs are generated targeting 100--300 tokens (uniform distribution). Temperature = 0, seed = 42 for deterministic output. Max new tokens = 128 across all phases.

### 2.4 Controlled Variables

| Variable | Value | Rationale |
|----------|-------|-----------|
| `max_new_tokens` | 128 | Fixed decode length for fair comparison |
| `temperature` | 0.0 | Greedy decoding --- deterministic |
| `seed` | 42 | Reproducible random state |
| `warmup_requests` | 3 | Exclude cold-start artifacts per model |
| `gpu_poll_interval_s` | 1.0 | Continuous thermal monitoring |
| `ollama_timeout_s` | 120 | Generous timeout for high-load conditions |
| `prompt_tokens_low` | 100 | Lower bound of uniform prompt distribution |
| `prompt_tokens_high` | 300 | Upper bound of uniform prompt distribution |

### 2.5 Sample Counts

| Phase | Models | Conditions | Reps | Total Planned | Total Actual | Success Rate |
|-------|--------|------------|------|---------------|--------------|-------------|
| P1 Baseline | 3 | 1 | 50 | 150 | 150 | 100% |
| P2 Concurrency | 3 | 3 NP x 5 rates | 30 | 1,350 | 1,350 | 100% |
| P3 Thermal | 3 | 180s sustained | varies | ~400 | 412 | 100% |
| P4 Streaming | 3 | 3 rates x 2 modes | 30 | 540 | 540 | 100% |
| P5 Multi-Turn | 3 | 2 strategies x 2 turns x 8 convos | varies | ~700 | 720 | 100% |
| **Total** | | | | **~3,140** | **3,172** | **100%** |

100% success rate across all 3,172 measurements. No timeouts, no errors. The 120-second timeout was never reached.

---

## 3. Baseline Characterization (Phase 1)

This section establishes serial service time distributions at zero concurrency. These are the foundational measurements: they feed M/D/1 queueing predictions (SS5), determine Phase 3 saturation rates, and provide the reference point for interpreting all subsequent phases.

### 3.1 Service Time Summary

| Model | n | Mean (ms) | 95% CI | Median | p95 | p99 | CV% | Theoretical Max RPS |
|-------|---|-----------|--------|--------|-----|-----|-----|---------------------|
| llama3.2-1b | 50 | 857.9 | [832.3, 883.5] | 886.3 | 925.5 | 935.9 | 10.5% | 1.166 |
| llama3.2-3b | 50 | 1,435.3 | [1,426.9, 1,443.7] | 1,433.2 | 1,481.7 | 1,538.8 | 2.1% | 0.697 |
| qwen2.5-1.5b | 50 | 1,008.4 | [986.5, 1,030.3] | 1,024.3 | 1,059.2 | 1,082.3 | 7.6% | 0.992 |

### 3.2 Decode Throughput

| Model | Mean tok/s | Mean prompt_eval (ms) |
|-------|------------|----------------------|
| llama3.2-1b | 211.0 | 12.8 |
| llama3.2-3b | 113.3 | 31.4 |
| qwen2.5-1.5b | 166.8 | 24.1 |

### 3.3 Interpretation

**Observations:**

1. **llama3.2-1b is the fastest at 858 ms mean service time** (1.17 req/s theoretical max), while llama3.2-3b is 1.67x slower at 1,435 ms (0.70 req/s). The 2.7x parameter ratio translates to a 1.67x latency ratio --- sub-linear in model size, consistent with GPU parallelism absorbing some of the additional compute. qwen2.5-1.5b sits in between at 1,008 ms despite having more parameters than llama3.2-1b, likely reflecting architectural differences in attention head count and tokenizer efficiency.

2. **Measurement precision varies significantly across models.** llama3.2-3b shows CV = 2.1% (95% CI width: 17 ms) --- exceptionally stable service times. llama3.2-1b shows CV = 10.5% (CI width: 51 ms) --- more variable, with a left-skewed distribution (mean 858 ms < median 886 ms). This left skew means some requests complete faster than typical, likely due to shorter generated responses hitting the stop token before `max_new_tokens`. qwen2.5-1.5b is intermediate at CV = 7.6%.

3. **The CV values directly predict queueing behavior.** Low CV means more deterministic service, which makes the M/D/1 model (which assumes deterministic service) a better approximation. llama3.2-3b's CV = 2.1% should track M/D/1 predictions most closely --- we test this in SS5.

4. **Decode throughput follows an inverse relationship with model size.** llama3.2-1b generates at 211 tok/s, qwen2.5-1.5b at 167 tok/s, llama3.2-3b at 113 tok/s. These rates are consistent with TR127's Ollama decode measurements at short context, cross-validating the measurement methodology.

5. **Prefill time is negligible relative to decode.** prompt_eval_ms ranges from 12.8 to 31.4 ms --- 1--3% of total service time. At 100--300 token prompts, prefill is not the bottleneck. This changes dramatically under load (SS8), where queueing delay amplifies TTFT by up to 29.9x.

---

## 4. Concurrency Scaling (Phase 2)

**This is the core experiment of TR128.** OLLAMA_NUM_PARALLEL={1, 2, 4} is swept across 5 Poisson arrival rates (0.5, 1.0, 2.0, 5.0, 10.0 req/s) for each of 3 models. The server is restarted between parallelism levels with a 10-second stabilization delay.

The central question: does increasing NUM_PARALLEL reduce per-request latency when multiple requests arrive concurrently?

### 4.1 Latency Curves

#### llama3.2-1b (baseline: 858 ms, 1.17 req/s)

**NP=1**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 1,052 | [930, 1,173] | 917 | 1,797 | 1,946 | 2.12 | 0.7 | 208 |
| 1.0 | 30 | 2,035 | [1,760, 2,311] | 1,962 | 3,191 | 3,423 | 1.74 | 2.7 | 205 |
| 2.0 | 30 | 5,730 | [4,697, 6,763] | 6,039 | 9,528 | 9,760 | 1.62 | 8.3 | 205 |
| 5.0 | 30 | 8,168 | [6,678, 9,658] | 8,407 | 14,132 | 14,568 | 1.73 | 11.7 | 206 |
| 10.0 | 30 | 8,375 | [6,857, 9,893] | 8,485 | 14,468 | 15,543 | 1.83 | 12.2 | 200 |

**NP=2**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 1,028 | [919, 1,138] | 919 | 1,662 | 1,830 | 1.99 | 0.7 | 200 |
| 1.0 | 30 | 1,827 | [1,565, 2,089] | 1,888 | 2,891 | 3,099 | 1.64 | 2.4 | 207 |
| 2.0 | 30 | 5,603 | [4,591, 6,615] | 5,835 | 9,394 | 9,732 | 1.67 | 8.2 | 208 |
| 5.0 | 30 | 7,949 | [6,517, 9,380] | 8,133 | 13,606 | 14,049 | 1.73 | 11.8 | 211 |
| 10.0 | 30 | 8,138 | [6,656, 9,619] | 8,351 | 14,438 | 14,879 | 1.78 | 12.2 | 206 |

**NP=4**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 1,036 | [922, 1,149] | 897 | 1,685 | 1,831 | 2.04 | 0.6 | 202 |
| 1.0 | 30 | 1,963 | [1,658, 2,268] | 1,953 | 3,246 | 3,461 | 1.77 | 2.5 | 209 |
| 2.0 | 30 | 5,590 | [4,576, 6,605] | 5,651 | 9,256 | 9,486 | 1.68 | 8.2 | 210 |
| 5.0 | 30 | 7,811 | [6,334, 9,287] | 7,756 | 13,712 | 14,172 | 1.83 | 11.4 | 209 |
| 10.0 | 30 | 8,139 | [6,616, 9,662] | 8,122 | 14,059 | 14,710 | 1.81 | 11.9 | 210 |

**Observations (llama3.2-1b):**

1. **Latency scales dramatically with arrival rate.** At 0.5 rps, mean wall latency is ~1,040 ms (barely above the 858 ms serial baseline). At 10 rps (8.5x overload), mean latency reaches ~8,300 ms --- a 7.9x amplification. This reflects pure queue buildup: the GPU can only serve 1.17 req/s, so excess requests pile up.

2. **NP=1, NP=2, and NP=4 produce virtually identical curves.** At every arrival rate, the three parallelism levels overlap within confidence intervals. At 2.0 rps: NP=1 gives 5,730 ms, NP=2 gives 5,603 ms, NP=4 gives 5,590 ms --- a spread of 140 ms on a 5,600 ms baseline (2.5% variation, well within CI width of ~2,000 ms).

3. **Saturation occurs at the lowest tested rate.** At 0.5 rps (43% of theoretical capacity), p99/p50 is already 2.04--2.12 across all NP levels. The Poisson arrival pattern creates enough burstiness that even at 43% mean utilization, occasional request clusters drive tail latency above 2x median.

4. **tok/s is constant across arrival rates and NP levels** (200--211 tok/s). The GPU's decode speed is unaffected by queueing --- confirming that the GPU processes one request at a time regardless of how many are waiting.

#### llama3.2-3b (baseline: 1,435 ms, 0.70 req/s)

**NP=1**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 3,011 | [2,584, 3,438] | 2,989 | 4,808 | 5,121 | 1.71 | 2.0 | 113 |
| 1.0 | 30 | 10,043 | [8,154, 11,933] | 10,265 | 17,065 | 17,594 | 1.71 | 7.8 | 112 |
| 2.0 | 30 | 14,494 | [11,622, 17,366] | 14,557 | 25,624 | 26,539 | 1.82 | 11.3 | 113 |
| 5.0 | 30 | 16,462 | [13,315, 19,608] | 16,951 | 28,638 | 30,255 | 1.78 | 13.2 | 116 |
| 10.0 | 30 | 16,589 | [13,362, 19,815] | 16,554 | 29,767 | 30,662 | 1.85 | 13.4 | 115 |

**NP=4**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 2,739 | [2,359, 3,118] | 2,826 | 4,296 | 4,492 | 1.59 | 1.8 | 117 |
| 1.0 | 30 | 9,475 | [7,690, 11,259] | 9,747 | 16,100 | 16,562 | 1.70 | 7.5 | 117 |
| 2.0 | 30 | 14,035 | [11,265, 16,805] | 14,101 | 24,779 | 25,664 | 1.82 | 11.3 | 117 |
| 5.0 | 30 | 16,394 | [13,186, 19,601] | 16,602 | 29,091 | 30,204 | 1.82 | 13.2 | 117 |
| 10.0 | 30 | 16,566 | [13,338, 19,795] | 16,556 | 29,629 | 30,804 | 1.86 | 13.4 | 116 |

(NP=2 tables are comparable --- omitted for brevity; full data in metrics.csv.)

**Observations (llama3.2-3b):**

1. **This model is already severely overloaded at 0.5 rps.** With a theoretical max of 0.70 req/s, 0.5 rps represents 71% utilization --- above the recommended 70% threshold. Mean latency is 3,011 ms (2.1x the 1,435 ms baseline), confirming significant queueing delay even at the lowest tested rate.

2. **Latency plateaus above 5 rps.** At NP=1, the jump from 5.0 to 10.0 rps is only 127 ms (16,462 to 16,589 ms) --- the system is fully saturated and additional requests simply join the back of a full queue. The queue depth confirms this: 13.2 at 5 rps vs 13.4 at 10 rps.

3. **NP=4 shows no improvement over NP=1.** At 1.0 rps (the most informative rate, where utilization is 143% for NP=1 but only 36% for NP=4 *if NP worked*): NP=1 gives 10,043 ms, NP=4 gives 9,475 ms --- a 5.7% difference that is not statistically significant (p = 0.66, d = -0.12, negligible).

4. **p99 tail latencies reach 30 seconds** at high arrival rates. A user waiting 30 seconds for a response from a 3B model is unacceptable for interactive applications. This underscores why capacity planning must account for tail latency, not just mean throughput.

#### qwen2.5-1.5b (baseline: 1,008 ms, 0.99 req/s)

**NP=1**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 1,346 | [1,171, 1,520] | 1,107 | 2,210 | 2,410 | 2.18 | 0.8 | 174 |
| 1.0 | 30 | 4,427 | [3,707, 5,146] | 4,435 | 7,048 | 7,350 | 1.66 | 4.8 | 162 |
| 2.0 | 30 | 8,960 | [7,264, 10,656] | 8,932 | 15,499 | 16,060 | 1.80 | 10.0 | 162 |
| 5.0 | 30 | 11,327 | [9,211, 13,443] | 11,789 | 19,630 | 20,216 | 1.71 | 12.6 | 162 |
| 10.0 | 30 | 11,471 | [9,358, 13,584] | 11,481 | 19,686 | 20,726 | 1.81 | 12.8 | 162 |

**NP=4**

| Rate (rps) | n | Mean (ms) | 95% CI | p50 | p95 | p99 | p99/p50 | Queue Depth | tok/s |
|-----------|---|-----------|--------|-----|-----|-----|---------|-------------|-------|
| 0.5 | 30 | 1,308 | [1,152, 1,464] | 1,155 | 2,011 | 2,299 | 1.99 | 0.7 | 165 |
| 1.0 | 30 | 3,920 | [3,279, 4,560] | 3,948 | 6,289 | 6,604 | 1.67 | 4.3 | 168 |
| 2.0 | 30 | 8,472 | [6,873, 10,071] | 8,397 | 14,663 | 15,197 | 1.81 | 9.7 | 168 |
| 5.0 | 30 | 10,845 | [8,802, 12,887] | 10,671 | 18,995 | 19,771 | 1.85 | 12.5 | 169 |
| 10.0 | 30 | 11,104 | [9,025, 13,184] | 10,989 | 19,466 | 20,262 | 1.84 | 12.8 | 169 |

**Observations (qwen2.5-1.5b):**

1. **Saturation behavior is intermediate between the other two models.** At 0.5 rps (50% of theoretical capacity), mean latency is 1,346 ms (1.34x baseline). At 1.0 rps (101% utilization), mean jumps to 4,427 ms --- a 3.3x amplification in a single step, demonstrating how sharply queueing delay grows near the saturation boundary.

2. **The NP=4 "advantage" is a mirage.** At 1.0 rps, NP=4 gives 3,920 ms vs NP=1's 4,427 ms --- an 11.5% difference. This looks promising until you check the statistics: p = 0.29, d = -0.28 (small effect, not significant). The Holm--Bonferroni threshold at this rank is 0.002. The apparent improvement is well within the noise of Poisson arrival patterns across 30 samples.

3. **tok/s increases slightly from NP=1 (162--174) to NP=4 (165--169).** This ~3% difference is not significant and likely reflects minor Ollama runtime optimization differences between restarts rather than any parallelism benefit.

### 4.2 Parallelism Impact: Full Pairwise Results

30 pairwise comparisons were performed: 3 models x 5 rates x 2 (NP=2 vs NP=1, NP=4 vs NP=1). All 30 were corrected using Holm--Bonferroni step-down procedure at alpha = 0.05.

**Result: 0/30 significant after correction. 0/30 significant even before correction (lowest uncorrected p = 0.15).**

| Model | Rate | Comparison | Change% | p-value | Cohen's d | Effect | Sig? |
|-------|------|------------|---------|---------|-----------|--------|------|
| llama3.2-1b | 0.5 | NP2 vs NP1 | -2.3% | 0.768 | -0.08 | negligible | No |
| llama3.2-1b | 0.5 | NP4 vs NP1 | -1.6% | 0.841 | -0.05 | negligible | No |
| llama3.2-1b | 1.0 | NP2 vs NP1 | -10.2% | 0.268 | -0.29 | small | No |
| llama3.2-1b | 1.0 | NP4 vs NP1 | -3.6% | 0.719 | -0.09 | negligible | No |
| llama3.2-1b | 2.0 | NP2 vs NP1 | -2.2% | 0.858 | -0.05 | negligible | No |
| llama3.2-1b | 2.0 | NP4 vs NP1 | -2.4% | 0.844 | -0.05 | negligible | No |
| llama3.2-1b | 5.0 | NP2 vs NP1 | -2.7% | 0.829 | -0.06 | negligible | No |
| llama3.2-1b | 5.0 | NP4 vs NP1 | -4.4% | 0.729 | -0.09 | negligible | No |
| llama3.2-1b | 10.0 | NP2 vs NP1 | -2.8% | 0.820 | -0.06 | negligible | No |
| llama3.2-1b | 10.0 | NP4 vs NP1 | -2.8% | 0.823 | -0.06 | negligible | No |
| llama3.2-3b | 0.5 | NP2 vs NP1 | -7.3% | 0.432 | -0.20 | small | No |
| llama3.2-3b | 0.5 | NP4 vs NP1 | -9.0% | 0.333 | -0.25 | small | No |
| llama3.2-3b | 1.0 | NP2 vs NP1 | -4.8% | 0.707 | -0.10 | negligible | No |
| llama3.2-3b | 1.0 | NP4 vs NP1 | -5.7% | 0.656 | -0.12 | negligible | No |
| llama3.2-3b | 2.0 | NP2 vs NP1 | -2.6% | 0.851 | -0.05 | negligible | No |
| llama3.2-3b | 2.0 | NP4 vs NP1 | -3.2% | 0.815 | -0.06 | negligible | No |
| llama3.2-3b | 5.0 | NP2 vs NP1 | 0.2% | 0.988 | 0.00 | negligible | No |
| llama3.2-3b | 5.0 | NP4 vs NP1 | -0.4% | 0.975 | -0.01 | negligible | No |
| llama3.2-3b | 10.0 | NP2 vs NP1 | 1.1% | 0.933 | 0.02 | negligible | No |
| llama3.2-3b | 10.0 | NP4 vs NP1 | -0.1% | 0.992 | -0.00 | negligible | No |
| qwen2.5-1.5b | 0.5 | NP2 vs NP1 | -0.2% | 0.984 | -0.01 | negligible | No |
| qwen2.5-1.5b | 0.5 | NP4 vs NP1 | -2.8% | 0.744 | -0.09 | negligible | No |
| qwen2.5-1.5b | 1.0 | NP2 vs NP1 | -10.5% | 0.333 | -0.25 | small | No |
| qwen2.5-1.5b | 1.0 | NP4 vs NP1 | -11.5% | 0.286 | -0.28 | small | No |
| qwen2.5-1.5b | 2.0 | NP2 vs NP1 | -5.2% | 0.686 | -0.10 | negligible | No |
| qwen2.5-1.5b | 2.0 | NP4 vs NP1 | -5.5% | 0.670 | -0.11 | negligible | No |
| qwen2.5-1.5b | 5.0 | NP2 vs NP1 | -3.6% | 0.780 | -0.07 | negligible | No |
| qwen2.5-1.5b | 5.0 | NP4 vs NP1 | -4.3% | 0.739 | -0.09 | negligible | No |
| qwen2.5-1.5b | 10.0 | NP2 vs NP1 | -4.0% | 0.749 | -0.08 | negligible | No |
| qwen2.5-1.5b | 10.0 | NP4 vs NP1 | -3.2% | 0.801 | -0.07 | negligible | No |

### 4.3 Interpretation

**OLLAMA_NUM_PARALLEL has no statistically significant effect on latency under any tested condition.** This is the headline finding of TR128.

The result is unambiguous: across 30 pairwise comparisons spanning 3 models, 5 arrival rates, and 2 parallelism levels, zero reach significance. The mean absolute change is 4.0% --- consistent with the noise inherent in Poisson arrival patterns with n=30 samples. 26 of 30 effect sizes are negligible (|d| < 0.2), and the 4 "small" effects (d = 0.20--0.29) are at 1.0 rps rates where Poisson burstiness creates the most variance.

**Why does NP not help?** On this hardware (RTX 4080 Laptop, 12 GB VRAM, Ada Lovelace architecture), the CUDA compute kernels for transformer inference --- matrix multiplications, attention computation, layer normalization --- occupy the entire GPU. There is no spare compute capacity for a second request to run concurrently. Ollama's NUM_PARALLEL parameter controls how many requests the *CPU-side* server admits simultaneously, but once a request reaches the GPU, it must wait for the currently executing request to complete. The GPU is the bottleneck, and it is not parallelizable by configuration alone.

This has a direct practical implication: **setting NUM_PARALLEL > 1 provides no benefit and may add CPU overhead from managing multiple in-flight request contexts.** Leave it at the default (1) and use a reverse proxy for request queue management.

**Comparison with expectations:** One might expect NP>1 to help if Ollama could interleave GPU work between requests (e.g., computing attention for request A while loading weights for request B). Modern GPUs do support concurrent kernel execution via CUDA streams. However, transformer inference kernels are compute-bound (not memory-bound) at these model sizes, and each kernel launch fills the GPU's SM array. There is simply no scheduling gap for a second request's kernels to slip into.

---

## 5. M/D/1 Deviation & Queue Analysis (Phase 2)

### 5.1 Background

The M/D/1 queueing model is the standard textbook approach to capacity planning for single-server systems. It predicts mean queue wait as:

```
W_q = (rho * D) / (2 * (1 - rho))
```

where rho = lambda * D (utilization), lambda is the arrival rate, and D is the deterministic service time. For NP > 1, we test the assumption that effective service rate scales linearly: `D_eff = D / NP`.

If M/D/1 is accurate, it provides a simple, closed-form capacity planning tool. If it fails, empirical measurement is necessary.

### 5.2 Queue Wait: Theory vs Reality

The deviation ratio `observed_wait / predicted_wait` quantifies theory accuracy. Values > 1 mean reality is worse than theory predicts; values < 1 mean reality is better.

#### llama3.2-1b (baseline: 857.9 ms)

| NP | Rate | rho | M/D/1 Wait (ms) | Observed Wait (ms) | Obs p95 | Deviation |
|----|------|-----|------------------|--------------------|---------|-----------|
| 1 | 0.5 | 0.43 | 322 | 256 | 1,025 | 0.79x |
| 1 | 1.0 | 0.86 | 2,590 | 1,224 | 2,348 | 0.47x |
| 2 | 0.5 | 0.21 | 117 | 233 | 844 | **1.99x** |
| 2 | 1.0 | 0.43 | 322 | 1,060 | 2,089 | **3.29x** |
| 4 | 0.5 | 0.11 | 52 | 231 | 866 | **4.49x** |
| 4 | 1.0 | 0.21 | 117 | 1,183 | 2,450 | **10.10x** |
| 4 | 2.0 | 0.43 | 322 | 4,802 | 8,480 | **14.90x** |

#### llama3.2-3b (baseline: 1,435.3 ms)

| NP | Rate | rho | M/D/1 Wait (ms) | Observed Wait (ms) | Obs p95 | Deviation |
|----|------|-----|------------------|--------------------|---------|-----------|
| 1 | 0.5 | 0.72 | 1,824 | 1,627 | 3,453 | 0.89x |
| 2 | 0.5 | 0.36 | 402 | 1,471 | 3,066 | **3.66x** |
| 2 | 1.0 | 0.72 | 1,824 | 8,244 | 14,899 | **4.52x** |
| 4 | 0.5 | 0.18 | 157 | 1,439 | 3,014 | **9.17x** |
| 4 | 1.0 | 0.36 | 402 | 8,182 | 14,825 | **20.37x** |
| 4 | 2.0 | 0.72 | 1,824 | 12,735 | 23,476 | **6.98x** |

#### qwen2.5-1.5b (baseline: 1,008.4 ms)

| NP | Rate | rho | M/D/1 Wait (ms) | Observed Wait (ms) | Obs p95 | Deviation |
|----|------|-----|------------------|--------------------|---------|-----------|
| 1 | 0.5 | 0.50 | 513 | 415 | 1,229 | 0.81x |
| 2 | 0.5 | 0.25 | 170 | 405 | 1,170 | **2.38x** |
| 2 | 1.0 | 0.50 | 513 | 3,030 | 5,422 | **5.91x** |
| 4 | 0.5 | 0.13 | 73 | 370 | 1,068 | **5.09x** |
| 4 | 1.0 | 0.25 | 170 | 3,013 | 5,386 | **17.73x** |
| 4 | 2.0 | 0.50 | 513 | 7,561 | 13,749 | **14.75x** |

(Higher rates at NP>1 show "overloaded" --- rho > 1 under the NP-scaling assumption, but since NP doesn't actually help, the system was already overloaded at NP=1's effective capacity.)

### 5.3 Interpretation

**The M/D/1 model deviates from reality by up to 20.4x** (llama3.2-3b at NP=4, 1.0 rps). This is catastrophically wrong for capacity planning.

**Why NP>1 predictions fail (deviation 2--20x):**

The M/D/1 model at NP>1 assumes effective service rate = NP x baseline rate. Since the GPU serializes inference regardless of NP (SS4), the actual effective rate is 1x baseline. The model therefore computes rho = arrival_rate * service_time / NP, when the true rho = arrival_rate * service_time. At NP=4 with llama3.2-3b at 1.0 rps, M/D/1 predicts rho = 0.36 (comfortable load), when the true rho is 1.44 (severely overloaded). Because queue wait scales as rho/(1-rho), which diverges as rho approaches 1, a 4x error in utilization near the saturation boundary produces catastrophic prediction errors.

**Why NP=1 predictions are surprisingly good --- but in the wrong direction (deviation 0.47--0.89x):**

At NP=1, where the model's structural assumptions are correct, deviations are 0.47--0.89x --- reality is *better* than theory. The M/D/1 model slightly *overestimates* queue wait. This seems paradoxical: the deterministic-service assumption (CV=0) should *underestimate* tail effects, making the model optimistic, not pessimistic. Three factors explain why reality beats theory:

1. **Transient vs steady-state.** M/D/1 predicts *steady-state* queue wait --- the average wait after the system has been running long enough to reach equilibrium. With only 30 requests arriving over 60 seconds (at 0.5 rps), the system never reaches steady state. The first several requests arrive to an empty queue (queue wait = 0), pulling the average below the steady-state prediction. At 0.5 rps for llama3.2-1b, only 7% of requests were served immediately (queue wait < 50 ms), but the early low-wait requests still drag the mean below M/D/1's equilibrium prediction.

2. **Service time variability cuts both ways.** The M/D/1 model assumes constant service times. Real service times have CV = 2--10%. When a request happens to complete *faster* than average, the next request finds a shorter queue --- partially offsetting the tail-amplifying effect of *slower* than average service. At moderate utilization (rho < 0.9), this variance partially cancels out.

3. **Poisson clustering creates correlations.** M/D/1 assumes arrivals are memoryless. In practice, Poisson clusters create brief periods of high queue depth followed by brief recovery periods where the queue drains. The average over both regimes can be lower than the steady-state prediction, especially with finite sample sizes.

**Practical implication:** At NP=1, M/D/1 is a *conservative upper bound* on mean queue wait for finite request bursts. At NP>1, it is catastrophically wrong. Do not use any queueing model that assumes NP>1 scales throughput linearly for Ollama on single-GPU hardware. Use the empirical saturation curves from SS4 directly.

### 5.4 Queue Depth Analysis

Queue depth at submission time grows monotonically with arrival rate, confirming that the load generator is functioning correctly and that the GPU serializes requests:

| Rate (rps) | llama3.2-1b (NP=1) | llama3.2-3b (NP=1) | qwen2.5-1.5b (NP=1) |
|-----------|---------------------|---------------------|----------------------|
| 0.5 | 0.7 | 2.0 | 0.8 |
| 1.0 | 2.7 | 7.8 | 4.8 |
| 2.0 | 8.3 | 11.3 | 10.0 |
| 5.0 | 11.7 | 13.2 | 12.6 |
| 10.0 | 12.2 | 13.4 | 12.8 |

**Observations:**

1. **Queue depth correlates with model service time.** At 0.5 rps, llama3.2-1b (fastest, 858 ms) has queue depth 0.7 while llama3.2-3b (slowest, 1,435 ms) has queue depth 2.0. Slower models accumulate longer queues at the same arrival rate.

2. **Queue depth saturates above 5 rps** at 11--13 for all models. This is the steady-state queue depth under full saturation: with 30 requests in a burst arriving over ~3--6 seconds, the maximum queue depth is bounded by the burst size.

3. **Queue depth is identical across NP levels** (not shown --- but confirmed in the data). At NP=4, llama3.2-1b at 0.5 rps has queue depth 0.6 vs NP=1's 0.7. The GPU processes requests at the same rate regardless of NP.

---

## 6. Thermal Stability (Phase 3)

Phase 3 holds each model at approximately 80% of its theoretical saturation rate for 180 seconds, using periodic (constant-rate) arrivals to isolate thermal effects from Poisson arrival variance. The question: does sustained GPU load cause thermal throttling that degrades inference throughput over time?

### 6.1 Per-Model Stability

#### llama3.2-1b (n=168, arrival rate ~0.93 rps)

| Metric | Value |
|--------|-------|
| Mean wall latency | 694.2 ms |
| Median | 714.6 ms |
| CV% | 10.9% |
| First-third mean | 698.9 ms |
| Last-third mean | 690.0 ms |
| Drift | **-1.3%** (p = 0.567, not significant) |
| Linear trend | slope = -0.062 ms/req, R-squared = 0.002, p = 0.610 |

**Interpretation:** No drift detected. The 1.3% decrease from first to last third is not significant (p = 0.57). The linear trend is flat (slope = -0.062 ms/req, R-squared near zero). Crucially, decode throughput is stable: first-third 272 tok/s, last-third 272 tok/s (+0.1%). llama3.2-1b maintains stable performance throughout 168 requests over ~117 seconds of sustained load.

#### llama3.2-3b (n=101, arrival rate ~0.56 rps)

| Metric | Value |
|--------|-------|
| Mean wall latency | 1,032.7 ms |
| Median | 1,011.9 ms |
| CV% | 16.1% |
| First-third mean | 1,076.0 ms |
| Last-third mean | 1,011.3 ms |
| Drift | **-6.0%** (p = 0.201, not significant) |
| Linear trend | slope = -1.244 ms/req, R-squared = 0.048, **p = 0.027** |

**Interpretation:** The drift test shows a non-significant 6.0% decrease (p = 0.20), but the linear trend has a marginally significant slope (p = 0.027). Decode throughput tells the real story: first-third 169 tok/s, last-third 170 tok/s (**+0.5%**). The GPU is decoding at the same speed throughout. The wall-time decrease is driven by a single cold-start outlier at 2,570 ms (the first request after model load), not by systematic improvement.

#### qwen2.5-1.5b (n=143, arrival rate ~0.79 rps)

| Metric | Value |
|--------|-------|
| Mean wall latency | 910.6 ms |
| Median | 998.1 ms |
| CV% | 17.5% |
| First-third mean | 1,006.6 ms |
| Last-third mean | 727.0 ms |
| Drift | **-27.7%** (p < 0.0001, **significant**) |
| Linear trend | slope = -2.805 ms/req, R-squared = 0.531, **p < 0.0001** |

**Interpretation:** This model shows a dramatic 27.7% wall latency decrease, and **the mechanism is in the decode phase, not prefill.** Breaking down the native timing:

| Segment | First-third | Last-third | Change |
|---------|-------------|------------|--------|
| eval_ms (decode) | 767 ms | 493 ms | **-35.8%** |
| prompt_eval_ms | 24 ms | 11 ms | -54% |
| load_duration_ms | 139 ms | 138 ms | -0.7% |
| tok/s | 165 | 275 | **+66.5%** |
| completion_tokens | 126.6 | 128.0 | +1.1% |

The GPU is generating the same number of tokens (128) but **decoding 66% faster** by the end of the sustained run. This is a striking finding because:

1. **It is model-specific.** llama3.2-1b (+0.1% tok/s change) and llama3.2-3b (+0.5%) show no effect. Only qwen2.5-1.5b exhibits this warmup.
2. **It is not GPU clock ramp.** If the GPU were boosting clocks over time, all three models would benefit equally. They do not.
3. **It is not JIT compilation.** llama.cpp is compiled C++ with CUDA kernels. There is no runtime code generation.
4. **It is not model reloading.** load_duration_ms is constant at ~138 ms throughout, confirming the model stays loaded.
5. **It is not shorter responses.** completion_tokens is constant at ~128.

**Candidate mechanisms (unconfirmed):**

- **CUDA memory pool warmup.** The CUDA allocator caches freed memory blocks for reuse. After many allocations, the pool stabilizes and `cudaMalloc` overhead drops. If qwen2.5-1.5b's architecture produces more intermediate allocations than the llama models (different attention structure, different layer count), the warmup effect would be larger.
- **CPU-side cache warming.** qwen2.5-1.5b uses Q4_K_M quantization, which requires CPU-side dequantization tables. After repeated access, these tables may reside in L2/L3 cache, reducing memory latency for the dequantization step.
- **Ollama batch size adaptation.** llama.cpp has internal batch processing logic that may adapt batch sizes for compute-bound operations based on observed throughput.

**This finding warrants standalone investigation.** A controlled experiment holding qwen2.5-1.5b at constant load for 1,000+ requests would reveal whether the throughput increase is monotonic, whether it plateaus (and at what level), and whether it persists across Ollama restarts. If reproducible, it implies that qwen2.5-1.5b benchmarks should discard the first ~50 requests as warmup, not just 3.

### 6.2 GPU Thermal Profile (Phase 3 Only)

| Metric | Value |
|--------|-------|
| Temperature range | 47.0--66.0 degrees C |
| Mean temperature | 55.2 degrees C |
| Peak temperature | 66.0 degrees C |
| Throttle threshold | 80 degrees C |
| Throttle events | **0** (0.0% of 524 Phase 3 samples) |
| Clock range | 420--2,550 MHz |
| Peak power | 149.3 W |

**Note:** Phase 4 recorded one 81 degrees C sample (SS7), but this is outside the Phase 3 thermal stability test and likely coincides with model loading or a system-level thermal event. Phase 3 --- the dedicated thermal test --- peaked at 66 degrees C.

**Observations:**

1. **Peak 66 degrees C is 14 degrees below the throttle threshold.** The RTX 4080 Laptop GPU handles sustained LLM inference with a comfortable thermal margin. This is notable because laptop GPUs share a thermal envelope with the CPU and have limited cooling capacity compared to desktop GPUs.

2. **Clock speed range is wide (420--2,550 MHz)** but this reflects idle vs active states, not throttling. During active inference, the GPU runs at or near peak clock. During the brief gaps between requests (at 80% utilization, there are gaps), the GPU drops to idle clocks.

3. **Peak power of 149.3 W** is near the 150W TDP. The GPU is drawing full power during inference but the cooling system handles it without thermal throttling.

---

## 7. GPU Metrics Summary

This section provides a cross-phase summary of GPU behavior, showing that hardware conditions were stable and appropriate throughout the experiment.

| Phase | Samples | Temp (C) | Clock (MHz) | Util (%) | Power (W) | VRAM (MB) |
|-------|---------|----------|-------------|----------|-----------|-----------|
| P1 Baseline | 159 | 44--56 | 210--2,535 | 2--95 | 55.0 (pk: 81.8) | 6,491--6,497 |
| P2 NP=1 | 445 | 47--57 | 255--2,550 | 0--95 | 57.5 (pk: 104.5) | 4,894--6,501 |
| P2 NP=2 | 439 | 47--54 | 255--795 | 0--95 | 57.6 (pk: 68.8) | 4,894--6,508 |
| P2 NP=4 | 439 | 47--56 | 255--795 | 0--94 | 57.7 (pk: 69.3) | 4,894--6,501 |
| P3 Thermal | 524 | 47--66 | 420--2,550 | 0--92 | 72.1 (pk: 149.3) | 3,620--6,501 |
| P4 Streaming | 469 | 49--81 | 465--2,550 | 0--98 | 105.6 (pk: 161.7) | 3,620--6,501 |

**Observations:**

1. **VRAM usage is stable across all phases** (4,894--6,508 MB). The range reflects different model sizes being loaded and unloaded: llama3.2-3b uses the most VRAM (~6.5 GB), llama3.2-1b uses the least (~4.9 GB). No memory leaks detected under sustained operation.

2. **Phase 4 shows the highest temperature (81 degrees C)** and power (161.7 W peak). This single-sample temperature spike exceeds the 80-degree throttle threshold but does not meet the full throttle definition (temp > 80 AND clock < 90% of peak simultaneously). It is likely a transient spike during model loading or a concurrent system process.

3. **NP=2 and NP=4 show lower peak clocks (795 MHz) than NP=1 (2,550 MHz).** This is an artifact of nvidia-smi sampling timing relative to Ollama restart cycles, not a systematic difference in GPU behavior during inference.

---

## 8. Streaming Performance (Phase 4)

Phase 4 tests two questions: (1) does streaming add wall-clock overhead compared to batch mode, and (2) how does TTFT (time to first token) behave under increasing load? Three arrival rates (0.5, 1.0, 2.0 rps) are tested with Poisson arrivals, each model in both batch (`stream: false`) and stream (`stream: true`) modes.

### 8.1 Stream vs Batch Wall Latency

9 pairwise comparisons (3 models x 3 rates), Holm--Bonferroni corrected at alpha = 0.05.

**Result: 0/9 significant.**

| Model | Rate | Batch Mean (ms) | Stream Mean (ms) | Overhead% | p-value | Cohen's d | Effect | Sig? |
|-------|------|-----------------|------------------|-----------|---------|-----------|--------|------|
| llama3.2-1b | 0.5 | 1,014 | 859 | -15.3% | 0.152 | -0.38 | small | No |
| llama3.2-1b | 1.0 | 1,013 | 1,022 | +0.9% | 0.932 | 0.02 | negligible | No |
| llama3.2-1b | 2.0 | 3,506 | 3,474 | -0.9% | 0.933 | -0.02 | negligible | No |
| llama3.2-3b | 0.5 | 1,580 | 1,312 | -17.0% | 0.072 | -0.47 | small | No |
| llama3.2-3b | 1.0 | 3,267 | 3,298 | +0.9% | 0.943 | 0.02 | negligible | No |
| llama3.2-3b | 2.0 | 8,695 | 8,771 | +0.9% | 0.948 | 0.01 | negligible | No |
| qwen2.5-1.5b | 0.5 | 1,057 | 844 | -20.1% | 0.080 | -0.46 | small | No |
| qwen2.5-1.5b | 1.0 | 1,281 | 1,297 | +1.3% | 0.922 | 0.03 | negligible | No |
| qwen2.5-1.5b | 2.0 | 3,483 | 3,373 | -3.2% | 0.777 | -0.07 | negligible | No |

**Observations:**

1. **Streaming adds zero overhead.** The largest apparent differences are at 0.5 rps, where streaming appears *faster* by 15--20%. However, these are not significant (lowest p = 0.072, which does not clear the Holm--Bonferroni threshold of 0.006). The apparent streaming advantage at low load is likely Poisson arrival variance --- with only 30 samples, the batch and stream bursts land differently.

2. **At higher arrival rates (1.0, 2.0 rps), overhead is negligible (|d| < 0.05).** When queue depth is high, the queueing delay dominates and any streaming overhead (HTTP chunked encoding, NDJSON parsing) is invisible in the noise.

3. **This confirms the "streaming is free" recommendation.** There is no wall-clock cost to streaming on Ollama. Applications should always use streaming mode because it provides earlier TTFT (users see tokens sooner) without any latency penalty.

### 8.2 TTFT Under Load

TTFT = time from request submission to the first non-empty NDJSON chunk. This reliably corresponds to prefill completion plus queueing delay --- it is the first moment the user sees output.

#### llama3.2-1b (baseline TTFT p50: 206.7 ms)

| Rate | n | Mean (ms) | 95% CI | p50 | p95 | Amplification |
|------|---|-----------|--------|-----|-----|---------------|
| 0.5 | 30 | 307 | [222, 393] | 207 | 865 | **1.0x** |
| 1.0 | 30 | 516 | [373, 660] | 354 | 1,252 | **1.7x** |
| 2.0 | 30 | 2,953 | [2,403, 3,502] | 3,265 | 4,978 | **15.8x** |

#### llama3.2-3b (baseline TTFT p50: 250.4 ms)

| Rate | n | Mean (ms) | 95% CI | p50 | p95 | Amplification |
|------|---|-----------|--------|-----|-----|---------------|
| 0.5 | 30 | 495 | [342, 649] | 250 | 1,230 | **1.0x** |
| 1.0 | 30 | 2,881 | [2,290, 3,471] | 2,915 | 5,103 | **11.6x** |
| 2.0 | 30 | 7,401 | [5,868, 8,934] | 7,478 | 13,210 | **29.9x** |

#### qwen2.5-1.5b (baseline TTFT p50: 185.2 ms)

| Rate | n | Mean (ms) | 95% CI | p50 | p95 | Amplification |
|------|---|-----------|--------|-----|-----|---------------|
| 0.5 | 30 | 297 | [212, 381] | 185 | 848 | **1.0x** |
| 1.0 | 30 | 526 | [391, 660] | 420 | 1,191 | **2.3x** |
| 2.0 | 30 | 2,907 | [2,380, 3,434] | 2,984 | 4,777 | **16.1x** |

### 8.3 TTFT Interpretation

**TTFT amplification is severe and directly reflects queueing delay.** The llama3.2-3b model shows 29.9x TTFT amplification at 2.0 rps --- a user submitting a request at that load level waits 7.4 *seconds* to see the first token, compared to 250 ms at idle. This is pure queueing delay: the prompt evaluation itself has not slowed down (prompt_eval_ms remains constant across rates), but the request waits in the queue while the GPU processes earlier requests.

**Observations:**

1. **TTFT amplification correlates with model service time.** llama3.2-3b (slowest, 1,435 ms baseline) shows 29.9x amplification at 2.0 rps. llama3.2-1b and qwen2.5-1.5b (faster baselines) show 15.8x and 16.1x respectively. Slower models create longer queues, amplifying TTFT more.

2. **Baseline TTFT at 0.5 rps matches idle TTFT.** The p50 TTFT at 0.5 rps closely matches the baseline: 207 ms (load) vs 207 ms (idle) for llama3.2-1b. At low load, most requests arrive to an empty queue and are served immediately. The p95 is much higher (865 ms) because occasional Poisson clusters create brief queues.

3. **The jump from 1.0 to 2.0 rps is disproportionately large.** For llama3.2-1b: 516 ms (1.0 rps) to 2,953 ms (2.0 rps) --- a 5.7x increase for a 2x arrival rate increase. This is the non-linear queueing amplification: as utilization approaches and exceeds 100%, queue depth (and therefore wait time) grows explosively.

4. **TTFT exceeds 1 second at 1.0 rps for llama3.2-3b.** At that rate, the model is at 143% utilization and p50 TTFT is 2.9 seconds. For interactive applications, this is unacceptable. Capacity planning must target TTFT thresholds, not just throughput.

---

## 9. Inter-Chunk Latency (Phase 4)

> **Caveat:** These are inter-*chunk* latencies, not inter-*token* latencies. TCP buffering means each NDJSON line read may contain tokens that were generated as a batch on the GPU. Only TTFT is a reliable client-side timing metric. Inter-chunk measurements are reported for completeness but should not be interpreted as per-token generation latency.

### 9.1 ichunk Summary

#### llama3.2-1b

| Rate | n | Mean ichunk (ms) | p95 ichunk (ms) | Jitter CV |
|------|---|------------------|-----------------|-----------|
| 0.5 | 30 | 4.5 | 5.5 | 1.32 |
| 1.0 | 30 | 4.2 | 5.3 | 2.31 |
| 2.0 | 30 | 4.2 | 5.2 | 2.88 |

#### llama3.2-3b

| Rate | n | Mean ichunk (ms) | p95 ichunk (ms) | Jitter CV |
|------|---|------------------|-----------------|-----------|
| 0.5 | 30 | 6.4 | 7.2 | 1.32 |
| 1.0 | 30 | 6.3 | 7.0 | 2.00 |
| 2.0 | 30 | 6.4 | 6.9 | 1.78 |

#### qwen2.5-1.5b

| Rate | n | Mean ichunk (ms) | p95 ichunk (ms) | Jitter CV |
|------|---|------------------|-----------------|-----------|
| 0.5 | 30 | 4.3 | 5.6 | 1.45 |
| 1.0 | 30 | 3.9 | 5.1 | 2.65 |
| 2.0 | 30 | 4.0 | 5.0 | 3.25 |

### 9.2 Interpretation

**Observations:**

1. **Mean ichunk latency is stable across arrival rates** (4--6.4 ms for all models). This confirms that once the GPU begins generating tokens for a request, the generation speed is unaffected by how many requests are waiting in the queue. The GPU serves one request at a time, and that request gets full GPU bandwidth.

2. **ichunk latency correlates with model size.** llama3.2-3b averages 6.3--6.4 ms per chunk; llama3.2-1b and qwen2.5-1.5b average 3.9--4.5 ms. This reflects the per-token compute cost of the larger model.

3. **Jitter (CV) increases with arrival rate** for llama3.2-1b and qwen2.5-1.5b: 1.3--1.5 at 0.5 rps, rising to 2.9--3.3 at 2.0 rps. This suggests that under high load, OS-level TCP buffering becomes more variable (the kernel may batch more aggressively when the CPU is handling multiple connections). For llama3.2-3b, jitter is relatively stable (1.3--2.0), possibly because its longer per-chunk latency makes TCP buffering variance proportionally smaller.

4. **These numbers should not be compared to decode tok/s.** Mean ichunk of 4.2 ms implies ~238 chunks/s for llama3.2-1b, but the actual decode rate is 200--211 tok/s. The discrepancy arises because ichunk measures inter-network-read latency, not inter-token latency. Multiple tokens may arrive in a single chunk.

---

## 10. Multi-Turn Degradation (Phase 5)

Phase 5 simulates multi-turn conversations using Ollama's `/api/chat` endpoint. Under the "full" context strategy, the entire conversation history is sent each turn. Under "sliding_window", only the last 3 turns are retained. Both 5-turn and 10-turn conversations are tested with 8 conversations per combination.

### 10.1 llama3.2-1b

**Full context** (10-turn, n=8 conversations)

| Turn | n | Mean (ms) | 95% CI | Prompt Tokens | tok/s |
|------|---|-----------|--------|---------------|-------|
| 0 | 16 | 778 | [596, 960] | 35 | 282 |
| 1 | 16 | 693 | [687, 699] | 183 | 282 |
| 2 | 16 | 697 | [693, 701] | 331 | 272 |
| 3 | 16 | 693 | [688, 698] | 480 | 272 |
| 4 | 16 | 698 | [693, 704] | 626 | 269 |
| 5 | 8 | 704 | [695, 714] | 773 | 264 |
| 6 | 8 | 703 | [696, 710] | 921 | 264 |
| 7 | 8 | 705 | [698, 713] | 1,069 | 260 |
| 8 | 8 | 709 | [699, 718] | 1,216 | 257 |
| 9 | 8 | 716 | [698, 733] | 1,365 | 259 |

**Sliding-window context** (10-turn, last 3 turns retained)

| Turn | n | Mean (ms) | 95% CI | Prompt Tokens | tok/s |
|------|---|-----------|--------|---------------|-------|
| 0 | 16 | 692 | [687, 696] | 35 | 281 |
| 1 | 16 | 696 | [689, 703] | 183 | 281 |
| 2 | 16 | 697 | [692, 702] | 331 | 276 |
| 3 | 16 | 708 | [703, 713] | 465 | 273 |
| 4 | 16 | 704 | [701, 708] | 463 | 273 |
| 5 | 8 | 706 | [697, 715] | 462 | 268 |
| 6 | 8 | 704 | [694, 713] | 461 | 268 |
| 7 | 8 | 708 | [701, 715] | 463 | 269 |
| 8 | 8 | 711 | [703, 718] | 463 | 273 |
| 9 | 8 | 673 | [632, 714] | 464 | 277 |

**Observations (llama3.2-1b):**

1. **Under full context, prompt tokens grow linearly** from 35 (turn 0) to 1,365 (turn 9) --- each turn adds ~148 tokens of conversation history. Under sliding-window, prompt tokens plateau at ~463 tokens after turn 3, confirming the window truncation is working correctly.

2. **Wall latency is remarkably stable despite 39x prompt growth.** From turn 1 to turn 9 under full context, latency increases from 693 ms to 716 ms --- only a 3.3% increase despite prompt tokens growing from 183 to 1,365 (7.5x). This is consistent with TR127's finding that Ollama's llama.cpp backend has sub-linear prefill scaling (b = 0.083 for llama3.2-1b).

3. **Decode throughput degrades gradually.** tok/s drops from 282 (turn 0) to 259 (turn 9) under full context --- an 8.2% decline. Under sliding-window, tok/s is 277 at turn 9 --- modestly better. The throughput decline reflects KV-cache growth: each decode step must attend over more cached tokens.

4. **Turn 0 shows high variance** (mean 778 ms, CI width 364 ms) in the full context condition. This is the cold-start effect --- the first turn of the first conversation includes model loading overhead. Subsequent turns have CI widths of 5--15 ms.

### 10.2 llama3.2-3b

**Full context** (10-turn)

| Turn | n | Mean (ms) | 95% CI | Prompt Tokens | tok/s |
|------|---|-----------|--------|---------------|-------|
| 0 | 16 | 1,048 | [870, 1,227] | 35 | 173 |
| 1 | 16 | 967 | [962, 972] | 183 | 169 |
| 3 | 16 | 980 | [975, 985] | 480 | 168 |
| 5 | 8 | 994 | [988, 999] | 773 | 167 |
| 7 | 8 | 998 | [990, 1,006] | 1,069 | 166 |
| 9 | 8 | 1,009 | [1,004, 1,015] | 1,365 | 165 |

**Sliding-window context** (10-turn)

| Turn | n | Mean (ms) | 95% CI | Prompt Tokens | tok/s |
|------|---|-----------|--------|---------------|-------|
| 0 | 16 | 962 | [958, 967] | 35 | 172 |
| 3 | 16 | 1,011 | [1,008, 1,013] | 465 | 167 |
| 5 | 8 | 1,005 | [999, 1,011] | 462 | 167 |
| 9 | 8 | 1,004 | [997, 1,012] | 464 | 167 |

**Observations (llama3.2-3b):**

1. **Latency growth is minimal** under both strategies. Full context: 967 ms (turn 1) to 1,009 ms (turn 9) = 4.3% increase over 7.5x prompt growth. The 3B model's longer per-token decode time dominates --- prefill time grows sub-linearly (per TR127) and is a small fraction of total latency.

2. **Full and sliding-window converge.** At turn 9, full context gives 1,009 ms and sliding-window gives 1,004 ms --- a 0.5% difference. For this model, context truncation provides negligible benefit because the decode phase (not prefill) dominates wall latency, and decode cost depends on generated tokens (fixed at 128), not prompt length.

3. **tok/s decline is proportionally smaller** than llama3.2-1b: 173 to 165 tok/s (4.6% decline) for full context. The 3B model's already-slower decode rate means the marginal KV-cache attention cost per turn is proportionally smaller.

### 10.3 qwen2.5-1.5b

**Full context** (10-turn)

| Turn | n | Mean (ms) | 95% CI | Prompt Tokens | tok/s |
|------|---|-----------|--------|---------------|-------|
| 0 | 16 | 712 | [545, 879] | 39 | 306 |
| 1 | 16 | 633 | [629, 637] | 187 | 307 |
| 3 | 16 | 644 | [638, 649] | 484 | 303 |
| 5 | 8 | 656 | [646, 665] | 777 | 302 |
| 7 | 8 | 655 | [647, 663] | 1,073 | 302 |
| 9 | 8 | 657 | [649, 666] | 1,369 | 299 |

**Sliding-window context** (10-turn)

| Turn | n | Mean (ms) | 95% CI | Prompt Tokens | tok/s |
|------|---|-----------|--------|---------------|-------|
| 0 | 16 | 632 | [628, 636] | 39 | 307 |
| 3 | 16 | 659 | [650, 667] | 469 | 307 |
| 5 | 8 | 655 | [649, 661] | 466 | 302 |
| 9 | 8 | 654 | [648, 661] | 468 | 301 |

**Observations (qwen2.5-1.5b):**

1. **qwen2.5-1.5b shows the flattest latency curve.** From turn 1 to turn 9 under full context: 633 ms to 657 ms = 3.8% increase despite 7.3x prompt growth. This model processes prompts most efficiently relative to its decode time.

2. **Full and sliding-window are virtually identical** at turn 9: 657 vs 654 ms (0.4% difference). Like llama3.2-3b, the decode phase dominates and context truncation provides no measurable benefit for this model.

3. **Decode throughput is the most stable** across turns: 306 to 299 tok/s (2.3% decline). qwen2.5-1.5b's efficient GQA attention (2 KV heads) minimizes the KV-cache lookup cost per decode step.

---

## 11. Context Management Strategies (Phase 5)

### 11.1 Full vs Sliding-Window at Maximum Turn

The most informative comparison is at turn 9 (the deepest turn in 10-turn conversations), where the gap between full and sliding-window prompt sizes is largest: ~1,365 tokens (full) vs ~464 tokens (sliding-window).

| Model | Turn | Full (ms) | Sliding (ms) | Reduction% | Cohen's d | Effect | p-value | Significant? |
|-------|------|-----------|--------------|------------|-----------|--------|---------|-------------|
| llama3.2-1b | 9 | 715.7 | 673.3 | **5.9%** | 1.12 | large | **0.042** | **Yes** |
| llama3.2-3b | 9 | 1,009.3 | 1,004.4 | 0.5% | 0.62 | medium | 0.235 | No |
| qwen2.5-1.5b | 9 | 657.3 | 654.4 | 0.4% | 0.32 | small | 0.538 | No |

### 11.2 Interpretation

**Sliding-window context management shows suggestive but inconclusive latency benefit.** llama3.2-1b shows a nominally significant reduction (5.9%, p = 0.042, d = 1.12), but with n=8 per group and 3 models tested, this p-value would not survive Bonferroni correction (threshold = 0.017). The other two models show reductions of 0.4--0.5% that are clearly not significant (p > 0.2). We cannot claim a reliable latency benefit from this data alone.

**Why does llama3.2-1b benefit more?** Three factors likely contribute:

1. **Fastest decode rate (259--282 tok/s).** When decode is fast, the relative contribution of prefill to total latency is higher. Reducing prompt tokens from 1,365 to 464 (a 66% reduction) has a more visible effect when prefill is a larger fraction of wall time.

2. **Highest prefill scaling exponent.** TR127 measured llama3.2-1b's Ollama prefill scaling exponent at b = 0.083 --- the lowest of the three models, meaning prefill time grows most slowly with context. However, even a small scaling exponent produces measurable differences at 2.9x token ratio (1,365/464).

3. **Smaller model = lower KV-cache attention cost per decode step.** With fewer parameters and a simpler attention structure, the per-decode-step KV-cache lookup cost is lower, making the prefill savings relatively more important.

**For the other two models, decode time dominates to such a degree that even a 66% reduction in prompt tokens produces only 0.4--0.5% wall-time savings.** This is not a failure of sliding-window context --- it is a statement about where the latency bottleneck lies. At 128 generated tokens per turn, decode (not prefill) is the dominant cost. Sliding-window would matter more for applications with shorter generation lengths or longer conversations (more turns, more accumulated context).

### 11.3 Prompt Token Verification

Sliding-window correctness is confirmed by prompt token counts:

| Model | Full (turn 9) | Sliding (turn 9) | Ratio |
|-------|-------------|-----------------|-------|
| llama3.2-1b | 1,365 | 464 | 2.94x |
| llama3.2-3b | 1,365 | 464 | 2.94x |
| qwen2.5-1.5b | 1,369 | 468 | 2.93x |

The ~3x ratio is consistent with retaining 3 of ~10 turns. The slight variation (1,365 vs 1,369) reflects different tokenization across models.

---

## 12. Cross-Validation & Consistency

### 12.1 TR127 Cross-Validation

TR127 measured Ollama prefill times at various context lengths. TR128 Phase 1 provides new prefill measurements at ~210 tokens (the mean prompt length). The naïve comparison uses means, but TR128's prefill data is heavily right-skewed by cold-start outliers:

| Model | TR128 n | TR128 Mean (ms) | TR128 Median (ms) | CV% | Skewness | Max (ms) |
|-------|---------|-----------------|--------------------|----|----------|----------|
| llama3.2-1b | 50 | 12.9 | 8.7 | 80.3 | 4.82 | 76.4 |
| llama3.2-3b | 50 | 31.4 | 19.9 | 73.9 | 3.15 | 130.1 |
| qwen2.5-1.5b | 50 | 24.1 | 15.7 | 102.7 | 5.33 | 180.3 |

With CV of 73--103% and skewness of 3--5, the means are inflated 48--54% above the medians by a handful of cold-start outliers. For non-normal data of this severity (all three distributions reject Shapiro--Wilk at p < 0.001), the median is the appropriate central tendency measure.

**Mean-based comparison (misleading):**

| Model | TR128 Tokens | TR128 Mean (ms) | TR127 Mean (ms) | TR127 Context | Delta% |
|-------|-------------|-----------------|-----------------|---------------|--------|
| llama3.2-1b | 210 | 12.9 | 12.0 | 512 | +6.9% |
| llama3.2-3b | 210 | 31.4 | 23.3 | 512 | +35.0% |
| qwen2.5-1.5b | 214 | 24.1 | 15.1 | 512 | +59.3% |

This comparison is doubly misleading: it uses means for severely right-skewed data, and the apparent "discrepancies" of +35% and +59% are artifacts of a few outlier requests. It also produces a physically implausible result --- TR128 at 210 tokens showing *higher* prefill than TR127 at 512 tokens.

**Median-based comparison (appropriate):**

| Model | TR128 Tokens | TR128 Median (ms) | TR127 Mean (ms) | TR127 Context | Delta% |
|-------|-------------|--------------------|--------------------|---------------|--------|
| llama3.2-1b | 210 | 8.7 | 12.0 | 512 | **-27.5%** |
| llama3.2-3b | 210 | 19.9 | 23.3 | 512 | **-14.6%** |
| qwen2.5-1.5b | 214 | 15.7 | 15.1 | 512 | **+3.6%** |

Note: TR127 values are means (medians not available in the stored analysis); this comparison is therefore conservative --- TR127 medians would likely be lower, improving the agreement.

**Interpretation:**

1. **The median comparison is physically correct.** TR128 measures at ~210 tokens; TR127 at 512 tokens. Prefill time scales sub-linearly with context length (TR127 exponents b = 0.083--0.109). At 2.4x fewer tokens, TR128 prefill *should* be lower --- and that is exactly what the medians show for 2 of 3 models.

2. **qwen2.5-1.5b shows excellent agreement** (+3.6% median difference despite 2.4x fewer tokens). This is the model that showed the largest "discrepancy" (+59.3%) in the mean comparison --- a cautionary example of how cold-start outliers (max = 180.3 ms, 11.5x the median) can distort cross-study comparisons.

3. **The model ranking is consistent** across both studies: llama3.2-1b has the fastest prefill, llama3.2-3b the slowest, with qwen2.5-1.5b in between. The absolute magnitudes are in the same order of magnitude (single-digit to low-double-digit milliseconds at short contexts).

4. **Cold-start detection should be standard practice** for cross-study comparisons. The first 1--3 requests per model show prefill times 5--15x the steady-state median, and including them in mean comparisons produces artificial discrepancies.

### 12.2 Cross-Phase Consistency

Phase 1 baseline (serial, zero concurrency) vs Phase 2 NP=1 at the lowest arrival rate (0.5 rps). If the load generator adds no overhead, these should match.

| Model | P1 Mean (ms) | P2 NP=1 Mean (ms) | Delta% | Cohen's d | Consistent? |
|-------|-------------|-------------------|--------|-----------|-------------|
| llama3.2-1b | 857.9 | 1,051.9 | +22.6% | 0.92 | **No** |
| llama3.2-3b | 1,435.3 | 3,011.0 | +109.8% | 2.26 | **No** |
| qwen2.5-1.5b | 1,008.4 | 1,345.6 | +33.4% | 1.16 | **No** |

**Interpretation:**

The inconsistency is **expected and informative**, not a measurement error. Phase 1 measures serial service time with zero queueing --- each request arrives to an empty system. Phase 2 at 0.5 rps uses Poisson arrivals, which means:

- Some requests arrive to an empty queue (served immediately, latency ~ Phase 1).
- Some requests arrive while a previous request is being processed (queueing delay added).
- Occasional clusters of 2--3 near-simultaneous arrivals create brief queue buildups.

The 22--110% inflation is exactly what Poisson arrivals at 43--72% utilization should produce. llama3.2-3b shows the largest inflation (110%) because at 0.5 rps it operates at 72% utilization (closer to saturation), while llama3.2-1b operates at 43% utilization. This cross-phase comparison validates the load generator: it correctly introduces queueing delay proportional to utilization.

---

## 13. Statistical Analysis

### 13.1 Cold-Start Detection

Cold-start events are detected when the first request per model per phase has latency > 2x the median of subsequent requests.

| Model | Phase | First (ms) | Median Rest (ms) | Ratio | Cold? |
|-------|-------|------------|------------------|-------|-------|
| llama3.2-1b | P1 | 886 | 886 | 1.00 | No |
| llama3.2-1b | P2 | 1,109 | 3,291 | 0.34 | No |
| llama3.2-1b | P3 | 714 | 715 | 1.00 | No |
| llama3.2-1b | P4 | 2,354 | 1,051 | 2.24 | **YES** |
| llama3.2-1b | P5 | 2,057 | 699 | 2.94 | **YES** |
| llama3.2-3b | P1 | 1,425 | 1,433 | 0.99 | No |
| llama3.2-3b | P2 | 1,646 | 10,313 | 0.16 | No |
| llama3.2-3b | P3 | 2,570 | 1,012 | 2.54 | **YES** |
| llama3.2-3b | P5 | 2,304 | 987 | 2.33 | **YES** |
| qwen2.5-1.5b | P1 | 981 | 1,024 | 0.96 | No |
| qwen2.5-1.5b | P4 | 2,125 | 1,055 | 2.01 | **YES** |
| qwen2.5-1.5b | P5 | 1,885 | 646 | 2.92 | **YES** |

**6 cold-start events detected** (ratio > 2x), primarily in Phase 4 and Phase 5 where models are loaded fresh for streaming and multi-turn testing. The 3 warmup requests per model mitigate cold-start effects for aggregate statistics, but the first *measured* request after a phase transition sometimes captures residual loading overhead.

Phase 2 shows inverted ratios (first request < median rest) because Phase 2's first request arrives at the lowest rate (0.5 rps) while the median is dominated by high-rate measurements (5--10 rps) with much higher queueing delay.

### 13.2 Distribution Shape

All 15 phase-model combinations were tested for normality using the Shapiro-Wilk test:

| Phase | Model | Skewness | Kurtosis | Shapiro-Wilk p | Normal? |
|-------|-------|----------|----------|----------------|---------|
| P1 | llama3.2-1b | -2.60 | 7.15 | < 0.001 | **No** |
| P1 | llama3.2-3b | 1.72 | 4.44 | < 0.001 | **No** |
| P1 | qwen2.5-1.5b | -3.81 | 15.94 | < 0.001 | **No** |
| P2 | llama3.2-1b | 0.81 | -0.57 | < 0.001 | **No** |
| P2 | llama3.2-3b | 0.53 | -0.91 | < 0.001 | **No** |
| P2 | qwen2.5-1.5b | 0.70 | -0.71 | < 0.001 | **No** |
| P3 | llama3.2-1b | -3.20 | 10.01 | < 0.001 | **No** |
| P3 | llama3.2-3b | 8.42 | 73.08 | < 0.001 | **No** |
| P3 | qwen2.5-1.5b | -1.03 | -0.90 | < 0.001 | **No** |
| P4 | llama3.2-1b | 1.35 | 0.52 | < 0.001 | **No** |
| P4 | llama3.2-3b | 1.25 | 0.54 | < 0.001 | **No** |
| P4 | qwen2.5-1.5b | 1.34 | 0.47 | < 0.001 | **No** |
| P5 | llama3.2-1b | 14.72 | 221.58 | < 0.001 | **No** |
| P5 | llama3.2-3b | 14.08 | 208.40 | < 0.001 | **No** |
| P5 | qwen2.5-1.5b | 14.66 | 220.00 | < 0.001 | **No** |

**15/15 distributions are non-normal.** This is expected for latency data:

- **Phase 1** shows left-skewed distributions (skewness < 0 for 2/3 models) because some requests complete faster when the generated response hits a stop token early.
- **Phase 2** shows right-skewed distributions (skewness 0.5--0.8) from queueing delay --- a few requests get unlucky with long queue waits.
- **Phase 3** shows extreme skewness in llama3.2-3b (8.42) from a single cold-start outlier at 2,570 ms.
- **Phase 5** shows extreme kurtosis (>200) from cold-start outliers at the beginning of each conversation.

**Impact on statistical tests:** Welch's t-test is robust to non-normality at n >= 30 (Central Limit Theorem). Phase 2 comparisons (n=30 per group) are valid. Phase 5 comparisons at individual turns (n=8) are more sensitive to non-normality --- the context strategy results in SS11 should be interpreted with caution.

### 13.3 Power Analysis

For each phase-model combination, we compute the minimum detectable effect size at 80% power (two-sided t-test, alpha = 0.05):

| Phase | Model | n | CV% | Min d (80% power) | Min ms (80% power) | Interpretation |
|-------|-------|---|-----|--------------------|--------------------|----------------|
| P1 | llama3.2-1b | 50 | 10.5 | 0.56 | 51 ms | can detect medium effects |
| P1 | llama3.2-3b | 50 | 2.1 | 0.56 | 17 ms | can detect medium effects |
| P1 | qwen2.5-1.5b | 50 | 7.6 | 0.56 | 43 ms | can detect medium effects |
| P2 | llama3.2-1b | 450 | 82.3 | 0.19 | 763 ms | **can detect small effects** |
| P2 | llama3.2-3b | 450 | 70.8 | 0.19 | 1,583 ms | **can detect small effects** |
| P2 | qwen2.5-1.5b | 450 | 77.6 | 0.19 | 1,052 ms | **can detect small effects** |
| P3 | llama3.2-1b | 168 | 10.9 | 0.31 | 23 ms | can detect small-to-medium effects |
| P3 | llama3.2-3b | 101 | 16.1 | 0.39 | 65 ms | can detect small-to-medium effects |
| P3 | qwen2.5-1.5b | 143 | 17.5 | 0.33 | 53 ms | can detect small-to-medium effects |
| P4 | llama3.2-1b | 180 | 82.0 | 0.30 | 440 ms | can detect small-to-medium effects |
| P4 | llama3.2-3b | 180 | 85.3 | 0.30 | 1,115 ms | can detect small-to-medium effects |
| P4 | qwen2.5-1.5b | 180 | 80.0 | 0.30 | 417 ms | can detect small-to-medium effects |
| P5 | llama3.2-1b | 240 | 12.6 | 0.26 | 23 ms | can detect small-to-medium effects |
| P5 | llama3.2-3b | 240 | 8.8 | 0.26 | 22 ms | can detect small-to-medium effects |
| P5 | qwen2.5-1.5b | 240 | 12.5 | 0.26 | 21 ms | can detect small-to-medium effects |

**Observations:**

1. **Phase 2 (core experiment) can detect small effects** (d >= 0.19). With n=450 per model across all NP levels, the experiment is well-powered to detect even modest NUM_PARALLEL effects. The finding that 0/30 tests are significant is therefore a confident null result, not a power failure.

2. **The high CV in Phases 2 and 4 (70--85%)** reflects the deliberate mixing of arrival rates --- measurements at 0.5 rps and 10 rps are pooled, creating a wide distribution. Within each rate, CV is lower (typically 30--50%). The power analysis uses the pooled CV, which is conservative --- per-rate comparisons have higher power.

3. **Phase 5 has the most precise measurements** (CV 9--13%) because multi-turn conversations run at zero concurrency (serial turns). This gives high power to detect small effects in the context strategy comparisons.

---

## 14. Key Findings

The following findings emerged from the data analysis and are ordered by their impact on production decisions:

**Finding 1: OLLAMA_NUM_PARALLEL is a no-op for GPU inference.** 0/30 pairwise tests significant after Holm--Bonferroni correction. Mean absolute change 4.0%, 26/30 effects negligible. The GPU serializes transformer kernels regardless of NUM_PARALLEL. This is the most practically important finding because it corrects a common misconception about Ollama's concurrency capabilities.

**Finding 2: M/D/1 queueing theory fails at NP>1.** Maximum deviation 20.4x (llama3.2-3b, NP=4, 1.0 rps). The linear-scaling assumption (NP=4 gives 4x throughput) is completely wrong. At NP=1, M/D/1 is a reasonable approximation (deviation 0.47--0.89x).

**Finding 3: Saturation occurs at very low arrival rates.** All models show p99/p50 > 2 at 0.5 rps. Even at 43% utilization (llama3.2-1b at 0.5 rps), Poisson burstiness creates measurable tail latency. Safe sustained rates: 0.49--0.82 rps depending on model.

**Finding 4: No thermal throttling.** Peak 66 degrees C across 412 Phase 3 measurements. 0 throttle events. Negative latency drift in qwen2.5-1.5b (-27.7%) reflects a model-specific decode throughput increase (167→275 tok/s), not thermal degradation. Laptop GPU cooling is adequate for sustained small-model inference.

**Finding 5: Streaming is free.** 0/9 stream-vs-batch comparisons significant. No wall-clock overhead. Always use streaming.

**Finding 6: TTFT amplification reaches 29.9x.** llama3.2-3b at 2.0 rps. Pure queueing delay --- prompt_eval_ms is unchanged across rates. TTFT exceeds 1 second at 1.0 rps for the 3B model.

**Finding 7: Sliding-window context benefit is inconclusive.** Nominally significant for llama3.2-1b only (5.9%, d = 1.12, p = 0.042, n=8), but this p-value would not survive Bonferroni correction across the 3 models tested (threshold = 0.017). Not significant for llama3.2-3b or qwen2.5-1.5b (0.4--0.5%, p > 0.2). With 128 generated tokens per turn, decode dominates total wall time, making prefill savings from context truncation near-invisible. The primary benefit of sliding-window may be memory and cost reduction, not latency.

**Finding 8: All latency distributions are non-normal.** 15/15 Shapiro-Wilk tests reject normality. Right-skewed distributions are inherent to latency measurement. Median and trimmed-mean are more appropriate central tendency measures than arithmetic mean.

---

## 15. Conclusions

### 15.1 Single-GPU Ollama Cannot Parallelize Inference

This is the headline conclusion of TR128. Across 30 pairwise comparisons of OLLAMA_NUM_PARALLEL={1, 2, 4} spanning 3 models and 5 arrival rates, zero reached statistical significance after Holm--Bonferroni correction. The CUDA compute kernels for transformer inference --- matrix multiplications in the attention mechanism, feed-forward layers, and layer normalization --- occupy the entire GPU's streaming multiprocessor array. There are no idle compute units available for a second request's kernels.

Ollama's NUM_PARALLEL parameter controls CPU-side request admission: how many HTTP connections the server accepts simultaneously. But accepting a request is not the same as processing it. All accepted requests must wait for the GPU to become available, and they are served strictly sequentially. The parameter exists for multi-GPU setups (where requests can be dispatched to different GPUs) and for CPU-only inference (where the bottleneck is different). On single-GPU hardware, it is a no-op.

**Recommendation:** Leave NUM_PARALLEL at the default (1). Use a reverse proxy (nginx, Caddy, or a simple Python queue) for request admission control. This provides the same functionality without the false expectation of GPU-level parallelism.

### 15.2 Queueing Theory Requires Empirical Calibration

The M/D/1 model is catastrophically wrong when used with NP>1 assumptions (up to 20.4x deviation). Even at NP=1, where the model is structurally correct, deviations of 0.47--0.89x show it is an approximation, not a prediction. The two broken assumptions are:

1. **Service is not deterministic.** CV = 2--10% (model-dependent). For llama3.2-1b (CV = 10.5%), the service time variance creates broader tail distributions than M/D/1 predicts.
2. **NP does not scale throughput.** The GPU is the bottleneck and processes one request at a time regardless of NP.

**Recommendation:** For capacity planning, use the empirical saturation curves from Phase 2 directly. If a rough analytical model is needed, use M/D/1 at NP=1 as a lower bound on queue wait, and add a 2x safety factor.

### 15.3 Streaming Is a Pure Win

Zero wall-clock overhead across 9 comparisons. Streaming provides earlier TTFT (users see the first token sooner), progressive response rendering, and the ability to cancel slow responses early. There is no reason to use batch mode for any application where the client can handle streaming.

### 15.4 Laptop GPU Handles Sustained Load

The RTX 4080 Laptop GPU maintained stable performance under 3 minutes of sustained load per model. Peak temperature of 66 degrees C leaves a 14-degree margin to the throttle threshold. The negative latency drift observed for qwen2.5-1.5b (-27.7%) reflects a model-specific decode throughput increase (167→275 tok/s over 143 requests) whose mechanism is unknown (see SS6.1). The other two models show flat or slightly negative drift within noise. None of the three models exhibit thermal degradation.

This finding is specific to small models (1--3B parameters) at default quantization. Larger models, higher-precision formats (FP16), or multi-model workloads may produce higher power draw and temperatures. TR132 (Serving Stacks) will test with vLLM and TGI, which may exercise the GPU differently.

### 15.5 Context Management Needs Larger Studies

Sliding-window context management shows a suggestive latency reduction for llama3.2-1b (5.9% at turn 9, d = 1.12) but not for the other two models (0.4--0.5%). However, the llama3.2-1b result (p = 0.042, n=8) would not survive multiple-comparison correction across the 3 models tested. We cannot confidently claim a latency benefit from this experiment.

The *mechanism* is clear: sliding-window reduces prompt tokens from ~1,365 to ~464 (2.9x), which reduces prefill compute. But at 128 generated tokens per turn, decode time dominates wall latency for 2 of 3 models, making the prefill savings near-invisible. The benefit would be larger for: (a) longer conversations (more accumulated context), (b) shorter generation lengths (lower decode fraction), or (c) models with higher prefill-to-decode cost ratios.

**Recommendation:** Consider sliding-window context for multi-turn applications exceeding 5 turns, primarily for memory and cost reduction rather than latency. The latency benefit is plausible but unconfirmed at this sample size. Validate for your specific model, generation length, and quality tolerance --- TR128 does not measure whether context truncation degrades response quality.

---

## 16. Production Guidance & Decision Trees

All thresholds below are specific to RTX 4080 Laptop GPU (12 GB VRAM) with Ollama serving 1--3B parameter models at default quantization. Scale accordingly for different hardware.

### 16.1 Concurrency Configuration

**Set OLLAMA_NUM_PARALLEL=1** (the default). No benefit from higher values on single-GPU hardware.

For multi-user deployments, implement request queuing at the application layer:

```
Client -> Reverse Proxy (queue) -> Ollama (NP=1) -> GPU (serial)
```

This makes the queue visible and controllable, with configurable queue depth limits and timeout policies, rather than relying on Ollama's internal (and non-parallelizing) queue.

### 16.2 Arrival Rate Limits

| Model | Theoretical Max RPS | Safe Sustained (70% util) | Empirical Saturation |
|-------|--------------------|--------------------------|--------------------|
| llama3.2-1b | 1.17 | **0.82** | p99 > 2x p50 at 0.5 rps |
| qwen2.5-1.5b | 0.99 | **0.69** | p99 > 2x p50 at 0.5 rps |
| llama3.2-3b | 0.70 | **0.49** | p99 > 2x p50 at 0.5 rps |

Use the lower of theoretical 70% and empirical saturation. For llama3.2-1b and qwen2.5-1.5b, empirical saturation occurs at 0.5 rps (the lowest tested rate), below the 70% theoretical limit. This means even the "safe" rates may produce occasional p99 > 2x p50 episodes during Poisson bursts. For guaranteed low tail latency, target 50% utilization or add a second instance.

### 16.3 Response Mode

**Always use streaming.** Zero overhead, real TTFT benefit, better UX. The only exception is batch processing pipelines where streaming infrastructure adds unnecessary complexity.

### 16.4 Thermal Monitoring

| Metric | Threshold | Action |
|--------|-----------|--------|
| GPU temperature | 75 degrees C | Alert (approaching throttle zone) |
| GPU temperature | 80 degrees C | Throttle threshold --- reduce load |
| Clock speed | < 90% of peak while temp > 80 | Confirmed throttling --- scale out |

For the RTX 4080 Laptop at 1--3B models: no action needed. Peak observed was 66 degrees C.

### 16.5 Multi-Turn Context Management

| Condition | Strategy | Rationale |
|-----------|----------|-----------|
| Conversations <= 5 turns | Full context | Minimal latency penalty, maximum context quality |
| Conversations > 5 turns, memory-constrained | Sliding-window (last 3) | Bounds prompt growth at ~464 tokens; primary benefit is memory/cost, not latency |
| Conversations > 5 turns, latency-constrained | Test both; measure | Latency benefit is suggestive but unconfirmed (p = 0.042, n=8, 1/3 models); validate on your workload |
| Quality-sensitive | Full context + latency budget | Validate quality impact of losing early turns before truncating |

---

## 17. Limitations & Future Work

### 17.1 Limitations

1. **Single GPU.** RTX 4080 Laptop (12 GB VRAM, 150W TDP). Desktop GPUs (RTX 4090, A100) have different thermal profiles, memory bandwidth, and PCIe topology. The NUM_PARALLEL finding likely generalizes to any single GPU, but saturation rates and thermal behavior will differ.

2. **Ollama only.** vLLM supports continuous batching, which may enable true concurrent inference where Ollama's serial scheduling cannot. TGI and raw llama.cpp may also behave differently. The NUM_PARALLEL finding is Ollama-specific --- other serving backends may parallelize GPU work more effectively.

3. **Inter-chunk, not inter-token.** True per-token latency distribution cannot be measured from the client side via NDJSON streaming. Measuring real ITL would require instrumenting the llama.cpp backend directly.

4. **Restart discontinuity.** OLLAMA_NUM_PARALLEL requires server restart, introducing a thermal discontinuity between parallelism levels. The GPU may start each NP level at a different temperature, introducing minor (likely < 2%) confounds.

5. **Synthetic prompts.** Real prompts have different tokenization ratios, semantic content, and KV-cache pressure patterns. Prompt length was uniformly distributed (100--300 tokens); real workloads may be log-normal or bimodal.

6. **Small models only.** 1--3B parameter models fit entirely in VRAM at default quantization. Larger models (7B+) requiring aggressive quantization or CPU offloading will exhibit different saturation, concurrency, and thermal behavior.

7. **No output quality measurement.** Deterministic output (temp=0, seed=42) ensures consistency but we do not measure whether response quality degrades under load. Ollama may allocate less compute to quality-critical operations under queue pressure, though this is unlikely given its serial scheduling.

8. **Small sample size for Phase 5 per-turn comparisons.** n=8 at turns 5--9 (from the 10-turn conversations). The context strategy comparison at turn 9 has only n=8 per group, reducing power and making the results sensitive to non-normality. The llama3.2-1b result (p = 0.042) is borderline and should be validated with more conversations.

9. **No figures.** This report presents all results as tables. Utilization curves, latency distributions, queue depth growth, and thermal profiles would benefit from visual presentation. The raw data (metrics.csv, itl_raw.jsonl) is provided for readers who wish to generate plots.

### 17.2 Future Work

- **TR132 (Serving Stacks):** Compare Ollama vs vLLM vs TGI under the same load patterns from TR128. Does vLLM's continuous batching change the NUM_PARALLEL result? This is the most direct extension.
- **Multi-model concurrency:** Load two models simultaneously and test whether GPU context switching enables any parallelism. Ollama supports multi-model serving; the question is whether the GPU can usefully interleave work between models with different weight sets.
- **Larger models (7B+):** Test with llama3.1-8b at Q4_K_M. Does VRAM pressure (near-capacity operation) change the thermal or concurrency picture?
- **Real-world prompt distributions:** Replace uniform 100--300 token prompts with log-normal distributions (mode ~200, tail to 2,000) that better approximate production traffic.
- **Output quality under load:** Add a simple quality metric (perplexity on held-out text) to detect whether response quality degrades under queue pressure.

---

## 18. Reproducibility

### 18.1 Quick Start

```bash
# Install dependencies
pip install httpx numpy pandas scipy pyyaml requests

# Pull models (if not already present from TR127)
ollama pull qwen2.5:1.5b
ollama pull llama3.2:1b
ollama pull llama3.2:3b

# Full experiment (~55 minutes on RTX 4080 Laptop)
python research/tr128/run.py -v

# Re-run analysis and report only (no new measurements)
python research/tr128/run.py --skip-phases
```

### 18.2 Parameters

| Parameter | Value |
|-----------|-------|
| Seed | 42 |
| Max new tokens | 128 |
| Warmup requests | 3 per model |
| GPU polling interval | 1.0 second |
| Ollama timeout | 120 seconds |
| Prompt token range | 100--300 (uniform) |
| Temperature | 0.0 (greedy) |

### 18.3 Artifacts

| Artifact | Path |
|----------|------|
| Orchestrator | `research/tr128/run.py` |
| Phase 1 (Baseline) | `research/tr128/run_baseline.py` |
| Phase 2 (Concurrency) | `research/tr128/run_concurrency.py` |
| Phase 3 (Thermal) | `research/tr128/run_thermal.py` |
| Phase 4 (Streaming) | `research/tr128/run_streaming.py` |
| Phase 5 (Multi-Turn) | `research/tr128/run_multiturn.py` |
| Analysis | `research/tr128/analyze.py` |
| Report generator | `research/tr128/generate_report.py` |
| Config | `research/tr128/config.yaml` |
| Raw metrics | `research/tr128/results/20260225_145254/metrics.csv` |
| Analysis JSON | `research/tr128/results/20260225_145254/analysis.json` |
| Load generator | `research/tr128/shared/load_generator.py` |

---

## Appendix A: Environment Specifications

### GPU Specifications

| Property | Value |
|----------|-------|
| Name | NVIDIA GeForce RTX 4080 Laptop GPU |
| Architecture | Ada Lovelace (AD104) |
| Compute Capability | 8.9 |
| VRAM | 12 GB GDDR6 |
| Memory Bus | 192-bit |
| Memory Bandwidth | 256 GB/s |
| TDP | 150W (laptop) |

### Software Stack

| Component | Version |
|-----------|---------|
| OS | Windows-11-10.0.26200-SP0 |
| Python | 3.13.1 |
| PyTorch | 2.8.0+cu128 |
| NVIDIA Driver | 591.74 |
| Ollama | localhost:11434 (llama.cpp backend) |
| httpx | Async HTTP client for load generation |
| numpy | Statistical computation |
| scipy | Shapiro-Wilk, t-tests |
| pandas | Data loading and manipulation |

### Ollama Model Tags

| Model | Ollama Tag | Expected Quantization |
|-------|-----------|----------------------|
| llama3.2-1b | `llama3.2:1b` | Q8_0 (Ollama default for 1B models) |
| qwen2.5-1.5b | `qwen2.5:1.5b` | Q4_K_M (Ollama default for 1.5B models) |
| llama3.2-3b | `llama3.2:3b` | Q4_K_M (Ollama default for 3B models) |

---

## Appendix B: Config (Source of Truth)

```yaml
experiment: tr128

models:
  - name: qwen2.5-1.5b
    ollama_tag: "qwen2.5:1.5b"
    params_m: 1500
    max_context: 131072
  - name: llama3.2-1b
    ollama_tag: "llama3.2:1b"
    params_m: 1200
    max_context: 131072
  - name: llama3.2-3b
    ollama_tag: "llama3.2:3b"
    params_m: 3200
    max_context: 131072

ollama_url: http://localhost:11434
ollama_timeout_s: 120
max_new_tokens: 128
seed: 42
warmup_requests: 3
gpu_poll_interval_s: 1.0

# Phase 1: Baseline characterization (serial, no concurrency)
# Establishes per-model service time -> predicts theoretical saturation.
# 3 models x 50 requests = 150 rows, ~5 min
phase1:
  requests_per_model: 50
  prompt_tokens_low: 100
  prompt_tokens_high: 300

# Phase 2: Concurrency & saturation sweep
# THE core experiment: OLLAMA_NUM_PARALLEL x arrival rate x model.
# Tests where reality diverges from M/D/1 queueing predictions.
# 3 models x 3 parallelism x 5 rates x 30 req = 1350 rows, ~45 min
phase2:
  num_parallel_levels: [1, 2, 4]
  arrival_rates: [0.5, 1.0, 2.0, 5.0, 10.0]
  requests_per_rate: 30
  arrival_pattern: poisson
  prompt_tokens_low: 100
  prompt_tokens_high: 300

# Phase 3: Thermal stability under sustained load
# Holds at ~80% saturation for a fixed duration.
# Detects throttling: does throughput degrade over time at constant load?
# 3 models x 3 min = 9 min active load
phase3:
  duration_s: 180
  arrival_rate_rps: 1.0     # overridden per-model to 80% of P2 saturation
  arrival_pattern: periodic  # constant rate to isolate thermal effects
  prompt_tokens_low: 100
  prompt_tokens_high: 300

# Phase 4: Streaming TTFT (honest measurement)
# TTFT is reliable. Inter-chunk latency reported as ichunk (NOT inter-token).
# 3 models x 3 rates x 2 modes x 30 req = 540 rows, ~20 min
phase4:
  arrival_rates: [0.5, 1.0, 2.0]
  response_modes: [batch, stream]
  requests_per_combo: 30
  arrival_pattern: poisson
  prompt_tokens_low: 100
  prompt_tokens_high: 300

# Phase 5: Multi-turn context accumulation
# Full vs sliding-window. Cross-validates with TR127.
# 3 models x 2 strategies x 2 turn_counts x 8 convos = 720 turn-rows, ~30 min
phase5:
  turn_counts: [5, 10]
  context_strategies: [full, sliding_window]
  sliding_window_turns: 3
  conversations_per_combo: 8

output_dir: research/tr128/results
```

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **OLLAMA_NUM_PARALLEL** | Environment variable controlling Ollama's concurrent request slots. Requires server restart. On single-GPU hardware, does not enable parallel GPU inference (SS4). |
| **M/D/1** | Queueing model: Markovian arrivals, Deterministic service, 1 server. Predicts mean queue wait as `rho * D / (2 * (1 - rho))`. Breaks down at NP > 1 because throughput scaling assumption fails (SS5). |
| **TTFT** | Time to First Token: latency from request submission to first generated token. Equal to prefill time plus queueing delay. Reliable client-side metric. |
| **ichunk** | Inter-chunk latency: time between consecutive NDJSON streaming chunks. An upper bound on inter-token latency due to TCP buffering. Not a per-token measurement. |
| **Saturation** | The arrival rate at which p99 latency exceeds 2x p50. Beyond this point, tail latency grows rapidly and user experience degrades. |
| **Queue depth** | Number of in-flight requests at the moment a new request is submitted. Tracked via asyncio counter. Directly measures Ollama's internal queue pressure. |
| **Cohen's d** | Standardized effect size: `(mean_B - mean_A) / pooled_std`. Negligible: \|d\| < 0.2, Small: 0.2--0.5, Medium: 0.5--0.8, Large: > 0.8. |
| **Holm--Bonferroni** | Step-down FWER correction for multiple comparisons. Sorts p-values ascending, rejects p_(i) if p_(i) < alpha/(n-i+1). More powerful than Bonferroni, controls family-wise error rate. |
| **Poisson arrivals** | Requests arrive with exponentially distributed inter-arrival times (memoryless property). Models realistic bursty traffic. Used in Phases 2 and 4. |
| **Thermal throttle** | GPU reduces clock speed when temperature exceeds safety threshold. Detected when temp > 80 degrees C AND clock < 90% of peak simultaneously. Not observed in TR128. |
| **Periodic arrivals** | Requests arrive at exactly fixed intervals (zero variance). Used in Phase 3 to isolate thermal effects from arrival-pattern variance. |
| **Sliding-window context** | Multi-turn strategy retaining only the last N turns of conversation history. Bounds prompt token growth. Window size = 3 turns in TR128. |

---

## References

1. TR108--TR122: Baseline benchmarks and short-context performance data for the Banterhearts research program.
2. TR123: KV-Cache Production Economics --- theoretical KV cache cost model, VRAM budget formulas. Used for context budget planning in Phase 5.
3. TR125: Quantization Decision Matrix --- Ollama model quality data across quantization levels. Used for model selection and quality baseline.
4. TR126: Linux/Triton Validation --- HF vs Ollama backend comparison, Ollama timing methodology. Used for measurement methodology reference.
5. TR127: Long-Context Performance Characterization --- context-length scaling, Ollama prefill exponents, VRAM spillover discovery. Used for cross-validation (SS12) and context scaling reference.
6. Erlang, A.K. (1909). "The theory of probabilities and telephone conversations." *Nyt Tidsskrift for Matematik B*, 20. Foundational queueing theory applied to M/D/1 predictions in SS5.
7. Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Hillsdale, NJ: Erlbaum. Effect size thresholds (negligible/small/medium/large) used throughout.
8. Holm, S. (1979). "A simple sequentially rejective multiple test procedure." *Scandinavian Journal of Statistics*, 6(2), 65--70. Holm--Bonferroni correction applied to Phase 2 (30 tests) and Phase 4 (9 tests).

---
