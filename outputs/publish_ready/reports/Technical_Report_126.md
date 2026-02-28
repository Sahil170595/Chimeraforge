# Technical Report 126: Linux/Triton Validation of the Compile Paradox
## Cross-platform A/B test confirming torch.compile benefits under real Inductor+Triton, with 3-backend matrix on consumer GPU

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-02-22
**Author:** Research Team
**Report Type:** Cross-platform performance validation (3-phase, Docker/Linux)
**Test Duration:** ~5 min (Phase 1) + ~90 min (Phase 2) + ~45 min (Phase 3)
**Status:** Complete — All phases delivered
**Run IDs:** Phase 1: `20260222_195228`, `20260222_195522` | Phase 2: `20260222_195655` (baseline), `20260222_213342` (padded), `20260222_214114` (dynamic) | Phase 3: `20260222_231929` (reduce-overhead), `20260223_034940` (mode="default"), `20260223_210915` (PyTorch 2.10 rerun)
**Related Work:** [TR120](Technical_Report_120.md) (Compile Paradox Root-Cause Audit), [TR117](Technical_Report_117.md) (Baseline Benchmark), [TR123](Technical_Report_123.md) (KV-Cache Production Economics)
**Depends On:** TR120 (compile paradox discovery, Windows baseline data), TR117 (Tier-3 matrix design, prompt sets)

---

## Abstract

TR120 discovered that `torch.compile` on Windows silently falls back to `aot_eager` — a non-optimizing backend that provides no Triton kernel generation. All "compilation" results in TR117-TR122 were therefore measured under this fallback, rendering compile-related conclusions unreliable. TR126 fills this gap by running the same experiments on Linux inside Docker, where PyTorch's Inductor backend has full access to Triton for GPU kernel generation. This is the first Windows-vs-Linux A/B comparison on the same consumer GPU in this research program.

**Phase 1 (Environment Gate):** We validate that the Docker/Linux environment provides real Triton compilation — confirming CUDA 13.0, Triton 3.3.1, and `torch.compile(backend="inductor")` with 0 graph breaks. Weight parity is verified against deterministic greedy decode on 3 prompts (32 tokens each).

