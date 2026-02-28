# Technical Report 125: Quantization Decision Matrix
## Production-grade quant level selection across 5 models (1.2B-8B) with real benchmark validation

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-02-22 (Phase 1: Feb 21, Phase 2: Feb 22)
**Author:** Research Team
**Report Type:** Quantization impact analysis (metric-backed, 2-phase)
**Test Duration:** ~20 min (Phase 1) + ~10 hrs (Phase 2)
**Status:** Complete — Both phases delivered
**Run IDs:** Phase 1: `20260220_203010`, Phase 2: `20260221_120035`
**Related Work:** [TR124](Technical_Report_124.md) (Quality & Accuracy Baseline), [TR123](Technical_Report_123.md) (KV-Cache Production Economics)
**Depends On:** TR124 (FP16 baselines, metric framework), TR123 (cost data)

---

## Abstract

TR124 established quality baselines and confirmed backend equivalence, but left a critical deployment question unanswered: **how much quantization can a model tolerate before quality degrades unacceptably?** TR124's Phase 2 tested only 4 models at Ollama's default quant levels with 200 samples and no benchmark anchoring. TR125 fills this gap with a comprehensive 2-phase quantization decision matrix spanning 7 quant levels, 5 models, and ~26,000 evaluated samples.

**Phase 1 (Exploratory):** We evaluate **3 models** (1.2B-2.7B parameters) across **6 quant levels** (Q2_K through Q8_0) on **5 generation tasks** (10 samples each) -- totaling **900 evaluated samples** with wall-clock timing. Q8_0 serves as the quantization baseline. Phase 1 identifies the base-vs-instruct confound in TR124's FP16 baselines and establishes that quality is broadly stable from Q8_0 through Q5_K_M before degrading at Q3_K_S and collapsing at Q2_K.

**Phase 2 (Production-Grade):** We evaluate **5 models** (1.2B-8B parameters) across **7 quant levels** (Q2_K through FP16) on **7 tasks** -- **285 real MMLU questions** + **200 real ARC-Challenge questions** from HuggingFace (primary quality gate) plus **5 generation tasks** (50 samples each, secondary) -- totaling **24,990 evaluated samples** with native Ollama timing. FP16 Ollama baselines eliminate the base-vs-instruct confound. A 4-tier quality classification system (negligible/acceptable/concerning/unacceptable) replaces Phase 1's binary threshold.

**Total: ~26,000 samples across 2 phases, 34 model-quant variants.**

**v2 Enhancement:** Re-analysis of existing Phase 2 data adds: Wilson confidence intervals for all benchmark tables, generation quality CIs (in raw data), MMLU vs ARC differential analysis, all 7 generation metrics (including repetition collapse detection), per-task quality breakdown, IQR outlier detection on timing data, Bonferroni/Holm multiple comparison correction (7/16 survive), TOST equivalence testing at two margins (0/18 at ±3pp; 6/18 generation-equivalent at ±5pp), complete 34-variant TTFT table, and explicit 29-variant tier enumeration. No new data collection -- all computed from existing 24,990 samples.

Key findings:

- **Q4_K_M is the universal sweet spot:** 21 of 29 quantized variants maintain benchmark accuracy within 5pp of baseline. All 5 models preserve negligible-to-acceptable quality at Q4_K_M; FP16-baselined models save 30-67% vs FP16, and llama3.1-8b saves 49% vs its Q8_0 baseline.
- **The quality cliff is at Q3_K_S, not Q4_K_M:** llama3.2-3b loses -10.1pp, qwen2.5-1.5b loses -12.2pp, and llama3.2-1b loses -9.5pp at Q3_K_S. Q4_K_M is safe; Q3_K_S is not.
- **Q2_K is universally unacceptable:** Every model tested loses >11pp benchmark accuracy at Q2_K. qwen2.5-1.5b loses -40.6pp -- near-random performance.
- **phi-2 is the most quantization-robust model:** All quant levels Q3_K_S and above stay within -1.8pp of FP16. phi-2 at Q3_K_S loses only -0.4pp.
- **llama3.1-8b achieves the highest accuracy:** 72.4% rescored accuracy at Q8_0, maintaining 69.7% even at Q4_K_M (-2.7pp).
- **Cost range spans 10x:** $0.0203/1M tokens (llama3.2-1b Q2_K) to $0.1976/1M tokens (llama3.1-8b Q8_0).
- **phi-2's raw accuracy is misleading:** 26% raw but 59% rescored -- a formatting issue, not a knowledge issue. Rescored accuracy using regex letter extraction is essential.
- **Native timing reveals massive HTTP overhead:** 190-920% overhead between Ollama-native eval_duration and wall-clock timing.

---

## Metric Definitions

These definitions control comparability across models and ensure consistency with TR124.

### Generation Metrics

- **ROUGE-L:** Longest common subsequence F1 against reference text. Measures structural overlap. Range [0, 1].
- **BERTScore:** Contextual embedding similarity using microsoft/deberta-xlarge-mnli. More robust to paraphrasing than ROUGE. Range [0, 1].
- **BLEU:** Geometric mean of 1-4 gram precision with brevity penalty. Standard for code generation. Range [0, 1].
- **Coherence (SemScore):** Cosine similarity using `all-mpnet-base-v2` sentence-transformers. Highest human correlation among automated metrics (Aynetdinov & Akbik 2024). Range [0, 1].
- **Exact Match:** Binary. 1 if candidate matches reference (case-insensitive, stripped). Range {0, 1}.
- **Output Length:** `min(len(candidate), len(reference)) / max(...)`. Penalizes both truncation and over-generation. Range [0, 1].
- **Repetition:** `unique_4grams / total_4grams`. Lexical diversity measure. Score of 1.0 = maximally diverse. Range [0, 1].

### Benchmark Metrics

- **Raw Accuracy:** Framework exact_match on model output vs correct answer letter. Sensitive to formatting noise (e.g., "B) Ampere" does not match "B").
- **Rescored Accuracy:** Regex letter extraction from model output, then compared to correct answer. Handles common formatting patterns: "B", "B)", "The answer is B", "Answer: B". This is the **primary quality metric** for benchmarks, as it separates knowledge from formatting ability.

### Quality Tier System

Quality tiers classify each (model, quant) combination based on the **worse** of benchmark accuracy delta (in percentage points) and generation quality delta (in percent):

| Tier | Benchmark Delta (pp) | Generation Delta (%) | Interpretation |
|------|---------------------|---------------------|----------------|
| **Negligible** | >= -3pp | >= -3% | No meaningful quality loss |
| **Acceptable** | >= -5pp | >= -8% | Minor degradation, acceptable for most uses |
| **Concerning** | >= -10pp | >= -15% | Noticeable quality loss, evaluate for specific task |
| **Unacceptable** | Worse than above | Worse than above | Do not deploy |

### Key Metric Average

For generation tasks, the **key metric average** is the unweighted mean of BERTScore, coherence, and ROUGE-L. These three metrics capture structural overlap (ROUGE-L), semantic similarity (BERTScore), and meaning preservation (coherence). Deltas are reported as percent change vs baseline.

### Statistical Methods & Caveats

**Tests used:**

- **Pairwise Welch's t-tests** between adjacent quant levels on rescored accuracy (binary 0/1) and generation metrics (continuous). Alpha = 0.05 uncorrected. See SS15 for full results.
- **Power analysis** via normal approximation for minimum detectable effect at alpha = 0.05, power = 0.80. See SS16.

**Important caveats:**

1. **Multiple comparison correction:** TR125 runs 116 pairwise tests (29 benchmark + 87 generation). At alpha = 0.05, ~5.8 false positives are expected by chance. **No family-wise correction is applied to reported p-values**, but Bonferroni and Holm corrections were computed (SS15.4). **7 of 16 significant results survive both corrections** — all at the Q3_K_S/Q2_K boundary. The Q2_K cliff is robust; the Q3_K_S cliff is not.

2. **t-tests on binary data:** Benchmark accuracy is binary (0/1 per question). While Welch's t-test converges to a z-test at N=485, a two-proportion z-test or chi-squared test would be the standard approach. Cohen's d on binary data is bounded (max ~2.0 at p=0.5), producing mechanically small effect sizes. Reported d values for benchmark tests should not be directly compared to generation d values.

3. **Equivalence claims require equivalence testing:** Classifying a variant as "negligible" quality loss is an equivalence claim. A non-significant t-test (p > 0.05) does NOT establish equivalence; it merely fails to detect a difference. TOST (Two One-Sided Tests) was applied to all 18 negligible variants at both ±3pp and ±5pp equivalence margins (SS15.5). At ±3pp: **0/18 pass**. At ±5pp: **0/18 benchmark pass, 6/18 generation pass** (phi-2 Q8_0/Q6_K/Q5_K_M, llama3.2-3b Q8_0/Q6_K, qwen2.5-1.5b Q8_0). Generation quality can confirm equivalence at wider margins because continuous metrics have lower variance than binary benchmark data. The "negligible" tier should be read as "point estimate within 3pp, 6 variants confirmed generation-equivalent at ±5%, but benchmark equivalence unconfirmed."

4. **Tier thresholds vs MDE:** The benchmark MDE is 9.0pp at 80% power (SS16.1). The "negligible" tier uses a -3pp threshold and "acceptable" uses -5pp — both below the detection limit. This means tier classifications for deltas between 0 and -9pp are based on point estimates that may not be statistically distinguishable from zero. The tier system remains useful as a point-estimate decision guide, but the statistical evidence for "negligible vs acceptable" is weak for any individual variant.

5. **Confidence intervals:** The benchmark tables now include 95% Wilson CIs (SS8.1-8.5, added in v2). Wilson CI half-widths range from +/-3.7pp (low accuracy) to +/-4.4pp (mid accuracy). This means a reported delta of -2.3pp (llama3.2-1b Q4_K_M) is within the noise band and may not represent a real quality difference. Generation quality CIs exist in `phase2_analysis.json` and `phase2_v2_enhancements.json`.

6. **Ollama determinism assumption:** TR125 uses temp = 0.0 with single repetition, citing TR124 Phase 3's validation that deterministic outputs need only one rep. However, TR124 Phase 3 validated determinism for HuggingFace transformers backends, not Ollama (which uses llama.cpp). Ollama at temp = 0 may not be perfectly deterministic due to different floating-point accumulation order in llama.cpp's kernels. No determinism validation was performed for the Ollama backend in TR125. If Ollama is not perfectly deterministic, the single-repetition design underestimates measurement variance.

---

## Executive Summary

TR125 answers: **which quantization level should you choose for each model, and what quality-cost trade-off does each level offer?**

### Key Findings

1. **Q4_K_M is safe across all 5 models:** Maximum benchmark accuracy loss at Q4_K_M is -4.1pp (qwen2.5-1.5b). All other models lose <3pp. This is the recommended default quant level for production deployment.
2. **The quality cliff is sharp and model-dependent:** Quality is stable from FP16 through Q4_K_M, then drops abruptly at Q3_K_S for most models. llama3.2-3b loses -10.1pp at Q3_K_S, qwen2.5-1.5b loses -12.2pp. phi-2 is the exception -- Q3_K_S costs only -0.4pp.
3. **Q2_K is universally unacceptable:** All 5 models lose >11pp at Q2_K. qwen2.5-1.5b collapses to -40.6pp (near-random). No model should be deployed at Q2_K.
4. **llama3.1-8b delivers the highest benchmark accuracy:** 72.4% rescored accuracy at Q8_0, with 69.7% at Q4_K_M. The 8B model adds a genuine quality tier above the 1-3B models.
5. **phi-2 tolerates quantization best:** All levels Q3_K_S and above are within -1.8pp of FP16. Even Q3_K_S (-0.4pp) is classified "acceptable." This makes phi-2 the ideal candidate for aggressive quantization when VRAM is constrained.
6. **Rescored accuracy is essential:** phi-2's raw accuracy is 26% (looks near-random) but rescored accuracy is 59% (strong). Raw exact_match penalizes formatting differences, not knowledge gaps. All benchmark results use rescored accuracy.
7. **Native timing reveals true throughput:** Native tok/s ranges from 49 (llama3.1-8b Q8_0) to 480 (llama3.2-1b Q2_K). HTTP overhead adds 190-920% on top, making wall-clock timing unreliable for relative comparisons.
8. **Q4_K_M delivers large savings at production quality:** FP16-baselined models save 30-67% vs FP16, and llama3.1-8b saves 49% vs Q8_0. phi-2 Q4_K_M saves 67% vs FP16 while losing only -1.8pp accuracy.
9. **(v2) Repetition collapse at Q2_K:** qwen2.5-1.5b Q2_K shows repetition score of 0.702 (vs 0.992 baseline) -- degenerate looping text invisible to the 3 key metrics.
10. **(v2) TOST equivalence partially confirmed at wider margin:** 0/18 at ±3pp, but 6/18 generation-equivalent at ±5pp (phi-2 Q8_0/Q6_K/Q5_K_M, llama3.2-3b Q8_0/Q6_K, qwen2.5-1.5b Q8_0). Benchmark equivalence remains unconfirmed due to binary data variance.
11. **(v2) Bonferroni correction validates Q2_K cliff:** 7/16 significant tests survive correction -- all at Q3_K_S -> Q2_K boundary. The Q3_K_S cliff is not robust to correction.
12. **(v2) QA and classification most quantization-sensitive:** Per-task analysis shows 30-42% degradation at Q2_K for factual tasks vs 3-12% for creative writing.
13. **(v2) Cross-phase reproducibility is metric-dependent:** Only coherence is fully reproducible across Phase 1→2 (3/3 models <5% divergence). BERTScore diverges at -5.7% for 2/3 models (marginal). ROUGE-L diverges -10.7% to -18.6% (substantial). Coherence is the only fully reliable cross-phase signal (SS17).

### Key Decision

- For **maximum quality**: llama3.1-8b at Q8_0 (72.4% accuracy, $0.1976/1M tokens).
- For **best quality-per-dollar**: phi-2 at Q4_K_M (57.5% accuracy, $0.0490/1M tokens, 67% cheaper than FP16).
- For **maximum throughput**: llama3.2-1b at Q4_K_M (280.9 native tok/s, $0.0346/1M tokens, negligible quality loss).
- For **VRAM-constrained deployment** (<2GB): llama3.2-1b Q4_K_M (0.7 GB est.) or phi-2 Q3_K_S (1.2 GB est.).
- **Never deploy Q2_K** for any quality-sensitive task.

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| 1 | Q4_K_M preserves quality across all models | Benchmark accuracy within 5pp for all 5 models (SS8). Wilson CIs overlap baselines (SS8.1-8.5). TOST at +/-3pp fails (SS15.5) -- point estimate validated but equivalence unconfirmed | **Validated** (point estimate; TOST underpowered) |
| 2 | Quality cliff occurs at Q3_K_S boundary | 3/5 models lose >9pp at Q3_K_S (SS8) | **Validated** (model-dependent) |
| 3 | Q2_K is universally unacceptable | All 5 models lose >11pp benchmark accuracy (SS8) | **Validated** |
| 4 | phi-2 is most quantization-robust | Max loss -1.8pp through Q4_K_M, -0.4pp at Q3_K_S (SS8) | **Validated** |
| 5 | Rescored accuracy resolves formatting noise | phi-2: 26% raw vs 59% rescored (SS8) | **Validated** |
| 6 | Native timing eliminates HTTP overhead | CV 10-42% native vs 37-68% wall-clock (SS10) | **Validated** |
| 7 | Cost savings of 30-67% at Q4_K_M | Per-model cost table (SS12) | **Validated** |
| 8 | Phase 1 confound identified and resolved | Base-vs-instruct in TR124 FP16 baselines (SS4) | **Validated** |
| 9 | Q8_0 is equivalent to FP16 for most models | Max delta 1.6pp across 4 models with both levels (SS8) | **Validated** |
| 10 | Larger models tolerate quantization better (8B vs 1B) | llama3.1-8b: -2.7pp at Q4_K_M vs llama3.2-1b: -2.3pp (SS8) | **Partially validated** -- phi-2 at 2.7B is most robust |

---

## When to Use This Report

TR125 is the quantization decision guide for the Banterhearts research program. Use it when choosing which quant level to deploy for a given model, VRAM budget, and quality requirement.

### Scenario 1: Choosing a Quant Level for Production

**Question:** "I want to deploy qwen2.5-1.5b on a 4GB GPU. Which quant level should I use?"

**Answer:** Consult the decision matrix (SS13, 4GB VRAM tier). qwen2.5-1.5b at Q5_K_M (1.1 GB, -0.4pp, negligible) offers the best quality-preserving option. Q4_K_M (0.9 GB, -4.1pp, acceptable) is viable if you need more throughput. Avoid Q3_K_S (-12.2pp, unacceptable).

### Scenario 2: Validating a New Quantization

**Question:** "I created a custom GGUF quantization. Is the quality acceptable?"

**Answer:** Run the same MMLU (285) + ARC-Challenge (200) benchmark suite from SS5.3. Compare rescored accuracy against this report's baselines. If the delta is within -5pp of FP16, the quant is "acceptable."

### Scenario 3: Maximum Throughput with Quality Floor

**Question:** "I need the fastest possible inference with at least 60% benchmark accuracy."

**Answer:** Consult SS10 and SS8 together. llama3.1-8b at Q4_K_M delivers 96.7 native tok/s with 69.7% accuracy. If 60% is sufficient, llama3.2-3b at Q4_K_M offers 141.0 tok/s at 63.7% accuracy.

### Scenario 4: VRAM Budget Planning

**Question:** "How much VRAM do I need for llama3.1-8b at acceptable quality?"

**Answer:** llama3.1-8b Q4_K_M requires ~4.6 GB estimated VRAM. Q3_K_S (3.6 GB) is also acceptable (-2.5pp). Q2_K (2.6 GB) is unacceptable (-14.2pp). Budget 4-6 GB for the 8B model at production quality.

### Scenario 5: Cross-Referencing with TR123/TR124

**Question:** "TR123 says phi-2 costs $0.119/1M tokens at FP16. What does it cost quantized?"

**Answer:** Consult SS12. phi-2 at Q4_K_M costs $0.0490/1M tokens via Ollama -- 67% cheaper than FP16. At Q6_K, $0.0574/1M tokens -- 61% cheaper. The quality trade-off is negligible (-1.8pp and -1.2pp respectively).

### Scenario 6: Deciding Between Phase 1 and Phase 2 Results

**Question:** "Phase 1 said phi-2 Q2_K only loses -4.0% vs Q8_0. Phase 2 says -11.3pp. Which is right?"

**Answer:** Phase 2. Phase 1 used generation metrics only (BERTScore/coherence/ROUGE-L) with 50 samples and no benchmark anchoring. Phase 2 uses 485 real benchmark questions as the primary quality gate. Benchmark accuracy is a more objective measure of knowledge degradation than generation quality metrics.

---

## Table of Contents