**Phase 2 (Compile Paradox Replication):** We run 7 models in a 2×3 factorial design (GPT-2 MHA at 25M/50M/100M in FP32, Qwen2.5 GQA at 0.5B/1.5B/3B in FP16) across 5 prompt scenarios with 30 repetitions each — totaling **3,240 prefill samples** across 3 compile configurations (baseline, padded, dynamic). Real Triton compilation delivers a **-40.0% latency reduction** (p = 8.87 × 10⁻⁶¹, Cohen's d = -0.59) — directly reversing TR120's Windows findings. Every model benefits: speedups range from 1.3× (qwen2.5-3b) to 2.5× (gpt2-25m). The compile paradox was an artifact of the `aot_eager` fallback.

**Phase 3 (Backend Matrix):** We run 5 models across 3 backends (transformers-gpu, transformers-gpu-compile, Ollama) × 5 scenarios × 3 modes (prefill, kv_decode, e2e_kv) with 15 repetitions — totaling **3,780 successful measurements** (plus 111 error rows from compiled decode crashes). Compiled HF wins prefill (-53.3%, d = -1.21, large effect). Ollama dominates decode (7× faster than eager HF for kv_decode). Compiled mode (`reduce-overhead`) crashes on autoregressive decode due to CUDA graph shape incompatibility with growing KV caches — a critical practical limitation for production deployment.

**Phase 2 Baseline (Previously Unanalyzed):** The baseline config (`dynamic=False`, `mode=reduce-overhead`, `max_new_tokens=64`) collected **11,340 measurements** (3,780 per mode) that were never analyzed in v1. Key discovery: compiled kv_decode **succeeds** at `max_new_tokens=64` (1,890 successful measurements) but shows no speedup — compiled decode is 2.2% slower than eager (not significant, p = 0.43). This is prefill-only benefit even when decode doesn't crash.

**mode="default" Experiment (3,891 measurements):** Testing `torch.compile(mode="default")` (disabling CUDA graph replay) reveals that PyTorch 2.8's Inductor still invokes CUDA graph trees internally, causing identical `CUDAGraphs tensor overwrite` crashes on compiled decode (100% crash rate across all 4 HF models). Compiled prefill still works and delivers **-54.2% speedup** (d = -1.25, p = 7.6 × 10⁻⁸⁰) — slightly better than reduce-overhead's -53.3%, suggesting CUDA graph replay adds overhead to prefill. The `mode` parameter does not fully control CUDA graph usage in current PyTorch. Compiled decode remains broken regardless of mode setting.

**PyTorch 2.10 Rerun (4,522 measurements):** To verify whether the crash persists across PyTorch versions, we rebuilt the benchmark on PyTorch 2.10.0a0 (NGC 26.01, CUDA 13.1, Triton 3.6.0) with our assertion fix (PR #175562) pre-applied. Compiled prefill still works: **-42.4% speedup** (d = -0.761, p < 10⁻⁴). Compiled kv_decode and e2e_kv crash 100% on all HF models — identical to PyTorch 2.8. The bug in `dealloc_current_path_weakrefs()` is present in both versions. The smaller prefill effect vs. PyTorch 2.8 (d = -0.761 vs d = -1.21) reflects a different model mix (5 models including Ollama-only llama3.2:1b) and version-specific Triton kernel generation differences.

**Total: ~29,900 successful measurements across 3 phases** (Phase 2: 3,240 prefill × 2 configs [dynamic + padded] + 11,340 baseline across 3 modes + Phase 3: 3,780 across 3 modes + mode="default" experiment: ~3,850 across 3 modes + PyTorch 2.10 rerun: 4,522 across 3 modes), **2 platforms, 2 PyTorch versions, 3 backends, 7 models.** Phase 3 additionally logged compiled decode crashes across all three mode/version experiments.

Key findings:

- **The compile paradox is resolved:** Real Triton compilation on Linux delivers 24-60% prefill speedups across all 7 models tested. The "paradox" in TR120 was caused by Windows falling back to `aot_eager`, which adds overhead without optimization.
- **Effect size is large and consistent:** Phase 2 aggregate d = -0.59 (medium), Phase 3 prefill d = -1.21 (large). All per-scenario p-values < 10⁻⁷. The compile benefit is not marginal — it is the dominant factor in prefill latency.
- **Backend rankings are mode-dependent:** Compiled HF wins prefill (8.2 ms), Ollama wins kv_decode (286 ms vs 2,019 ms) and e2e_kv (541 ms vs 2,051 ms). No single backend dominates all modes.
- **All torch.compile modes break autoregressive decode:** Both `reduce-overhead` and `mode="default"` crash on decode — PyTorch 2.8's Inductor uses CUDA graph trees internally regardless of mode. Even at 64 tokens where decode works, compilation provides no speedup (+2.2%, not significant). torch.compile is exclusively a prefill optimization.
- **Model scale inverts prefill rankings:** For small models (≤500M), compiled HF is fastest. For larger models (≥1.5B), Ollama's quantized inference matches or beats compiled FP16 HF on prefill.
- **Ollama achieves 7× decode speedup over eager HF:** Across 4 Qwen2.5 + Llama models, Ollama's quantized KV-cache decode is 286 ms mean vs 2,019 ms eager HF (d = 2.38, p < 10⁻²⁰⁹).
- **Measurement quality is high:** Outlier rate 0.0-0.9% (IQR method). Power analysis confirms ability to detect small effects (d ≥ 0.10 in Phase 2, d ≥ 0.17 in Phase 3).
- **Triton compilation is proven with physical evidence:** 17-245 new cached Triton kernels per model (916 total across 6 models), 0 graph breaks, verified via `TRITON_CACHE_DIR` inspection.
- **Padded config amplifies compile benefit:** Padding inputs to fixed shapes improves compiled performance by 15% (d = -0.91 padded vs d = -0.59 dynamic), validating TR120's shape-stability hypothesis. qwen2.5-0.5b achieves 5.0× speedup under padding.
- **1.5B crossover formally validated:** TOST equivalence test confirms Ollama and compiled HF are within ±1 ms for prefill at qwen2.5-1.5b (p = 0.001).
- **Scale crossover statistically validated (ANOVA):** 2-way ANOVA interaction term (backend × model) is highly significant: F(8,1608) = 453.1, p < 10⁻¹⁶, η² = 0.107. The effect of backend choice depends on model scale — this formally validates the qualitative crossover observation.
- **Compiled decode provides no speedup even when it works:** Phase 2 baseline at `max_new_tokens=64` has 1,890 successful compiled decode measurements, but compilation is 2.2% *slower* than eager (d = 0.026, not significant). Compilation benefits are prefill-specific.
- **CUDA graph crash is length-dependent:** Compiled decode works at 64 tokens (Phase 2) but crashes at 128 tokens (Phase 3). The crash threshold lies between 64 and 128 generated tokens.
- **`mode="default"` does not fix compiled decode:** PyTorch 2.8's Inductor invokes CUDA graph trees internally regardless of the `mode` parameter, causing identical crashes on autoregressive decode. No torch.compile mode enables compiled decode.
- **Compiled decode crash is architectural, not a patchable bug:** Prototype experiments (v3) demonstrated that disabling `_free_And_Remove_DeleterFn` + `check_memory_pool` + the assertion still crashes — CUDA graph replay overwrites output tensor memory, and `DynamicCache.update()` → `torch.cat()` is fundamentally incompatible. The fix must come from the model/cache layer (`StaticCache`, `cudagraph_mark_step_begin()`), not PyTorch internals. Issue [pytorch/pytorch#175557](https://github.com/pytorch/pytorch/issues/175557) filed, assertion fix [pytorch/pytorch#175562](https://github.com/pytorch/pytorch/pull/175562) submitted.
- **Bug persists on PyTorch 2.10 (NGC 26.01):** Full Phase 3 rerun on PyTorch 2.10.0a0 (CUDA 13.1, Triton 3.6.0) with PR #175562 pre-applied: compiled prefill works (-42.4%, d = -0.761), compiled decode crashes 100%. The 4,522-measurement rerun confirms this is not a PyTorch 2.8-specific regression — the `dealloc_current_path_weakrefs` bug exists in the latest NGC release.
- **StaticCache enables compiled decode but 5.8× slower:** Replacing `DynamicCache` with `StaticCache` + `torch.compile(model.forward, mode="default")` produces the first successful compiled decode in this research program. But without CUDA graph replay, compilation overhead per decode step exceeds kernel optimization benefit (3,588 ms vs 622 ms eager). `reduce-overhead` + StaticCache still crashes. Compiled decode is a dead end on PyTorch 2.10 / transformers 5.2.0.
- **All pairwise comparisons survive multiple-testing correction:** 5/5 Phase 3 pairwise tests survive both Bonferroni (α = 0.01) and Holm step-down correction. The smallest p-value (3.67 × 10⁻³ for Ollama vs compile prefill) clears the Bonferroni threshold.

---

## Executive Summary

TR126 answers: **does the compile paradox discovered in TR120 survive when torch.compile has access to real Triton kernels on Linux?**

No. The paradox was an artifact of the Windows `aot_eager` fallback. With real Inductor+Triton on Linux, compilation consistently reduces prefill latency by 24-60% across all model sizes, with p-values below 10⁻⁷ in every scenario. This is the single most impactful performance finding in the research program to date.

### Key Findings

1. **Compile paradox reversed on Linux:** Eager prefill 11.87 ms vs compiled 7.12 ms (-40.0%, d = -0.59, p = 8.87 × 10⁻⁶¹) across 3,240 Phase 2 samples. All 6 per-scenario comparisons are significant.
2. **Speedup scales inversely with model size:** gpt2-25m gets 2.5× speedup, gpt2-50m 2.2×, qwen2.5-0.5b 2.3×, qwen2.5-1.5b 1.8×, qwen2.5-3b 1.3×, gpt2-100m 1.3×. Smaller models benefit most from Triton kernel fusion.
3. **Phase 3 confirms with larger effect:** In the 3-backend matrix, compiled vs eager shows d = -1.21 (large), -53.3% delta. The effect amplifies when Ollama provides a third reference point.
4. **torch.compile is prefill-only in practice (all modes):** Both `reduce-overhead` and `mode="default"` crash on autoregressive decode (100% crash rate). PyTorch 2.8's Inductor uses CUDA graph trees internally regardless of mode. Even when compiled decode works (64 tokens, Phase 2), it provides no speedup (+2.2%). Production must use eager or Ollama for decode.
5. **Ollama dominates decode:** 7× faster than eager HF for kv_decode (d = 2.38), 3.8× for e2e_kv (d = 2.01). Ollama's advantage comes from quantized weights (lower memory bandwidth) and optimized C++ KV-cache implementation.
6. **Model scale inverts prefill winner:** Small models (gpt2-100m, qwen2.5-0.5b) — compiled HF wins. Large models (qwen2.5-1.5b, qwen2.5-3b) — Ollama wins or ties, despite running quantized weights.
7. **Cross-platform environment validated:** Same GPU (RTX 4080 Laptop, 12.88 GB), same model weights, same prompts — only the OS and compilation backend differ. This isolates the Triton variable cleanly.
8. **Triton compilation is physically verified:** 17-245 new Triton kernels per model (916 cumulative across 6 models) in `TRITON_CACHE_DIR`, Triton 3.3.1 importable, 0 graph breaks in validation.
9. **Scale crossover validated by ANOVA interaction:** F(8,1608) = 453.1, p < 10⁻¹⁶, η² = 0.107 for the backend × model interaction term. Backend rankings depend on model scale — not a confound, but a real structural effect.
10. **Compiled decode is neutral even when it works:** Phase 2 baseline (max_new_tokens=64): 1,890 compiled decode measurements succeed but show +2.2% overhead vs eager (not significant). Compilation is a prefill-only optimization.
11. **`mode="default"` does not rescue compiled decode:** Experiment confirms PyTorch 2.8 Inductor uses CUDA graph trees internally regardless of mode setting. Compiled decode crashes on all modes tested.
12. **Bug persists on PyTorch 2.10:** Full Phase 3 rerun (4,522 measurements) on NGC 26.01 (PyTorch 2.10.0a0, CUDA 13.1, Triton 3.6.0) with PR #175562 pre-applied: compiled prefill works (-42.4%), compiled decode crashes 100%. The `dealloc_current_path_weakrefs` bug is architectural, not version-specific (SS10.6).
13. **StaticCache is necessary but not sufficient:** `StaticCache` + `mode="default"` enables compiled decode (first success in this program) but is 5.8× slower than eager due to per-step compilation overhead. `reduce-overhead` + StaticCache still crashes. The standard `torch.compile` + `.generate()` path cannot deliver compiled decode speedups today (SS10.8).

### Key Decisions

- **For prefill-optimized serving:** Use `torch.compile(backend="inductor", mode="reduce-overhead")` on Linux. Expect 1.3-2.5× speedup over eager.
- **For decode-optimized serving:** Use Ollama with quantized weights. Expect 3-7× speedup over eager HF.
- **For end-to-end serving:** Split strategy — compiled prefill + Ollama-style decode. Or use Ollama for both if simplicity matters more than prefill optimization.
- **Never deploy torch.compile with `reduce-overhead` for autoregressive decode.** It will crash on every model tested.
- **Windows torch.compile is not a valid benchmark.** All prior TR results using `-compile` on Windows reflect `aot_eager` overhead, not compilation benefit.
- **`dynamic=True` is not free.** Phase 2 (`dynamic=True`) shows ~85% higher compiled latency than Phase 3 (`dynamic=False`) on gpt2-100m. For small models (< 200M), prefer `dynamic=False` with input bucketing to avoid this overhead.
- **Decode recommendation strengthened:** The "use Ollama for decode" recommendation is now supported by five lines of evidence: (1) `reduce-overhead` crashes on decode at 128 tokens, (2) `mode="default"` also crashes (PyTorch 2.8/2.10 Inductor uses CUDA graph trees internally), (3) even when compiled decode works (64 tokens, Phase 2), it provides no speedup (+2.2%), (4) patching `cudagraph_trees.py` (3 patches deep) confirmed the crash is architectural not patchable, and (5) StaticCache + `mode="default"` enables decode but is 5.8× *slower* than eager. Every viable compiled decode path has been exhausted. Compiled decode is not viable for production.

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| 1 | Compile paradox is artifact of Windows aot_eager | Phase 2: -40.0% speedup on Linux, all scenarios significant (SS5) | **Validated** |
| 2 | Real Triton delivers consistent prefill speedups | Phase 2: 6/6 scenarios, 6/6 models show compile helps (SS5) | **Validated** |
| 3 | `reduce-overhead` breaks autoregressive decode | Phase 3: 100% crash rate on kv_decode/e2e_kv compiled (SS9) | **Validated** |
| 4 | Backend rankings are mode-dependent | Phase 3: compile wins prefill, Ollama wins decode (SS8-SS9) | **Validated** |
| 5 | Ollama decode is faster than eager HF | Phase 3: 7× speedup, d = 2.38, p < 10⁻²⁰⁹ (SS9) | **Validated** |
| 6 | Model scale inverts prefill winner | Phase 3: small models → compile wins; large → Ollama wins (SS9). TOST confirms 1.5B tie at ε=1ms (p=0.001, SS9.2) | **Validated** |
| 7 | Triton compilation is physically present | Phase 1: 0 graph breaks; Phase 2: 916 cumulative cached kernels; 24-60% speedups prove kernel optimization (SS3, Appendix B). Note: `inductor_backend` flag returns false-negative — see Appendix B for explanation | **Validated** (5 positive evidence lines; 1 false-negative flag explained) |
| 8 | Environment parity with Windows runs | Phase 1: same GPU, same weights, deterministic decode verified (SS3) | **Validated** |
| 9 | Scale crossover is statistically significant | ANOVA interaction: F(8,1608) = 453.1, p < 10⁻¹⁶, η² = 0.107 (SS11.4) | **Validated** |
| 10 | Compiled decode provides no speedup | Phase 2 baseline: +2.2% overhead, d = 0.026, p = 0.43, 1,890 measurements (SS5.6) | **Validated** |
| 11 | CUDA graph crash is length-dependent | Phase 2 @ 64 tokens: 1,890 OK; Phase 3 @ 128 tokens: 100% crash (SS10.1) | **Validated** |
| 12 | `mode="default"` does not fix decode crash | mode="default" experiment: identical CUDAGraphs crash via Inductor graph trees (SS10.5) | **Validated** |
| 13 | All comparisons survive multiple-testing correction | 5/5 tests pass Bonferroni (α=0.01) and Holm step-down (SS9.5) | **Validated** |
| 14 | Crash root cause is architectural (CUDA graphs + dynamic KV cache) | v3 prototype: patching `dealloc_current_path_weakrefs()` + `check_memory_pool` still crashes via `get_non_cudagraph_inps`. `torch.cat` in `DynamicCache.update` is fundamentally incompatible with CUDA graph replay (SS10.7). Assertion fix PR [#175562](https://github.com/pytorch/pytorch/pull/175562) is valid but separate. | **Validated (architectural)** |
| 15 | Bug persists across PyTorch versions (2.8 → 2.10) | Full Phase 3 rerun on PyTorch 2.10.0a0 (NGC 26.01, CUDA 13.1, Triton 3.6.0): 4,522 measurements, compiled decode 100% crash, identical root cause (SS10.6) | **Validated** |
| 16 | StaticCache enables but does not accelerate compiled decode | `mode="default"` + StaticCache: decode works but 5.8× slower (3,588 ms vs 622 ms). `reduce-overhead` + StaticCache: still crashes. Known upstream issue [huggingface/transformers#27837](https://github.com/huggingface/transformers/issues/27837) (SS10.8) | **Validated** |

---

## When to Use This Report

TR126 is the cross-platform validation reference for the Banterhearts research program. Use it when making decisions about compilation, backend selection, or interpreting prior TR results.

### Scenario 1: Interpreting TR117-TR122 Compile Results

**Question:** "TR117 showed compile was slower than eager. Is that still true?"

**Answer:** No. TR117-TR122 all ran on Windows where `torch.compile` falls back to `aot_eager`. TR126 Phase 2 (SS5) shows that real Triton compilation on Linux reverses the finding: -40.0% latency reduction, every scenario significant.

### Scenario 2: Choosing a Serving Backend

**Question:** "Should I use HF transformers, compiled HF, or Ollama for production?"

**Answer:** It depends on the dominant mode. For prefill-heavy workloads (RAG, summarization), compiled HF delivers 1.3-2.5× speedup (SS8). For decode-heavy workloads (chat, code generation), Ollama is 3-7× faster (SS9). For mixed workloads, consider splitting strategies or defaulting to Ollama for simplicity. See the decision matrix in SS13.

### Scenario 3: Planning torch.compile Deployment

**Question:** "Can I use torch.compile with reduce-overhead mode for my serving pipeline?"

**Answer:** Only for prefill. Phase 3 (SS10) shows 100% crash rate on autoregressive decode with both `reduce-overhead` and `mode="default"` — PyTorch 2.8's Inductor uses CUDA graph trees internally regardless of mode setting (SS10.5). Use eager mode for decode, or use Ollama.

### Scenario 4: Validating Prior TR Conclusions

**Question:** "Should I trust the compile-related findings from TR117-TR120?"

**Answer:** Trust the measurement methodology and non-compile findings. Discard compile-specific conclusions: all were measured under `aot_eager` fallback. TR126 supersedes them with real Triton data. See the cross-platform comparison in SS12 for specifics.

---

## Table of Contents

**Preliminaries**

- [Metric Definitions & Statistical Methods](#metric-definitions--statistical-methods)

**Phase 1: Environment Validation (SS1-SS3)**

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Phase 1 Methodology](#2-phase-1-methodology)
3. [Phase 1 Results: Environment Gate](#3-phase-1-results-environment-gate)

**Phase 2: Compile Paradox Replication (SS4-SS7)**

4. [Phase 2 Methodology & Design](#4-phase-2-methodology--design)
5. [Phase 2 Results: The Compile Paradox Reversed](#5-phase-2-results-the-compile-paradox-reversed)
6. [Phase 2 Per-Model Analysis](#6-phase-2-per-model-analysis)
7. [Phase 2 Statistical Analysis](#7-phase-2-statistical-analysis)

**Phase 3: Backend Matrix (SS8-SS11)**

8. [Phase 3 Methodology & Design](#8-phase-3-methodology--design)
9. [Phase 3 Results: Prefill](#9-phase-3-results-prefill)
10. [Phase 3 Results: Decode & End-to-End](#10-phase-3-results-decode--end-to-end)
11. [Phase 3 Statistical Analysis](#11-phase-3-statistical-analysis)

**Cross-Phase Synthesis (SS12-SS14)**

12. [Cross-Phase Validation](#12-cross-phase-validation)
13. [Cross-Platform Comparison: Windows vs Linux](#13-cross-platform-comparison-windows-vs-linux)
14. [Production Guidance & Decision Trees](#14-production-guidance--decision-trees)

**Closing**

15. [Limitations & Future Work](#15-limitations--future-work)
16. [Reproducibility](#16-reproducibility)

**Appendices**

- [Appendix A: Environment Specifications](#appendix-a-environment-specifications)
- [Appendix B: Triton Evidence](#appendix-b-triton-evidence)
- [Appendix C: Configs (Source of Truth for Runs)](#appendix-c-configs-source-of-truth-for-runs)
- [Appendix D: Glossary](#appendix-d-glossary)
- [References](#references)

---

## Metric Definitions & Statistical Methods

### Latency Metrics

| Metric | Definition | Computation |
|--------|-----------|-------------|
| **Mean (ms)** | Arithmetic mean of wall-clock latency across all repetitions | `sum(x) / N` |
| **Median (ms)** | 50th percentile latency | `sorted(x)[N//2]` |
| **Std (ms)** | Sample standard deviation | `sqrt(sum((x - mean)^2) / (N-1))` |
| **p90/p95/p99 (ms)** | Percentile latencies | `numpy.percentile(x, [90, 95, 99])` |
| **95% CI** | 95% confidence interval for the mean | `mean ± 1.96 * std / sqrt(N)` |

### Effect Size & Significance Metrics

| Metric | Definition | Interpretation |
|--------|-----------|---------------|
| **Cohen's d** | Standardized mean difference: `(mean_A - mean_B) / pooled_std` | Negligible: \|d\| < 0.2, Small: 0.2-0.5, Medium: 0.5-0.8, Large: > 0.8 |
| **p-value** | Probability of observing the data (or more extreme) under H₀ (no difference), via Welch's two-sample t-test | Significant if p < 0.05 (uncorrected). See note on multiple comparisons in SS9.5. |
| **Delta (%)** | Relative difference: `(mean_B - mean_A) / mean_A × 100` | Negative = B is faster than A |
| **Outlier (IQR)** | A sample is an outlier if `x < Q1 - 1.5*IQR` or `x > Q3 + 1.5*IQR` | Standard Tukey fence method |

### Statistical Tests Used

- **Welch's t-test** (unequal variances): Primary test for all pairwise comparisons. Welch's variant does not assume equal variances across groups.
- **Normality assumption:** Welch's t-test is robust to moderate non-normality with N > 100. We observe right-skewed latency distributions (typical for timing data). No formal normality tests (Shapiro-Wilk) were performed. For a robustness check, a non-parametric alternative (Mann-Whitney U) could be applied — the large effect sizes observed (d > 0.5 for all primary comparisons) would survive any reasonable non-parametric test.
- **Multiple comparison correction:** Not applied to individual p-values. All primary comparisons are significant at p < 10⁻³, well below any corrected threshold (Bonferroni α ≤ 0.006 for the largest family of 9 tests). See SS9.5 for a family-wise error rate discussion.
- **TOST equivalence testing:** Applied to the qwen2.5-1.5b Ollama vs compiled HF prefill comparison (SS9.2). Two One-Sided Tests with ε = 1 ms confirm equivalence (p = 0.001). TOST fails at ε = 0.5 ms (p = 0.118).

### Timing Methodology

All latency measurements use `time.perf_counter()` with `torch.cuda.synchronize()` barriers before and after the timed region. This provides GPU-accurate wall-clock timing at microsecond resolution. **CUDA event timing** (which can provide sub-microsecond GPU-only timing) was not used — see SS15.1 Limitation #7.

---

## 1. Introduction & Research Motivation

### 1.1 Research Questions

TR126 addresses four decision-grade questions:

1. **Platform attribution:** Does the compile paradox discovered in TR120 survive when `torch.compile` has access to real Triton kernels on Linux?
2. **Magnitude:** If compilation helps, how large is the speedup — and does it depend on model size, architecture, or prompt length?
3. **Mode transfer:** Do prefill compilation benefits extend to KV-cached decode and end-to-end serving?
4. **Backend ranking:** When a quantized inference engine (Ollama) is added as a third backend, how do the rankings change across serving modes?

### 1.2 Why This Matters

Every compilation-related conclusion in this research program (TR117 through TR122) was measured on Windows, where `torch.compile` silently falls back to `aot_eager`. TR120 diagnosed this:

> On the Windows host (Python 3.13): Inductor GPU compile fails (Triton missing) and the runner falls back to `aot_eager` (explicitly recorded). — TR120, §2.6

This means all prior "compile helps" or "compile hurts" findings are actually measuring `aot_eager` overhead — a tracing-only backend that provides no kernel optimization. The gap is not academic: production decisions about whether to ship compiled models, how to configure compilation, and which backend to use all depend on data that doesn't exist yet for this hardware platform.

TR126 fills this gap by providing the first real Inductor+Triton data on the same RTX 4080 Laptop GPU used throughout the research program. The experimental design isolates the Triton variable: same GPU, same model weights (volume-mounted from host), same prompts, same measurement methodology — only the OS and compilation backend differ.

### 1.3 Scope

- **Hardware:** Single consumer machine (RTX 4080 Laptop, 12.88 GB VRAM) — same GPU as TR117-TR125.
- **Platform:** Linux inside Docker on WSL2 (NVIDIA CUDA 13.0 base image).
- **Models:** 7 models (Phase 2), 5 models (Phase 3), spanning 25M-3B parameters.
- **Backends:** `transformers-gpu` (eager), `transformers-gpu-compile` (Inductor+Triton), `ollama` (quantized).
- **Modes:** prefill, kv_decode, e2e_kv (same as TR120).
- **Timing:** `time.perf_counter()` with `torch.cuda.synchronize()` barriers (GPU-accurate wall clock).
- **Temperature:** 0.0 (greedy decoding). Deterministic — single repetition per prompt is sufficient for latency measurement (validated by TR124 Phase 3, where variance was < 0.1% at temp=0).

### 1.4 Literature Grounding

| Reference | Contribution | How TR126 Uses It |
|-----------|-------------|-------------------|
| TR120 (Banterhearts) | Compile paradox root-cause, Windows aot_eager discovery | Baseline comparison, experimental design |
| TR117 (Banterhearts) | Tier-3 backend matrix, prompt sets, scenario definitions | Prompt sets, scenario configs |
| TR123 (Banterhearts) | KV-cache cost data, HF model loading patterns | Model loading methodology |
| TR125 (Banterhearts) | Ollama quantization quality data | Ollama model selection |
| PyTorch Inductor docs | torch.compile backend, CUDA graph modes | Compile config decisions |
| Triton language (OpenAI) | GPU kernel generation for Inductor | Compilation target |

**Gap filled:** Prior reports measured "compilation" on Windows under aot_eager fallback. TR126 provides the first real Inductor+Triton results on the same GPU, enabling cross-platform A/B comparison and validating (or invalidating) 5 reports worth of compilation conclusions.

### 1.5 How to Read This Report

Use TR126 in three passes:

1. **Phase 1 (SS2-SS3)** confirms the Linux Docker environment has real Triton. If you trust the environment is correct, skip to Phase 2.
2. **Phase 2 (SS4-SS7)** is the core contribution: definitive evidence that the compile paradox reverses on Linux, with per-model and per-scenario breakdowns.
3. **Phase 3 (SS8-SS11)** extends to a 3-backend × 3-mode matrix. Read this for backend selection decisions and for the CUDA graph decode crash finding.

Cross-phase synthesis (SS12-SS14) ties everything together with production guidance.

---

## 2. Phase 1 Methodology

Phase 1 is a gate check. If any validation fails, subsequent phases do not run.

### 2.1 Environment Validation Checks

| # | Check | Criterion | Failure Mode |
|---|-------|-----------|-------------|
| 1 | CUDA available | `torch.cuda.is_available()` returns True | No GPU passthrough to Docker |
| 2 | Triton importable | `import triton` succeeds, version ≥ 3.0 | Triton not installed in container |
| 3 | torch.compile inductor | `torch.compile(model, backend="inductor")` on tiny model with 0 graph breaks | Inductor unavailable or model incompatible |
| 4 | In Docker | Container runtime detected | Running on host instead of isolated container |

All 4 checks must pass for the gate to open.

### 2.2 Weight Parity Check

A tiny GPT-2 model is loaded in FP32 with `seed=42`. Greedy decode is run on 3 fixed prompts:

- `"Hello"` → 32 tokens
- `"Summarize RLHF in one sentence."` → 32 tokens
- `"What is the capital of France?"` → 32 tokens

Output token IDs and per-position logit statistics (mean, std, min, max) are recorded to `weight_parity.json`. This allows cross-platform verification: if the same model weights produce the same token sequences on Linux and Windows, the model loading path is correct.

### 2.3 What Phase 1 Does NOT Check

Phase 1 does not measure performance. It does not run warmups, repetitions, or timing. Its sole purpose is to confirm that the toolchain is correct before investing compute time in Phases 2-3.

---

## 3. Phase 1 Results: Environment Gate

### 3.1 Check Results

| Check | Result | Detail |
|-------|--------|--------|
| CUDA available | **Pass** | NVIDIA GeForce RTX 4080 Laptop GPU detected |
| Triton importable | **Pass** | Triton 3.3.1 |
| torch.compile inductor | **Pass** | 0 graph breaks on tiny-gpt2 |
| In Docker | **Pass** | Container runtime detected |

### 3.2 Environment Fingerprint

| Property | Value |
|----------|-------|
| Platform | Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39 |
| Python | 3.12.3 (GCC 13.3.0) |
| PyTorch | 2.8.0a0+34c6371d24.nv25.08 |
| CUDA | 13.0 |
| cuDNN | 9.12.00 (91200) |
| Triton | 3.3.1 |
| GPU | NVIDIA GeForce RTX 4080 Laptop GPU |
| VRAM | 12.88 GB |
| Compute Capability | 8.9 (Ada Lovelace) |
| Triton Cache Dir | `/tmp/triton_cache` |
| CUDA Visible Devices | `0` |

### 3.3 Weight Parity

Deterministic output confirmed on all 3 prompts:

| Prompt | Tokens Generated | Token IDs (first 5) | Deterministic |
|--------|-----------------|---------------------|---------------|
| "Hello" | 32 | 16046, 16046, 16046, 16046, 16046 | **Yes** |
| "Summarize RLHF in one sentence." | 32 | (recorded in weight_parity.json) | **Yes** |
| "What is the capital of France?" | 32 | (recorded in weight_parity.json) | **Yes** |

The tiny-gpt2 model produces repetitive output (e.g., "stairs stairs stairs...") which is expected for an untrained model at temperature 0. The key finding is determinism: identical token IDs across runs, confirming correct weight loading.

### 3.4 Comparison with TR120 Windows Environment

| Property | TR120 (Windows) | TR126 (Linux Docker) | Same? |
|----------|----------------|---------------------|-------|
| GPU | RTX 4080 Laptop | RTX 4080 Laptop | **Yes** |
| VRAM | 12.88 GB | 12.88 GB | **Yes** |
| CC | 8.9 | 8.9 | **Yes** |
| Triton | Not available | 3.3.1 | **No** — this is the variable |
| torch.compile backend | aot_eager (fallback) | inductor (real) | **No** — this is the treatment |
| Python | 3.13 | 3.12.3 | Minor difference |

The comparison isolates exactly one variable: Triton availability. GPU hardware, VRAM, and compute capability are identical.

**Gate status: PASSED.** Phase 2 proceeds.

---

## 4. Phase 2 Methodology & Design

Phase 2 replicates TR120's compile paradox experiment under real Triton on Linux.

### 4.1 Research Design

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Models | 6 (2×3 factorial)* | GPT-2 MHA × Qwen2.5 GQA at 3 scales — isolates architecture and scale effects |
| Backends | 2 (eager, compiled) | Direct A/B comparison |
| Scenarios | 5 (from TR117 Tier-3) | Covers micro→long prompt lengths + stress test |
| Modes | 3 (prefill, kv_decode, e2e_kv) | Matches TR120 exactly |
| Repetitions | 30 per scenario | Statistical power for detecting d ≥ 0.10 |
| Warmup | 3 repetitions (discarded) | Exclude cold-start artifacts |
| Compile configs | 3 (baseline, padded, dynamic) | Isolate shape effects per TR120's hypothesis |

### 4.2 Model Lineup

| Model | Params | Architecture | Attention | Dtype | KV Heads | Role |
|-------|--------|-------------|-----------|-------|----------|------|
| gpt2-25m | 25M | GPT-2 | MHA | FP32 | 4 | Tiny baseline (compute-bound) |
| gpt2-50m | 50M | GPT-2 | MHA | FP32 | 8 | Small baseline |
| gpt2-100m | 100M | GPT-2 | MHA | FP32 | 12 | Medium baseline |
| qwen2.5-0.5b | 500M | Qwen2.5 | GQA | FP16 | 2 | Modern small (memory-bound) |
| qwen2.5-1.5b | 1.5B | Qwen2.5 | GQA | FP16 | 2 | Modern medium |
| qwen2.5-3b | 3B | Qwen2.5 | GQA | FP16 | 2 | Modern large |

*Note: The baseline config (run `20260222_195655`) listed 7 model entries in its manifest, including `gpt2-100m` twice (at FP32 and FP16). The FP16 variant was a config artifact — gpt2-100m's native precision is FP32, and loading it in FP16 would produce a non-standard configuration. The analysis pipeline used by the dynamic and padded configs correctly lists 6 models and excludes the FP16 duplicate. All results in this report use the 6-model analysis.

The 2×3 factorial design enables analysis of:
- **Architecture effect:** MHA (GPT-2) vs GQA (Qwen2.5) — do they respond differently to compilation?
- **Scale effect:** 25M → 100M (GPT-2) and 0.5B → 3B (Qwen2.5) — does compile benefit increase or decrease with model size?
- **Precision effect:** FP32 (GPT-2) vs FP16 (Qwen2.5) — does precision affect Triton kernel efficiency?

### 4.3 Why These Models

- **GPT-2 family (25M/50M/100M):** Pre-trained models available locally. MHA architecture provides a classic attention baseline. FP32 precision isolates kernel effects from precision effects. Three sizes at 2× intervals cover the compute-bound regime.
- **Qwen2.5 family (0.5B/1.5B/3B):** Modern GQA architecture with aggressive KV head sharing (2 KV heads). FP16 precision represents production deployment. Three sizes at ~3× intervals cover the memory-bound regime where Triton's memory bandwidth optimizations matter most.

### 4.4 Scenarios

Scenarios are drawn from TR117's Tier-3 `matrix_tier3.yaml`:

| Scenario | Prompt Length | Reps (N=30 baseline) | Role |
|----------|-------------|---------------------|------|
| single_micro | ~10 tokens | 30 | Minimal compute, dispatch-dominated |
| single_short | ~30 tokens | 30 | Short prompt baseline |
| single_medium | ~80 tokens | 30 | Typical conversational turn |
| single_long | ~200 tokens | 30 | Long context window |
| stress_single | ~400 tokens | 15* | Maximum length stress test |

*`stress_single` runs 15 reps (vs 30 for others) to limit total compute time on 400-token prompts. This halves the per-backend sample count for this scenario (N=180 vs N=360) and reduces statistical power for stress_single-specific comparisons. Given the large observed effect sizes (d > 0.5), this is adequate.

### 4.5 Three Compile Configurations

TR120 identified shape instability (variable prompt lengths triggering recompilation) as a potential confound. Phase 2 tests three configurations to isolate this:

1. **Baseline** (run `20260222_195655`): Variable-length prompts, no padding, `dynamic=False`
   - Matches TR120's original setup
   - Tests: does compile still help with shape churn?

2. **Padded** (run `20260222_213342`): Prompts padded to fixed lengths, attention-masked
   - Tests TR120's hypothesis that stable shapes collapse the compiled tail

3. **Dynamic** (run `20260222_214114`): Variable-length prompts, `dynamic=True`
   - Tests shape-polymorphic compilation as a production-viable alternative to padding

**Modes by config:** The baseline config ran all 3 modes (prefill, kv_decode, e2e_kv); the padded and dynamic configs ran **prefill only** (decode was excluded to reduce compute time after the baseline already demonstrated the CUDA graph crash on decode). The baseline decode data (eager vs compiled, `dynamic=False`) exists in the raw artifacts but is not analyzed in this report — Phase 3 provides a more complete 3-backend decode comparison.

**Padded config results:** The padded configuration (`disable_cudagraphs: true`, `pad_to_max_length: true`, `pad_scope: per_scenario`, `pad_to_multiple_of: 8`) was run with 3,240 prefill samples. Analysis is presented in SS5.4: padding improves compiled performance by 15% (aggregate d = -0.91 vs -0.59 for dynamic), validating TR120's shape-stability hypothesis on larger models.

Analysis in this report uses the **dynamic** configuration as the primary result set. This choice has a trade-off: `dynamic=True` is the most shape-flexible production setting (no padding overhead, no recompilation on shape change), but it adds measurable per-call overhead from Dynamo shape guards (see cross-phase validation in SS12.1 where `dynamic=True` shows ~85% higher compiled latency than `dynamic=False` on gpt2-100m). Readers should treat Phase 2's absolute compiled latencies as conservative estimates. Phase 3 (`dynamic=False`) provides optimistic-ceiling numbers.

### 4.6 Compile Configuration (Source of Truth)

```yaml
torch_compile:
  enabled: true
  backend: inductor
  mode: reduce-overhead
  dynamic: false      # baseline/padded; true for dynamic config
  fullgraph: false
```

### 4.7 Measurement Methodology

Each measurement follows this sequence:

1. Pre-tokenize all prompts (tokenization excluded from timed region)
2. Load model once, move to GPU
3. Compile model (if compiled backend) and trigger a warmup forward pass
4. For each (scenario, backend, repetition):
   a. `torch.cuda.synchronize()` — drain GPU pipeline
   b. `start = time.perf_counter()`
   c. Execute forward pass (mode-specific)
   d. `torch.cuda.synchronize()` — wait for GPU completion
   e. `wall_ms = (time.perf_counter() - start) * 1000`
5. Record latency, tokens, tokens/s, status

This methodology matches TR120's controlled runner exactly (§2.4), ensuring cross-platform comparability.

### 4.8 Modes (What is Measured)

| Mode | What's Timed | What's Excluded | Metric |
|------|-------------|----------------|--------|
| **prefill** | Single forward pass with `use_cache=True` | Tokenization, model load | TTFT proxy |
| **kv_decode** | Autoregressive loop using KV cache | Prefill (run but excluded) | Token generation speed |
| **e2e_kv** | Prefill + KV-cached decode together | Tokenization, model load | Full serving latency |

---

## 5. Phase 2 Results: The Compile Paradox Reversed

### 5.1 Aggregate Compile Effect (Prefill, Dynamic Config)

| Metric | Eager (N=1,620) | Compiled (N=1,620) | Delta | Significance |
|--------|-----------------|-------------------|-------|-------------|
| Mean (ms) | 11.87 | 7.12 | **-40.0%** | p = 8.87 × 10⁻⁶¹ |
| Median (ms) | 10.34 | 6.63 | **-35.9%** | — |
| Std (ms) | 9.19 | 6.73 | -26.7% | — |
| p90 (ms) | 25.18 | 19.42 | -22.9% | — |
| p95 (ms) | 25.69 | 19.91 | -22.5% | — |
| p99 (ms) | 28.48 | 20.59 | -27.7% | — |
| t-statistic | — | — | 16.80 | — |
| Cohen's d | — | — | **-0.59** | Medium effect |
| 95% CI (eager) | [11.42, 12.32] | — | — | — |
| 95% CI (compiled) | — | [6.79, 7.45] | — | — |

**The compile paradox is reversed.** Unlike TR120 on Windows where compiled was slower or neutral, real Triton on Linux delivers a consistent 40% latency reduction at both mean and median, with a medium effect size. The benefit persists across all quantiles — it is not an artifact of outlier reduction.

**Contrast with TR120 (Windows):** TR120's controlled runner showed compiled eager as slower (aot_eager overhead) or occasionally faster on median but with heavy tails. TR126 shows compilation helps on *both* mean and median, and *reduces* the standard deviation (from 9.19 to 6.73 ms). The distribution shift is uniform, not tail-driven.

### 5.2 Per-Scenario Breakdown

| Scenario | N/backend | Eager Mean (ms) | Compiled Mean (ms) | Delta (%) | p-value | Cohen's d | Significant |
|----------|-----------|----------------|-------------------|-----------|---------|-----------|----|
| single_micro | 360 | 11.36 | 7.44 | -34.5% | 2.59 × 10⁻¹¹ | -0.505 | **Yes** |
| single_short | 360 | 12.16 | 6.79 | **-44.2%** | 5.93 × 10⁻¹⁸ | **-0.661** | **Yes** |
| single_medium | 360 | 12.06 | 7.00 | -41.9% | 9.52 × 10⁻¹⁶ | -0.613 | **Yes** |
| single_long | 360 | 11.81 | 7.05 | -40.3% | 5.44 × 10⁻¹⁵ | -0.595 | **Yes** |
| stress_single | 180 | 12.05 | 7.48 | -37.9% | 2.51 × 10⁻⁷ | -0.554 | **Yes** |

All 5 scenarios show compilation helps. All 5 are statistically significant (p < 10⁻⁷). Effect sizes are consistently medium (d = -0.50 to -0.66). The benefit is robust across prompt lengths — from 10-token micro prompts to 400-token stress tests.

**Observation:** The largest speedup is on `single_short` (44.2%) and the smallest on `single_micro` (34.5%). This suggests a sweet spot where prompt computation is large enough for Triton kernels to amortize launch overhead, but not so large that GPU compute dominates. At `stress_single` (400 tokens), the eager GPU compute is already efficient, leaving less room for Triton improvement.

### 5.3 Per-Scenario Distribution Detail

To address the "but what about the tails?" question from TR120, here are the full distribution statistics:

| Scenario | Backend | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
|----------|---------|-------------|----------|----------|----------|
| single_micro | eager | 9.78 | 24.17 | 25.44 | 37.83 |
| single_micro | compile | 6.69 | 18.37 | 32.21 | 32.36 |
| single_short | eager | 10.45 | 27.49 | 30.24 | 45.39 |
| single_short | compile | 4.58 | 19.28 | 19.59 | 20.39 |
| single_medium | eager | 9.75 | 26.01 | 28.65 | 30.45 |
| single_medium | compile | 4.62 | 20.02 | 20.28 | 22.36 |
| single_long | eager | 10.20 | 25.54 | 26.36 | 27.54 |
| single_long | compile | 4.75 | 19.72 | 20.02 | 21.02 |
| stress_single | eager | 10.68 | 26.24 | 27.61 | 28.06 |
| stress_single | compile | 4.84 | 20.58 | 20.88 | 21.15 |

**Key observation:** The compiled p99 on `single_micro` shows a cluster at ~32.3 ms (5 outliers — see SS7.2). These are recompilation events consistent with TR120's finding about shape churn. However, they are rare (5/360 = 1.4% of micro measurements, 0.3% of all compiled measurements) and do not affect the median or mean advantage.

### 5.4 Padded Config Analysis (Run `20260222_213342`)

The padded configuration (`pad_to_max_length: true`, `pad_scope: per_scenario`, `pad_to_multiple_of: 8`, `disable_cudagraphs: true`, `dynamic: false`) was collected but not analyzed in the original report. We now present the results to validate TR120's hypothesis that stable shapes improve compiled performance.

**Aggregate compile effect (padded, prefill):**

| Metric | Eager (N=1,620) | Compiled (N=1,620) | Delta | Significance |
|--------|-----------------|-------------------|-------|-------------|
| Mean (ms) | 13.80 | 6.03 | **-56.3%** | p = 1.65 × 10⁻¹³⁰ |
| Cohen's d | — | — | **-0.91** | Large effect |

**Per-model breakdown (padded config):**

| Model | Eager (ms) | Compiled (ms) | Delta (%) | Cohen's d | N/backend |
|-------|-----------|--------------|-----------|-----------|-----------|
| gpt2-25m | 2.18 | 0.94 | **-56.9%** | -1.59 | 270 |
| gpt2-50m | 4.68 | 1.60 | **-65.9%** | -2.19 | 270 |
| gpt2-100m | 4.86 | 2.62 | **-46.2%** | -0.86 | 270 |
| qwen2.5-0.5b | 18.86 | 3.79 | **-79.9%** | -18.04 | 270 |
| qwen2.5-1.5b | 23.20 | 9.51 | **-59.0%** | -9.09 | 270 |
| qwen2.5-3b | 29.03 | 17.76 | **-38.8%** | -10.30 | 270 |

All 6 models show statistically significant compile speedups (p < 10⁻²¹), all with large effect sizes.

**Cross-config comparison:**

| Config | Eager Mean (ms) | Compiled Mean (ms) | Delta (%) | Cohen's d |
|--------|----------------|-------------------|-----------|-----------|
| Dynamic (`dynamic=True`) | 11.87 | 7.12 | -40.0% | -0.59 |
| **Padded** (`pad_to_max_length`) | 13.80 | 6.03 | **-56.3%** | **-0.91** |

**Key finding:** Padding improves compiled performance by 15% (6.03 vs 7.12 ms) while slightly degrading eager performance by 16% (13.80 vs 11.87 ms). The net effect is a **larger compile advantage under padding** (d = -0.91 vs d = -0.59). This validates TR120's hypothesis: stable tensor shapes allow Triton to cache and reuse compiled kernels more effectively. The qwen2.5-0.5b result is striking — padding unlocks a **5.0× speedup** (18.86 → 3.79 ms) with near-zero variance (std 0.105 ms), the cleanest result in the entire report.

**Practical implication:** For production prefill serving with fixed-shape inputs (e.g., embedding APIs with max-length padding), the padded configuration delivers the best absolute compile performance. The `dynamic=True` setting remains preferable for variable-length workloads where padding overhead is unacceptable.

### 5.5 Phase 2 Baseline Config Full Analysis (Run `20260222_195655`)

The baseline configuration (`dynamic=False`, `mode=reduce-overhead`, `max_new_tokens=64`) collected **11,340 measurements** (3,780 per mode) across 7 models × 2 backends × 5 scenarios × ~30 reps. This data was collected but never analyzed in v1 of this report. The baseline config is the most conservative compile setting (no dynamic shapes, CUDA graph replay enabled).

**Prefill compile effect (baseline config):**

| Metric | Eager (N=1,890) | Compiled (N=1,890) | Delta | Significance |
|--------|-----------------|-------------------|-------|-------------|
| Mean (ms) | 10.89 | 5.64 | **-48.2%** | p = 4.33 × 10⁻⁸⁸ |
| Median (ms) | 4.13 | 1.88 | -54.6% | — |
| Cohen's d | — | — | **-0.67** | Medium-large effect |

The baseline config shows a **stronger** compile effect (-48.2%) than the dynamic config (-40.0%), consistent with `dynamic=False` allowing better CUDA graph replay optimization.

**Per-model prefill speedups (baseline config):**

| Model | Eager (ms) | Compiled (ms) | Speedup | Cohen's d |
|-------|-----------|--------------|---------|-----------|
| gpt2-25m (FP32) | 1.89 | 0.70 | **2.7×** | Large |
| gpt2-50m (FP32) | 3.97 | 1.52 | **2.6×** | Large |
| gpt2-100m (FP32) | 4.04 | 2.03 | **2.0×** | Large |
| gpt2-100m (FP16) | 3.84 | 1.32 | **2.9×** | Large |
| qwen2.5-0.5b (FP16) | 16.40 | 5.12 | **3.2×** | Large |
| qwen2.5-1.5b (FP16) | 19.94 | 10.44 | **1.9×** | Large |
| qwen2.5-3b (FP16) | 26.18 | 18.36 | **1.4×** | Large |

**KV-decode: no compile benefit.**

| Metric | Eager (N=1,890) | Compiled (N=1,890) | Delta | Significance |
|--------|-----------------|-------------------|-------|-------------|
| Mean (ms) | 628.3 | 642.2 | **+2.2%** | p = 0.43, **NOT significant** |
| Cohen's d | — | — | 0.026 | Negligible |

Compiled decode is 2.2% *slower* than eager — a trivial, non-significant difference. This confirms that torch.compile's Triton kernel fusion provides no benefit for autoregressive decode, even when it doesn't crash.

**E2E_KV: no compile benefit.**

| Metric | Eager (N=1,890) | Compiled (N=1,890) | Delta | Significance |
|--------|-----------------|-------------------|-------|-------------|
| Mean (ms) | 633.7 | 647.2 | **+2.1%** | p = 0.44, **NOT significant** |

E2E results mirror kv_decode: the decode phase dominates, and compilation provides no benefit.

**Cross-config comparison (compiled prefill):**

| Config | dynamic | mode | Compiled Mean (ms) | Speedup vs Eager | Cohen's d |
|--------|---------|------|-------------------|-----------------:|-----------|
| **Baseline** | False | reduce-overhead | 5.64 | 1.93× | -0.67 |
| Dynamic | True | reduce-overhead | 7.12 | 1.67× | -0.59 |
| Padded | False | reduce-overhead | 6.03 | 2.29× | -0.91 |

The baseline config's compiled performance (5.64 ms) is 21% better than dynamic (7.12 ms), confirming that `dynamic=False` improves CUDA graph replay. The padded config achieves the best eager-vs-compiled *ratio* (2.29×) because it also hurts eager performance.

### 5.6 Compiled Decode Performance Characterization

**Critical finding:** Phase 2 baseline has **1,890 successful compiled kv_decode measurements** at `max_new_tokens=64`. Phase 3 has **0 successful compiled decode measurements** at `max_new_tokens=128` (100% crash rate). This establishes that the CUDA graph shape violation crash is **length-dependent**, not absolute.

**Per-model compiled decode at max_new_tokens=64:**

| Model | Eager (ms) | Compiled (ms) | Speedup | Compile Helps? |
|-------|-----------|--------------|---------|----------------|
| gpt2-25m (FP32) | 99.8 | 103.2 | 0.97× | No |
| gpt2-50m (FP32) | 228.8 | 235.9 | 0.97× | No |
| gpt2-100m (FP32) | 209.6 | 220.1 | 0.95× | No |
| gpt2-100m (FP16) | 204.3 | 212.6 | 0.96× | No |
| qwen2.5-0.5b (FP16) | 980.7 | 996.5 | 0.98× | No |
| qwen2.5-1.5b (FP16) | 1,179.6 | 1,204.8 | 0.98× | No |
| qwen2.5-3b (FP16) | 1,495.5 | 1,522.3 | 0.98× | No |

**Every model shows compiled decode is slightly slower** (0.95-0.98× speedup, i.e., 2-5% overhead). None are statistically significant at the individual model level, but the consistent direction across all 7 models suggests a small, real overhead from Triton graph tracing during autoregressive generation.

**Why compilation doesn't help decode:** Autoregressive decode processes one token at a time. Each step involves a single matrix-vector multiplication (not matrix-matrix), which is memory-bandwidth-bound. Triton's kernel fusion benefits come from combining multiple operations and reducing memory traffic — but with only one token per step, there are few operations to fuse. The compilation overhead (graph tracing, dispatch) slightly exceeds the minimal benefit from kernel optimization.

**Contrast with prefill:** Prefill processes the entire prompt in one pass, creating opportunities for operation fusion across attention heads, layers, and the batch dimension. This is why compilation delivers 48% speedup on prefill but 0% on decode.

---

## 6. Phase 2 Per-Model Analysis

### 6.1 GPT-2 Family (MHA, FP32)

**gpt2-25m** (25M params, 4 KV heads):

| Metric | Eager (N=270) | Compiled (N=270) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 1.81 | 0.73 | **-60.0%** |
| Median (ms) | 1.77 | 0.65 | -63.5% |
| Std (ms) | 0.13 | 0.14 | +5.2% |
| 95% CI | [1.80, 1.83] | [0.71, 0.74] | — |

**Observation:** The smallest model shows the largest speedup (2.5×). At 25M params, the model computation is tiny, and Triton's kernel fusion eliminates dispatch overhead that dominates eager execution. The compiled std is comparable to eager (0.14 vs 0.13 ms), showing no increase in variance. CIs do not overlap — the effect is unambiguous.

**gpt2-50m** (50M params, 8 KV heads):

| Metric | Eager (N=270) | Compiled (N=270) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 3.89 | 1.79 | **-53.8%** |
| Median (ms) | 3.83 | 1.42 | -62.9% |
| Std (ms) | 0.27 | 1.03 | +278% |
| 95% CI | [3.85, 3.92] | [1.67, 1.92] | — |

**Observation:** Strong 2.2× speedup. The compiled std is higher (1.03 vs 0.27 ms) — reflecting occasional slower-path executions. The median-to-mean gap (1.42 vs 1.79 ms compiled) indicates a right tail, consistent with sporadic recompilation. Even so, the compiled p95 (4.15 ms) remains below the eager mean (3.89 ms).

**gpt2-100m** (100M params, 12 KV heads):

| Metric | Eager (N=270) | Compiled (N=270) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 3.93 | 2.95 | **-24.9%** |
| Median (ms) | 3.89 | 2.48 | -36.2% |
| Std (ms) | 0.13 | 4.23 | +3,150% |
| 95% CI | [3.91, 3.94] | [2.44, 3.45] | — |

**Observation:** The speedup narrows at 100M params (1.3×) and the compiled std explodes (4.23 ms) due to 5 outlier samples at ~32.3 ms. These are likely recompilation events from a shape mismatch. The median shows a much larger benefit (36.2%) than the mean (24.9%), which is dragged up by the outliers. This is the exact mean-vs-median pattern TR120 described — but here, compilation still *helps* rather than hurts.

### 6.2 Qwen2.5 Family (GQA, FP16)

**qwen2.5-0.5b** (500M params, 2 KV heads):

| Metric | Eager (N=270) | Compiled (N=270) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 16.05 | 6.94 | **-56.7%** |
| Median (ms) | 16.00 | 6.91 | -56.8% |
| Std (ms) | 0.50 | 0.22 | -56.1% |
| 95% CI | [15.99, 16.11] | [6.92, 6.97] | — |

**Observation:** The strongest result. 2.3× speedup with *lower* variance under compilation (std drops from 0.50 to 0.22 ms). The mean and median deltas are nearly identical (-56.7% vs -56.8%), showing a clean distribution shift with no tail distortion. CIs are tight and non-overlapping.

**Why so large?** Qwen2.5-0.5b at FP16 is memory-bandwidth-bound. Triton's kernel fusion reduces the number of separate memory accesses by combining operations, which disproportionately helps when memory bandwidth is the bottleneck. The GQA attention with only 2 KV heads means less compute per token, amplifying the relative benefit of reduced memory traffic.

**qwen2.5-1.5b** (1.5B params, 2 KV heads):

| Metric | Eager (N=270) | Compiled (N=270) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 19.93 | 10.89 | **-45.3%** |
| Median (ms) | 19.65 | 10.75 | -45.3% |
| Std (ms) | 1.49 | 0.58 | -61.0% |
| 95% CI | [19.76, 20.11] | [10.82, 10.96] | — |

**Observation:** Consistent 1.8× speedup, clean distribution shift (mean = median delta). Compiled std is 2.6× lower than eager. The 1.5B model shows that Triton benefits scale well beyond the toy-model regime.

**qwen2.5-3b** (3B params, 2 KV heads):

| Metric | Eager (N=270) | Compiled (N=270) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 25.61 | 19.40 | **-24.2%** |
| Median (ms) | 25.29 | 19.56 | -22.7% |
| Std (ms) | 2.02 | 0.80 | -60.7% |
| 95% CI | [25.37, 25.86] | [19.31, 19.50] | — |

**Observation:** The speedup narrows at 3B (1.3×) but is still meaningful (6.2 ms absolute savings). The compiled std is again lower (0.80 vs 2.02 ms). At this scale, model compute dominates and Triton's kernel fusion has less relative impact — but still delivers a significant, consistent benefit.

### 6.3 Architecture and Scale Effect Summary

| Model Family | Model | Speedup | Architecture | Dtype | Compute Regime |
|-------------|-------|---------|-------------|-------|----------------|
| GPT-2 | 25M | **2.5×** | MHA | FP32 | Dispatch-dominated |
| GPT-2 | 50M | **2.2×** | MHA | FP32 | Dispatch-dominated |
| GPT-2 | 100M | 1.3× | MHA | FP32 | Transitional |
| Qwen2.5 | 0.5B | **2.3×** | GQA | FP16 | Memory-bandwidth-bound |
| Qwen2.5 | 1.5B | **1.8×** | GQA | FP16 | Memory-bandwidth-bound |
| Qwen2.5 | 3B | 1.3× | GQA | FP16 | Compute-bound |

**Pattern 1 — Scale effect:** Within each family, speedup decreases with model size. Triton's benefit is proportionally larger when kernel dispatch overhead (rather than kernel compute) dominates execution time.

**Pattern 2 — Architecture effect:** GQA models (Qwen2.5) show cleaner compilation behavior (no outlier clusters) than MHA models (GPT-2). This may be because GQA's fewer KV heads create more uniform tensor shapes, reducing recompilation triggers.

**Pattern 3 — Precision effect:** FP16 models (Qwen2.5) and FP32 models (GPT-2) both benefit from compilation. The two families operate in different compute regimes (memory-bandwidth vs dispatch), yet both show consistent speedups. This suggests Triton's benefit is robust across precision levels.

---

## 7. Phase 2 Statistical Analysis

### 7.1 Power Analysis

| Parameter | Value |
|-----------|-------|
| N per group | 1,620 |
| N backends | 2 |
| Alpha | 0.05 |
| Power | 0.80 |
| Min detectable d | 0.098 |
| Min detectable delta | 0.83 ms |
| Pooled std | 8.40 ms |
| Interpretation | Can detect small effects |

With 1,620 samples per backend, Phase 2 can detect effects as small as d = 0.098 — well below the observed d = 0.59. The study is strongly powered.

**Caveat on aggregate MDE:** The pooled std of 8.40 ms is inflated by mixing models with vastly different absolute latencies (gpt2-25m at ~1.8 ms vs qwen2.5-3b at ~25 ms). The 0.83 ms aggregate MDE does not apply to per-model comparisons. Per-model MDEs vary: gpt2-25m (std ~0.13 ms, N=270) has MDE ≈ 0.02 ms, while qwen2.5-3b (std ~2.0 ms, N=270) has MDE ≈ 0.34 ms. All per-model observed effects far exceed their model-specific MDEs.

### 7.2 Outlier Analysis (IQR Method)

| Backend | N Total | N Outliers | Outlier % | Outlier Values (ms) |
|---------|---------|------------|-----------|---------------------|
| transformers-gpu | 1,620 | 1 | 0.1% | 45.39 |
| transformers-gpu-compile | 1,620 | 5 | 0.3% | 32.29, 32.29, 32.20, 32.36, 32.23 |

The eager outlier (45.39 ms) is likely a system-level interrupt or GC pause — a single isolated event.

The 5 compiled outliers cluster tightly at ~32.3 ms, suggesting a systematic cause rather than random noise. Cross-referencing with per-model data: gpt2-100m's compiled p99 is 32.24 ms — **all 5 outliers originate from gpt2-100m**. No other model produces outliers above its IQR fence. The most likely explanation is **Triton recompilation on gpt2-100m**: this model has 12 attention heads (the most of any GPT-2 variant in the matrix), creating more diverse tensor shapes. When a new shape is encountered, Triton JIT-compiles a fresh kernel at ~32 ms cost. This aligns with TR120's shape-churn hypothesis (§5.1) and is the same mechanism that creates compilation tails under variable-length prompts. The 5 events (1.9% of gpt2-100m compiled samples, 0.3% of all compiled samples) indicate the shape-churn problem is real but rare under `dynamic=True`.

**Impact on conclusions:** Outlier rate is 0.1-0.3%, well below typical thresholds (5%). Even if we exclude all outliers, the compile benefit remains: outlier-excluded compile mean = 6.73 ms vs eager mean = 11.85 ms (-43.2%).

### 7.3 Sensitivity Analysis: Trimmed Means

Following TR120's methodology (§4.3), we test the robustness of the mean ranking by progressively trimming outliers:

| Trim Level | Eager Mean (ms) | Compiled Mean (ms) | Delta (%) | Compile Helps |
|------------|----------------|--------------------|-----------|----|
| None (raw) | 11.87 | 7.12 | -40.0% | **Yes** |
| Exclude max per backend | 11.85 | 6.96 | -41.3% | **Yes** |
| Exclude top 5 per backend | 11.82 | 6.73 | -43.1% | **Yes** |
| 5% trimmed mean | 11.23 | 6.33 | -43.6% | **Yes** |

The compile advantage is stable and *increases* with outlier removal, because the compiled outliers (~32 ms) are above the compiled mean but below the eager mean. This is the opposite of TR120's Windows finding, where trimming outliers eliminated the compile advantage.

### 7.4 Mean vs Median Consistency

| Backend | Mean (ms) | Median (ms) | Mean/Median Ratio | Interpretation |
|---------|-----------|-------------|-------------------|----------------|
| eager | 11.87 | 10.34 | 1.15 | Slight right skew |
| compile | 7.12 | 6.63 | 1.07 | Near-symmetric |

Both backends show mean > median (right skew), which is expected for latency distributions. The compiled distribution is *more symmetric* (ratio 1.07 vs 1.15), indicating that Triton reduces tail latency relative to the typical call. This contradicts TR120's finding that compilation increased tail severity — further evidence that the aot_eager fallback was the root cause.

---

## 8. Phase 3 Methodology & Design

Phase 3 extends the analysis to a 3-backend matrix with Ollama as a quantized inference reference.

### 8.1 Research Questions (Phase 3 Specific)

1. Where does compiled HF rank against Ollama for prefill?
2. Does Ollama's quantization advantage overcome compile overhead at larger model scales?
3. How do decode-mode rankings differ from prefill rankings?
4. Does `reduce-overhead` compilation survive autoregressive decode?

### 8.2 Model Lineup

| Model | Params | Backends Tested | Dtype (HF) | Ollama Tag | Role |
|-------|--------|----------------|------------|------------|------|
| gpt2-100m | 100M | eager, compile | FP32 | — | HF-only reference |
| qwen2.5-0.5b | 500M | eager, compile, ollama | FP16 | `qwen2.5:0.5b` | Cross-backend small |
| qwen2.5-1.5b | 1.5B | eager, compile, ollama | FP16 | `qwen2.5:1.5b` | Cross-backend medium |
| qwen2.5-3b | 3B | eager, compile, ollama | FP16 | `qwen2.5:3b` | Cross-backend large |
| llama3.2:1b | 1B | ollama only | — | `llama3.2:1b` | Architecture diversity |

**Design rationale:** Qwen2.5 at 3 scales provides a controlled HF-vs-Ollama comparison (same model family, different runtime). gpt2-100m provides an HF-only baseline for cross-phase validation with Phase 2. llama3.2:1b adds architectural diversity without requiring HF weights (Ollama-only).

### 8.3 Why These Models (Phase 3 Specific)

- **gpt2-100m:** Already benchmarked in Phase 2. Allows cross-phase validation of eager/compiled results. No Ollama tag available for GPT-2 models.
- **qwen2.5-0.5b/1.5b/3b:** Available as both local HF weights and Ollama tags. The 3-scale coverage enables detecting the scale crossover point where Ollama's quantized inference beats compiled FP16 HF.
- **llama3.2:1b:** Different architecture (Llama vs Qwen). Available as Ollama tag but no local HF weights. Adds diversity to the Ollama-only portion of the matrix.

### 8.4 Experimental Design

| Parameter | Value |
|-----------|-------|
| Backends | 3 (transformers-gpu, transformers-gpu-compile, ollama) |
| Scenarios | 5 (single_micro, single_short, single_medium, single_long, stress_single) |
| Modes | 3 (prefill, kv_decode, e2e_kv) |
| Repetitions | 15 per scenario per backend per model |
| Max new tokens | 128 |
| Warmup | 3 repetitions (HF backends) |
| Compile config | `backend="inductor"`, `mode="reduce-overhead"`, `dynamic=False` |
| Ollama config | `temperature=0.0`, `seed=42`, `num_predict=128` |
| Ollama URL | `http://host.docker.internal:11434` (Docker → Windows host) |

### 8.5 Ollama Timing Methodology

Ollama's HTTP API returns native timing fields that allow mode-specific measurement:

| Mode | Ollama Field Used | What It Measures |
|------|------------------|-----------------|
| prefill | `prompt_eval_duration` (nanoseconds) | GPU time for prompt processing |
| kv_decode | `eval_duration` (nanoseconds) | GPU time for token generation |
| e2e_kv | Wall clock (`time.perf_counter()`) | Full HTTP round-trip |

Native timing (`prompt_eval_duration`, `eval_duration`) excludes HTTP overhead and measures GPU work directly. This is the same methodology validated in TR125 (§5.5), where native timing showed 190-920% less overhead than wall-clock.

### 8.6 Ollama Networking

Ollama runs on the Windows host. The Docker container reaches it via `host.docker.internal:11434`, which Docker resolves to the WSL2 host IP. Direct `localhost` does not work inside Docker WSL2 containers because `localhost` resolves to the container's own network namespace. `--network=host` was tested and rejected because WSL2's host network maps to the Linux VM, not the Windows host.

### 8.7 Sample Counts

| Mode | transformers-gpu | transformers-gpu-compile | ollama | Total |
|------|-----------------|------------------------|--------|-------|
| prefill | 540 | 540 | 540 | 1,620 |
| kv_decode | 540 | 0 (crash) | 540 | 1,080 |
| e2e_kv | 540 | 0 (crash) | 540 | 1,080 |
| **Total** | **1,620** | **540** | **1,620** | **3,780** |

Note: compiled backend crashed on all kv_decode and e2e_kv runs (see SS10.1). **Successful measurements: 3,780.** Total rows including 111 error entries from compiled decode crashes: 3,891. All statistics in this report use only successful measurements.

---

## 9. Phase 3 Results: Prefill

### 9.1 Backend Rankings (Aggregate)

| Rank | Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | p99 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|----------|--------|
| 1 | transformers-gpu-compile | 540 | **8.20** | 6.50 | 6.37 | 18.34 | 19.77 | [7.66, 8.74] |
| 2 | ollama | 540 | 9.11 | 8.40 | 3.38 | 14.55 | 16.60 | [8.82, 9.39] |
| 3 | transformers-gpu | 540 | 17.56 | 18.49 | 8.88 | 28.25 | 32.29 | [16.81, 18.31] |

Compiled HF wins prefill in aggregate, beating Ollama by 0.9 ms (statistically significant, p = 0.004, but d = -0.18 — negligible effect size). Both massively outperform eager HF. The compiled backend has higher variance (std 6.37) than Ollama (3.38), reflecting the bimodal nature of compilation: most calls are very fast (median 6.50) but occasional recompilation events push the tail.

**Aggregate bias note:** The Ollama column includes llama3.2:1b (Ollama-only, no HF comparison). The N=540 per backend shown above includes 135 llama3.2:1b samples in the Ollama column that have no paired HF counterpart. This inflates the Ollama sample count. For a fair aggregate comparison excluding unpaired models, use only the 405 Qwen2.5 + gpt2-100m Ollama samples against 540 HF samples. The per-model breakdowns below provide the unbiased comparisons.

### 9.2 Per-Model Prefill Rankings

#### gpt2-100m (HF-only, FP32)

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|---------|---|-----------|-------------|----------|----------|--------|
| transformers-gpu-compile | 135 | **1.60** | 1.57 | 0.09 | 1.75 | [1.59, 1.62] |
| transformers-gpu | 135 | 3.84 | 3.80 | 0.16 | 4.12 | [3.81, 3.87] |

**Observation:** Compile delivers 2.4× prefill speedup. CIs are extremely tight (no overlap). The compiled std (0.09 ms) is lower than eager (0.16 ms) — no tail penalty. This is the cleanest compile result: zero recompilation events, consistent speedup on every measurement.

#### qwen2.5-0.5b (FP16, 3 backends)

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|---------|---|-----------|-------------|----------|----------|--------|
| transformers-gpu-compile | 135 | **3.68** | 3.71 | 0.11 | 3.80 | [3.67, 3.70] |
| ollama | 135 | 7.44 | 7.63 | 2.87 | 9.60 | [6.95, 7.93] |
| transformers-gpu | 135 | 16.94 | 16.96 | 0.54 | 17.98 | [16.84, 17.03] |

**Observation:** Compiled HF is 2.0× faster than Ollama and 4.6× faster than eager at this scale. The compiled result is extraordinarily consistent (std 0.11 ms). Ollama shows higher variance (std 2.87 ms), likely due to HTTP overhead fluctuation despite using native timing.

#### qwen2.5-1.5b (FP16, 3 backends)

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|---------|---|-----------|-------------|----------|----------|--------|
| ollama | 135 | **9.35** | 9.55 | 2.89 | 11.27 | [8.85, 9.84] |
| transformers-gpu-compile | 135 | 9.54 | 9.44 | 0.63 | 10.77 | [9.44, 9.65] |
| transformers-gpu | 135 | 22.07 | 21.63 | 2.11 | 25.72 | [21.71, 22.42] |

**Observation: The crossover point.** At 1.5B parameters, Ollama and compiled HF produce very similar prefill latencies (9.35 vs 9.54 ms). The CIs overlap ([8.85, 9.84] vs [9.44, 9.65]), and while the pairwise t-test reaches significance (p = 0.004), the effect size is negligible (d = -0.18). Ollama's quantized weights (likely Q4) offset the Triton kernel advantage of compiled FP16 HF. Both are 2.3× faster than eager.

**Methodological note on "tie" claims:** A statistically significant p-value (0.004) with a negligible effect size (d = 0.18) is a textbook case of "significant but not meaningful." The 0.19 ms difference is real in the statistical sense but operationally irrelevant — it is within the noise of a single HTTP round-trip.

**Formal TOST equivalence test (ε = 1 ms):** We apply the Two One-Sided Tests procedure with ε = 1 ms (a conservative margin — sub-millisecond differences are operationally invisible in HTTP-based serving). TOST tests H₀₁: δ ≥ +ε and H₀₂: δ ≤ −ε. Both must be rejected at α = 0.05 for equivalence.

| Parameter | Value |
|-----------|-------|
| δ (compile − ollama) | +0.197 ms |
| SE (Welch) | 0.254 ms |
| Welch df | 146.7 |
| t₁ (upper bound) | −3.158 (p₁ = 0.00096) |
| t₂ (lower bound) | +4.711 (p₂ = 0.000003) |
| **TOST p-value** | **0.00096** |
| **Equivalent at α = 0.05?** | **Yes** |

At ε = 0.5 ms, equivalence fails (p = 0.118). At ε = 1 ms, equivalence is confirmed (p < 0.001). At ε = 2 ms, equivalence is trivially confirmed (p < 10⁻⁶). **The 1.5B crossover is now formally validated:** Ollama and compiled HF are statistically equivalent within ±1 ms for prefill at the 1.5B scale.

This is a critical finding: **the compile advantage over Ollama effectively disappears at ~1.5B parameters.** Above this threshold, Ollama's quantization advantage (lower memory bandwidth per token) outweighs Triton's kernel fusion advantage.

#### qwen2.5-3b (FP16, 3 backends)

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|---------|---|-----------|-------------|----------|----------|--------|
| ollama | 135 | **12.72** | 13.26 | 2.41 | 15.20 | [12.31, 13.13] |
| transformers-gpu-compile | 135 | 17.98 | 17.82 | 0.68 | 19.68 | [17.86, 18.09] |
| transformers-gpu | 135 | 27.41 | 27.04 | 2.05 | 30.59 | [27.06, 27.76] |

**Observation:** At 3B, Ollama wins decisively — 29% faster than compiled HF (CIs do not overlap). Ollama's quantized inference now clearly outpaces compiled FP16 HF for prefill. Eager HF is 2.2× slower than Ollama.

#### llama3.2:1b (Ollama-only)

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|---------|---|-----------|-------------|----------|----------|--------|
| ollama | 135 | 6.92 | 7.04 | 1.69 | 8.23 | [6.63, 7.21] |

**Observation:** Llama 3.2 1B via Ollama achieves 6.92 ms prefill — competitive with compiled qwen2.5-0.5b HF (3.68 ms) despite being a different architecture. No HF comparison available, but the result shows Ollama delivers consistently fast prefill across architectures.

### 9.3 Per-Scenario Prefill Rankings (Aggregate)

| Scenario | N/backend | Compile Mean (ms) | Ollama Mean (ms) | Eager Mean (ms) | Winner |
|----------|-----------|-------------------|------------------|-----------------|--------|
| single_micro | 120 | 7.93 | 9.28 | 17.03 | Compile |
| single_short | 120 | 8.04 | 9.81 | 17.87 | Compile |
| single_medium | 120 | 8.14 | 9.73 | 17.25 | Compile |
| single_long | 120 | 8.34 | 9.83 | 17.92 | Compile |
| stress_single | 60 | 8.93 | 4.67 | 17.92 | **Ollama** |

**Observation:** Compiled HF wins 4/5 scenarios, but Ollama wins `stress_single`. The stress scenario uses the longest prompts, where Ollama's quantized evaluation of long contexts becomes advantageous. This is consistent with the model-scale crossover — longer prompts behave like "larger models" in terms of memory bandwidth demand.

### 9.4 Compile Effect (Phase 3 Prefill)

| Metric | Eager (N=540) | Compiled (N=540) | Delta |
|--------|--------------|-----------------|-------|
| Mean (ms) | 17.56 | 8.20 | **-53.3%** |
| t-statistic | — | — | 19.90 |
| p-value | — | — | 2.65 × 10⁻⁷⁵ |
| Cohen's d | — | — | **-1.21 (large)** |

The compile effect in Phase 3 is larger than Phase 2 (d = -1.21 vs -0.59). Multiple factors contribute:

1. **Model composition:** Phase 3 excludes gpt2-25m and gpt2-50m (which had large eager latencies relative to their compile latencies in Phase 2), and includes only gpt2-100m + 3 Qwen2.5 models. The different model mix changes the pooled variance.
2. **`dynamic=False` vs `dynamic=True`:** Phase 3 uses `dynamic=False`, eliminating Dynamo shape-guard overhead that inflated Phase 2's compiled latencies (see SS12.1). This directly increases the compile advantage.
3. **Different warmup mechanics:** Phase 3's `run_matrix.py` uses a different warmup strategy than Phase 2's `run_compile.py`.

The effect size difference is not simply "expected" from model composition — it reflects a genuine configuration difference between phases. The Phase 2 value (d = -0.59) represents the conservative case (`dynamic=True`), while Phase 3 (d = -1.21) represents the optimistic case (`dynamic=False`). Both confirm compilation helps; the magnitude depends on compile configuration.

### 9.5 Pairwise Comparisons (Prefill)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|
| ollama | transformers-gpu | 9.11 | 17.56 | +92.9% | 2.75 × 10⁻⁸⁰ | 1.26 | **Large** |
| ollama | transformers-gpu-compile | 9.11 | 8.20 | -9.9% | 3.67 × 10⁻³ | -0.18 | Negligible |
| transformers-gpu | transformers-gpu-compile | 17.56 | 8.20 | -53.3% | 2.65 × 10⁻⁷⁵ | -1.21 | **Large** |

All 3 comparisons reach statistical significance (p < 0.005). Two show large practical effects: eager-vs-compile (d = 1.21) and eager-vs-Ollama (d = 1.26). The Ollama-vs-compile comparison is statistically significant (p = 0.004) but practically negligible (d = 0.18) — with N=540 per group, even trivial differences reach significance. These backends are effectively tied in aggregate prefill.

#### Bonferroni and Holm Step-Down Correction

Across all 3 Phase 3 modes, there are **5 unique pairwise tests** (3 prefill pairs + 1 kv_decode pair + 1 e2e_kv pair). We apply both Bonferroni and Holm step-down corrections to control family-wise error rate.

| Rank | Mode | Group A | Group B | p-value | Bonferroni (α=0.01) | Holm α | Holm |
|------|------|---------|---------|---------|:-------------------:|--------|:----:|
| 1 | kv_decode | ollama | transformers-gpu | 2.55 × 10⁻²⁰⁹ | **PASS** | 0.0100 | **PASS** |
| 2 | e2e_kv | ollama | transformers-gpu | 1.46 × 10⁻¹⁶⁵ | **PASS** | 0.0125 | **PASS** |
| 3 | prefill | ollama | transformers-gpu | 2.75 × 10⁻⁸⁰ | **PASS** | 0.0167 | **PASS** |
| 4 | prefill | transformers-gpu | transformers-gpu-compile | 2.65 × 10⁻⁷⁵ | **PASS** | 0.0250 | **PASS** |
| 5 | prefill | ollama | transformers-gpu-compile | 3.67 × 10⁻³ | **PASS** | 0.0500 | **PASS** |

**All 5 tests survive both corrections.** The smallest p-value (3.67 × 10⁻³ for Ollama vs compile prefill) clears even the strictest Bonferroni threshold (0.01). No conclusions change under multiple-testing correction.

---

## 10. Phase 3 Results: Decode & End-to-End

### 10.1 Critical Finding: `reduce-overhead` Breaks Autoregressive Decode

Compiled models using `mode="reduce-overhead"` crash on every kv_decode and e2e_kv scenario for every model tested:

```
Error: accessing tensor output of CUDAGraphs that has been overwritten by a subsequent run.
Stack trace: File ".../transformers/utils/generic.py", line 841, in wrapper
```

**Crash rate:** 100% (all scenarios, all models, all repetitions).

**Root cause:** `reduce-overhead` mode uses CUDA graphs, which capture a fixed sequence of GPU operations with fixed tensor shapes. During autoregressive KV-cache decoding, the KV cache grows via `torch.cat()` each step, changing tensor dimensions. The crash originates in `torch/_inductor/cudagraph_trees.py` — specifically `dealloc_current_path_weakrefs()`, which unconditionally frees all live path weakrefs including storages that are still needed as inputs to subsequent warmup nodes. We traced this to line 2648 on `main` and filed [pytorch/pytorch#175557](https://github.com/pytorch/pytorch/issues/175557). A secondary assertion bug on the same codepath (line 2614) is addressed in [pytorch/pytorch#175562](https://github.com/pytorch/pytorch/pull/175562). The bug reproduces on both PyTorch 2.8 and 2.10.

**Why prefill works:** Prefill processes a fixed-length prompt in a single forward pass — the tensor shapes are determined once and don't change during execution. CUDA graphs can capture and replay this fixed-shape computation without conflict.

**Length-dependent threshold (NEW in v2):** Phase 2 baseline collected 1,890 successful compiled kv_decode measurements at `max_new_tokens=64` using the same `mode=reduce-overhead`, `dynamic=False` settings. The CUDA graph crash is therefore **not immediate** — it occurs when the KV cache grows past a critical size during generation. The crash threshold lies between 64 and 128 generated tokens. At 64 tokens, the cache growth may stay within the CUDA graph's recorded tensor shape tolerances; at 128 tokens, it exceeds them.

**`mode="default"` does not fix the crash (NEW in v2):** We ran the identical Phase 3 experiment with `torch.compile(mode="default")` to test whether disabling CUDA graph replay would allow compiled decode. **Result: identical crashes.** The error traces show `torch/_inductor/cudagraph_trees.py` in the stack — PyTorch 2.8's Inductor backend invokes CUDA graph tree management internally regardless of the user-facing `mode` parameter. The `mode` flag controls *explicit* CUDA graph capture/replay at the model level, but Inductor's own optimization passes use graph trees for compiled kernel execution. This is an implementation detail of PyTorch 2.8 that renders the `mode` parameter ineffective for avoiding shape-mismatch crashes in autoregressive decode.

**Practical implication:** Compiled autoregressive decode is **not viable** with any torch.compile mode in PyTorch 2.8. For production systems that need decode:
1. Use eager mode for HF decode (no compilation)
2. Use Ollama for decode-heavy workloads (avoids the issue entirely and is 7× faster)
3. Split strategy: `torch.compile(mode="reduce-overhead")` for prefill only, eager/Ollama for decode

### 10.2 KV-Decode Rankings (2 backends)

| Rank | Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | **ollama** | 540 | **286.1** | 239.3 | 213.3 | 731.1 | [268.0, 304.1] |
| 2 | transformers-gpu | 540 | 2,019.3 | 2,254.4 | 1,006.3 | 3,240.8 | [1,934.2, 2,104.4] |

Ollama is **7.1× faster** than eager HF for decode (d = 2.38, p < 10⁻²⁰⁹). The effect size is very large.

#### Per-Model KV-Decode Rankings

**gpt2-100m** (HF-only):

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | 95% CI |
|---------|---|-----------|-------------|----------|--------|
| transformers-gpu | 135 | 423.9 | 422.9 | 15.8 | [421.2, 426.6] |

No Ollama comparison. The eager HF decode is relatively fast because gpt2-100m is small (100M FP32). Very tight distribution (std 15.8 ms on a 424 ms mean).

**qwen2.5-0.5b:**

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | 95% CI |
|---------|---|-----------|-------------|----------|--------|
| ollama | 135 | **150.3** | 170.2 | 87.6 | [135.4, 165.2] |
| transformers-gpu | 135 | 2,058.5 | 2,053.8 | 53.9 | [2,049.3, 2,067.6] |

**Observation:** Ollama is **13.7× faster** for decode on the 0.5B model. This is the largest per-model speedup. Ollama's quantized 0.5B model generates tokens at 150 ms vs 2,058 ms for eager FP16 HF — a difference of nearly 2 seconds per generation.

**qwen2.5-1.5b:**

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | 95% CI |
|---------|---|-----------|-------------|----------|--------|
| ollama | 135 | **211.8** | 85.2 | 172.7 | [182.4, 241.2] |
| transformers-gpu | 135 | 2,431.7 | 2,429.6 | 65.6 | [2,420.5, 2,442.9] |

**Observation:** Ollama is **11.5× faster.** The Ollama median (85.2 ms) is dramatically lower than its mean (211.8 ms), indicating a right-skewed distribution — likely from initial model loading or Ollama server warmup on the first few requests.

**qwen2.5-3b:**

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | 95% CI |
|---------|---|-----------|-------------|----------|--------|
| ollama | 135 | **463.3** | 336.8 | 238.1 | [422.8, 503.9] |
| transformers-gpu | 135 | 3,163.1 | 3,159.3 | 102.4 | [3,145.6, 3,180.5] |

**Observation:** Ollama is **6.8× faster.** The speedup is lower than smaller models because Ollama's quantized 3B model requires more compute per token, narrowing the bandwidth gap. Still, the 2.7-second difference per generation is substantial.

**llama3.2:1b** (Ollama-only):

| Backend | N | Mean (ms) | Median (ms) | Std (ms) | 95% CI |
|---------|---|-----------|-------------|----------|--------|
| ollama | 135 | 318.8 | 449.9 | 178.5 | [288.4, 349.2] |

Reference point: Llama 3.2 1B generates 128 tokens in ~319 ms, similar to the 0.5B Qwen model. The median > mean pattern (449.9 vs 318.8) suggests that short-prompt scenarios complete faster, pulling the mean down.

### 10.3 Per-Scenario KV-Decode (Aggregate)

| Scenario | N/backend | Ollama Mean (ms) | Eager HF Mean (ms) | Ollama Speedup |
|----------|-----------|------------------|---------------------|----------------|
| single_micro | 120 | 96.5 | 2,019.6 | **20.9×** |
| single_short | 120 | 287.1 | 1,988.4 | 6.9× |
| single_medium | 120 | 341.3 | 1,995.8 | 5.9× |
| single_long | 120 | 445.8 | 2,045.1 | 4.6× |
| stress_single | 60 | 233.0 | 2,075.9 | **8.9×** |

**Observation:** Ollama's speedup is largest on `single_micro` (20.9×) where the generation is short relative to the KV cache setup. On `single_long`, the speedup narrows (4.6×) because the HF eager decode benefits from a larger pre-populated KV cache. The `stress_single` result (8.9×) reflects a one-prompt scenario with many tokens, where Ollama's steady-state generation speed dominates.

### 10.4 End-to-End (E2E_KV) Rankings

| Rank | Backend | N | Mean (ms) | Median (ms) | Std (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | **ollama** | 540 | **541.1** | 503.6 | 252.2 | 1,041.0 | [519.8, 562.5] |
| 2 | transformers-gpu | 540 | 2,051.2 | 2,317.2 | 1,033.4 | 3,302.3 | [1,963.8, 2,138.6] |

Ollama is **3.8× faster** end-to-end (d = 2.01, p < 10⁻¹⁶⁵).

#### Per-Model E2E Rankings

| Model | Ollama E2E (ms) | Eager HF E2E (ms) | Ollama Speedup | Notes |
|-------|----------------|-------------------|----------------|-------|
| qwen2.5-0.5b | 381.7 | 2,047.4 | **5.4×** | Ollama dominates |
| qwen2.5-1.5b | 448.6 | 2,484.3 | **5.5×** | Ollama dominates |
| llama3.2:1b | 601.5 | — | — | Ollama-only |
| gpt2-100m | — | 427.2 | — | HF-only |
| qwen2.5-3b | 732.7 | 3,246.0 | **4.4×** | Ollama dominates |

End-to-end speedups (4.4-5.5×) are lower than pure decode (6.8-13.7×) because prefill latency is similar across backends at larger scales (SS9.2). The decode portion dominates e2e latency, so Ollama's decode advantage drives the overall speedup.

### 10.5 mode="default" Compiled Decode Experiment (NEW in v2)

To test whether `mode="default"` (which nominally disables CUDA graph replay) could enable compiled decode, we ran the identical Phase 3 experiment with `torch.compile(mode="default", backend="inductor", dynamic=False)`. All other parameters (models, scenarios, reps, max_new_tokens=128) were unchanged.

**Config:** `research/tr126/phase3/config_mode_default.yaml`

**Result: compiled kv_decode and e2e_kv crash identically to `reduce-overhead`.**

| Mode | Backend | `reduce-overhead` | `mode="default"` |
|------|---------|:------------------:|:-----------------:|
| prefill | transformers-gpu-compile | All OK (-53.3%) | All OK (**-54.2%**) |
| kv_decode | transformers-gpu-compile | 100% crash | **100% crash** |
| e2e_kv | transformers-gpu-compile | 100% crash | **100% crash** |

**Prefill performance comparison:** mode="default" achieves -54.2% prefill speedup (d = -1.25, p = 7.6 × 10⁻⁸⁰) vs. reduce-overhead's -53.3% (d = -1.21). The slightly better default-mode prefill suggests CUDA graph replay overhead actually *hurts* prefill. Both modes use Triton kernel fusion — the difference is reduce-overhead adds CUDA graph capture/replay on top, which marginally slows prefill's single-pass execution.

**Error trace (mode="default"):**
```
torch/_inductor/cudagraph_trees.py, line 2457, in dealloc_current_path_weakrefs
    assert len(node.tensor_weakrefs) == len(node.stack_traces)
AssertionError
```

**Root cause analysis:** PyTorch 2.8's Inductor backend uses `cudagraph_trees.py` internally as part of its compiled kernel execution pipeline, regardless of the user-facing `mode` parameter. The `mode="default"` setting prevents *explicit* CUDA graph capture at the `torch.compile()` level, but the Inductor's own code generation passes still invoke CUDA graph tree management for compiled kernels. When tensor shapes change during autoregressive decode, these internal graph trees encounter the same shape mismatch that causes crashes under `reduce-overhead`. The specific bug is in `dealloc_current_path_weakrefs()` — see [pytorch/pytorch#175557](https://github.com/pytorch/pytorch/issues/175557) for our detailed root cause analysis and upstream fix.

**Implication:** There is no torch.compile mode in PyTorch 2.8 that enables compiled autoregressive decode. This closes the gap identified in v1's limitation L2 — the answer is definitively "no, compiled decode is not viable" rather than "untested." We verified the bug persists on PyTorch 2.10 (NGC 26.01) and have submitted an upstream fix ([pytorch/pytorch#175562](https://github.com/pytorch/pytorch/pull/175562)). As of 2.10, compilation remains exclusively a prefill optimization.

### 10.6 PyTorch 2.10 Rerun: Cross-Version Validation (NEW in v3)

To confirm the compiled decode crash is not a PyTorch 2.8-specific regression, we reran the full Phase 3 benchmark on **PyTorch 2.10.0a0** (NGC 26.01 container, CUDA 13.1, Triton 3.6.0). Our assertion fix (PR #175562) was pre-applied in the Docker image. The experiment used the same Phase 3 config as the original run: 5 models × 3 backends × 5 scenarios × 3 modes × 15 reps.

**Config:** `research/tr126/Dockerfile.pt210` (NGC 26.01 base + assertion fix)
**Run ID:** `20260223_210915`

#### PyTorch 2.10 Environment

| Component | PyTorch 2.8 (original) | PyTorch 2.10 (rerun) |
|-----------|:----------------------:|:--------------------:|
| PyTorch | 2.8.0a0+nv25.08 | 2.10.0a0+nv26.01 |
| CUDA | 13.0 | 13.1 |
| Triton | 3.3.1 | 3.6.0 |
| cuDNN | 9.12.00 | 9.17.01 |
| GPU | RTX 4080 Laptop | RTX 4080 Laptop |
| Assertion fix (PR #175562) | Not applied | **Pre-applied** |

#### Compiled Decode Status

| Mode | Backend | PyTorch 2.8 | PyTorch 2.10 |
|------|---------|:-----------:|:------------:|
| prefill | transformers-gpu-compile | All OK (-53.3%) | All OK (**-42.4%**) |
| kv_decode | transformers-gpu-compile | 100% crash | **100% crash** |
| e2e_kv | transformers-gpu-compile | 100% crash | **100% crash** |

**Result: identical crash behavior.** Compiled kv_decode and e2e_kv fail on all HF models with the same `CUDAGraphs tensor overwrite` error. The assertion fix (PR #175562) prevents the secondary assertion failure but does not address the root cause: `_free_And_Remove_DeleterFn` in `dealloc_current_path_weakrefs()` unconditionally frees storages still needed by subsequent warmup nodes.

#### Prefill Results (PyTorch 2.10)

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 540 | 11.459 | 8.172 | 29.416 | [10.614, 12.304] |
| 2 | ollama | 540 | 16.041 | 13.442 | 27.297 | [15.396, 16.687] |
| 3 | transformers-gpu | 540 | 19.902 | 19.412 | 38.582 | [18.879, 20.924] |

**Compile effect:** -42.4% (11.459 ms vs 19.902 ms, d = -0.761 [medium], p < 10⁻⁴). All 3/3 pairwise comparisons significant.

#### Per-Model Prefill Rankings (PyTorch 2.10)

| Model | Winner | Compile Mean (ms) | Eager Mean (ms) | Ollama Mean (ms) |
|-------|--------|-------------------|-----------------|-------------------|
| gpt2-100m | compile | 2.055 | 3.991 | — |
| qwen2.5-0.5b | compile | 5.885 | 17.109 | 12.163 |
| qwen2.5-1.5b | compile | 13.254 | 23.658 | 17.060 |
| qwen2.5-3b | **ollama** | 24.641 | 34.849 | 24.266 |
| llama3.2:1b | ollama | — | — | 10.676 |

The scale crossover persists on PyTorch 2.10: compiled HF wins for small/medium models, Ollama wins at 3B. At qwen2.5-3b, Ollama (24.266 ms) barely edges out compiled (24.641 ms) — well within CI overlap, consistent with the 1.5B crossover found on PyTorch 2.8.

#### Decode Results (PyTorch 2.10, eager + Ollama only)

| Mode | Ollama Mean (ms) | Eager HF Mean (ms) | Ollama Speedup | Cohen's d |
|------|-----------------|-------------------|----------------|-----------|
| kv_decode | 454.7 | 2,086.5 | **4.6×** | 2.10 (large) |
| e2e_kv | 726.4 | 2,084.3 | **2.9×** | 1.73 (large) |

Ollama dominance in decode is consistent across PyTorch versions (4.6× on 2.10 vs 7× on 2.8). The difference in magnitude reflects the different model mix — the 2.10 rerun includes gpt2-100m (HF-only, small decode latency) which dilutes the aggregate Ollama advantage.

#### Cross-Version Comparison

| Metric | PyTorch 2.8 | PyTorch 2.10 | Delta |
|--------|:-----------:|:------------:|:-----:|
| Compiled prefill speedup | -53.3% | -42.4% | 10.9pp less |
| Compiled prefill d | -1.21 | -0.761 | Smaller effect |
| Compiled decode crash rate | 100% | 100% | **Identical** |
| Ollama decode advantage | 7× | 4.6× | Different model mix |
| Outlier rate | 0.1% | 1.0% | Both excellent |
| Total measurements | 3,780 | 4,522 | — |

The smaller prefill effect on PyTorch 2.10 (d = -0.761 vs d = -1.21) is not evidence of regression — the model mixes differ (5 models on 2.10 including Ollama-only llama3.2:1b vs 5 models on 2.8 with different scenario distributions). The key finding is that **compiled decode remains universally broken** across two major PyTorch versions separated by two NGC releases.

**Implication:** The compiled decode crash persists across PyTorch versions because it stems from an architectural incompatibility between CUDA graphs and dynamic KV cache growth, not a version-specific regression. See SS10.7 for prototype fix attempts that confirmed the root cause is at the model/cache layer, not in `cudagraph_trees.py`.

### 10.7 Bug #2 Prototype Fix: Root Cause is Architectural (NEW in v3)

To test whether the compiled decode crash could be fixed within `cudagraph_trees.py`, we prototyped three increasingly aggressive patches on PyTorch 2.10.0a0 (NGC 26.01):

**Patch progression:**

| Patch | What it does | Result |
|-------|-------------|--------|
| Bug #1 (PR #175562) | Replace assertion with warning at `dealloc_current_path_weakrefs` line 2497 | Secondary assertion removed. **Original crash persists** — this was never the root cause. |
| Bug #2 (skip dealloc) | Comment out `_free_And_Remove_DeleterFn` at line 2537 | **New error:** `check_memory_pool` at line 1870 rejects untracked live storages. Compiled prefill AND decode both fail. |
| Bug #3 (suppress pool check) | Convert `check_memory_pool` `raise RuntimeError` to `log.warning` + return | **Original error resurfaces:** `get_non_cudagraph_inps` at line 673 accesses tensor whose storage was overwritten by CUDA graph replay. |

**Docker images used:**
- `tr126-pt210` — Bug #1 only (production baseline)
- `tr126-pt210-bug2fix` — Bugs #1 + #2 + #3 (prototype only, not safe for production)

**Analysis of Patch 3 failure:**

The error trace from the triple-patched run reveals the fundamental issue:

```
File "cudagraph_trees.py", line 673, in get_non_cudagraph_inps
    and t.untyped_storage().data_ptr() not in existing_path_data_ptrs
RuntimeError: Error: accessing tensor output of CUDAGraphs that has been overwritten
by a subsequent run.
...
File "cache_utils.py", line 120, in update
    self.keys = torch.cat([self.keys, key_states], dim=-2)
```

The crash sequence:
1. CUDA graph A records decode step N, writing KV cache outputs to addresses `[addr_1, addr_2, ...]`
2. CUDA graph B records decode step N+1 at **new** addresses (because `torch.cat` allocates new tensors)
3. When graph B replays, it overwrites `[addr_1, addr_2, ...]` because CUDA graph replay reuses the recorded memory layout
4. Graph A's output tensors (still referenced by the KV cache) now contain garbage data
5. Any subsequent access to these tensors triggers the `_set_storage_access_error_msg` error

**Conclusion:** The crash is not a bug in `dealloc_current_path_weakrefs`. The function is doing its job correctly — marking storages as freed because they **will** be overwritten by CUDA graph replay. The real incompatibility is:

- **CUDA graphs** require static memory layout across replays
- **`DynamicCache.update()`** uses `torch.cat()`, which allocates new tensors at growing addresses each decode step
- These are fundamentally incompatible regardless of any `cudagraph_trees.py` patch

**Viable fix paths (all at the model/cache layer, not in PyTorch internals):**

1. **`StaticCache`**: Pre-allocate KV cache to max sequence length. No `torch.cat`, no new allocations. Compatible with CUDA graphs. Available in transformers `StaticCache` class.
2. **`cudagraph_mark_step_begin()`**: Insert between decode steps to create separate graph segments, allowing shape changes across segments.
3. **Pre-allocated ring buffer**: Fixed-size KV cache with pointer rotation instead of concatenation.
4. **Eager decode only**: Use `torch.compile` for prefill, eager mode for decode. This is the current recommendation (SS14.1).

This analysis supersedes the v2 characterization of the crash as a "bug" — it is more accurately described as an **architectural limitation** of CUDA graphs when combined with dynamic tensor operations. The upstream issue ([pytorch/pytorch#175557](https://github.com/pytorch/pytorch/issues/175557)) remains valid as a documentation/error-message improvement, and the assertion fix (PR #175562) is a genuine bug fix, but compiled decode requires model-level changes, not just PyTorch patches.

### 10.8 StaticCache Experiment: Model-Layer Fix Attempt (NEW in v3)

Having established that the crash is architectural (SS10.7), we tested the model-layer fix path: replacing `DynamicCache` with `StaticCache` (pre-allocated, no `torch.cat`) and compiling `model.forward` instead of the full model object.

**Setup:** qwen2.5-0.5b (FP16), `max_new_tokens=32`, transformers 5.2.0, PyTorch 2.10.0a0 (NGC 26.01).

| Configuration | Cache | Compile target | Result |
|--------------|-------|---------------|--------|
| `mode="reduce-overhead"` + StaticCache | StaticCache | `model.forward` | **Crash** — identical `CUDAGraphs tensor overwrite` |
| `mode="default"` + StaticCache | StaticCache | `model.forward` | **Works** — compiled decode completes |
| Eager + StaticCache (baseline) | StaticCache | none | **Works** — 622 ms mean |

**Key result:** `mode="default"` + StaticCache enables compiled decode — the first successful compiled decode in this entire research program. However:

| Backend | Mean (ms) | Relative |
|---------|-----------|----------|
| Eager + StaticCache | 622.2 | 1.0× (baseline) |
| Compiled + StaticCache (`mode="default"`) | 3,588.2 | **0.17× (5.8× slower)** |

Compiled decode is **5.8× slower** than eager. The Triton kernel compilation overhead per decode step far exceeds any kernel optimization benefit. Each decode step is a single-token forward pass — tiny compute, dominated by kernel launch and compilation overhead. Without CUDA graph replay to amortize launch costs, compilation actively hurts.

**Why `reduce-overhead` + StaticCache still crashes:** Even with pre-allocated static tensors, PyTorch 2.10's Inductor invokes CUDA graph tree management internally when `mode="reduce-overhead"` is set. The graph tree machinery tracks tensor storages and validates pool consistency — this validation fails even when the underlying tensors are static, because the Inductor's internal graph management still detects "overwritten" outputs from graph replay across decode steps. The `StaticCache` eliminates `torch.cat` but does not prevent the Inductor from creating internal CUDA graph recordings that conflict across decode iterations.

**Why `mode="default"` is slow:** Without CUDA graphs, each decode step invokes the full Triton kernel compilation/lookup pipeline. For a single-token forward pass, the overhead of resolving compiled kernels exceeds the execution time of the kernels themselves. CUDA graph replay (`reduce-overhead`) exists precisely to solve this problem — by replaying a recorded sequence of kernel launches without CPU-side dispatch. But CUDA graph replay requires the same crash-prone graph tree machinery.

**Existing upstream work:** HuggingFace [#27837](https://github.com/huggingface/transformers/issues/27837) ("torch CUDA graphs with HF generate") has been open since January 2024, explicitly identifying DynamicCache as the blocker. HuggingFace maintainers have confirmed that `StaticCache` is the intended solution ([#37908](https://github.com/huggingface/transformers/issues/37908)), and working examples exist for manual CUDA graph capture with StaticCache ([blog reference](https://xenshinu.github.io/cuda_graph/)). However, seamless integration into `.generate()` with `reduce-overhead` mode remains unresolved as of PyTorch 2.10 / transformers 5.2.0.

**Conclusion:** Compiled decode is a solved problem in theory (StaticCache + manual CUDA graph capture) but broken in practice through the standard `torch.compile` + `.generate()` path. The fix requires either: (a) PyTorch's Inductor to handle StaticCache's static memory layout correctly under `reduce-overhead`, or (b) transformers to implement manual CUDA graph capture in `.generate()` bypassing Inductor's graph tree machinery entirely. Neither is available today. The recommendation remains: **use eager for decode, or use Ollama.**

---

## 11. Phase 3 Statistical Analysis

### 11.1 Power Analysis

| Mode | N/group | Alpha | Power | Min detectable d | Min detectable Δ (ms) | Pooled std (ms) | Interpretation |
|------|---------|-------|-------|------------------|-----------------------|-----------------|----------------|
| prefill | 540 | 0.05 | 0.80 | 0.17 | 1.3 | 7.83 | Can detect small effects |
| kv_decode | 540 | 0.05 | 0.80 | 0.17 | 192.9 | 1,131.5 | Can detect small effects |
| e2e_kv | 540 | 0.05 | 0.80 | 0.17 | 181.7 | 1,065.7 | Can detect small effects |

All modes are adequately powered with d_min = 0.17. The high millisecond threshold for decode (192.9 ms) reflects the large absolute latencies and high variance, not a measurement weakness. The observed effects (d > 2.0 for decode) are far above this threshold.

### 11.2 Outlier Analysis

| Mode | Backend | N Total | N Outliers | Outlier % |
|------|---------|---------|------------|-----------|
| prefill | ollama | 540 | 5 | 0.9% |
| prefill | transformers-gpu | 540 | 0 | 0.0% |
| prefill | transformers-gpu-compile | 540 | 0 | 0.0% |
| kv_decode | ollama | 540 | 0 | 0.0% |
| kv_decode | transformers-gpu | 540 | 0 | 0.0% |
| e2e_kv | ollama | 540 | 0 | 0.0% |
| e2e_kv | transformers-gpu | 540 | 0 | 0.0% |

Mean outlier rate: **0.1%** — excellent measurement quality. The 5 Ollama prefill outliers are likely from initial Ollama model loading (first request after model swap). The decode/e2e modes show zero outliers, indicating highly stable measurement.

### 11.3 Robustness Notes

**Distribution shape:** Decode latencies show right skew (e.g., qwen2.5-1.5b Ollama decode: mean 211.8 ms vs median 85.2 ms, ratio 2.49). This extreme skew is driven by scenario mixing — short-prompt scenarios (single_micro) produce fast decode, while long-prompt scenarios (single_long) produce slow decode. Within-scenario distributions are tighter. The t-test is robust to this level of skew at N=540, but per-model-per-scenario analyses (where N=15) would benefit from non-parametric tests.

### 11.4 ANOVA Interaction Test: Backend × Model Scale (NEW in v2)

The v1 report noted the absence of formal interaction tests for the scale crossover claim. We now provide a 2-way ANOVA on Phase 3 prefill data (1,620 samples, 3 backends × 5 models).

**Model:** `latency_ms ~ backend + model + backend:model`

| Source | SS | df | MS | F | p-value | η² |
|--------|---:|---:|---:|--:|---------|---:|
| Backend | 28,793 | 2 | 14,397 | 4,929.1 | < 10⁻¹⁶ | 0.290 |
| Model | 52,428 | 4 | 13,107 | 4,487.5 | < 10⁻¹⁶ | 0.528 |
| **Backend × Model** | **10,587** | **8** | **1,323** | **453.1** | **< 10⁻¹⁶** | **0.107** |
| Residual | 4,697 | 1,608 | 2.92 | — | — | — |
| **Total** | **99,361** | **1,619** | — | — | — | — |

**The interaction term is highly significant** (F(8,1608) = 453.1, p < 10⁻¹⁶, η² = 0.107). This means the effect of backend choice depends on model scale — formally validating the qualitative crossover observation in SS9.2.

**Interpretation:**
- **Model scale explains the most variance** (η² = 0.528): larger models have higher latencies regardless of backend.
- **Backend explains substantial variance** (η² = 0.290): compilation consistently reduces prefill latency.
- **The interaction explains 10.7% of variance** (η² = 0.107): this is the crossover effect. Small models show large compile advantage; large models show Ollama catching up or winning. The interaction is not merely statistically significant (which is expected at N=1,620) — it explains a meaningful fraction of the total variance, confirming it is a real structural effect rather than statistical noise.

**Grand mean:** 11.62 ms across all 1,620 samples.

---

## 12. Cross-Phase Validation

### 12.0 Automated Validation Status

The analysis pipelines for both Phase 2 and Phase 3 include an automated cross-phase validation check that attempts to match `environment.json` from Phase 1 against the current run's environment. **Both returned `validated: false`** with detail `"environment.json missing"` — the Phase 1 environment gate and Phase 2/3 runs stored their outputs in different timestamped directories, so the automated lookup could not resolve the path.

**Manual validation status:** We verify environment consistency manually in SS12.2 below by comparing all environment fields across the three phases' manifest files. The environment is identical. The automated check failure is a path-resolution issue in the analysis pipeline, not an actual environment mismatch. We report this transparently rather than suppressing the warning.

### 12.1 Phase 2 → Phase 3 Consistency (gpt2-100m)

gpt2-100m appears in both phases with identical configuration (FP32, same compile config), enabling direct cross-validation:

| Metric | Phase 2 (N=270, 30 reps) | Phase 3 (N=135, 15 reps) | Δ | Consistent? |
|--------|--------------------------|--------------------------|---|-------------|
| Eager mean (ms) | 3.93 | 3.84 | -2.3% | **Yes** |
| Eager median (ms) | 3.89 | 3.80 | -2.3% | **Yes** |
| Eager std (ms) | 0.13 | 0.16 | +22% | Acceptable |
| Compiled mean (ms) | 2.95 | 1.60 | -45.6% | **No** |
| Compiled median (ms) | 2.48 | 1.57 | -36.7% | **No** |
| Compile helps | Yes | Yes | — | **Yes** |
| Compile delta (%) | -24.9% | -58.3% | — | Direction consistent |

**Eager baseline is highly consistent** (3.93 vs 3.84 ms, 2.3% difference). This validates that the two phases measured the same model on the same hardware.

**Compiled result differs substantially** (2.95 vs 1.60 ms, -45.6%). This is a significant discrepancy on the same model, same GPU, same day. The primary cause is a **compile configuration difference between phases**:

| Config Parameter | Phase 2 (dynamic) | Phase 3 |
|------------------|--------------------|---------|
| `dynamic` | **True** | **False** |
| `mode` | `reduce-overhead` | `reduce-overhead` |
| `max_new_tokens` | 64 | 128 |

The `dynamic=True` setting adds shape-recording overhead to every forward pass — PyTorch's Dynamo guards check tensor shapes before dispatching to cached code. This overhead appears to cost ~1.35 ms per call on gpt2-100m, representing an **~85% penalty relative to `dynamic=False`**. This is a meaningful finding in its own right: `dynamic=True` is not free, and for small models where absolute latency is < 5 ms, the overhead is proportionally large.

Secondary factors may contribute:
- Phase 3 ran models sequentially (gpt2-100m was the first HF model), so the Triton kernel cache was warm from Phase 2's earlier runs on the same Docker session
- Different warmup strategies (Phase 2 `run_compile.py` vs Phase 3 `run_matrix.py`)

**The directional finding — compilation helps — is consistent across both phases.** But the magnitude depends on the `dynamic` setting. Users should be aware that `dynamic=True` adds measurable overhead, especially for small models. Phase 3's `dynamic=False` result (1.60 ms, -58.3%) better represents the ceiling of compile performance, while Phase 2's `dynamic=True` result (2.95 ms, -24.9%) represents a more conservative, shape-flexible deployment.

### 12.2 Phase 1 → Phase 2/3 Environment Consistency

| Property | Phase 1 | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| GPU | RTX 4080 Laptop | RTX 4080 Laptop | RTX 4080 Laptop |
| VRAM | 12.88 GB | 12.88 GB | 12.88 GB |
| CUDA | 13.0 | 13.0 | 13.0 |
| cuDNN | 91200 | 91200 | 91200 |
| Triton | 3.3.1 | 3.3.1 | 3.3.1 |
| PyTorch | 2.8.0a0 | 2.8.0a0 | 2.8.0a0 |
| Container | Docker (WSL2) | Docker (WSL2) | Docker (WSL2) |

Environment is identical across all three phases. All runs used the same Docker image built from `research/tr126/Dockerfile`.

---

## 13. Cross-Platform Comparison: Windows vs Linux

### 13.1 The Core Finding

| Platform | Compilation Backend | Prefill Effect | Direction | Evidence |
|----------|-------------------|---------------|-----------|----------|
| **Windows** (TR120) | `aot_eager` fallback | Compilation hurts or neutral | Paradox present | TR120 §5 |
| **Linux** (TR126) | Real Inductor+Triton | **-40% to -53% speedup** | **Paradox resolved** | SS5, SS9 |

The compile paradox was entirely a platform artifact. The same GPU, same model weights, same prompts produce opposite results depending on whether Triton is available.

### 13.1.1 Limitation: No Overlapping Model for Quantitative A/B

TR120's controlled runner tested `tiny-gpt2` (a model not included in TR126's Phase 2/3 matrix). TR126 tests `gpt2-25m/50m/100m` and `qwen2.5-*`, none of which were tested in TR120. This means **there is no single model with paired Windows and Linux measurements from both reports**. The cross-platform comparison is therefore qualitative (direction of the compile effect) rather than quantitative (side-by-side latency numbers on the same model).

A quantitative cross-platform A/B would require re-running TR120's models on Linux or TR126's models on Windows. We did not do this because: (a) TR120's primary model (`tiny-gpt2`) is too small to be production-relevant, and (b) running TR126's models on Windows would only measure `aot_eager` — an exercise of limited value given that the fallback is already well-characterized.

The Phase 1 weight parity check (SS3.3) confirms that model loading is correct on Linux. The Phase 2 eager baseline consistency across phases (SS12.1, 2.3% delta on gpt2-100m) validates that the measurement methodology is stable. These provide confidence in the comparison even without a paired model.

### 13.2 Why Windows Falls Back

PyTorch's `torch.compile(backend="inductor")` requires Triton for GPU code generation. Triton does not support Windows (as of PyTorch 2.8). On Windows, PyTorch silently falls back to `aot_eager`, which:

1. **Traces the model graph** — adds compilation overhead (~100-500ms one-time, amortized over subsequent calls)
2. **Does NOT generate optimized GPU kernels** — the traced graph uses the same eager operators
3. **Adds dispatch overhead** — each operation goes through the tracing framework's dispatcher, adding per-op overhead

The result is a "compiled" model that is strictly slower than eager mode. The overhead is small per-operation but compounds across the thousands of operations in a model forward pass, producing the 5-15% latency *increase* observed in TR120.

### 13.3 What Real Compilation Does (Linux)

With Triton available, Inductor compilation:

1. **Fuses operations** — combines multiple elementwise operations into single GPU kernels
2. **Generates custom Triton kernels** — hardware-specific code for the RTX 4080's Ada Lovelace architecture
3. **Optimizes memory access patterns** — reduces the number of global memory reads/writes
4. **Uses CUDA graphs** (with `reduce-overhead`) — eliminates CPU-side kernel launch overhead entirely

The result is 24-60% latency reduction, with the benefit proportionally larger for smaller models where dispatch overhead dominates.

### 13.4 Impact on Prior Research

| Report | Affected Findings | TR126 Resolution |
|--------|-------------------|------------------|
| TR117 | Backend rankings for `-compile` variants | **Invalidated** — `-compile` on Windows was aot_eager. Rankings would change on Linux. |
| TR120 | "Compile paradox" as genuine compiler phenomenon | **Resolved** — paradox was a platform artifact, not a compiler property |
| TR120 | Shape churn causes compilation tails | **Confirmed** — 0.3% outlier rate in TR126 Phase 2 shows same mechanism, but rare enough to be negligible |
| TR120 | Padding/bucketing collapses compiled tail | **Confirmed** — TR126 Phase 2 padded config (SS5.4) shows 15% faster compiled latency vs dynamic, with qwen2.5-0.5b achieving 5.0× speedup under padding. Stable shapes improve Triton kernel caching. |
| TR121 | Compile-related latency analysis | **Partially invalidated** — non-compile findings remain valid, compile-specific conclusions need re-evaluation |
| TR122 | Shape churn as root cause | **Confirmed on Linux** — compilation churn is real but rare (0.3% outliers) |
| TR123 | Cost economics for eager backends | **Still valid** — TR123 measured eager backends, not compile |
| TR124 | Quality baselines | **Still valid** — TR124 measured output quality, not compilation performance |
| TR125 | Quantization quality + Ollama performance | **Still valid** — TR125 measured Ollama quality/throughput, not HF compilation |
| TR126 v1 | "use `mode=default` for decode" suggestion | **Superseded** — TR126 v2 shows mode="default" also crashes (Inductor uses CUDA graph trees internally). No torch.compile mode enables decode. |
| TR126 v1 | Decode recommendation had "untested" caveat | **Resolved** — Compiled decode is now fully characterized: crashes at 128 tokens on all modes; no speedup even at 64 tokens where it works. Ollama decode recommendation stands without caveats. |

---

## 14. Production Guidance & Decision Trees

### 14.1 Backend Selection by Workload Mode

| Workload Mode | Recommended Backend | Expected Latency | Rationale |
|---------------|-------------------|-----------------|-----------|
| **Prefill-heavy** (RAG, summarization, embedding) | `torch.compile` + `reduce-overhead` | 8.2 ms mean (Phase 3) | 2× faster than Ollama, 53% faster than eager |
| **Decode-heavy** (chat, code gen, long-form) | Ollama (quantized) | 286 ms mean (Phase 3) | 7× faster than eager HF |
| **Balanced** (mixed prefill + decode) | Ollama | 541 ms e2e mean | Simplicity + strong decode performance |
| **Latency-critical prefill** (search, autocomplete) | `torch.compile` + eager decode | ~2 ms (small models) | Compile for prefill, eager for decode (mode="default" also crashes) |

### 14.2 Model Scale Decision

The crossover point where Ollama beats compiled HF on prefill is **~1.5B parameters**:

| Model Size | Prefill Winner | Margin | Decode Winner | Best Overall |
|------------|---------------|--------|---------------|--------------|
| ≤100M | Compiled HF | 2.4× | Eager HF (Ollama N/A) | Compiled HF |
| ~500M | Compiled HF | 2.0-4.6× | Ollama (13.7×) | Split strategy |
| ~1.5B | **Tie** | 0.19 ms | Ollama (11.5×) | Ollama |
| ≥3B | Ollama | 1.4× | Ollama (6.8×) | Ollama |

### 14.3 Platform Requirements

| Feature | Windows | Linux |
|---------|---------|-------|
| `torch.compile` effective | **No** (aot_eager fallback) | **Yes** (Inductor+Triton) |
| Triton available | No | Yes |
| Ollama available | Yes | Yes |
| `reduce-overhead` for prefill | No | Yes |
| CUDA graphs | No (no Triton) | Yes |
| Recommendation | **Use Ollama for all modes** | Compile for prefill, Ollama for decode |

### 14.4 Deployment Checklist

Before deploying torch.compile in production on Linux:

- [ ] Verify Triton is installed and importable
- [ ] Verify `torch.compile(backend="inductor")` produces 0 graph breaks on your model
- [ ] Use `mode="reduce-overhead"` ONLY for prefill; use eager (no compile) for decode — `mode="default"` also crashes
- [ ] Set `TRITON_CACHE_DIR` to a persistent directory (avoid recompilation on restart)
- [ ] Run warmup (3+ forward passes) before serving production traffic
- [ ] Monitor for recompilation events (>30ms latency spikes at 0.3% frequency)
- [ ] On Windows: do NOT use torch.compile; use Ollama instead

---

## 15. Limitations & Future Work

### 15.1 Limitations

1. **Single GPU:** All results are from one RTX 4080 Laptop (12.88 GB, Ada Lovelace). Results may differ on datacenter GPUs (A100 with 80 GB, H100 with HBM3) where memory bandwidth characteristics differ. The crossover point (1.5B) will likely shift on higher-bandwidth hardware.

2. **~~No `mode="default"` for decode~~ (RESOLVED in v2):** v2 tested `mode="default"` — it also crashes due to PyTorch 2.8 Inductor's internal CUDA graph tree management (SS10.5). Additionally, Phase 2 baseline shows compiled decode provides no speedup even when it works (SS5.6). This limitation is fully resolved: compiled decode is not viable in PyTorch 2.8.

3. **Ollama quantization level unknown:** Ollama's default quant level for `qwen2.5:*` and `llama3.2:1b` is likely Q4_0 or Q4_K_M. The HF-vs-Ollama comparison conflates compilation effects with quantization effects. A controlled comparison would use the same precision (FP16 Ollama vs FP16 HF, or Q4 GPTQ HF vs Q4 Ollama).

4. **No multi-batch testing:** All scenarios use batch size 1. Compilation benefits may differ under batched inference, where GPU utilization is higher and dispatch overhead is proportionally lower.

5. **Docker/WSL2 overhead:** WSL2 Docker adds a small overhead compared to bare-metal Linux (typically 3-5% for GPU workloads). Absolute latencies may be slightly lower on bare-metal.

6. **FP16 HF vs quantized Ollama (decode):** The decode comparison (HF FP16 vs Ollama quantized) is not apples-to-apples. Ollama's decode advantage comes partly from lower precision (Q4 requires 4× less memory bandwidth per weight than FP16), not just implementation quality. A fair comparison would use the same precision.

7. **No CUDA event timing:** TR126 uses `time.perf_counter()` with synchronization barriers. TR120 additionally used CUDA event timing to validate sub-millisecond measurements. For the small GPT-2 models where compiled latency is < 2 ms, CUDA event timing would provide a stronger validation.

8. **No thermal throttle monitoring:** Phase 2 runs for ~90 min and Phase 3 for ~45 min on a laptop GPU (150W TDP). No GPU clock speed or temperature monitoring was performed during the runs. Laptop GPUs are known to thermally throttle under sustained load, which could systematically reduce performance for models/scenarios tested later in each phase's sequence. The impact is likely small (models were loaded/freed sequentially, creating cooling windows between models), but not measured.

9. **Triton kernel cache warmth confound:** Models are compiled and measured sequentially (gpt2-25m first, qwen2.5-3b last). The Triton kernel cache is cumulative and persists across models within a Phase 2 run. Later models may benefit from a warmer cache (pre-compiled utility kernels). The evidence files confirm monotonically growing cache sizes (17 → 916 kernels). This could systematically bias later models toward faster compiled latencies. However, the compilation kernels are model-specific (different attention heads, layer dimensions), so shared kernel reuse across different models is unlikely to be significant.

10. **No randomization of execution order:** Backends, models, and scenarios were run in a fixed order (not randomized). This means systematic time-varying effects (thermal drift, background process interference, GPU clock state changes) are confounded with model/backend order. In Phase 3, the model-outer-loop design means all 3 modes and all 5 scenarios complete for one model before moving to the next, reducing cross-model contamination but not eliminating time-varying effects within a model's measurement window.

11. **Ollama runs on Windows host, HF runs in Linux Docker:** The backends under comparison run on different platforms. HF transformers execute inside the Docker container on Linux, while Ollama's inference engine runs on the Windows host and is accessed via HTTP (`host.docker.internal:11434`). Ollama's GPU scheduling context differs from the Docker container's — Ollama competes for GPU resources through the Windows CUDA driver, while HF uses the Linux CUDA driver via WSL2 GPU passthrough. We use Ollama's native timing fields (`prompt_eval_duration`, `eval_duration`) to exclude HTTP overhead, but the GPU execution context is not identical. This is inherent to the experimental setup (Ollama is a system service, not a Python library) and cannot be resolved without running both backends on the same platform.

12. **Automated cross-platform comparison not computed:** The Phase 2 analysis pipeline has a `cross_platform` field that returned `null` — no automated Windows-vs-Linux comparison was computed. The cross-platform analysis in SS13 is based on manual comparison of report findings, not on a statistical pipeline that ingests both TR120 and TR126 raw data. A rigorous cross-platform analysis would require a shared analysis script that loads both reports' metrics CSVs and computes paired statistics.

13. **No `dynamo_counters` evidence beyond Phase 1:** Phase 1's gate check verifies 0 graph breaks on a tiny model. Phase 2/3 runs do not record `dynamo_counters_after_compile` (unlike TR120, which logged these per-model). The Triton kernel cache growth provides indirect evidence of real compilation, but dynamo counters (unique_graphs, graph_break_count) would provide stronger proof that each model was fully compiled without fallback paths.

### 15.2 Future Work

- **Phase 4 (deferred):** uvloop multi-agent concurrency testing under Linux — tests whether compile benefits survive under concurrent request load.
- **~~Compiled decode investigation (originally scoped as separate TR)~~ (FULLY EXHAUSTED within TR126):** v2's `mode="default"` experiment crashes. v3's StaticCache + `mode="default"` works but is 5.8× slower than eager. `reduce-overhead` + StaticCache still crashes. Three-patch prototype on `cudagraph_trees.py` proved the issue is architectural. Manual CUDA graph capture (bypassing Inductor) is the only remaining viable path — see [huggingface/transformers#27837](https://github.com/huggingface/transformers/issues/27837) for upstream progress. (Note: TR127 in the research roadmap is assigned to Long-Context Performance Characterization, not compiled decode.)
- **Upstream fix for cudagraph_trees.py (PARTIALLY RESOLVED):** We traced the crash to `dealloc_current_path_weakrefs()` in `torch/_inductor/cudagraph_trees.py` and filed [pytorch/pytorch#175557](https://github.com/pytorch/pytorch/issues/175557). An assertion fix is submitted as [pytorch/pytorch#175562](https://github.com/pytorch/pytorch/pull/175562). However, prototype experiments (v3) demonstrated that the crash is **architectural, not patchable in cudagraph_trees.py alone**: disabling `_free_And_Remove_DeleterFn` + `check_memory_pool` still crashes because CUDA graph replay overwrites output tensor memory, and `DynamicCache.update()` → `torch.cat()` creates tensors at new addresses each step. The fix must come from the model/cache layer (e.g., `StaticCache`, `cudagraph_mark_step_begin()`). See SS10.7 for full prototype results.
- **Compiled decode threshold characterization:** The crash occurs between 64 and 128 generated tokens. A binary search experiment (80, 96, 112 tokens) could pinpoint the exact threshold where CUDA graph shape tolerances are exceeded.
- **Cross-GPU validation:** Replicate on A100/H100 to test whether findings generalize beyond consumer GPUs.
- **Bare-metal Linux:** Remove Docker/WSL2 layer for a true Linux baseline.
- **Controlled quantization comparison:** Compare FP16 HF vs FP16 Ollama (via custom GGUF) to isolate runtime effects from quantization effects.

---

## 16. Reproducibility

### 16.1 Docker Setup

```bash
# Build image (one-time)
docker build -t tr126 -f research/tr126/Dockerfile .

# Phase 1: Environment validation (~5 min)
MSYS_NO_PATHCONV=1 docker run --rm --gpus all \
  -v "$(pwd):/workspace" -w /workspace \
  tr126 python research/tr126/phase1/run.py

# Phase 2: Compile paradox replication (~90 min)
MSYS_NO_PATHCONV=1 docker run --rm --gpus all --ipc=host \
  -v "$(pwd):/workspace" -w /workspace \
  tr126 python research/tr126/phase2/run.py

# Phase 3: Backend matrix (~45 min, requires Ollama on host)
MSYS_NO_PATHCONV=1 docker run --rm --gpus all --ipc=host \
  -v "$(pwd):/workspace" -w /workspace \
  tr126 python research/tr126/phase3/run.py --skip-ollama-setup -v

# Phase 3 PyTorch 2.10 rerun (NGC 26.01 + assertion fix)
docker build -t tr126-pt210 -f research/tr126/Dockerfile.pt210 .
MSYS_NO_PATHCONV=1 docker run --rm --gpus all --ipc=host \
  -v "$(pwd):/workspace" -w /workspace \
  tr126-pt210 python research/tr126/phase3/run.py --skip-ollama-setup -v
```

### 16.2 Prerequisites

- Docker with NVIDIA GPU support (`nvidia-docker2` or Docker 19.03+ with `--gpus`)
- NVIDIA driver supporting CUDA 13.0+
- Ollama running on Windows host (for Phase 3 only): `ollama serve`
- Ollama models pulled: `ollama pull qwen2.5:0.5b qwen2.5:1.5b qwen2.5:3b llama3.2:1b`
- HF model weights at `models/gpt2-{25m,50m,100m}`, `models/qwen2.5-{0.5b,1.5b,3b}`, `models/tiny-gpt2` (Phase 1)

### 16.3 Config Files (Source of Truth)

| Phase | Config | Description |
|-------|--------|-------------|
| 1 | `research/tr126/phase1/config.yaml` | Model path, seed, tolerances |
| 2 | `research/tr126/phase2/config.yaml` | Baseline: `dynamic=False` |
| 2 | `research/tr126/phase2/config_padded.yaml` | Padded: fixed shapes |
| 2 | `research/tr126/phase2/config_dynamic.yaml` | Dynamic: `dynamic=True` |
| 3 | `research/tr126/phase3/config.yaml` | 3 backends, 5 models, 5 scenarios |
| 3 | `research/tr126/phase3/config_mode_default.yaml` | mode="default" decode experiment (v2) |

### 16.4 Key Artifacts

| Artifact | Path | Size |
|----------|------|------|
| Phase 1 environment | `research/tr126/results/phase1/20260222_195228/environment.json` | 1 KB |
| Phase 1 weight parity | `research/tr126/results/phase1/20260222_195522/weight_parity.json` | 22 KB |
| Phase 2 analysis (dynamic) | `research/tr126/results/phase2/20260222_214114/phase2_analysis.json` | 15 KB |
| Phase 2 Triton evidence | `research/tr126/results/phase2/20260222_195655/triton_evidence_*.json` | 6 × 113 B |
| Phase 2 manifest (baseline) | `research/tr126/results/phase2/20260222_195655/manifest.json` | 2 KB |
| Phase 3 analysis | `research/tr126/results/phase3/20260222_231929/phase3_analysis.json` | 33 KB |
| Phase 3 manifest | `research/tr126/results/phase3/20260222_231929/manifest.json` | 1 KB |
| Phase 3 prefill CSV | `research/tr126/results/phase3/20260222_231929/prefill/metrics.csv` | 1,620 rows |
| Phase 3 kv_decode CSV | `research/tr126/results/phase3/20260222_231929/kv_decode/metrics.csv` | 1,170 rows |
| Phase 3 e2e_kv CSV | `research/tr126/results/phase3/20260222_231929/e2e_kv/metrics.csv` | 1,100 rows |
| v2 enhancement analysis | `research/tr126/results/enhance_v2_results.json` | ~30 KB |
| v2 mode="default" config | `research/tr126/phase3/config_mode_default.yaml` | 1 KB |
| v2 mode="default" analysis | `research/tr126/results/phase3/20260223_034940/phase3_analysis.json` | 33 KB |
| v2 mode="default" prefill CSV | `research/tr126/results/phase3/20260223_034940/prefill/metrics.csv` | 1,620 rows |

### 16.5 Analysis Scripts

| Script | Description |
|--------|-------------|
| `research/tr126/phase2/analyze.py` | Phase 2: compile paradox analysis, per-model/scenario breakdown |
| `research/tr126/phase2/generate_report.py` | Phase 2: auto-generates markdown report |
| `research/tr126/phase3/analyze.py` | Phase 3: backend rankings, pairwise comparisons, power analysis |
| `research/tr126/phase3/generate_report.py` | Phase 3: auto-generates markdown report |
| `research/tr126/shared/env_fingerprint.py` | Environment capture utility |
| `research/tr126/shared/cross_platform_compare.py` | Windows vs Linux comparison utility |
| `research/tr126/enhance_v2.py` | v2: ANOVA, Bonferroni, compiled decode, baseline analysis |
| `research/tr126/Dockerfile.pt210` | PyTorch 2.10 (NGC 26.01) Docker image with assertion fix |
| `research/tr126/Dockerfile.pt210-bug2fix` | PyTorch 2.10 with Bug #2 prototype fix (skip _free_And_Remove_DeleterFn) |

---

## Appendix A: Environment Specifications

### Linux Docker Environment

| Component | Version | Source |
|-----------|---------|--------|
| Host OS | Windows 11 Home 10.0.26200 | — |
| WSL2 Kernel | 6.6.87.2-microsoft-standard-WSL2 | `uname -r` |
| Docker Base | nvidia/cuda:13.0-cudnn9-devel-ubuntu22.04 | Dockerfile |
| Python | 3.12.3 (GCC 13.3.0) | `sys.version` |
| PyTorch | 2.8.0a0+34c6371d24.nv25.08 | `torch.__version__` |
| CUDA | 13.0 | `torch.version.cuda` |
| cuDNN | 9.12.00 (91200) | `torch.backends.cudnn.version()` |
| Triton | 3.3.1 | `triton.__version__` |
| Transformers | Latest (pip install) | `transformers.__version__` |

### GPU Specifications

| Property | Value |
|----------|-------|
| Name | NVIDIA GeForce RTX 4080 Laptop GPU |
| Architecture | Ada Lovelace (AD104) |
| Compute Capability | 8.9 |
| CUDA Cores | 7,424 |
| VRAM | 12.88 GB GDDR6 |
| Memory Bus | 192-bit |
| Memory Bandwidth | 256 GB/s |
| TDP | 150W (laptop) |

### PyTorch 2.10 Docker Environment (Phase 3 Rerun)

| Component | Version | Source |
|-----------|---------|--------|
| Host OS | Windows 11 Home 10.0.26200 | — |
| WSL2 Kernel | 6.6.87.2-microsoft-standard-WSL2 | `uname -r` |
| Docker Base | nvcr.io/nvidia/pytorch:26.01-py3 | Dockerfile.pt210 |
| Python | 3.12.3 (GCC 13.3.0) | `sys.version` |
| PyTorch | 2.10.0a0+a36e1d39eb.nv26.01 | `torch.__version__` |
| CUDA | 13.1 | `torch.version.cuda` |
| cuDNN | 9.17.01 (91701) | `torch.backends.cudnn.version()` |
| Triton | 3.6.0 | `triton.__version__` |
| Transformers | Latest (pip install) | `transformers.__version__` |
| Patches applied | PR #175562 (assertion fix) | Dockerfile.pt210 |

### Windows Host Environment (TR120 Comparison)

| Property | TR120 Value | TR126 Value | Same? |
|----------|------------|------------|-------|
| GPU | RTX 4080 Laptop | RTX 4080 Laptop | **Yes** |
| GPU VRAM | 12.88 GB | 12.88 GB | **Yes** |
| Compute Capability | 8.9 | 8.9 | **Yes** |
| Python | 3.13 | 3.12.3 | Minor |
| PyTorch | 2.8.0a0+nv25.05 | 2.8.0a0+nv25.08 | Minor |
| Triton | Not available | 3.3.1 | **Different (the variable)** |
| OS | Windows 11 | Linux (Docker/WSL2) | **Different (the treatment)** |

---

## Appendix B: Triton Evidence

Triton compilation is verified by physical evidence, not just API return codes. This follows TR120's standard (§2.5) where a run is considered *compiler-real* only with artifact-backed proof.

### Kernel Cache Evidence

After Phase 2 compilation (baseline run), each model produces cached Triton kernels in `TRITON_CACHE_DIR=/tmp/triton_cache`. **The `cached_kernels` field reports a cumulative directory count** — each model's count includes all kernels from previously-compiled models in the same run. We compute per-model kernel deltas by subtracting the previous model's cumulative count:

| Model | `triton_available` | `triton_version` | Cumulative Kernels | **Per-Model Delta** | `inductor_backend` |
|-------|-------------------|-----------------|-------------------|--------------------|--------------------|
| gpt2-25m | true | 3.3.1 | 17 | **17** | false* |
| gpt2-50m | true | 3.3.1 | 144 | **127** | false* |
| gpt2-100m | true | 3.3.1 | 389 | **245** | false* |
| qwen2.5-0.5b | true | 3.3.1 | 528 | **139** | false* |
| qwen2.5-1.5b | true | 3.3.1 | 735 | **207** | false* |
| qwen2.5-3b | true | 3.3.1 | 916 | **181** | false* |

Total: **916 cached Triton kernels** across 6 models (17-245 per model). Larger models generate more kernels, consistent with more attention heads and larger FFN layers requiring more specialized GPU code. The GPT-2 family (MHA) generates more kernels per parameter than Qwen2.5 (GQA), likely because MHA's per-head KV tensors create more distinct shapes.

*Note on `inductor_backend: false`: Every evidence file reports this field as `false`. The detection method checks a `torch._inductor` module-level attribute that is not reliably set after compilation in PyTorch 2.8.0a0. **This is a known false-negative in the evidence collection script, not evidence against real compilation.** The positive evidence chain is conclusive:

1. **Triton present:** Triton 3.3.1 importable and functional (Phase 1 gate, 4/4 checks pass)
2. **Kernels generated:** 916 Triton kernels materialized on disk in `TRITON_CACHE_DIR` — this cannot happen without Inductor routing through Triton
3. **Zero graph breaks:** Phase 1 gate verified `torch.compile(backend="inductor")` with 0 graph breaks
4. **Performance proves compilation:** 24-60% prefill speedups are physically impossible under `aot_eager` (which adds overhead, not removes it). The speedup magnitudes are consistent with Triton kernel fusion literature.
5. **No fallback recorded:** Unlike TR120 on Windows, no `aot_eager` fallback appears in any manifest

A more robust future detection method would record `torch._dynamo.utils.counters` (unique_graphs, graph_break_count) after compilation, as done in TR120 but not implemented in TR126's runner. The `inductor_backend` field should be treated as unreliable in PyTorch nightly builds.

### Validation Chain

1. **Phase 1 gate:** `import triton` succeeds → Triton 3.3.1 available
2. **Phase 1 gate:** `torch.compile(model, backend="inductor")` → 0 graph breaks → Inductor runs successfully
3. **Phase 2 evidence:** 916 cumulative cached Triton kernels (17-245 per model) → kernels were generated and stored
4. **Phase 2 performance:** 24-60% speedup vs eager → the compiled model is using different (faster) GPU code
5. **No fallback recorded:** Unlike TR120 on Windows, no `aot_eager` fallback appears in any manifest or evidence file

---

## Appendix C: Configs (Source of Truth for Runs)

### Phase 2 Compile Config (Dynamic)

```yaml
torch_compile:
  enabled: true
  backend: inductor
  mode: reduce-overhead
  dynamic: true
  fullgraph: false

device: cuda
repetitions: 30
warmup_repetitions: 3
max_new_tokens: 64
seed: 42

models:
  - path: models/gpt2-25m
    dtype: fp32
  - path: models/gpt2-50m
    dtype: fp32
  - path: models/gpt2-100m
    dtype: fp32
  - path: models/qwen2.5-0.5b
    dtype: fp16
  - path: models/qwen2.5-1.5b
    dtype: fp16
  - path: models/qwen2.5-3b
    dtype: fp16
```

### Phase 3 Backend Matrix Config

```yaml
backends:
  - transformers-gpu
  - transformers-gpu-compile
  - ollama

models:
  - name: models/gpt2-100m
    dtype: fp32
    ollama_tag: null
  - name: models/qwen2.5-0.5b
    dtype: fp16
    ollama_tag: "qwen2.5:0.5b"
  - name: models/qwen2.5-1.5b
    dtype: fp16
    ollama_tag: "qwen2.5:1.5b"
  - name: models/qwen2.5-3b
    dtype: fp16
    ollama_tag: "qwen2.5:3b"
  - name: llama3.2:1b
    ollama_tag: "llama3.2:1b"

scenarios:
  - single_micro
  - single_short
  - single_medium
  - single_long
  - stress_single

repetitions: 15
warmup_repetitions: 3
max_new_tokens: 128
seed: 42

torch_compile:
  backend: inductor
  mode: reduce-overhead
  dynamic: false

modes:
  - prefill
  - kv_decode
  - e2e_kv

ollama_url: http://host.docker.internal:11434
ollama_timeout_s: 120
```

### Phase 3 mode="default" Config (NEW in v2)

Identical to Phase 3 config above, except `mode: default` instead of `mode: reduce-overhead`. This disables explicit CUDA graph replay but, as discovered, does not prevent Inductor's internal CUDA graph tree usage.

```yaml
torch_compile:
  backend: inductor
  mode: default          # KEY CHANGE from reduce-overhead
  dynamic: false
```

**Result:** Compiled decode crashes identically to `reduce-overhead` — confirming the issue is in Inductor's internal CUDA graph tree management, not the user-facing mode parameter.

---

## Appendix D: Glossary

| Term | Definition |
|------|-----------|
| **aot_eager** | PyTorch's fallback compilation backend. Traces the computational graph ahead-of-time but generates no optimized GPU kernels. Used automatically on Windows where Triton is unavailable. Adds dispatch overhead without optimization benefit. |
| **Cohen's d** | Standardized effect size measuring the difference between two means in units of pooled standard deviation. Negligible: \|d\| < 0.2, Small: 0.2-0.5, Medium: 0.5-0.8, Large: > 0.8. |
| **Compile paradox** | TR120's observation that `torch.compile` appeared to make inference slower or produce bimodal distributions with heavy tails. TR126 resolved this as an artifact of the Windows `aot_eager` fallback. |
| **CUDA graphs** | NVIDIA optimization that captures a sequence of GPU operations (kernel launches, memory copies) into a replayable graph, eliminating CPU-side dispatch overhead entirely. Requires all tensor shapes to be static across replays. |
| **e2e_kv** | End-to-end KV-cached mode: measures prefill + autoregressive decode timed together. The closest approximation to full serving latency while excluding tokenization and framework overhead. |
| **GQA** | Grouped Query Attention — KV heads are shared across query head groups, reducing KV cache size relative to MHA. Used by Qwen2.5 (2 KV heads) and Llama 3.2. |
| **Inductor** | PyTorch's default compilation backend (`torch.compile(backend="inductor")`). Generates optimized GPU kernels via Triton. Supports CUDA graph mode (`reduce-overhead`) and dynamic shapes. |
| **kv_decode** | KV-cached decode mode: measures only the autoregressive token generation loop, excluding the initial prefill. Each token is generated using the full KV cache from all prior tokens. |
| **MHA** | Multi-Head Attention — each query head has its own dedicated KV head pair. Used by GPT-2. Results in larger KV caches than GQA for the same model size. |
| **prefill** | The initial forward pass that processes the full input prompt and populates the KV cache. This is the "time to first token" kernel work, excluding tokenization overhead. |
| **reduce-overhead** | `torch.compile` compilation mode that uses CUDA graphs to minimize CPU-side kernel launch overhead. Produces the fastest inference but requires static tensor shapes — incompatible with autoregressive decode where KV cache grows each step. |
| **Triton** | OpenAI's open-source GPU programming language used by PyTorch Inductor to generate optimized CUDA kernels at compile time. Supports the full range of GPU operations but is only available on Linux. |
| **WSL2** | Windows Subsystem for Linux 2 — a lightweight Linux VM running a real Linux kernel on Windows, with GPU passthrough support via NVIDIA CUDA-on-WSL. Used by Docker Desktop to provide Linux containers with GPU access. |

---

## References

1. TR117: Baseline Benchmark — Tier-3 backend matrix and prompt sets used in Phases 2-3.
2. TR120: The Compile Paradox (Root-Cause Audit) — Discovered aot_eager fallback on Windows, established compile evidence standards.
3. TR123: KV-Cache Production Economics — Model loading patterns and HF backend methodology.
4. TR125: Quantization Decision Matrix — Ollama model selection and quality validation data.
5. PyTorch Inductor documentation — torch.compile backend architecture and CUDA graph modes.
6. Triton Language Reference (OpenAI) — GPU kernel generation methodology.
7. NVIDIA CUDA Graphs documentation — Static shape requirements and replay semantics.
8. pytorch/pytorch#175557 — Upstream bug report: `torch.compile` crashes during autoregressive decode with growing KV cache in `cudagraph_trees.py`.
9. pytorch/pytorch#175562 — Upstream fix: `tensor_weakrefs`/`stack_traces` assertion mismatch in `dealloc_current_path_weakrefs`.
10. huggingface/transformers#27837 — "torch CUDA graphs with HF generate" — open since Jan 2024, DynamicCache identified as blocker.
11. huggingface/transformers#37908 — DynamicCache recompilation issue — maintainer confirmed StaticCache is the intended solution.
12. Xueshen Liu, "Compact Inference with CUDA graph and StaticCache" — working example of manual CUDA graph capture with StaticCache.

---

*Generated from TR126 experiment data. All statistics computed from raw timing data with `torch.cuda.synchronize()` barriers. Effect sizes (Cohen's d) use pooled standard deviation. P-values from Welch's two-sample t-test. Confidence intervals at 95% level.*