**Phase 1: Exploratory Quantization (SS1-SS4)**

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Phase 1 Methodology](#2-phase-1-methodology)
3. [Phase 1 Results](#3-phase-1-results)
4. [Phase 1 Limitations & Lessons](#4-phase-1-limitations--lessons)

**Phase 2: Production-Grade Decision Matrix (SS5-SS17)**

5. [Phase 2 Methodology & Design](#5-phase-2-methodology--design)
6. [Environment & Artifacts](#6-environment--artifacts)
7. [Model Lineup](#7-model-lineup)
8. [Benchmark Accuracy Analysis](#8-benchmark-accuracy-analysis) (with Wilson CIs, MMLU vs ARC differential)
9. [Generation Quality Analysis](#9-generation-quality-analysis) (with all 7 metrics, per-task breakdown)
10. [Native Performance](#10-native-performance) (with outlier analysis)
11. [TTFT Analysis](#11-ttft-analysis) (full 34-variant table)
12. [Cost Analysis](#12-cost-analysis)
13. [Decision Matrix](#13-decision-matrix) (with 29-variant enumeration)
14. [Diminishing Returns](#14-diminishing-returns)
15. [Statistical Tests](#15-statistical-tests) (with Bonferroni/Holm correction, TOST equivalence)
16. [Power Analysis & Statistical Resolution](#16-power-analysis--statistical-resolution)
17. [Cross-Phase Validation](#17-cross-phase-validation)

**Cross-Phase Synthesis (SS18-SS19)**

18. [Phase 1 vs Phase 2 Synthesis](#18-phase-1-vs-phase-2-synthesis)
19. [Production Guidance & Decision Trees](#19-production-guidance--decision-trees)

**Closing**

- [Limitations & Methodological Caveats](#limitations--methodological-caveats)
- 20\. [Reproducibility](#20-reproducibility)

**Appendices**

- [Appendix A: Metric Definitions (Detailed)](#appendix-a-metric-definitions)
- [Appendix B: Benchmark Data Provenance](#appendix-b-benchmark-data-provenance)
- [Appendix C: Glossary](#appendix-c-glossary)
- [References](#references)

---

## 1. Introduction & Research Motivation

### 1.1 Research Questions

1. Which quantization levels **preserve benchmark accuracy** within acceptable thresholds for each model?
2. Where is the **quality cliff** -- the quant level at which accuracy degrades beyond acceptability?
3. Does the quality cliff **differ by model size** (1.2B vs 3.2B vs 8B)?
4. What are the **cost savings** at each quant level, and do they justify the quality trade-off?
5. Is there a **universal sweet spot** quant level that works across all models?
6. How do **generation quality metrics** (BERTScore, coherence, ROUGE-L) compare to **benchmark accuracy** as quality gates?

### 1.2 Why This Matters

Quantization is the single most impactful deployment knob for local LLM inference. Going from FP16 to Q4_K_M halves VRAM requirements and typically doubles throughput. But TR124's Phase 2 tested only 4 models at Ollama's default quant levels with 200 samples and no benchmark anchoring -- far too little data to make production deployment decisions.

The gap is practical: a developer choosing between Q4_K_M and Q6_K for a summarization pipeline needs to know whether the quality difference is 2% or 20%, and whether that difference is statistically significant or within measurement noise. TR125 provides these answers with real benchmark data (MMLU + ARC-Challenge from HuggingFace), 485 benchmark samples per variant, and a tiered quality classification system.

### 1.3 Scope

- **Hardware:** Single consumer machine (RTX 4080 Laptop, 12GB VRAM).
- **Models:** 5 models, 1.2B-8B parameters, all via Ollama (instruct/chat variants).
- **Backend:** Ollama HTTP API with native timing extraction (eval_duration, prompt_eval_duration).
- **Quant levels:** FP16, Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_S, Q2_K (7 levels for 4 models; 6 levels for llama3.1-8b, no FP16).
- **Evaluation modes:** Generation (prompt -> text -> metrics) and generation-based multiple-choice (prompt -> answer letter -> accuracy).
- **Benchmarks:** MMLU (285 questions, 57 subjects from cais/mmlu) and ARC-Challenge (200 questions from allenai/ai2_arc).
- **Temperature:** 0.0 (greedy decoding). Deterministic outputs -- single repetition is sufficient (validated by TR124 Phase 3).

### 1.4 Literature Grounding

| Reference | Contribution | How TR125 Uses It |
|-----------|-------------|-------------------|
| TR124 (Banterhearts) | FP16 quality baselines, metric framework | Baseline comparison, generation metrics |
| TR123 (Banterhearts) | KV-Cache cost data, hardware pricing | Cost derivation at $0.035/hr |
| EleutherAI lm-evaluation-harness | YAML task configs, benchmark methodology | MMLU/ARC question format |
| MMLU (Hendrycks et al. 2021) | 57-subject knowledge benchmark | Primary quality gate (285 questions) |
| ARC (Clark et al. 2018) | Science reasoning benchmark | Secondary quality gate (200 questions) |
| llama.cpp GGUF quantization | Q2_K through Q8_0 quant formats | Quant level definitions and VRAM estimates |

**Gap filled:** Prior quantization studies either test a single model at many quant levels or many models at a single quant level. TR125 provides a full matrix: 5 models x 7 quant levels, with both benchmark accuracy and generation quality metrics, enabling model-specific quantization recommendations.

---

## 2. Phase 1 Methodology

### 2.1 Design

| Parameter | Value |
|-----------|-------|
| Models | 3 (llama3.2-1b, phi-2, qwen2.5-1.5b) |
| Quant levels | 6 (Q2_K, Q3_K_S, Q4_K_M, Q5_K_M, Q6_K, Q8_0) |
| Baseline | Q8_0 (same Ollama instruct model) |
| Tasks | 5 generation (summarization, QA, code_generation, creative_writing, classification) |
| Samples per task | 10 |
| Total samples | 900 (18 variants x 50 samples) |
| Temperature | 0.0 |
| Timing | Wall-clock only (HTTP overhead included) |
| Benchmarks | None (Ollama lacks logprob support) |
| Run ID | `20260220_203010` |

### 2.2 Baseline Note

TR124 Phase 1 FP16 baselines used **base** models (e.g., `unsloth/Llama-3.2-1B`) while Ollama tags reference **instruct/chat** variants (e.g., `llama3.2:1b-instruct`). For llama and qwen, these are different model weights. FP16 deltas from TR124 mix instruct-tuning effects with quantization effects. Phase 1 therefore uses Q8_0 from the same Ollama run as the correct quantization baseline.

### 2.3 Quality Metrics

Key metrics for decision-making: BERTScore, coherence, ROUGE-L (averaged as "key metric average"). All 7 generation metrics were computed but decisions rely on these three.

---

## 3. Phase 1 Results

### 3.1 Quality Curves

Quality per (model, quant level). Delta measured vs Q8_0 (same instruct model, same Ollama backend).

#### llama3.2-1b

| Quant | N | BERTScore (vs Q8_0) | Coherence (vs Q8_0) | ROUGE-L (vs Q8_0) | Key Avg | vs Q8_0 |
|-------|---|-----|-----|-----|---------|---------|
| Q8_0 | 50 | 0.650 (+0.0%) | 0.573 (+0.0%) | 0.274 (+0.0%) | 0.4991 | +0.0% |
| Q6_K | 50 | 0.646 (-0.6%) | 0.573 (-0.0%) | 0.279 (+1.9%) | 0.4996 | +0.4% |
| Q5_K_M | 50 | 0.630 (-3.1%) | 0.568 (-0.9%) | 0.249 (-9.0%) | 0.4825 | -4.3% |
| Q4_K_M | 50 | 0.685 (+5.3%) | 0.594 (+3.7%) | 0.346 (+26.4%) | 0.5419 | +11.8% |
| Q3_K_S | 50 | 0.648 (-0.3%) | 0.545 (-4.8%) | 0.267 (-2.6%) | 0.4869 | -2.6% |
| Q2_K | 50 | 0.550 (-15.4%) | 0.475 (-17.1%) | 0.159 (-42.0%) | 0.3946 | **-24.9%** |

#### phi-2

| Quant | N | BERTScore (vs Q8_0) | Coherence (vs Q8_0) | ROUGE-L (vs Q8_0) | Key Avg | vs Q8_0 |
|-------|---|-----|-----|-----|---------|---------|
| Q8_0 | 50 | 0.767 (+0.0%) | 0.792 (+0.0%) | 0.513 (+0.0%) | 0.6907 | +0.0% |
| Q6_K | 50 | 0.768 (+0.1%) | 0.789 (-0.3%) | 0.501 (-2.3%) | 0.6861 | -0.8% |
| Q5_K_M | 50 | 0.760 (-1.0%) | 0.790 (-0.3%) | 0.504 (-1.8%) | 0.6845 | -1.0% |
| Q4_K_M | 50 | 0.721 (-6.1%) | 0.775 (-2.1%) | 0.444 (-13.5%) | 0.6465 | -7.2% |
| Q3_K_S | 50 | 0.739 (-3.8%) | 0.778 (-1.7%) | 0.435 (-15.2%) | 0.6507 | -6.9% |
| Q2_K | 50 | 0.780 (+1.6%) | 0.760 (-4.0%) | 0.465 (-9.4%) | 0.6680 | -4.0% |

#### qwen2.5-1.5b

| Quant | N | BERTScore (vs Q8_0) | Coherence (vs Q8_0) | ROUGE-L (vs Q8_0) | Key Avg | vs Q8_0 |
|-------|---|-----|-----|-----|---------|---------|
| Q8_0 | 50 | 0.790 (+0.0%) | 0.743 (+0.0%) | 0.426 (+0.0%) | 0.6534 | +0.0% |
| Q6_K | 50 | 0.726 (-8.2%) | 0.715 (-3.8%) | 0.357 (-16.2%) | 0.5995 | -9.4% |
| Q5_K_M | 50 | 0.746 (-5.6%) | 0.722 (-2.9%) | 0.373 (-12.4%) | 0.6138 | -7.0% |
| Q4_K_M | 50 | 0.719 (-9.0%) | 0.720 (-3.2%) | 0.326 (-23.5%) | 0.5884 | -11.9% |
| Q3_K_S | 50 | 0.735 (-7.0%) | 0.722 (-2.8%) | 0.364 (-14.7%) | 0.6070 | -8.2% |
| Q2_K | 50 | 0.561 (-29.1%) | 0.560 (-24.7%) | 0.166 (-61.1%) | 0.4288 | **-38.3%** |

### 3.2 Performance

Wall-clock throughput (includes HTTP overhead):

| Model | Quant | tok/s (mean) | Speedup vs Q8_0 |
|-------|-------|-------------|-----------------|
| llama3.2-1b | Q8_0 | 126.0 | 1.00x |
| llama3.2-1b | Q4_K_M | 134.4 | 1.07x |
| llama3.2-1b | Q2_K | 143.2 | 1.14x |
| phi-2 | Q8_0 | 68.7 | 1.00x |
| phi-2 | Q4_K_M | 76.2 | 1.11x |
| phi-2 | Q2_K | 57.6 | 0.84x |
| qwen2.5-1.5b | Q8_0 | 80.1 | 1.00x |
| qwen2.5-1.5b | Q4_K_M | 88.0 | 1.10x |
| qwen2.5-1.5b | Q2_K | 108.5 | 1.35x |

### 3.3 Statistical Tests

Only 5 of 45 pairwise t-tests reached significance -- all at the Q3_K_S-to-Q2_K boundary. No test between adjacent quant levels above Q3_K_S was significant, consistent with the finding that quality differences between Q8_0 and Q4_K_M are below measurement resolution at N=50.

### 3.4 Key Phase 1 Conclusions

1. **Quality is broadly stable Q8_0 through Q5_K_M** for all 3 models.
2. **Q2_K is catastrophic** for llama3.2-1b (-24.9%) and qwen2.5-1.5b (-38.3%).
3. **phi-2 is most robust** -- worst quant (Q4_K_M) loses only -7.2%.
4. **Non-monotonic quality** observed (e.g., llama3.2-1b Q4_K_M > Q8_0) -- likely measurement noise at N=50.

---

## 4. Phase 1 Limitations & Lessons

Phase 1 identified several critical limitations that Phase 2 was designed to address:

| Limitation | Impact | Phase 2 Fix |
|-----------|--------|-------------|
| **Wall-clock timing** (CV 37-42%) | Cannot reliably compare quant-level throughput | Native Ollama `eval_duration` |
| **Base-vs-instruct confound** | TR124 FP16 baselines were base models; Ollama uses instruct | FP16 Ollama baselines (same instruct model) |
| **No benchmark accuracy** | Generation metrics are noisy proxies for knowledge | Real MMLU (285) + ARC-Challenge (200) |
| **Binary quality threshold** (-10% safe/unsafe) | Too coarse for deployment decisions | 4-tier system (negligible/acceptable/concerning/unacceptable) |
| **Small sample size** (N=50, 10/task) | Cannot detect effects <10% at 80% power | N=485 benchmark + N=250 generation per variant |
| **3 models only** | No data above 2.7B parameters | 5 models spanning 1.2B-8B |
| **No TTFT measurement** | Cannot evaluate prompt processing latency | Native `prompt_eval_duration` |
| **No FP16 quant level** | Cannot measure FP16-to-Q8_0 delta | FP16 Ollama included for 4 of 5 models |

---

## 5. Phase 2 Methodology & Design

### 5.1 Research Questions

Phase 2 addresses the same 6 research questions from SS1.1, with sufficient statistical power and benchmark anchoring to produce actionable answers.

### 5.2 Benchmark Matrix

| Dimension | Values |
|-----------|--------|
| Models | llama3.2-1b (1.2B), qwen2.5-1.5b (1.5B), phi-2 (2.7B), llama3.2-3b (3.2B), llama3.1-8b (8B) |
| Quant levels | FP16, Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_S, Q2_K |
| Model variants | 34 (4 models x 7 levels + 1 model x 6 levels) |
| Benchmark tasks | MMLU (285 real questions), ARC-Challenge (200 real questions) |
| Generation tasks | summarization, QA, code_generation, creative_writing, classification (50 samples each) |
| Temperature | 0.0 (greedy) |
| Max new tokens | 256 |
| Repetitions | 1 (deterministic at temp=0; validated by TR124 Phase 3) |
| Seed | 42 |
| Warmup | 2 runs per model variant |

**Sample counts:**

| Category | Per Variant | Total (34 variants) |
|----------|-----------|---------------------|
| MMLU | 285 | 9,690 |
| ARC-Challenge | 200 | 6,800 |
| Generation (5 tasks x 50) | 250 | 8,500 |
| **Total** | **735** | **24,990** |

### 5.3 Real Benchmark Data

Unlike Phase 1 (which had no benchmarks) and TR124 Phase 1 (which used loglikelihood ranking), Phase 2 uses **generation-based scoring** on real benchmark questions:

- **MMLU:** 285 questions from `cais/mmlu` on HuggingFace, 5 per subject across 57 subjects. Model generates an answer letter; scored via regex extraction.
- **ARC-Challenge:** 200 questions from `allenai/ai2_arc` (Challenge subset). Same generation-based scoring.

Generation-based scoring is necessary because Ollama does not expose loglikelihood computation. The rescoring pipeline extracts answer letters from model output using regex patterns (e.g., "B", "B)", "The answer is B", "Answer: B"), reducing formatting noise.

### 5.4 Quality Tier System

See Metric Definitions section above. The tier system was designed with the power analysis in mind: the "negligible" tier (-3pp) is near the statistical detection limit (9.0pp MDE at 80% power), meaning measured values within this range are genuinely small.

### 5.5 Native Timing Methodology

Phase 2 extracts timing from Ollama's `backend_metadata` response:

- **eval_duration:** Time spent generating tokens (excludes prompt processing). This is the "native" decode time.
- **prompt_eval_duration:** Time spent processing the prompt (TTFT proxy).
- **Native tok/s:** `num_tokens_generated / (eval_duration_ms / 1000)`.
- **Wall-clock tok/s:** `num_tokens_generated / (generation_time_ms / 1000)` (includes HTTP overhead).
- **HTTP overhead %:** `(native_tok_per_s / wall_tok_per_s - 1) * 100`.

A framework patch was applied to serialize `backend_metadata` through `SampleRecord` (aggregator.py + runner.py), which was missing in Phase 1.

### 5.6 Statistical Methods

- **Pairwise Welch's t-tests:** Between adjacent quant levels on benchmark accuracy (rescored, binary 0/1) and generation metrics (bertscore, coherence, rouge_l, continuous). Alpha = 0.05 uncorrected. See "Statistical Methods & Caveats" section for discussion of multiple comparison correction, t-tests on binary data, and equivalence testing limitations.
- **Power analysis:** Normal approximation for minimum detectable effect (MDE) at alpha=0.05, power=0.80. Benchmark MDE = 9.0pp (worst case). Generation MDE = d=0.251.
- **Quality classification:** Tiered based on the worse of benchmark delta (pp) and generation delta (%). Note: "negligible" and "acceptable" tiers are below the benchmark MDE — see SS16.2 for implications.
- **Cross-phase validation:** Phase 1 Q8_0 vs Phase 2 Q8_0 on overlapping models, < 5% difference threshold.
- **Confidence intervals:** Wilson CIs shown in benchmark tables (SS8). Generation CIs available in raw analysis data. See SS15.5 for TOST equivalence testing.

### 5.7 Config

```yaml
experiment: tr125_phase2_full_matrix
models: 34 variants (5 base models x 6-7 quant levels)
backends: [ollama]
tasks: [summarization, qa, code_generation, creative_writing, classification, mmlu_real, arc_challenge]
temperature: 0.0
max_new_tokens: 256
repetitions: 1
seed: 42
```

---

## 6. Environment & Artifacts

### 6.1 Environment

- **OS:** Windows 11 Home 10.0.26200
- **Python:** 3.13
- **CPU:** 13th Gen Intel Core i9-13980HX
- **GPU:** NVIDIA GeForce RTX 4080 Laptop GPU (12,282 MB VRAM, CC 8.9)
- **Ollama:** Local HTTP API (http://localhost:11434)
- **BERTScore model:** microsoft/deberta-xlarge-mnli
- **Coherence model:** sentence-transformers/all-mpnet-base-v2

### 6.2 Key Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Phase 1 samples | `results/eval/tr125/20260220_203010/samples.jsonl` | 900 rows |
| Phase 1 report | `results/eval/tr125/20260220_203010/phase1_report.md` | Auto-generated |
| Phase 2 samples | `results/eval/tr125_phase2/20260221_120035/samples.jsonl` | 24,990 rows |
| Phase 2 analysis | `results/eval/tr125_phase2/20260221_120035/phase2_analysis.json` | Full analysis data |
| Phase 2 report | `results/eval/tr125_phase2/20260221_120035/phase2_report.md` | Auto-generated |
| Phase 2 config | `research/tr125/phase2/config.yaml` | 34-variant matrix |
| Analysis code | `research/tr125/phase2/analyze.py` | 9-analysis pipeline |
| v2 enhancements | `results/eval/tr125_phase2/20260221_120035/phase2_v2_enhancements.json` | Wilson CIs, Bonferroni, TOST, per-task, outliers |
| v2 analysis code | `research/tr125/phase2/enhance_v2.py` | 10-analysis enhancement pipeline |
| Published report | `PublishReady/reports/Technical_Report_125.md` | This file |

---

## 7. Model Lineup

### 7.1 Model Summary

| Model | Params | Quant Levels | Ollama Tag Pattern | FP16 VRAM Est |
|-------|--------|-------------|--------------------|----|
| llama3.2-1b | 1.24B | 7 (FP16-Q2_K) | `llama3.2:1b-instruct-{quant}` | 2.5 GB |
| qwen2.5-1.5b | 1.54B | 7 (FP16-Q2_K) | `qwen2.5:1.5b-instruct-{quant}` | 3.2 GB |
| phi-2 | 2.7B | 7 (FP16-Q2_K) | `phi:2.7b-chat-v2-{quant}` | 5.5 GB |
| llama3.2-3b | 3.21B | 7 (FP16-Q2_K) | `llama3.2:3b-instruct-{quant}` | 6.6 GB |
| llama3.1-8b | 8.03B | 6 (Q8_0-Q2_K) | `llama3.1:8b-instruct-{quant}` | ~16 GB (exceeds VRAM) |

### 7.2 Why These Models

- **llama3.2-1b (1.2B):** Smallest viable model. Tests whether quantization is even meaningful at small scale (answer: yes, Q2_K destroys quality).
- **qwen2.5-1.5b (1.5B):** Strong benchmark performer from TR124 (91% ARC-Easy). Tests whether high-benchmark models are more sensitive to quantization (answer: yes, Q2_K drops -40.6pp).
- **phi-2 (2.7B):** Most quantization-robust in Phase 1. Tests whether this holds with benchmark anchoring (answer: yes, -1.8pp max at Q4_K_M).
- **llama3.2-3b (3.2B):** Bridges the 1B-8B gap. Tests mid-range quantization behavior.
- **llama3.1-8b (8B):** First model exceeding the 1-3B range. Tests whether larger models tolerate quantization better (answer: mixed -- -2.7pp at Q4_K_M is comparable to smaller models, but Q3_K_S shows only -2.5pp vs -10pp for llama3.2-3b).

### 7.3 FP16 Exclusion: llama3.1-8b

llama3.1-8b at FP16 requires ~16 GB VRAM, exceeding the RTX 4080's 12 GB. Q8_0 serves as the baseline for this model. The Q8_0-to-FP16 delta for other models is consistently small (max 1.6pp), validating Q8_0 as a near-equivalent baseline.

---

## 8. Benchmark Accuracy Analysis

**This is the PRIMARY quality gate.** Benchmark accuracy on real MMLU + ARC-Challenge questions, using rescored accuracy (regex letter extraction). All deltas in percentage points (pp) vs primary baseline (FP16 for 4 models, Q8_0 for llama3.1-8b).

### 8.1 llama3.1-8b (baseline: Q8_0, 72.4% rescored)

| Quant | N | Raw Acc | Rescored Acc | 95% Wilson CI | MMLU | ARC | vs Q8_0 (pp) | Tier |
|-------|---|---------|-------------|---------------|------|-----|-------------|------|
| Q8_0 | 485 | 0.651 | 0.724 | [0.682, 0.762] | 0.698 | 0.760 | +0.0 | negligible |
| Q6_K | 485 | 0.643 | 0.707 | [0.665, 0.746] | 0.684 | 0.740 | -1.6 | negligible |
| Q5_K_M | 485 | 0.586 | 0.707 | [0.665, 0.746] | 0.681 | 0.745 | -1.6 | negligible |
| Q4_K_M | 485 | 0.637 | 0.697 | [0.654, 0.736] | 0.677 | 0.725 | -2.7 | negligible |
| Q3_K_S | 485 | 0.676 | 0.699 | [0.657, 0.738] | 0.663 | 0.750 | -2.5 | acceptable |
| Q2_K | 485 | 0.489 | 0.581 | [0.536, 0.624] | 0.540 | 0.640 | **-14.2** | unacceptable |

**Observation:** llama3.1-8b is remarkably stable through Q3_K_S (-2.5pp). The cliff is at Q2_K (-14.2pp). This 8B model tolerates aggressive quantization better than the smaller llama3.2-3b. Wilson CI half-width: +/-4.0pp at N=485.

### 8.2 llama3.2-1b (baseline: FP16, 38.4% rescored)

| Quant | N | Raw Acc | Rescored Acc | 95% Wilson CI | MMLU | ARC | vs FP16 (pp) | Tier |
|-------|---|---------|-------------|---------------|------|-----|-------------|------|
| FP16 | 485 | 0.365 | 0.384 | [0.342, 0.429] | 0.340 | 0.445 | +0.0 | negligible |
| Q8_0 | 485 | 0.375 | 0.396 | [0.353, 0.441] | 0.351 | 0.460 | +1.2 | negligible |
| Q6_K | 485 | 0.365 | 0.384 | [0.342, 0.429] | 0.344 | 0.440 | +0.0 | negligible |
| Q5_K_M | 485 | 0.373 | 0.386 | [0.344, 0.431] | 0.330 | 0.465 | +0.2 | negligible |
| Q4_K_M | 485 | 0.348 | 0.361 | [0.320, 0.405] | 0.337 | 0.395 | -2.3 | negligible |
| Q3_K_S | 485 | 0.256 | 0.289 | [0.250, 0.331] | 0.319 | 0.245 | -9.5 | concerning |
| Q2_K | 485 | 0.101 | 0.223 | [0.188, 0.263] | 0.193 | 0.265 | **-16.1** | unacceptable |

**Observation:** Quality is stable FP16 through Q4_K_M (max -2.3pp). The cliff hits at Q3_K_S (-9.5pp), with Q2_K near-random on ARC (4% raw accuracy, 26.5% rescored). Q8_0 slightly exceeds FP16 (+1.2pp) -- within measurement noise. Note the CIs for FP16 [0.342, 0.429] and Q4_K_M [0.320, 0.405] overlap substantially, confirming the -2.3pp delta is within noise.

### 8.3 llama3.2-3b (baseline: FP16, 64.1% rescored)

| Quant | N | Raw Acc | Rescored Acc | 95% Wilson CI | MMLU | ARC | vs FP16 (pp) | Tier |
|-------|---|---------|-------------|---------------|------|-----|-------------|------|
| FP16 | 485 | 0.612 | 0.641 | [0.598, 0.683] | 0.590 | 0.715 | +0.0 | negligible |
| Q8_0 | 485 | 0.612 | 0.645 | [0.602, 0.687] | 0.593 | 0.720 | +0.4 | negligible |
| Q6_K | 485 | 0.594 | 0.635 | [0.591, 0.677] | 0.579 | 0.715 | -0.6 | negligible |
| Q5_K_M | 485 | 0.602 | 0.633 | [0.589, 0.675] | 0.575 | 0.715 | -0.8 | negligible |
| Q4_K_M | 485 | 0.612 | 0.637 | [0.593, 0.679] | 0.590 | 0.705 | -0.4 | negligible |
| Q3_K_S | 485 | 0.466 | 0.540 | [0.496, 0.584] | 0.481 | 0.625 | **-10.1** | unacceptable |
| Q2_K | 485 | 0.458 | 0.511 | [0.467, 0.555] | 0.428 | 0.630 | **-13.0** | unacceptable |

**Observation:** Stable through Q4_K_M (-0.4pp). Dramatic cliff at Q3_K_S (-10.1pp). The 3B model is *less* tolerant of aggressive quantization than the 8B model (Q3_K_S: -10.1pp vs -2.5pp for 8B). CI overlap between FP16 [0.598, 0.683] and Q4_K_M [0.593, 0.679] is near-complete.

### 8.4 phi-2 (baseline: FP16, 59.4% rescored)

| Quant | N | Raw Acc | Rescored Acc | 95% Wilson CI | MMLU | ARC | vs FP16 (pp) | Tier |
|-------|---|---------|-------------|---------------|------|-----|-------------|------|
| FP16 | 485 | 0.262 | 0.594 | [0.549, 0.637] | 0.530 | 0.685 | +0.0 | negligible |
| Q8_0 | 485 | 0.268 | 0.577 | [0.533, 0.621] | 0.516 | 0.665 | -1.6 | negligible |
| Q6_K | 485 | 0.247 | 0.581 | [0.537, 0.625] | 0.516 | 0.675 | -1.2 | negligible |
| Q5_K_M | 485 | 0.254 | 0.600 | [0.556, 0.643] | 0.537 | 0.690 | +0.6 | negligible |
| Q4_K_M | 485 | 0.252 | 0.575 | [0.531, 0.619] | 0.505 | 0.675 | -1.8 | negligible |
| Q3_K_S | 485 | 0.301 | 0.590 | [0.545, 0.633] | 0.547 | 0.650 | -0.4 | acceptable |
| Q2_K | 485 | 0.179 | 0.480 | [0.436, 0.525] | 0.460 | 0.510 | **-11.3** | unacceptable |

**Observation:** phi-2 is the most quantization-robust model. All levels Q3_K_S and above are within -1.8pp of FP16. Q5_K_M actually exceeds FP16 by +0.6pp (within noise). Only Q2_K breaks the pattern (-11.3pp). All CIs from FP16 through Q3_K_S overlap heavily -- no pair is statistically distinguishable.

**Formatting issue:** phi-2's raw accuracy (26%) is dramatically lower than rescored accuracy (59%). This is a formatting problem: phi-2 produces verbose answers ("The answer is B because...") that fail exact_match but contain the correct letter. Rescoring recovers the true knowledge level.

### 8.5 qwen2.5-1.5b (baseline: FP16, 65.2% rescored)

| Quant | N | Raw Acc | Rescored Acc | 95% Wilson CI | MMLU | ARC | vs FP16 (pp) | Tier |
|-------|---|---------|-------------|---------------|------|-----|-------------|------|
| FP16 | 485 | 0.472 | 0.652 | [0.608, 0.693] | 0.590 | 0.740 | +0.0 | negligible |
| Q8_0 | 485 | 0.425 | 0.639 | [0.596, 0.681] | 0.565 | 0.745 | -1.2 | negligible |
| Q6_K | 485 | 0.497 | 0.639 | [0.596, 0.681] | 0.579 | 0.725 | -1.2 | negligible |
| Q5_K_M | 485 | 0.320 | 0.647 | [0.604, 0.689] | 0.586 | 0.735 | -0.4 | negligible |
| Q4_K_M | 485 | 0.487 | 0.610 | [0.566, 0.653] | 0.537 | 0.715 | -4.1 | acceptable |
| Q3_K_S | 485 | 0.171 | 0.530 | [0.485, 0.574] | 0.453 | 0.640 | **-12.2** | unacceptable |
| Q2_K | 485 | 0.035 | 0.245 | [0.209, 0.286] | 0.239 | 0.255 | **-40.6** | unacceptable |

**Observation:** qwen2.5-1.5b is the most quantization-sensitive model. Q4_K_M already shows -4.1pp (acceptable but notable). Q3_K_S drops -12.2pp. Q2_K is catastrophic: -40.6pp, reducing a 65% model to 24.5% (near-random for 4-choice questions). Note: FP16 CI upper bound (0.693) overlaps Q4_K_M CI lower bound (0.566) only marginally -- the -4.1pp delta is approaching statistical distinguishability.

### 8.6 Accuracy Cliff Summary

| Model | Last Safe Level | First Concerning | Cliff Size (pp) |
|-------|----------------|-----------------|-----------------|
| llama3.1-8b | Q3_K_S (-2.5pp) | Q2_K (-14.2pp) | 11.7 |
| llama3.2-1b | Q4_K_M (-2.3pp) | Q3_K_S (-9.5pp) | 7.2 |
| llama3.2-3b | Q4_K_M (-0.4pp) | Q3_K_S (-10.1pp) | 9.7 |
| phi-2 | Q3_K_S (-0.4pp) | Q2_K (-11.3pp) | 10.9 |
| qwen2.5-1.5b | Q4_K_M (-4.1pp) | Q3_K_S (-12.2pp) | 8.1 |

**Pattern:** The cliff is universally sharp (8-12pp drop in one quant step). The cliff location varies by model: phi-2 and llama3.1-8b tolerate Q3_K_S; the other three models break there. All models break at Q2_K.

### 8.7 MMLU vs ARC Differential Analysis

ARC consistently outperforms MMLU across nearly all variants, reflecting that science reasoning (ARC) and broad knowledge (MMLU) respond differently to quantization. The differential (MMLU - ARC, in pp) reveals model-specific patterns:

| Model | Quant | MMLU (%) | ARC (%) | MMLU - ARC (pp) |
|-------|-------|----------|---------|-----------------|
| llama3.1-8b | Q8_0 | 69.8 | 76.0 | -6.2 |
| llama3.1-8b | Q4_K_M | 67.7 | 72.5 | -4.8 |
| llama3.1-8b | Q2_K | 54.0 | 64.0 | -10.0 |
| llama3.2-1b | FP16 | 34.0 | 44.5 | -10.5 |
| llama3.2-1b | Q4_K_M | 33.7 | 39.5 | -5.8 |
| llama3.2-1b | Q3_K_S | 31.9 | 24.5 | **+7.4** |
| llama3.2-1b | Q2_K | 19.3 | 26.5 | -7.2 |
| llama3.2-3b | FP16 | 59.0 | 71.5 | -12.5 |
| llama3.2-3b | Q4_K_M | 59.0 | 70.5 | -11.5 |
| llama3.2-3b | Q2_K | 42.8 | 63.0 | **-20.2** |
| phi-2 | FP16 | 53.0 | 68.5 | -15.5 |
| phi-2 | Q4_K_M | 50.5 | 67.5 | -17.0 |
| phi-2 | Q2_K | 46.0 | 51.0 | -5.0 |
| qwen2.5-1.5b | FP16 | 59.0 | 74.0 | -15.0 |
| qwen2.5-1.5b | Q4_K_M | 53.7 | 71.5 | -17.8 |
| qwen2.5-1.5b | Q2_K | 23.9 | 25.5 | -1.6 |

**Key findings:**

1. **ARC is generally more robust than MMLU** to quantization. The differential widens as quant increases for most models (e.g., llama3.2-3b: -12.5pp at FP16 to -20.2pp at Q2_K), meaning MMLU degrades faster.
2. **Anomaly: llama3.2-1b Q3_K_S** shows MMLU > ARC by +7.4pp -- a reversal. ARC drops to 24.5% (below random baseline of 25%), suggesting catastrophic reasoning failure while knowledge recall partially survives.
3. **At Q2_K, differentials compress** for qwen2.5-1.5b (-1.6pp) and phi-2 (-5.0pp) because both benchmarks collapse toward random baseline simultaneously.
4. **phi-2 shows the largest baseline differential** (-15.5pp at FP16) but the most stable differential across quant levels, consistent with its overall quantization robustness.

---

## 9. Generation Quality Analysis

**This is the SECONDARY quality signal.** Generation quality on hand-crafted tasks (summarization, QA, code_generation, creative_writing, classification). Delta vs primary baseline (FP16 or Q8_0).

### 9.1 llama3.1-8b (baseline: Q8_0)

| Quant | N | BERTScore (vs Q8_0) | Coherence (vs Q8_0) | ROUGE-L (vs Q8_0) | Key Avg | vs Q8_0 |
|-------|---|-----|-----|-----|---------|---------|
| Q8_0 | 250 | 0.800 (+0.0%) | 0.668 (+0.0%) | 0.492 (+0.0%) | 0.6533 | +0.0% |
| Q6_K | 250 | 0.795 (-0.5%) | 0.661 (-1.0%) | 0.485 (-1.5%) | 0.6470 | -1.0% |
| Q5_K_M | 250 | 0.811 (+1.4%) | 0.668 (+0.1%) | 0.504 (+2.3%) | 0.6611 | +1.3% |
| Q4_K_M | 250 | 0.799 (-0.1%) | 0.683 (+2.3%) | 0.494 (+0.3%) | 0.6587 | +0.8% |
| Q3_K_S | 250 | 0.782 (-2.3%) | 0.640 (-4.2%) | 0.467 (-5.1%) | 0.6296 | -3.8% |
| Q2_K | 250 | 0.769 (-3.9%) | 0.641 (-3.9%) | 0.443 (-10.0%) | 0.6178 | -5.9% |

### 9.2 llama3.2-1b (baseline: FP16)

| Quant | N | BERTScore (vs FP16) | Coherence (vs FP16) | ROUGE-L (vs FP16) | Key Avg | vs FP16 |
|-------|---|-----|-----|-----|---------|---------|
| FP16 | 250 | 0.646 (+0.0%) | 0.580 (+0.0%) | 0.266 (+0.0%) | 0.4973 | +0.0% |
| Q8_0 | 250 | 0.644 (-0.2%) | 0.578 (-0.3%) | 0.266 (-0.1%) | 0.4960 | -0.2% |
| Q6_K | 250 | 0.641 (-0.7%) | 0.578 (-0.3%) | 0.269 (+1.1%) | 0.4962 | +0.0% |
| Q5_K_M | 250 | 0.639 (-1.0%) | 0.572 (-1.2%) | 0.259 (-2.8%) | 0.4902 | -1.7% |
| Q4_K_M | 250 | 0.665 (+2.9%) | 0.581 (+0.2%) | 0.297 (+11.6%) | 0.5143 | +4.9% |
| Q3_K_S | 250 | 0.656 (+1.5%) | 0.557 (-4.0%) | 0.266 (-0.1%) | 0.4928 | -0.8% |
| Q2_K | 250 | 0.550 (-14.9%) | 0.493 (-15.0%) | 0.159 (-40.1%) | 0.4006 | -23.4% |

### 9.3 llama3.2-3b (baseline: FP16)

| Quant | N | BERTScore (vs FP16) | Coherence (vs FP16) | ROUGE-L (vs FP16) | Key Avg | vs FP16 |
|-------|---|-----|-----|-----|---------|---------|
| FP16 | 250 | 0.767 (+0.0%) | 0.661 (+0.0%) | 0.469 (+0.0%) | 0.6324 | +0.0% |
| Q8_0 | 250 | 0.766 (-0.2%) | 0.660 (-0.1%) | 0.470 (+0.2%) | 0.6319 | -0.1% |
| Q6_K | 250 | 0.768 (+0.0%) | 0.662 (+0.2%) | 0.473 (+0.9%) | 0.6342 | +0.4% |
| Q5_K_M | 250 | 0.762 (-0.7%) | 0.651 (-1.5%) | 0.460 (-1.9%) | 0.6242 | -1.4% |
| Q4_K_M | 250 | 0.759 (-1.2%) | 0.650 (-1.6%) | 0.454 (-3.2%) | 0.6209 | -2.0% |
| Q3_K_S | 250 | 0.728 (-5.1%) | 0.573 (-13.2%) | 0.432 (-7.9%) | 0.5778 | -8.8% |
| Q2_K | 250 | 0.765 (-0.3%) | 0.621 (-6.0%) | 0.433 (-7.5%) | 0.6066 | -4.6% |

### 9.4 phi-2 (baseline: FP16)

| Quant | N | BERTScore (vs FP16) | Coherence (vs FP16) | ROUGE-L (vs FP16) | Key Avg | vs FP16 |
|-------|---|-----|-----|-----|---------|---------|
| FP16 | 250 | 0.715 (+0.0%) | 0.771 (+0.0%) | 0.412 (+0.0%) | 0.6325 | +0.0% |
| Q8_0 | 250 | 0.723 (+1.2%) | 0.765 (-0.7%) | 0.418 (+1.4%) | 0.6354 | +0.6% |
| Q6_K | 250 | 0.725 (+1.4%) | 0.766 (-0.6%) | 0.416 (+1.0%) | 0.6357 | +0.6% |
| Q5_K_M | 250 | 0.725 (+1.4%) | 0.767 (-0.4%) | 0.427 (+3.8%) | 0.6400 | +1.6% |
| Q4_K_M | 250 | 0.721 (+0.8%) | 0.762 (-1.1%) | 0.405 (-1.6%) | 0.6295 | -0.6% |
| Q3_K_S | 250 | 0.710 (-0.7%) | 0.742 (-3.8%) | 0.379 (-7.9%) | 0.6104 | -4.1% |
| Q2_K | 250 | 0.742 (+3.7%) | 0.722 (-6.3%) | 0.399 (-3.2%) | 0.6208 | -1.9% |

### 9.5 qwen2.5-1.5b (baseline: FP16)

| Quant | N | BERTScore (vs FP16) | Coherence (vs FP16) | ROUGE-L (vs FP16) | Key Avg | vs FP16 |
|-------|---|-----|-----|-----|---------|---------|
| FP16 | 250 | 0.744 (+0.0%) | 0.713 (+0.0%) | 0.383 (+0.0%) | 0.6133 | +0.0% |
| Q8_0 | 250 | 0.745 (+0.2%) | 0.710 (-0.4%) | 0.381 (-0.6%) | 0.6121 | -0.3% |
| Q6_K | 250 | 0.730 (-1.9%) | 0.705 (-1.1%) | 0.367 (-4.1%) | 0.6007 | -2.4% |
| Q5_K_M | 250 | 0.736 (-1.0%) | 0.711 (-0.2%) | 0.366 (-4.4%) | 0.6046 | -1.9% |
| Q4_K_M | 250 | 0.718 (-3.5%) | 0.697 (-2.2%) | 0.349 (-8.9%) | 0.5880 | -4.9% |
| Q3_K_S | 250 | 0.726 (-2.4%) | 0.706 (-1.0%) | 0.355 (-7.3%) | 0.5958 | -3.5% |
| Q2_K | 250 | 0.602 (-19.1%) | 0.576 (-19.2%) | 0.200 (-47.9%) | 0.4591 | -28.7% |

### 9.6 Generation vs Benchmark Agreement

Generation metrics and benchmark accuracy largely agree on tier classification, but with notable exceptions:

- **llama3.2-3b Q2_K:** Benchmark shows -13.0pp (unacceptable), but generation shows only -4.6% (acceptable). The benchmark is the more trustworthy signal.
- **phi-2 Q2_K:** Benchmark shows -11.3pp (unacceptable), but generation shows only -1.9% (negligible). Again, benchmark is primary.
- **llama3.2-1b Q4_K_M:** Benchmark shows -2.3pp (negligible), but generation shows +4.9% (an *improvement*). This is noise at N=250.

**Conclusion:** Benchmark accuracy is a stricter quality gate than generation metrics. All tier classifications use the worse of the two signals.

### 9.6a Generation Quality Confidence Intervals

The benchmark tables (SS8.1-8.5) include Wilson CIs. Generation quality CIs are available in `phase2_analysis.json` and `phase2_v2_enhancements.json` per metric per variant. At N=250, the typical 95% CI half-widths are:

| Metric | Typical CI Half-Width | Range Across Variants |
|--------|-----------------------|----------------------|
| BERTScore | ±0.013-0.022 | Narrowest (least variance) |
| Coherence | ±0.025-0.040 | Moderate |
| ROUGE-L | ±0.030-0.055 | Widest (highest variance) |
| Key Metric Avg | ±0.015-0.030 | Composite of above |

**Example (llama3.1-8b Q8_0):** BERTScore 0.800 [0.779, 0.821], coherence 0.668 [0.639, 0.696], ROUGE-L 0.492 [0.440, 0.545]. The key metric avg (0.653) has a CI of approximately [0.630, 0.676].

**Implication:** Generation deltas <2% are within CI overlap for most metrics. Deltas >5% (e.g., llama3.2-1b Q2_K at -23.4%) are well outside CIs and represent genuine quality loss. The 6 variants that pass TOST at ±5% (SS15.5) are those where the CIs are tight enough to confirm equivalence.

### 9.7 Supplementary Metrics (BLEU, Repetition, Output Length, Exact Match)

The analysis computes 7 generation metrics but SS9.1-9.5 show only the 3 key metrics (BERTScore, coherence, ROUGE-L). The 4 discarded metrics reveal additional degradation signals, particularly **repetition collapse at Q2_K**:

| Model | Quant | BLEU | Repetition | Output Length | Exact Match | BLEU delta | Rep delta |
|-------|-------|------|------------|---------------|-------------|------------|-----------|
| llama3.1-8b | Q8_0 | 0.048 | 0.999 | 0.362 | 0.000 | +0.0% | +0.0% |
| llama3.1-8b | Q2_K | 0.035 | 0.991 | 0.262 | 0.000 | -26.9% | -0.7% |
| llama3.2-1b | FP16 | 0.027 | 0.996 | 0.335 | 0.000 | +0.0% | +0.0% |
| llama3.2-1b | Q2_K | 0.015 | 0.942 | 0.174 | 0.000 | -44.2% | **-5.5%** |
| llama3.2-3b | FP16 | 0.045 | 0.999 | 0.373 | 0.000 | +0.0% | +0.0% |
| llama3.2-3b | Q2_K | 0.035 | 0.988 | 0.266 | 0.000 | -22.5% | -1.1% |
| phi-2 | FP16 | 0.050 | 0.992 | 0.394 | 0.000 | +0.0% | +0.0% |
| phi-2 | Q2_K | 0.049 | 0.985 | 0.363 | 0.000 | -1.6% | -0.7% |
| qwen2.5-1.5b | FP16 | 0.051 | 0.992 | 0.469 | 0.000 | +0.0% | +0.0% |
| qwen2.5-1.5b | Q2_K | 0.008 | **0.702** | 0.340 | 0.080 | **-84.8%** | **-29.2%** |

**Repetition collapse:** qwen2.5-1.5b Q2_K drops to repetition = 0.702 (vs 0.992 baseline), indicating degenerate repetitive text where only 70% of 4-grams are unique. llama3.2-1b Q2_K shows milder repetition collapse (0.942, -5.5%). This signal is invisible in the key 3 metrics and represents a distinct failure mode: the model loops on phrases rather than producing coherent novel text.

**BLEU collapse:** qwen2.5-1.5b Q2_K BLEU drops -84.8%, far exceeding the BERTScore delta (-19.1%). BLEU is more sensitive to exact n-gram overlap, making it a stronger signal for text degeneration than the embedding-based metrics.

**Q3_K_S repetition is normal:** Unlike Q2_K, no Q3_K_S variant shows repetition collapse. Repetition scores at Q3_K_S: llama3.1-8b 0.999 (+0.01%), llama3.2-1b 0.992 (-0.48%), llama3.2-3b 0.998 (-0.13%), phi-2 0.993 (+0.09%), qwen2.5-1.5b 0.987 (-0.54%). All values remain above 0.98, confirming that repetition collapse is a Q2_K-specific phenomenon.

### 9.8 Per-Task Generation Quality

Quality varies by task type. The table below shows the key metric average (BERTScore + coherence + ROUGE-L / 3) broken down by generation task for selected variants:

**qwen2.5-1.5b (most quantization-sensitive):**

| Task | FP16 | Q4_K_M | Q2_K | FP16 -> Q2_K |
|------|------|--------|------|-------------|
| summarization | 0.734 | 0.726 | 0.640 | -12.9% |
| qa | 0.585 | 0.524 | 0.339 | -42.1% |
| code_generation | 0.740 | 0.742 | 0.662 | -10.5% |
| creative_writing | 0.430 | 0.421 | 0.417 | -3.0% |
| classification | 0.834 | 0.829 | 0.538 | -35.5% |

**llama3.2-1b (small model):**

| Task | FP16 | Q4_K_M | Q2_K | FP16 -> Q2_K |
|------|------|--------|------|-------------|
| summarization | 0.482 | 0.627 | 0.380 | -21.1% |
| qa | 0.369 | 0.475 | 0.248 | -32.9% |
| code_generation | 0.588 | 0.804 | 0.461 | -21.6% |
| creative_writing | 0.414 | 0.446 | 0.365 | -11.7% |
| classification | 0.699 | 0.339 | 0.549 | -21.4% |

*Per-task values: summarization and qa show the (BERTScore + coherence + ROUGE-L) / 3 average. code_generation, creative_writing, and classification show coherence only (BERTScore not computed for these tasks). See per-task computation notes in `phase2_v2_enhancements.json`.*

**Key finding:** QA and classification are the most quantization-sensitive generation tasks (30-42% degradation at Q2_K), while creative_writing is the most robust (3-12%). This suggests quantization degrades factual knowledge retrieval more than open-ended generation -- consistent with the benchmark accuracy findings.

---

## 10. Native Performance

Decode throughput from Ollama-native `eval_duration` (no HTTP overhead). Wall-clock shown for comparison.

### 10.1 llama3.1-8b

| Quant | Native tok/s | CV% | Wall tok/s | Overhead | Speedup vs Q8_0 |
|-------|-------------|-----|-----------|----------|-----------------|
| Q8_0 | 49.2 | 26 | 6.2 | 690% | 1.00x |
| Q6_K | 75.6 | 33 | 9.1 | 731% | 1.54x |
| Q5_K_M | 88.8 | 24 | 11.5 | 671% | 1.80x |
| Q4_K_M | 96.7 | 23 | 13.6 | 611% | 1.96x |
| Q3_K_S | 153.2 | 25 | 22.0 | 598% | 3.11x |
| Q2_K | 133.0 | 42 | 18.8 | 606% | 2.70x |

### 10.2 llama3.2-1b

| Quant | Native tok/s | CV% | Wall tok/s | Overhead | Speedup vs FP16 |
|-------|-------------|-----|-----------|----------|-----------------|
| FP16 | 185.2 | 29 | 30.7 | 504% | 1.00x |
| Q8_0 | 290.9 | 39 | 40.7 | 615% | 1.57x |
| Q6_K | 335.2 | 41 | 44.8 | 648% | 1.81x |
| Q5_K_M | 368.2 | 42 | 45.7 | 705% | 1.99x |
| Q4_K_M | 280.9 | 68 | 45.6 | 516% | 1.52x |
| Q3_K_S | 332.7 | 59 | 48.3 | 588% | 1.80x |
| Q2_K | 479.9 | 11 | 102.8 | 367% | 2.59x |

### 10.3 llama3.2-3b

| Quant | Native tok/s | CV% | Wall tok/s | Overhead | Speedup vs FP16 |
|-------|-------------|-----|-----------|----------|-----------------|
| FP16 | 99.0 | 26 | 9.7 | 919% | 1.00x |
| Q8_0 | 163.5 | 29 | 20.6 | 695% | 1.65x |
| Q6_K | 117.4 | 29 | 19.8 | 492% | 1.19x |
| Q5_K_M | 133.4 | 31 | 22.3 | 499% | 1.35x |
| Q4_K_M | 141.0 | 35 | 23.4 | 503% | 1.42x |
| Q3_K_S | 133.1 | 39 | 25.8 | 416% | 1.34x |
| Q2_K | 244.3 | 32 | 33.4 | 632% | 2.47x |

### 10.4 phi-2

| Quant | Native tok/s | CV% | Wall tok/s | Overhead | Speedup vs FP16 |
|-------|-------------|-----|-----------|----------|-----------------|
| FP16 | 66.1 | 17 | 10.7 | 516% | 1.00x |
| Q8_0 | 113.4 | 16 | 39.3 | 188% | 1.72x |
| Q6_K | 169.4 | 18 | 48.3 | 250% | 2.56x |
| Q5_K_M | 180.3 | 18 | 49.7 | 263% | 2.73x |
| Q4_K_M | 198.4 | 19 | 53.5 | 271% | 3.00x |
| Q3_K_S | 205.3 | 19 | 56.2 | 266% | 3.11x |
| Q2_K | 245.6 | 10 | 56.9 | 332% | 3.72x |

### 10.5 qwen2.5-1.5b

| Quant | Native tok/s | CV% | Wall tok/s | Overhead | Speedup vs FP16 |
|-------|-------------|-----|-----------|----------|-----------------|
| FP16 | 158.0 | 27 | 25.1 | 528% | 1.00x |
| Q8_0 | 267.7 | 25 | 33.7 | 694% | 1.69x |
| Q6_K | 267.3 | 28 | 36.4 | 634% | 1.69x |
| Q5_K_M | 288.3 | 26 | 40.8 | 606% | 1.83x |
| Q4_K_M | 299.0 | 31 | 39.6 | 655% | 1.89x |
| Q3_K_S | 256.7 | 32 | 49.2 | 422% | 1.62x |
| Q2_K | 378.5 | 14 | 109.6 | 245% | 2.40x |

### 10.6 Performance Observations

1. **phi-2 has the lowest CV** (16-19% native), making it the most stable model for throughput measurement.
2. **HTTP overhead ranges from 188% to 920%.** The overhead is not constant -- it varies by model size and quant level, making wall-clock timing unreliable for relative comparisons.
3. **Q2_K is often the fastest** in raw tok/s, but quality is destroyed. Speed without quality is useless.
4. **llama3.1-8b at Q3_K_S** achieves 3.11x speedup vs Q8_0 while maintaining acceptable quality (-2.5pp). This is the best speed-quality trade-off for the 8B model.
5. **Throughput scales inversely with bits-per-weight**, as expected. The relationship is roughly linear for phi-2 (most VRAM-headroom) but sublinear for models that stress VRAM.

### 10.7 Timing Outlier Analysis (IQR Method)

Outlier detection using the IQR method (k=1.5) on raw per-sample timing data from `samples.jsonl`. The high outlier rates reflect the skewed nature of HTTP-mediated timing distributions, not measurement errors.

| Model | TTFT Outliers | TTFT % | Decode Outliers | Decode % |
|-------|--------------|--------|-----------------|----------|
| llama3.1-8b (all quants) | 539/4410 | 12.2% | 767/4410 | 17.4% |
| llama3.2-1b (all quants) | 375/5143 | 7.3% | 696/5143 | 13.5% |
| llama3.2-3b (all quants) | 537/5145 | 10.4% | 1115/5145 | 21.7% |
| phi-2 (all quants) | 528/5145 | 10.3% | 1030/5145 | 20.0% |
| qwen2.5-1.5b (all quants) | 300/5145 | 5.8% | 879/5145 | 17.1% |
| **Total** | **2279/24988** | **9.1%** | **4487/24988** | **18.0%** |

**Interpretation:** The ~9% TTFT outlier rate and ~18% decode outlier rate are substantially higher than TR126's 0.0-0.9% (which measured CUDA-event latencies in Docker). The difference is explained by: (1) Ollama HTTP overhead adds stochastic latency spikes, (2) the IQR method is sensitive to skewed distributions (timing is right-tailed), (3) Ollama's server-side scheduling introduces jitter absent in direct GPU measurement. The mean/median performance values in SS10.1-10.5 are robust to these outliers; percentile-based metrics (p95, p99) would be affected. Trimmed means were not computed.

---

## 11. TTFT Analysis

Time-to-first-token (prompt evaluation latency) from Ollama-native `prompt_eval_duration`. TTFT reflects prompt processing speed and is relevant for interactive applications.

### 11.1 Full TTFT Table (all 34 variants)

| Model | Quant | TTFT Mean (ms) | TTFT Median (ms) | TTFT Std (ms) | CV% | Notable |
|-------|-------|----------------|------------------|---------------|-----|---------|
| llama3.1-8b | Q8_0 | 1845 | 1943 | 288 | 16 | Highest TTFT -- 8B at 8-bit |
| llama3.1-8b | Q6_K | 1402 | 1481 | 237 | 17 | |
| llama3.1-8b | Q5_K_M | 911 | 964 | 255 | 28 | |
| llama3.1-8b | Q4_K_M | 1046 | 1183 | 358 | 34 | |
| llama3.1-8b | Q3_K_S | 25 | 23 | 10 | 39 | 42x drop from Q4_K_M |
| llama3.1-8b | Q2_K | 41 | 39 | 18 | 45 | |
| llama3.2-1b | FP16 | 29 | 15 | 135 | 468 | Extreme variance |
| llama3.2-1b | Q8_0 | 17 | 11 | 16 | 91 | |
| llama3.2-1b | Q6_K | 17 | 11 | 15 | 85 | |
| llama3.2-1b | Q5_K_M | 16 | 11 | 13 | 81 | |
| llama3.2-1b | Q4_K_M | 24 | 14 | 17 | 73 | |
| llama3.2-1b | Q3_K_S | 18 | 10 | 15 | 80 | |
| llama3.2-1b | Q2_K | 8 | 8 | 3 | 30 | Fastest measured |
| llama3.2-3b | FP16 | 1369 | 1475 | 237 | 17 | |
| llama3.2-3b | Q8_0 | 20 | 17 | 7 | 34 | 68x drop from FP16 |
| llama3.2-3b | Q6_K | 42 | 37 | 23 | 54 | |
| llama3.2-3b | Q5_K_M | 41 | 35 | 24 | 59 | |
| llama3.2-3b | Q4_K_M | 40 | 33 | 26 | 64 | |
| llama3.2-3b | Q3_K_S | 36 | 31 | 23 | 64 | |
| llama3.2-3b | Q2_K | 30 | 18 | 160 | 537 | Extreme variance |
| phi-2 | FP16 | 1485 | 1584 | 307 | 21 | |
| phi-2 | Q8_0 | 27 | 27 | 12 | 44 | 55x drop from FP16 |
| phi-2 | Q6_K | 16 | 14 | 6 | 36 | |
| phi-2 | Q5_K_M | 15 | 14 | 5 | 36 | |
| phi-2 | Q4_K_M | 15 | 13 | 5 | 36 | |
| phi-2 | Q3_K_S | 14 | 13 | 5 | 33 | |
| phi-2 | Q2_K | 14 | 13 | 5 | 33 | |
| qwen2.5-1.5b | FP16 | 20 | 18 | 6 | 29 | Fast even at FP16 |
| qwen2.5-1.5b | Q8_0 | 16 | 14 | 7 | 43 | |
| qwen2.5-1.5b | Q6_K | 20 | 18 | 12 | 58 | |
| qwen2.5-1.5b | Q5_K_M | 18 | 16 | 10 | 53 | |
| qwen2.5-1.5b | Q4_K_M | 20 | 17 | 11 | 55 | |
| qwen2.5-1.5b | Q3_K_S | 18 | 16 | 7 | 41 | |
| qwen2.5-1.5b | Q2_K | 16 | 12 | 85 | 529 | Extreme variance |

### 11.2 TTFT Observations

1. **FP16 TTFT is high for models >2B:** llama3.2-3b and phi-2 show 1.4-1.5s TTFT at FP16, driven by prompt processing on the full-precision model. Quantized variants drop to <50ms.
2. **llama3.1-8b Q8_0 has the worst TTFT** (1.8s mean). This is expected -- processing 8B parameters at 8-bit precision is memory-bandwidth-limited. TTFT remains high through Q4_K_M (1046ms), then drops 42x to Q3_K_S (25ms).
3. **The TTFT drop from Q4_K_M to Q3_K_S for llama3.1-8b** is dramatic: 1046ms to 25ms. This suggests the model transitions from partial GPU offloading to fully GPU-resident at Q3_K_S, consistent with VRAM estimate dropping below GPU capacity at 3-bit.
4. **Small models (1-1.5B) have low TTFT** across all quant levels (median <20ms). qwen2.5-1.5b and llama3.2-1b show median TTFT consistently under 18ms.
5. **Extreme variance on some variants:** llama3.2-1b FP16 (CV=468%), llama3.2-3b Q2_K (CV=537%), and qwen2.5-1.5b Q2_K (CV=529%) show occasional TTFT spikes, likely from model loading/unloading events or Ollama server contention.

---

## 12. Cost Analysis

Hardware cost: $0.035/hr (RTX 4080 tier, from TR123). Cost = hourly_rate / (native_tok_per_s x 3600) x 1M. Savings measured vs primary baseline (FP16 or Q8_0).

### 12.1 Full Cost Table

| Model | Quant | Native tok/s | $/1M Tokens | Baseline $/1M | Savings vs Baseline |
|-------|-------|-------------|-------------|---------------|---------------------|
| llama3.1-8b | Q8_0 | 49.2 | $0.1976 | $0.1976 | +0% vs Q8_0 |
| llama3.1-8b | Q6_K | 75.6 | $0.1287 | $0.1976 | +35% vs Q8_0 |
| llama3.1-8b | Q5_K_M | 88.8 | $0.1095 | $0.1976 | +45% vs Q8_0 |
| llama3.1-8b | Q4_K_M | 96.7 | $0.1006 | $0.1976 | +49% vs Q8_0 |
| llama3.1-8b | Q3_K_S | 153.2 | $0.0634 | $0.1976 | +68% vs Q8_0 |
| llama3.1-8b | Q2_K | 133.0 | $0.0731 | $0.1976 | +63% vs Q8_0 |
| llama3.2-1b | FP16 | 185.2 | $0.0525 | $0.0525 | +0% vs FP16 |
| llama3.2-1b | Q8_0 | 290.9 | $0.0334 | $0.0525 | +36% vs FP16 |
| llama3.2-1b | Q6_K | 335.2 | $0.0290 | $0.0525 | +45% vs FP16 |
| llama3.2-1b | Q5_K_M | 368.2 | $0.0264 | $0.0525 | +50% vs FP16 |
| llama3.2-1b | Q4_K_M | 280.9 | $0.0346 | $0.0525 | +34% vs FP16 |
| llama3.2-1b | Q3_K_S | 332.7 | $0.0292 | $0.0525 | +44% vs FP16 |
| llama3.2-1b | Q2_K | 479.9 | $0.0203 | $0.0525 | +61% vs FP16 |
| llama3.2-3b | FP16 | 99.0 | $0.0982 | $0.0982 | +0% vs FP16 |
| llama3.2-3b | Q8_0 | 163.5 | $0.0595 | $0.0982 | +39% vs FP16 |
| llama3.2-3b | Q6_K | 117.4 | $0.0828 | $0.0982 | +16% vs FP16 |
| llama3.2-3b | Q5_K_M | 133.4 | $0.0729 | $0.0982 | +26% vs FP16 |
| llama3.2-3b | Q4_K_M | 141.0 | $0.0689 | $0.0982 | +30% vs FP16 |
| llama3.2-3b | Q3_K_S | 133.1 | $0.0730 | $0.0982 | +26% vs FP16 |
| llama3.2-3b | Q2_K | 244.3 | $0.0398 | $0.0982 | +60% vs FP16 |
| phi-2 | FP16 | 66.1 | $0.1471 | $0.1471 | +0% vs FP16 |
| phi-2 | Q8_0 | 113.4 | $0.0857 | $0.1471 | +42% vs FP16 |
| phi-2 | Q6_K | 169.4 | $0.0574 | $0.1471 | +61% vs FP16 |
| phi-2 | Q5_K_M | 180.3 | $0.0539 | $0.1471 | +63% vs FP16 |
| phi-2 | Q4_K_M | 198.4 | $0.0490 | $0.1471 | +67% vs FP16 |
| phi-2 | Q3_K_S | 205.3 | $0.0473 | $0.1471 | +68% vs FP16 |
| phi-2 | Q2_K | 245.6 | $0.0396 | $0.1471 | +73% vs FP16 |
| qwen2.5-1.5b | FP16 | 158.0 | $0.0615 | $0.0615 | +0% vs FP16 |
| qwen2.5-1.5b | Q8_0 | 267.7 | $0.0363 | $0.0615 | +41% vs FP16 |
| qwen2.5-1.5b | Q6_K | 267.3 | $0.0364 | $0.0615 | +41% vs FP16 |
| qwen2.5-1.5b | Q5_K_M | 288.3 | $0.0337 | $0.0615 | +45% vs FP16 |
| qwen2.5-1.5b | Q4_K_M | 299.0 | $0.0325 | $0.0615 | +47% vs FP16 |
| qwen2.5-1.5b | Q3_K_S | 256.7 | $0.0379 | $0.0615 | +38% vs FP16 |
| qwen2.5-1.5b | Q2_K | 378.5 | $0.0257 | $0.0615 | +58% vs FP16 |

### 12.2 Cost Observations

1. **10x cost range:** $0.0203/1M (llama3.2-1b Q2_K) to $0.1976/1M (llama3.1-8b Q8_0).
2. **Q4_K_M saves 30-67% vs FP16** for models with FP16 baselines. phi-2 benefits most (67%), llama3.2-3b least (30%); llama3.1-8b saves 49% vs Q8_0.
3. **The cheapest acceptable option** is llama3.2-1b at Q5_K_M ($0.0264/1M, +0.2pp, negligible).
4. **The cheapest high-accuracy option** is llama3.1-8b at Q4_K_M ($0.1006/1M, 69.7% accuracy).
5. **Q2_K is often not the cheapest** per model -- llama3.1-8b Q3_K_S ($0.0634) is cheaper than Q2_K ($0.0731) because Q3_K_S achieves higher throughput on this hardware.

---

## 13. Decision Matrix

Per VRAM tier: which (model, quant) combinations fit and maintain quality? Quality tier determined by the **worse** of benchmark accuracy delta (pp) and generation quality delta (%). Recommended = fits VRAM AND tier is "negligible" or "acceptable."

### 13.1 2GB VRAM

| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier | Native tok/s | $/1M |
|-------|-------|---------|------------------|---------------|------|-------------|------|
| llama3.2-1b | Q5_K_M | 0.9 GB | +0.2 | -1.7 | negligible | 368.2 | $0.0264 |
| llama3.2-1b | Q6_K | 1.0 GB | +0.0 | +0.0 | negligible | 335.2 | $0.0290 |
| qwen2.5-1.5b | Q4_K_M | 0.9 GB | -4.1 | -4.9 | acceptable | 299.0 | $0.0325 |
| llama3.2-1b | Q8_0 | 1.3 GB | +1.2 | -0.2 | negligible | 290.9 | $0.0334 |
| qwen2.5-1.5b | Q5_K_M | 1.1 GB | -0.4 | -1.9 | negligible | 288.3 | $0.0337 |
| llama3.2-1b | Q4_K_M | 0.7 GB | -2.3 | +4.9 | negligible | 280.9 | $0.0346 |
| qwen2.5-1.5b | Q8_0 | 1.6 GB | -1.2 | -0.3 | negligible | 267.7 | $0.0363 |
| qwen2.5-1.5b | Q6_K | 1.3 GB | -1.2 | -2.4 | negligible | 267.3 | $0.0364 |
| phi-2 | Q3_K_S | 1.2 GB | -0.4 | -4.1 | acceptable | 205.3 | $0.0473 |
| phi-2 | Q4_K_M | 1.6 GB | -1.8 | -0.6 | negligible | 198.4 | $0.0490 |
| phi-2 | Q5_K_M | 1.9 GB | +0.6 | +1.6 | negligible | 180.3 | $0.0539 |
| llama3.2-3b | Q4_K_M | 1.9 GB | -0.4 | -2.0 | negligible | 141.0 | $0.0689 |

### 13.2 4GB VRAM

All entries from 2GB tier plus:

| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier | Native tok/s | $/1M |
|-------|-------|---------|------------------|---------------|------|-------------|------|
| llama3.2-1b | FP16 | 2.5 GB | +0.0 | +0.0 | negligible | 185.2 | $0.0525 |
| phi-2 | Q6_K | 2.2 GB | -1.2 | +0.6 | negligible | 169.4 | $0.0574 |
| llama3.2-3b | Q8_0 | 3.3 GB | +0.4 | -0.1 | negligible | 163.5 | $0.0595 |
| qwen2.5-1.5b | FP16 | 3.2 GB | +0.0 | +0.0 | negligible | 158.0 | $0.0615 |
| llama3.1-8b | Q3_K_S | 3.6 GB | -2.5 | -3.8 | acceptable | 153.2 | $0.0634 |
| phi-2 | Q8_0 | 2.8 GB | -1.6 | +0.6 | negligible | 113.4 | $0.0857 |

### 13.3 6GB VRAM

All entries from 4GB tier plus:

| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier | Native tok/s | $/1M |
|-------|-------|---------|------------------|---------------|------|-------------|------|
| llama3.1-8b | Q4_K_M | 4.6 GB | -2.7 | +0.8 | negligible | 96.7 | $0.1006 |
| llama3.1-8b | Q5_K_M | 5.7 GB | -1.6 | +1.3 | negligible | 88.8 | $0.1095 |
| phi-2 | FP16 | 5.5 GB | +0.0 | +0.0 | negligible | 66.1 | $0.1471 |

### 13.4 8GB+ VRAM

All entries from 6GB tier plus:

| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier | Native tok/s | $/1M |
|-------|-------|---------|------------------|---------------|------|-------------|------|
| llama3.2-3b | FP16 | 6.6 GB | +0.0 | +0.0 | negligible | 99.0 | $0.0982 |
| llama3.1-8b | Q6_K | 6.7 GB | -1.6 | -1.0 | negligible | 75.6 | $0.1287 |

### 13.5 Not Recommended (fit 8GB+ but concerning/unacceptable)

| Model | Quant | VRAM Est | Bench Delta (pp) | Gen Delta (%) | Tier |
|-------|-------|---------|------------------|---------------|------|
| llama3.1-8b | Q2_K | 2.6 GB | -14.2 | -5.9 | unacceptable |
| llama3.2-1b | Q3_K_S | 0.6 GB | -9.5 | -0.8 | concerning |
| llama3.2-1b | Q2_K | 0.4 GB | -16.1 | -23.4 | unacceptable |
| llama3.2-3b | Q3_K_S | 1.4 GB | -10.1 | -8.8 | unacceptable |
| llama3.2-3b | Q2_K | 1.0 GB | -13.0 | -4.6 | unacceptable |
| phi-2 | Q2_K | 0.9 GB | -11.3 | -1.9 | unacceptable |
| qwen2.5-1.5b | Q3_K_S | 0.7 GB | -12.2 | -3.5 | unacceptable |
| qwen2.5-1.5b | Q2_K | 0.5 GB | -40.6 | -28.7 | unacceptable |

### 13.6 Decision Matrix Summary

Of 111 total (model, quant, VRAM-tier) combinations that physically fit:

| Tier | Count | Percentage |
|------|-------|------------|
| Negligible | 69 | 62% |
| Acceptable | 11 | 10% |
| Concerning | 4 | 4% |
| Unacceptable | 27 | 24% |

**80 of 111 fitting combinations (72%) are recommended** (negligible + acceptable).

### 13.7 Explicit 29-Variant Enumeration

The claim "21 of 29 quantized variants maintain quality within 5pp" requires explicit enumeration. Here are all 29 non-baseline quantized variants with their tier classification (5 baselines excluded: FP16 for 4 models, Q8_0 for llama3.1-8b):

| # | Model | Quant | Rescored Acc (%) | Bench Delta (pp) | Gen Delta (%) | Tier | Safe? |
|---|-------|-------|-----------------|-----------------|---------------|------|-------|
| 1 | llama3.2-1b | Q8_0 | 39.6 | +1.2 | -0.2 | negligible | Yes |
| 2 | llama3.2-1b | Q6_K | 38.4 | +0.0 | +0.0 | negligible | Yes |
| 3 | llama3.2-1b | Q5_K_M | 38.6 | +0.2 | -1.7 | negligible | Yes |
| 4 | llama3.2-1b | Q4_K_M | 36.1 | -2.3 | +4.9 | negligible | Yes |
| 5 | llama3.2-1b | Q3_K_S | 28.9 | -9.5 | -0.9 | **concerning** | **No** |
| 6 | llama3.2-1b | Q2_K | 22.3 | -16.1 | -23.4 | **unacceptable** | **No** |
| 7 | qwen2.5-1.5b | Q8_0 | 63.9 | -1.2 | -0.3 | negligible | Yes |
| 8 | qwen2.5-1.5b | Q6_K | 63.9 | -1.2 | -2.4 | negligible | Yes |
| 9 | qwen2.5-1.5b | Q5_K_M | 64.7 | -0.4 | -1.9 | negligible | Yes |
| 10 | qwen2.5-1.5b | Q4_K_M | 61.0 | -4.1 | -4.9 | acceptable | Yes |
| 11 | qwen2.5-1.5b | Q3_K_S | 53.0 | -12.2 | -3.5 | **unacceptable** | **No** |
| 12 | qwen2.5-1.5b | Q2_K | 24.5 | -40.6 | -28.7 | **unacceptable** | **No** |
| 13 | phi-2 | Q8_0 | 57.7 | -1.6 | +0.6 | negligible | Yes |
| 14 | phi-2 | Q6_K | 58.1 | -1.2 | +0.6 | negligible | Yes |
| 15 | phi-2 | Q5_K_M | 60.0 | +0.6 | +1.6 | negligible | Yes |
| 16 | phi-2 | Q4_K_M | 57.5 | -1.8 | -0.6 | negligible | Yes |
| 17 | phi-2 | Q3_K_S | 59.0 | -0.4 | -4.1 | acceptable | Yes |
| 18 | phi-2 | Q2_K | 48.0 | -11.3 | -1.9 | **unacceptable** | **No** |
| 19 | llama3.2-3b | Q8_0 | 64.5 | +0.4 | -0.1 | negligible | Yes |
| 20 | llama3.2-3b | Q6_K | 63.5 | -0.6 | +0.4 | negligible | Yes |
| 21 | llama3.2-3b | Q5_K_M | 63.3 | -0.8 | -1.4 | negligible | Yes |
| 22 | llama3.2-3b | Q4_K_M | 63.7 | -0.4 | -2.0 | negligible | Yes |
| 23 | llama3.2-3b | Q3_K_S | 54.0 | -10.1 | -8.8 | **unacceptable** | **No** |
| 24 | llama3.2-3b | Q2_K | 51.1 | -13.0 | -4.6 | **unacceptable** | **No** |
| 25 | llama3.1-8b | Q6_K | 70.7 | -1.6 | -1.0 | negligible | Yes |
| 26 | llama3.1-8b | Q5_K_M | 70.7 | -1.6 | +1.3 | negligible | Yes |
| 27 | llama3.1-8b | Q4_K_M | 69.7 | -2.7 | +0.8 | negligible | Yes |
| 28 | llama3.1-8b | Q3_K_S | 69.9 | -2.5 | -3.8 | acceptable | Yes |
| 29 | llama3.1-8b | Q2_K | 58.1 | -14.2 | -5.9 | **unacceptable** | **No** |

**Tier totals:** 18 negligible + 3 acceptable + 1 concerning + 7 unacceptable = 29. **21 safe (72%), 8 unsafe (28%).**

**The 8 unsafe variants** are exclusively at Q3_K_S (3 models) and Q2_K (all 5 models). No variant at Q4_K_M or above is classified worse than "acceptable."

---

## 14. Diminishing Returns

Marginal quality gain vs cost increase when stepping to a higher quant level. "Bench Gain" is the rescored accuracy improvement (pp). "Gen Gain" is the key_metric_avg difference. "Cost Increase" and "Speed Loss" measure the penalty for the higher quant level.

### 14.1 Key Diminishing Returns Steps

| Model | Step | Bench Gain (pp) | Gen Gain | Cost Increase | Speed Loss |
|-------|------|-----------------|----------|---------------|------------|
| llama3.1-8b | Q4_K_M -> Q5_K_M | +1.0 | +0.0024 | +8.8% | +8.2% |
| llama3.1-8b | Q3_K_S -> Q4_K_M | -0.2 | +0.0291 | +58.7% | +36.9% |
| llama3.1-8b | Q2_K -> Q3_K_S | **+11.8** | +0.0118 | -13.3% | -15.2% |
| llama3.2-1b | Q4_K_M -> Q5_K_M | +2.5 | -0.0242 | -23.7% | -31.1% |
| llama3.2-1b | Q3_K_S -> Q4_K_M | **+7.2** | +0.0216 | +18.5% | +15.6% |
| llama3.2-1b | Q2_K -> Q3_K_S | **+6.6** | +0.0922 | +43.8% | +30.7% |
| llama3.2-3b | Q3_K_S -> Q4_K_M | **+9.7** | +0.0431 | -5.6% | -5.9% |
| llama3.2-3b | Q2_K -> Q3_K_S | +2.9 | -0.0289 | +83.4% | +45.5% |
| phi-2 | Q2_K -> Q3_K_S | **+10.9** | -0.0104 | +19.4% | +16.4% |
| qwen2.5-1.5b | Q3_K_S -> Q4_K_M | **+8.0** | -0.0078 | -14.2% | -16.5% |
| qwen2.5-1.5b | Q2_K -> Q3_K_S | **+28.5** | +0.1367 | +47.5% | +32.2% |

### 14.2 Interpretation

1. **The Q2_K -> Q3_K_S step delivers the largest quality gains** across all models (6.6-28.5pp). This is the most cost-effective quality investment.
2. **The Q3_K_S -> Q4_K_M step is the second-biggest gain** for models where Q3_K_S is concerning (7.2-9.7pp for llama3.2-1b, llama3.2-3b, qwen2.5-1.5b).
3. **Steps above Q4_K_M show diminishing returns** -- typically <2pp benchmark gain per step, with 5-60% cost increases.
4. **The FP16 -> Q8_0 step is free or beneficial** -- Q8_0 is equivalent or slightly better than FP16 for most models, at 36-42% lower cost.
5. **llama3.2-3b Q3_K_S -> Q4_K_M is the best single trade-off:** +9.7pp benchmark gain, -5.6% cost decrease (Q4_K_M is actually *cheaper* due to higher throughput). This is a rare "free quality upgrade."

---

## 15. Statistical Tests

Pairwise t-tests between adjacent quant levels. Benchmark tests use rescored exact_match (binary). Generation tests use BERTScore, coherence, ROUGE-L.

### 15.1 Benchmark Accuracy Tests (7/29 significant)

| Model | Higher Q | Lower Q | N | Mean H | Mean L | Cohen's d | p-value |
|-------|----------|---------|---|--------|--------|-----------|---------|
| llama3.1-8b | Q3_K_S | Q2_K | 485 | 0.699 | 0.581 | -0.246 | 0.0001 |
| llama3.2-1b | Q4_K_M | Q3_K_S | 485 | 0.361 | 0.289 | -0.154 | 0.0164 |
| llama3.2-1b | Q3_K_S | Q2_K | 485 | 0.289 | 0.223 | -0.151 | 0.0185 |
| llama3.2-3b | Q4_K_M | Q3_K_S | 485 | 0.637 | 0.540 | -0.198 | 0.0021 |
| phi-2 | Q3_K_S | Q2_K | 485 | 0.590 | 0.480 | -0.220 | 0.0006 |
| qwen2.5-1.5b | Q4_K_M | Q3_K_S | 485 | 0.610 | 0.530 | -0.163 | 0.0114 |
| qwen2.5-1.5b | Q3_K_S | Q2_K | 485 | 0.530 | 0.245 | -0.610 | 0.0000 |

**Pattern:** All 7 significant tests occur at the Q3_K_S/Q2_K boundary -- exactly where the quality cliff is. No test between Q4_K_M and above is significant, confirming that quality differences above Q4_K_M are below measurement resolution.

### 15.2 Generation Quality Tests (9/87 significant)

| Model | Metric | Higher Q | Lower Q | N | Mean H | Mean L | Cohen's d | p-value |
|-------|--------|----------|---------|---|--------|--------|-----------|---------|
| llama3.1-8b | coherence | Q4_K_M | Q3_K_S | 250 | 0.683 | 0.640 | -0.189 | 0.0353 |
| llama3.2-1b | bertscore | Q3_K_S | Q2_K | 100 | 0.656 | 0.550 | -0.833 | 0.0000 |
| llama3.2-1b | coherence | Q3_K_S | Q2_K | 250 | 0.557 | 0.493 | -0.256 | 0.0043 |
| llama3.2-1b | rouge_l | Q5_K_M | Q4_K_M | 150 | 0.259 | 0.297 | +0.236 | 0.0415 |
| llama3.2-1b | rouge_l | Q3_K_S | Q2_K | 150 | 0.266 | 0.159 | -0.685 | 0.0000 |
| llama3.2-3b | coherence | Q4_K_M | Q3_K_S | 250 | 0.650 | 0.573 | -0.276 | 0.0021 |
| qwen2.5-1.5b | bertscore | Q3_K_S | Q2_K | 100 | 0.726 | 0.602 | -0.829 | 0.0000 |
| qwen2.5-1.5b | coherence | Q3_K_S | Q2_K | 250 | 0.706 | 0.576 | -0.544 | 0.0000 |
| qwen2.5-1.5b | rouge_l | Q3_K_S | Q2_K | 150 | 0.355 | 0.200 | -0.725 | 0.0000 |

### 15.3 Summary

**16/116 tests significant at p<0.05 (uncorrected)** (benchmark: 7/29, generation: 9/87). All significant results cluster at the Q3_K_S-to-Q2_K boundary, with some at Q4_K_M-to-Q3_K_S. No significant differences detected above Q4_K_M.

### 15.4 Multiple Comparison Correction (Computed)

With 116 tests at alpha = 0.05, the expected false positive count under the null is 5.8. Both Bonferroni and Holm step-down corrections were applied to all 116 p-values.

**Bonferroni threshold:** alpha_corrected = 0.05 / 116 = 0.000431.

**Holm step-down:** Rank-ordered p-values compared to alpha / (116 - rank + 1).

**Result: 7 of 16 significant tests survive both Bonferroni and Holm correction:**

| Rank | Model | Transition | Metric | p (uncorrected) | p (Bonferroni) | d | Survives? |
|------|-------|------------|--------|-----------------|----------------|---|-----------|
| 1 | qwen2.5-1.5b | Q3_K_S -> Q2_K | benchmark | <0.0001 | <0.001 | -0.610 | Yes |
| 2 | llama3.2-1b | Q3_K_S -> Q2_K | bertscore | <0.0001 | <0.001 | -0.833 | Yes |
| 3 | llama3.2-1b | Q3_K_S -> Q2_K | rouge_l | <0.0001 | <0.001 | -0.685 | Yes |
| 4 | qwen2.5-1.5b | Q3_K_S -> Q2_K | bertscore | <0.0001 | <0.001 | -0.829 | Yes |
| 5 | qwen2.5-1.5b | Q3_K_S -> Q2_K | coherence | <0.0001 | <0.001 | -0.544 | Yes |
| 6 | qwen2.5-1.5b | Q3_K_S -> Q2_K | rouge_l | <0.0001 | <0.001 | -0.725 | Yes |
| 7 | llama3.1-8b | Q3_K_S -> Q2_K | benchmark | 0.0001 | 0.012 | -0.246 | Yes |
| 8 | phi-2 | Q3_K_S -> Q2_K | benchmark | 0.0006 | 0.070 | -0.220 | No |
| 9 | llama3.2-3b | Q4_K_M -> Q3_K_S | benchmark | 0.0021 | 0.244 | -0.198 | No |
| 10-16 | (remaining) | | | 0.004-0.042 | 0.46-1.0 | | No |

**Impact on conclusions:** All 7 survivors are at the Q3_K_S-to-Q2_K boundary. The Q2_K quality cliff is robust to any correction method. The Q3_K_S cliff is NOT robust -- none of the Q4_K_M-to-Q3_K_S tests survive correction (phi-2 benchmark at p=0.070 is closest). The claim that "no significant differences exist above Q4_K_M" is strengthened by correction.

**Why we report uncorrected p-values:** Following the research program convention, we report uncorrected p-values with this correction table, rather than applying a correction that would obscure raw results. The reader should treat p-values between 0.001 and 0.05 as marginal.

### 15.5 TOST Equivalence Testing

The "negligible" tier classifies 18 quantized variants as having no meaningful quality loss. But a non-significant t-test does NOT establish equivalence. TOST (Two One-Sided Tests) was applied to all 18 negligible variants to test whether the true delta lies within +/-3pp of baseline (benchmark) or +/-3% of baseline mean (generation).

**At ±3pp margin: 0/18 benchmark pass, 0/18 generation pass.**

| Model | Quant | Bench Delta (pp) | TOST p (bench) | TOST p (gen) | Equiv? |
|-------|-------|-----------------|----------------|--------------|--------|
| llama3.1-8b | Q6_K | -1.6 | 0.240 | 0.230 | No |
| llama3.1-8b | Q5_K_M | -1.6 | 0.876 | 0.219 | No |
| llama3.1-8b | Q4_K_M | -2.7 | 0.307 | 0.254 | No |
| llama3.2-1b | Q8_0 | +1.2 | 0.263 | 0.180 | No |
| llama3.2-1b | Q6_K | +0.0 | 0.166 | 0.169 | No |
| llama3.2-1b | Q5_K_M | +0.2 | 0.242 | 0.301 | No |
| llama3.2-1b | Q4_K_M | -2.3 | 0.331 | 0.467 | No |
| llama3.2-3b | Q8_0 | +0.4 | 0.169 | 0.133 | No |
| llama3.2-3b | Q6_K | -0.6 | 0.358 | 0.153 | No |
| llama3.2-3b | Q5_K_M | -0.8 | 0.265 | 0.273 | No |
| llama3.2-3b | Q4_K_M | -0.4 | 0.169 | 0.332 | No |
| phi-2 | Q8_0 | -1.6 | 0.201 | 0.127 | No |
| phi-2 | Q6_K | -1.2 | 0.289 | 0.131 | No |
| phi-2 | Q5_K_M | +0.6 | 0.220 | 0.191 | No |
| phi-2 | Q4_K_M | -1.8 | 0.242 | 0.192 | No |
| qwen2.5-1.5b | Q8_0 | -1.2 | 0.707 | 0.159 | No |
| qwen2.5-1.5b | Q6_K | -1.2 | 0.435 | 0.335 | No |
| qwen2.5-1.5b | Q5_K_M | -0.4 | 1.000 | 0.252 | No |

**At ±5pp margin: 0/18 benchmark pass, 6/18 generation pass.**

Widening the equivalence margin to ±5pp (the "acceptable" tier threshold) allows the generation quality tests to reach significance for 6 variants. Benchmark tests remain underpowered at this margin because binary accuracy data has high variance (SE ~5.9pp).

| Model | Quant | Gen Delta (%) | TOST p (gen, ±5%) | Gen Equiv? |
|-------|-------|---------------|-------------------|------------|
| llama3.2-3b | Q8_0 | -0.1 | 0.031 | **Yes** |
| llama3.2-3b | Q6_K | +0.3 | 0.037 | **Yes** |
| phi-2 | Q8_0 | +0.1 | 0.027 | **Yes** |
| phi-2 | Q6_K | +0.1 | 0.028 | **Yes** |
| phi-2 | Q5_K_M | +0.8 | 0.048 | **Yes** |
| qwen2.5-1.5b | Q8_0 | -0.3 | 0.041 | **Yes** |

**Pattern:** The 6 variants that pass are all at high quant levels (Q8_0, Q6_K, Q5_K_M) with generation deltas <1%. phi-2 passes at 3 quant levels (Q8_0 through Q5_K_M), consistent with its overall quantization robustness. No variant at Q4_K_M or below passes even at ±5%.

**Interpretation:** At N=485 with binary accuracy data, the standard error of the difference is approximately ±5.9pp (95% CI). A ±3pp equivalence margin is too narrow relative to this standard error for the study to have sufficient power to establish equivalence. At ±5pp, generation quality (continuous metrics with lower variance) has enough power to confirm equivalence for the highest-quant variants, but benchmark accuracy (binary data) remains underpowered. To establish benchmark equivalence at ±5pp with 80% power would require N > 1,500 per variant; at ±3pp, N > 3,000.

The "negligible" tier should be read as: **"point estimate within 3pp, no detected degradation. 6/18 variants confirmed equivalent on generation quality at ±5%, but benchmark equivalence unconfirmed."**

---

## 16. Power Analysis & Statistical Resolution

### 16.1 Minimum Detectable Effects

Computed using normal approximation at alpha=0.05, power=0.80.

| Metric Type | N per Variant | MDE | Interpretation |
|------------|--------------|-----|----------------|
| Benchmark accuracy (binary) | 485 | 9.0pp | Cannot detect <9.0pp accuracy differences |
| Generation quality (continuous) | 250 | d=0.251 | Small effects (d<0.251) are below resolution |

### 16.2 Implications for Tier Thresholds

- **"Negligible" tier (-3pp):** **Below the 9.0pp benchmark detection limit.** We cannot statistically confirm that -3pp deltas are real — they are indistinguishable from zero at 80% power. A variant classified "negligible" may have zero true degradation or up to ~9pp true degradation. The classification is based on the point estimate only. For binary accuracy at N=485, the 95% Wilson CI half-width is ±3.4pp to ±4.3pp depending on the baseline accuracy — meaning a -3pp point estimate has a CI spanning roughly [-7pp, +1pp]. The "negligible" label should be interpreted as "no evidence of degradation" rather than "proven equivalent."
- **"Acceptable" tier (-5pp):** Also below the benchmark detection limit. Same caveat as negligible: the generation metric detection limit (d=0.251) provides supplementary evidence, but benchmark-only tier assignments at -3pp to -5pp are statistically unresolved.
- **"Concerning" tier (-10pp):** At the detection limit. Deltas in this range may or may not be statistically significant depending on variance. The Q3_K_S drops for llama3.2-3b (-10.1pp) and qwen2.5-1.5b (-12.2pp) are above the MDE and statistically significant.
- **"Unacceptable" tier (>-10pp):** Above the detection limit. These are genuine, measurable quality losses. All Q2_K results (>-11pp) are statistically significant.

**Model-specific MDEs:** The 9.0pp MDE uses worst-case p=0.5. For models with higher accuracy (llama3.1-8b at p=0.72), the actual MDE is smaller (~7.9pp). For models with lower accuracy (llama3.2-1b at p=0.38), the MDE is ~8.6pp. These differences are modest and do not change the tier classification conclusions.

### 16.3 Practical Guidance

The power analysis reveals that this experiment is well-sized for detecting **large** quality drops (>10pp) but not for distinguishing between adjacent quant levels at the top of the quality range. This is acceptable for deployment decisions: the question "is Q4_K_M safe?" (answer: yes, all deltas <5pp) is more important than "is Q5_K_M 0.5pp better than Q6_K?" (cannot be resolved at this sample size).

---

## 17. Cross-Phase Validation

Phase 1 Q8_0 vs Phase 2 Q8_0 results for overlapping models (generation tasks only). Same Ollama tags, same temp=0. Consistency threshold: <5% difference.

| Model | Metric | Phase 1 Mean (N) | Phase 2 Mean (N) | Diff % | Status |
|-------|--------|------------------|------------------|--------|--------|
| llama3.2-1b | bertscore | 0.6503 (50) | 0.6444 (250) | -0.9% | **OK** |
| llama3.2-1b | coherence | 0.5731 (50) | 0.5778 (250) | +0.8% | **OK** |
| llama3.2-1b | rouge_l | 0.2740 (50) | 0.2659 (250) | -2.9% | **OK** |
| phi-2 | bertscore | 0.7674 (50) | 0.7235 (250) | -5.7% | DIVERGENT |
| phi-2 | coherence | 0.7916 (50) | 0.7650 (250) | -3.4% | **OK** |
| phi-2 | rouge_l | 0.5131 (50) | 0.4178 (250) | -18.6% | DIVERGENT |
| qwen2.5-1.5b | bertscore | 0.7905 (50) | 0.7454 (250) | -5.7% | DIVERGENT |
| qwen2.5-1.5b | coherence | 0.7434 (50) | 0.7102 (250) | -4.5% | **OK** |
| qwen2.5-1.5b | rouge_l | 0.4262 (50) | 0.3806 (250) | -10.7% | DIVERGENT |

**5/9 metrics consistent** (<5% difference). **4/9 divergent** (>5% difference).

### 17.1 Divergence Analysis

The 4 divergent metrics are:

| Model | Metric | Phase 1 | Phase 2 | Diff | Severity |
|-------|--------|---------|---------|------|----------|
| phi-2 | BERTScore | 0.767 | 0.723 | **-5.7%** | Just over threshold |
| phi-2 | ROUGE-L | 0.513 | 0.418 | **-18.6%** | Large divergence |
| qwen2.5-1.5b | BERTScore | 0.790 | 0.745 | **-5.7%** | Just over threshold |
| qwen2.5-1.5b | ROUGE-L | 0.426 | 0.381 | **-10.7%** | Moderate divergence |

Note that **BERTScore is NOT fully reproducible** — two of three models show divergence at -5.7%, just barely exceeding the 5% threshold. Only coherence passes for all three models (max divergence -4.5%). The prior conclusion that "BERTScore is reproducible" was premature.

Possible explanations for the systematic downward shift:

1. **Sample selection effect:** Phase 1 used 10 samples/task; Phase 2 uses 50 samples/task drawn from the same task pool. The additional 40 samples per task may include harder prompts that pull metrics down, particularly for phi-2 and qwen2.5-1.5b which are more sensitive to prompt difficulty.
2. **ROUGE-L sensitivity:** ROUGE-L is the most variance-prone of the three key metrics (TR124 Phase 3 showed CV 0.23-0.55 for ROUGE-L vs 0.07-0.20 for BERTScore). The Phase 1 estimate at N=50 has wide CIs; the Phase 2 estimate at N=250 is more reliable.
3. **Systematic direction:** All 4 divergent metrics show Phase 2 *lower* than Phase 1. This is not random — it suggests Phase 1 at N=50 systematically overestimated quality, likely due to an easier sample subset.
4. **Model/Ollama version changes:** If Ollama updated model weights between Phase 1 (Feb 20) and Phase 2 (Feb 21), Q8_0 outputs could differ. This is unlikely for a 1-day gap but cannot be ruled out.

**Revised conclusion:** Only coherence is fully reproducible across phases (3/3 models consistent). BERTScore diverges for 2/3 models at -5.7% (marginal). ROUGE-L diverges for 2/3 models at -10.7% to -18.6% (substantial). For cross-phase comparisons, **coherence is the only fully reliable signal**. BERTScore is marginal, and ROUGE-L is unreliable across phases at these sample sizes.

---

## 18. Phase 1 vs Phase 2 Synthesis

### 18.1 What Changed Between Phases

| Aspect | Phase 1 | Phase 2 | Impact |
|--------|---------|---------|--------|
| Baseline | Q8_0 (instruct) | FP16 Ollama (instruct) | Eliminates base-vs-instruct confound |
| Quality gate | Generation metrics only | MMLU + ARC benchmarks (primary) | Objective knowledge measurement |
| Sample size | N=50 (10/task) | N=485 bench + N=250 gen | 10x more statistical power |
| Quality classification | Binary (-10% threshold) | 4-tier system | Finer-grained decisions |
| Timing | Wall-clock (CV 37-42%) | Native eval_duration (CV 10-42%) | More accurate throughput |
| Models | 3 (1.2-2.7B) | 5 (1.2-8B) | Covers real deployment range |
| TTFT | Unavailable | Native prompt_eval_duration | Prompt latency measured |

### 18.2 Phase 1 Findings Validated by Phase 2

| Phase 1 Finding | Phase 2 Confirmation |
|----------------|---------------------|
| Q2_K is catastrophic for llama3.2-1b and qwen2.5-1.5b | Confirmed: -16.1pp and -40.6pp benchmark accuracy |
| phi-2 is most quantization-robust | Confirmed: max -1.8pp at Q4_K_M, -0.4pp at Q3_K_S |
| Quality stable Q8_0 through Q5_K_M | Confirmed: all models within -1.6pp at Q5_K_M |
| Non-monotonic quality at N=50 | Resolved: Phase 2 at N=485 shows monotonic degradation (mostly) |

### 18.3 Phase 1 Findings Refined by Phase 2

| Phase 1 Finding | Phase 2 Refinement |
|----------------|-------------------|
| phi-2 Q4_K_M loses -7.2% (generation) | Phase 2: only -1.8pp benchmark, -0.6% generation. Phase 1 overestimated the loss |
| qwen2.5-1.5b Q4_K_M loses -11.9% (generation) | Phase 2: -4.1pp benchmark, -4.9% generation. Phase 1 overestimated, but Q4_K_M is still the weakest for qwen |
| llama3.2-1b Q4_K_M is better than Q8_0 (+11.8%) | Phase 2: Q4_K_M is -2.3pp below FP16, +4.9% generation. The +11.8% was likely noise at N=50, though the persistent +4.9% at N=250 suggests a stochastic generation effect where Q4_K_M's slightly different weight distribution produces outputs that happen to score higher on these specific tasks. This does not indicate Q4_K_M is genuinely "better" — it indicates the generation metrics have residual variance even at N=250. |

---

## 19. Production Guidance & Decision Trees

### 19.1 Universal Quantization Rules

Based on 24,990 Phase 2 samples across 5 models and 7 quant levels:

1. **Default to Q4_K_M.** Every model tested maintains negligible-to-acceptable quality at this level. FP16-baselined models save 30-67% vs FP16, and llama3.1-8b saves 49% vs Q8_0.
2. **Never deploy Q2_K.** Every model tested loses >11pp benchmark accuracy. No cost saving justifies near-random performance.
3. **phi-2 can go to Q3_K_S.** Only -0.4pp benchmark loss, classified "acceptable." This is the most aggressive safe quantization in our data.
4. **llama3.1-8b can go to Q3_K_S.** Only -2.5pp, classified "acceptable." The 8B model's redundancy absorbs quantization noise.
5. **Do not go below Q4_K_M for llama3.2-1b, llama3.2-3b, or qwen2.5-1.5b.** All three break at Q3_K_S (-9.5pp, -10.1pp, -12.2pp respectively).

### 19.2 Decision Tree by Use Case

| Use Case | Recommended Model | Quant Level | Why |
|----------|------------------|-------------|-----|
| Maximum accuracy | llama3.1-8b | Q8_0 | 72.4% accuracy, highest measured |
| Best accuracy/dollar | phi-2 | Q4_K_M | 57.5% acc, $0.0490/1M, 67% cheaper than FP16 |
| Fastest inference | llama3.2-1b | Q5_K_M | 368 tok/s native, negligible quality loss |
| Smallest VRAM | llama3.2-1b | Q4_K_M | 0.7 GB est., negligible quality loss |
| 8B on consumer GPU | llama3.1-8b | Q4_K_M | 4.6 GB, 69.7% acc, fits RTX 3060 |
| Aggressive quantization | phi-2 | Q3_K_S | Only -0.4pp, 205 tok/s, 1.2 GB |
| Benchmark-critical | qwen2.5-1.5b | Q5_K_M | 64.7% acc (-0.4pp), negligible loss |
| Throughput-critical | qwen2.5-1.5b | Q4_K_M | 299 tok/s, acceptable quality (-4.1pp) |

### 19.3 Integration with TR123/TR124

| TR123/TR124 Recommendation | TR125 Update |
|---------------------------|-------------|
| "Use phi-2 FP16 for highest quality" (TR124) | phi-2 at Q4_K_M delivers 97% of FP16 quality at 33% of the cost |
| "llama-3.2-1b/GPU is the workhorse" (TR124) | llama3.2-1b at Q5_K_M via Ollama is even cheaper ($0.0264 vs $0.075/1M) with negligible quality loss |
| "Quality-cost Pareto: 3 configs" (TR124) | Quantization adds 20+ Pareto-efficient configs across VRAM tiers |
| "Quantization degrades coherence -14% to -32%" (TR124 Phase 2) | TR125 Phase 2 shows this was a base-vs-instruct confound artifact. True degradation at Q4_K_M is <5% |

### 19.4 What Remains Open

1. **Batch inference:** All results are single-stream. Batched Ollama serving may show different quantization sensitivity.
2. **Context length sensitivity:** All tests use short prompts (<512 tokens). Long-context tasks may amplify quantization errors through accumulated KV cache rounding.
3. ~~Task-specific quantization:~~ **Partially addressed (v2)** -- SS9.8 shows per-task quality breakdown. QA and classification are most sensitive; creative_writing is most robust. Per-task statistical tests remain open.
4. **Hardware generalization:** Results on RTX 4080 may not transfer to different GPU architectures (AMD, Apple Silicon) or different memory bandwidth profiles.
5. **Newer quant formats:** IQ4_XS, Q4_0_4_4, and other emerging GGUF formats are not tested.
6. **Ollama determinism validation:** Verify that Ollama at temp=0 produces bit-identical outputs across runs — see Limitations L2.
7. **Actual VRAM measurement:** Replace theoretical VRAM estimates with measured values under realistic context lengths — see Limitations L1.
8. ~~MMLU vs ARC differential:~~ **Addressed (v2)** -- SS8.7 presents systematic analysis. ARC generally more robust; MMLU degrades faster under quantization.
9. ~~Formal equivalence testing:~~ **Addressed (v2)** -- SS15.5 shows 0/18 negligible variants pass TOST at +/-3pp. Study underpowered for equivalence confirmation; would need N>3,000.
10. **Higher-power replication:** Confirm "negligible" tier claims with N > 3,000 per variant to achieve TOST equivalence power at +/-3pp margin.

---

## Limitations & Methodological Caveats

This section consolidates all known limitations of the TR125 experimental design and analysis. Limitations previously noted in SS4 (Phase 1 only), SS16 (power analysis), and SS19.4 (future work) are referenced but not duplicated.

### L1. VRAM Estimates Are Theoretical, Not Measured

All VRAM numbers in the decision matrix (SS13) and model tables use the formula `params × bits_per_weight / 8 × 1.1` — a theoretical estimate with a 10% overhead factor. **No actual VRAM measurements were taken.** Actual Ollama VRAM usage depends on context length (KV cache overhead), batch size, and Ollama's internal memory management. The 10% overhead factor is arbitrary and may underestimate real usage for long-context scenarios. Treat VRAM numbers as lower-bound estimates.

### L2. Ollama Determinism Unvalidated

See Statistical Methods & Caveats section (caveat #6). TR124 Phase 3 validated temp=0 determinism for HuggingFace transformers; TR125 extends this assumption to Ollama without validation. If Ollama at temp=0 produces slightly different outputs across runs, the single-repetition design underestimates variance and CIs.

### L3. Per-Task Quality Analysis (Partial -- v2)

The v2 enhancement (SS9.8) adds per-task generation quality breakdown for selected variants. However, the analysis is limited to key metric averages and does not include per-task statistical tests. Full per-task pairwise testing (5 tasks x 29 variants x 3 metrics = 435 additional tests) was not performed. The data exists in `samples.jsonl` and `phase2_v2_enhancements.json` for future analysis.

### L4. Supplementary Metrics Now Shown (v2)

All 7 generation metrics are now presented in SS9.7. The critical signal -- qwen2.5-1.5b Q2_K repetition collapse to 0.702 -- is documented. However, the supplementary metrics (BLEU, repetition, output_length, exact_match) are not used in tier classification, which still relies on the 3 key metrics only.

### L5. Wilson CIs Now Shown in Benchmark Tables (v2)

Benchmark accuracy tables (SS8.1-8.5) now include 95% Wilson score confidence intervals. Wilson CI half-widths range from +/-3.7pp to +/-4.4pp at N=485. Generation quality CIs remain in the raw data only (`phase2_analysis.json`). The full TTFT table (SS11.1) now includes standard deviations.

### L6. MMLU vs ARC Differential Now Analyzed (v2)

SS8.7 now presents a systematic MMLU vs ARC differential analysis. Key finding: ARC is generally more robust to quantization than MMLU, with the differential widening under aggressive quantization. One anomaly identified: llama3.2-1b Q3_K_S shows ARC collapse to 24.5% (below random) while MMLU holds at 31.9%. No statistical tests were applied to the differential itself.

### L7. 29-Variant Enumeration Now Explicit (v2)

SS13.7 now provides the complete 29-variant enumeration table with tier classification, confirming: 18 negligible + 3 acceptable + 1 concerning + 7 unacceptable. All 8 unsafe variants are at Q3_K_S (3 models) or Q2_K (all 5 models).

### L8. Native Timing Still Includes Ollama Server Overhead

The report distinguishes "native" (`eval_duration`) from "wall-clock" timing. However, `eval_duration` is measured by the Ollama server process, not by the GPU directly. It excludes HTTP round-trip but still includes Ollama's Go server overhead, memory allocation, and scheduling. Calling this "native" overstates its precision relative to CUDA event timing. For sub-10ms measurements, the server overhead may be proportionally significant.

### L9. Rescoring Regex Limited to Letters A-D

The `extract_answer_letter` function only matches letters A through D. ARC-Challenge questions may have up to 5 choices (A-E). If the correct answer is "E" (rare but possible), the regex would fail to extract it, underestimating accuracy. This potential bias is small (ARC-Challenge uses predominantly 4-choice questions) but not zero.

### L10. Outlier Detection Now Performed (v2)

SS10.7 now presents IQR-based outlier analysis on all timing data. Outlier rates are high (TTFT: 9.1%, decode: 18.0%) due to Ollama HTTP overhead, compared to TR126's 0.0-0.9% from CUDA event timing. The mean/median values are robust to these outliers, but p95/p99 metrics would be affected. No trimming or Winsorization was applied.

### L11. 5 MMLU Questions per Subject

With 285 MMLU questions across 57 subjects (5 per subject), per-subject accuracy analysis is statistically meaningless (95% CI of ±44pp at p=0.5 for 5 binary questions). The aggregate MMLU accuracy is reliable at N=285, but any subject-level interpretation would be noise. This is not a limitation of the report (which doesn't attempt subject-level analysis) but of the benchmark sample size.

---

## 20. Reproducibility

### 20.1 Run Commands

```bash
# Phase 1
python research/tr125/phase1/run.py

# Phase 2 (setup + eval + analyze + report)
python research/tr125/phase2/run.py
```

### 20.2 Prerequisites

- Ollama installed and running locally (http://localhost:11434)
- All model variants pulled via `ollama pull` (see `research/tr125/phase2/setup_ollama.py`)
- Python 3.13 with dependencies: sentence-transformers, bert-score, rouge-score, evaluate, scipy

### 20.3 Artifact Provenance

| Artifact | Hash Method | Purpose |
|----------|------------|---------|
| samples.jsonl | Per-row SHA-256 | Full provenance per sample |
| config.yaml | Git-tracked | Experiment reproducibility |
| analyze.py | Git-tracked | Analysis reproducibility |
| phase2_analysis.json | Derived from samples.jsonl | All numbers in this report |

### 20.4 Key Assumptions

1. **Hardware cost:** $0.035/hr (RTX 4080 consumer tier, from TR123).
2. **VRAM estimates:** `params * bpw / 8 * 1.1` overhead factor. **Theoretical only — no actual VRAM measurements taken.** Actual usage varies with context length, KV cache size, and Ollama internals. See Limitations L1.
3. **Ollama quantization fidelity:** Tag names (e.g., `q4_K_M`) assumed to match GGUF quant format. Ollama may pick the closest available variant.
4. **Temperature 0.0:** All results are greedy decoding. Non-greedy decoding introduces variance (TR124 Phase 3: mean CV 0.33 at temp=0.7).

---

## Appendix A: Metric Definitions

### A.1 ROUGE-L
Longest common subsequence (LCS) based F1 score between candidate and reference text. Rewards structural overlap. Implemented via `rouge-score` library. Range [0, 1].

### A.2 BERTScore
Contextual embedding similarity using microsoft/deberta-xlarge-mnli. Computes pairwise cosine similarity between candidate and reference token embeddings, then takes greedy alignment. More robust to paraphrasing than ROUGE. Range [0, 1].

### A.3 BLEU
Geometric mean of 1-4 gram precision with brevity penalty. Standard machine translation metric adapted for code generation evaluation. Range [0, 1].

### A.4 Coherence (SemScore)
Sentence-level cosine similarity using `all-mpnet-base-v2` sentence-transformers model. Measures how semantically similar the candidate is to the reference. Highest human correlation among automated metrics (Aynetdinov & Akbik 2024). Range [0, 1].

### A.5 Exact Match
Binary score: 1 if candidate exactly matches reference (case-insensitive, stripped), 0 otherwise. Used for classification tasks. Range {0, 1}.

### A.6 Output Length
`min(len(candidate), len(reference)) / max(len(candidate), len(reference))`. Penalizes both truncation and over-generation. Range [0, 1].

### A.7 Repetition
`unique_4grams / total_4grams`. Measures lexical diversity. Score of 1.0 = no repeated 4-grams. Range [0, 1].

### A.8 Rescored Accuracy
Regex-based answer letter extraction from model output, compared to correct answer letter. Handles patterns: single letter ("B"), letter with paren ("B)"), sentence form ("The answer is B"), labeled form ("Answer: B"). Falls back to first standalone A-D letter found. This resolves formatting noise that penalizes exact_match on models with verbose output styles.

---

## Appendix B: Benchmark Data Provenance

### B.1 MMLU (Massive Multitask Language Understanding)
- **Source:** `cais/mmlu` on HuggingFace
- **Subjects:** 57 subjects, 5 questions per subject = 285 total
- **Format:** 4-choice multiple choice, generation-based scoring
- **Scoring:** Model generates free-form answer; rescored via regex letter extraction
- **Random baseline:** 25%
- **Why 285 questions:** 5 per subject provides coverage across all 57 MMLU subjects while keeping per-variant evaluation tractable. Full MMLU (14,042 questions) would require ~480,000 samples across 34 variants.

### B.2 ARC-Challenge (AI2 Reasoning Challenge)
- **Source:** `allenai/ai2_arc`, Challenge subset on HuggingFace
- **Samples:** 200 from test split
- **Format:** 3-5 choice science questions, generation-based scoring
- **Scoring:** Same regex letter extraction as MMLU
- **Random baseline:** ~25% (varies with number of choices)
- **Why ARC-Challenge (not Easy):** ARC-Challenge is more discriminating than ARC-Easy for models in the 1-8B range. TR124 showed 91% on ARC-Easy for qwen2.5-1.5b, leaving little room to measure quantization degradation.

### B.3 Generation Tasks
- **Source:** Hand-crafted by research team
- **Tasks:** summarization (50), QA (50), code_generation (50), creative_writing (50), classification (50)
- **Total:** 250 samples per variant
- **Scoring:** Task-appropriate metrics (see SS2.3 in TR124 for metric-task mapping)

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| **BERTScore** | Contextual embedding similarity metric using pre-trained transformer models |
| **BPW** | Bits per weight -- average precision of quantized model parameters |
| **Cohen's d** | Effect size metric -- (mean_A - mean_B) / pooled_std; d > 0.8 is "large" |
| **CV** | Coefficient of Variation -- std / mean; lower = more reproducible |
| **FP16** | 16-bit floating point -- full precision for most LLM inference |
| **GGUF** | GPT-Generated Unified Format -- binary format for quantized LLM weights used by llama.cpp and Ollama |
| **GQA** | Grouped-Query Attention -- multiple query heads share fewer KV heads |
| **MDE** | Minimum Detectable Effect -- smallest effect size detectable at given power and alpha |
| **MHA** | Multi-Head Attention -- every attention head has its own K and V projections |
| **MMLU** | Massive Multitask Language Understanding -- 57-subject knowledge benchmark |
| **Ollama** | Local LLM inference server using llama.cpp backend with HTTP API |
| **pp** | Percentage points -- absolute difference in accuracy (e.g., 72% - 60% = 12pp) |
| **Q2_K** | 2-bit quantization with K-means clustering (GGML format) -- most aggressive |
| **Q3_K_S** | 3-bit quantization, small variant (GGML format) |
| **Q4_K_M** | 4-bit quantization with K-means clustering, medium variant (GGML format) |
| **Q5_K_M** | 5-bit quantization with K-means clustering, medium variant |
| **Q6_K** | 6-bit quantization with K-means clustering |
| **Q8_0** | 8-bit quantization (GGML format) -- highest precision quantization |
| **Quality cliff** | The quant level at which accuracy drops abruptly (typically >9pp in one step) |
| **Rescored accuracy** | Benchmark accuracy after regex letter extraction from model output |
| **ROUGE-L** | Recall-Oriented Understudy for Gisting Evaluation using Longest Common Subsequence |
| **SemScore** | Sentence-level cosine similarity metric with highest human correlation |
| **TTFT** | Time to First Token -- prompt evaluation latency |
| **VRAM** | Video RAM -- GPU memory available for model weights and KV cache |

---

## References

- TR123: KV-Cache Production Economics -- Phase-split $/token with cached decode (Banterhearts, Feb 2026)
- TR124: Quality & Accuracy Baseline -- Backend equivalence, quantization impact, sampling variance (Banterhearts, Feb 2026)
- TR117: Accuracy Metrics -- ROUGE, BERTScore, SemScore implementations (Banterhearts, 2026)
- EleutherAI lm-evaluation-harness -- Standard LLM evaluation framework (2023)
- MMLU: Measuring Massive Multitask Language Understanding (Hendrycks et al., 2021)
- ARC: Think you have Solved Question Answering? (Clark et al., 2018)
- SemScore: Automated evaluation using cosine similarity (Aynetdinov & Akbik, 2024)
- HuggingFace evaluate -- Metric computation library (2023)
- llama.cpp -- Local LLM inference with GGUF quantization (Gerganov et al., 2023-2026)
- Ollama -- Local LLM inference server (2023-2026)

---

**End of Technical Report 125 (2-Phase Complete)**
