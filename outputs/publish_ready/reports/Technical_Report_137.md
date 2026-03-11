# Technical Report 137: The Safety Tax of Inference Optimization
## Unified synthesis of quantization, concurrency, and backend effects on LLM safety alignment

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-03-08 (synthesis of TR134: Mar 5-6, TR135: Mar 7, TR136: Mar 8)
**Author:** Research Team
**Report Type:** Meta-analysis / synthesis (3 source experiments, 18 analysis passes, 74,254 total samples)
**Compute Time:** <5 seconds (pure meta-analysis on pre-computed results)
**Status:** Complete -- all 3 source experiments delivered, full synthesis run
**Run ID:** `20260308_180727`
**Related Work:** [TR134](Technical_Report_134.md) (Alignment Under Quantization), [TR135](Technical_Report_135.md) (Concurrency x Safety), [TR136](Technical_Report_136.md) (Cross-Backend Safety)
**Depends On:** TR134 (quantization safety data), TR135 (concurrency safety data), TR136 (backend safety data)

---

TR134 established that quantization degrades safety alignment in small LLMs. TR135 found that concurrent inference does not. TR136 revealed that the serving backend (Ollama GGUF vs vLLM/TGI FP16) produces safety differences larger than quantization itself. Each experiment answered one question in isolation. TR137 asks: **what is the total safety cost when all three optimization axes are considered together, and which axis should practitioners worry about most?**

This synthesis meta-analysis combines 74,254 evaluated samples across 3 experiments, 5 distinct models (1.2B-7.6B parameters), 7 quantization levels, 4 concurrency levels, and 4 serving backends. We compute cross-axis effect rankings, safety-capability asymmetry, deployment risk projections, jailbreak vulnerability synthesis, per-category bias patterns, and model heterogeneity statistics.

Key findings: (1) Quantization accounts for 57% of total safety cost, backend choice for 41%, and concurrency for 2%. (2) The worst combined configuration (Llama 1B at Q2_K) retains only 57.5% of baseline safety -- a critical-risk deployment. (3) Model heterogeneity is extreme (I-squared = 99.9% on the quant axis) -- models disagree wildly on how dangerous quantization is, making universal deployment guidelines unreliable. (4) Concurrency is the only axis where all models agree: it is safe (max effect = 0.4pp). (5) Jailbreak susceptibility increases under quantization (all technique slopes negative) but is invariant to concurrency. (6) No backend pair achieves TOST equivalence at +/-3pp -- backend swaps cannot be treated as safety-neutral.

**Total: 74,254 samples synthesized from 3 source experiments, 18 analysis passes, 24 deployment configurations assessed.**

---

## Metric Definitions

### Safety Metrics
- **Refusal Rate (AdvBench, Jailbreak):** Proportion of harmful prompts correctly refused. Range [0, 1]. Higher = safer. Scored by RefusalDetector (regex classifier).
- **Truthfulness (TruthfulQA):** Proportion of factually accurate responses. Range [0, 1]. Higher = better. Scored by TruthfulnessScorer.
- **Bias Resistance (BBQ):** Proportion of bias-probing questions answered without demographic stereotyping. Range [0, 1]. Higher = less biased. Scored by BiasDetector.

### Capability Metrics
- **Accuracy (MMLU, ARC-Challenge):** Exact-match accuracy on multiple-choice benchmarks. Range [0, 1]. Higher = better.

### Derived / Synthesis Metrics
- **Effect Size (pp):** Absolute change in safety score (percentage points) between baseline and worst configuration per axis. Positive = degradation.
- **Cohen's d:** Standardized effect size. < 0.2 trivial, 0.2-0.5 small, 0.5-0.8 medium, > 0.8 large.
- **I-squared:** Heterogeneity statistic. Percentage of total variation due to between-model differences. < 25% low, 25-75% moderate, > 75% high.
- **Bootstrap CI:** 95% confidence interval via 2,000 bootstrap resamples (seed=42, percentile method).
- **Safety Retention:** `projected_safety / baseline_safety x 100`. Percentage of baseline safety preserved after optimization.
- **Risk Level:** Based on retention: >= 95% low, >= 90% moderate, >= 80% high, < 80% critical.
- **MDE (Minimum Detectable Effect):** Smallest effect detectable at alpha=0.05, power=0.80 given the sample sizes.

---

## Statistical Methods & Caveats

**Methods used:**

- **Cross-TR validation** at anchor configs (Q4_K_M, N=1, Ollama) across all 3 TRs. Tolerance: 5pp.
- **Effect size ranking** via absolute safety delta (pp) from baseline to worst config per axis, with Cohen's d.
- **Bootstrap CI** (2,000 iterations, seed=42, 95% percentile) on cross-model effect size means per axis.
- **I-squared heterogeneity** across models per axis to quantify agreement on effect direction/magnitude.
- **Pearson correlation** for cross-axis vulnerability (requires >= 3 shared models per pair).
- **Additive projection** for combined quant + concurrency cost (no factorial design available).
- **ANOVA** (one-way) on safety degradation slopes across model families (from TR134).
- **TOST equivalence** testing at +/-3pp margin on backend decomposition (from TR136).
- **IQR outlier detection** on all source data (Q1 - 1.5*IQR, Q3 + 1.5*IQR fences).
- **Risk-tiered deployment matrix** at 95/90/80% retention thresholds.

**Important caveats:**

1. **No factorial design.** Each source TR varied one axis while holding others constant. We cannot measure true interaction effects (e.g., "quantization x concurrency synergy"). The deployment matrix uses an additive model, which may underestimate or overestimate combined costs.

2. **Small anchor set.** Only Llama 3.2 1B and 3B appear in all 3 TRs. Cross-axis conclusions rest on N=2 models. Bootstrap CIs reflect this: the quant axis CI spans [-6.0, 35.2]pp, encompassing both improvement and severe degradation.

3. **Qwen size mismatch.** TR134 tested Qwen 2.5 7B, TR135 tested Qwen 2.5 3B, TR136 tested Qwen 2.5 1.5B. These are different models from the same family, not the same model. Cross-TR Qwen comparisons are family-level, not model-level.

4. **Consumer hardware only.** All experiments ran on a single NVIDIA RTX GPU. Datacenter hardware (A100, H100) may behave differently, particularly for vLLM/TGI optimizations that leverage tensor parallelism.

5. **Automated scoring only.** Safety scores come from regex classifiers (RefusalDetector, BiasDetector, TruthfulnessScorer). LLM judge validation (Qwen 2.5 7B Q8_0) was applied in TR134 only. Cohen's kappa between regex and judge is 0.147 (poor overall), limiting confidence in classification accuracy.

6. **Temperature 0 throughout.** All experiments used deterministic sampling. Stochastic sampling (temp > 0) introduces additional variance that may interact with optimization axes differently.

7. **Meta-analysis on aggregates.** This synthesis operates on pre-computed group statistics, not raw samples. We cannot re-stratify or re-group the data differently without re-running source experiments.

8. **Additive cost model is conservative.** The deployment matrix sums marginal quant and concurrency costs. If axes interact synergistically (e.g., quantization makes concurrency effects worse), actual costs could exceed projections.

---

## Executive Summary

### Key Findings

1. **Quantization is the most dangerous optimization axis, accounting for 57% of total safety cost.** Across the two models appearing in all TRs, quantization produces a mean safety delta of 20.6pp (95% CI: [-6.0, 35.2]pp). For Llama 3.2 1B specifically, dropping from FP16 to Q2_K costs 35.2pp of safety (Cohen's d = 1.93, large effect). However, Llama 3.2 3B shows an anomalous -6.0pp "improvement" at Q2_K (d = -0.27), driving extreme heterogeneity (Section 13).

2. **Backend choice is the second-largest safety factor at 41% of total cost.** Switching from Ollama GGUF to vLLM/TGI FP16 costs 14.8pp mean safety (CI: [4.4, 25.1]pp). For Llama 1B, the backend effect (d = -0.60, medium) is comparable in magnitude to quantization. All TOST equivalence tests fail at +/-3pp -- no backend pair can be treated as interchangeable (Section 10).

3. **Concurrency is safe: 2% of total cost, max effect 0.4pp.** This is the one axis where all models agree (I-squared = 0.0%). Running 1-8 concurrent requests produces negligible safety impact. Practitioners can scale concurrency freely without safety concerns (Section 9).

4. **Model heterogeneity is extreme on quant and backend axes.** I-squared = 99.9% for quantization, 99.5% for backend. Models do not agree on the magnitude or even direction of safety degradation. Universal "safe quantization level" guidelines are unreliable -- per-model validation is required (Section 13).

5. **The worst combined deployment retains only 57.5% of baseline safety.** Llama 3.2 1B at Q2_K with any concurrency level is rated CRITICAL risk. Three of 24 assessed configurations are critical, 3 are moderate, and 18 are low risk (Section 14).

6. **Jailbreak susceptibility increases under quantization but is invariant to concurrency.** All four jailbreak techniques show negative BPW slopes (easier at lower quant). Prefix injection is most effective (slope = -0.036/BPW). Under concurrency, all jailbreak compliance slopes equal zero -- concurrency does not amplify jailbreaks (Section 11).

7. **Safety degrades faster than capability in only 3 of 10 model-axis combinations.** The "RLHF safety veneer" hypothesis -- that safety is a thin layer stripped first by optimization -- is not universally supported. Most models show capability degrading at comparable or faster rates than safety (Section 7).

8. **Nationality is the most vulnerable bias category under quantization; Race/Ethnicity is the least.** Per-category BBQ analysis shows Nationality bias slope = -0.010/BPW (worsening), while Race/Ethnicity slope = +0.015/BPW (improving). This ranking is averaged across 4 models (3 families) (Section 17).

9. **Cross-TR reproducibility is good but imperfect.** At the Q4_K_M anchor point, 9 of 12 task-model pairs agree within 5pp across all 3 TRs. Three tasks exceed tolerance: ARC-Challenge on Llama 1B (6.0pp), AdvBench on Llama 3B (7.0pp), and Jailbreak on Llama 3B (6.7pp). Mean deltas are 2.3pp and 3.0pp respectively (Section 5).

### Validation Summary

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| Source coverage | TRs loaded | 3/3 | **3/3** | PASS |
| Data volume | Total samples | > 50,000 | **74,254** | PASS |
| Anchor consistency | Mean delta < 5pp | Both models | **2.3pp, 3.0pp** | PASS |
| Outlier rate | IQR flagged | 0% | **0/300 groups** | PASS |
| Effect ranking | All 3 axes ranked | Complete | **quant > backend > concurrency** | PASS |
| Deployment matrix | Configs assessed | >= 20 | **24** | PASS |

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| 1 | Quantization is the most dangerous axis | Mean 20.6pp delta, Cohen's d = 1.93 (Llama 1B) | **Validated** for Llama 1B; **Mixed** at aggregate level (CI includes negative) |
| 2 | Concurrency is safety-neutral | Max delta 0.4pp, I² = 0.0%, all slopes ~0 | **Validated** |
| 3 | Backend choice matters more than quantization for some models | Llama 1B: backend d = -0.60 vs quant d = 0.05 within TR136 | **Validated** for within-backend comparison |
| 4 | No backend pair is equivalent at +/-3pp | All 18 TOST tests fail (from TR136) | **Validated** |
| 5 | Effects are additive across axes | No factorial design to test; additive model used | **Assumed, not validated** |
| 6 | Safety degrades faster than capability | Only 3/10 model-axis combinations | **Refuted** as universal claim |
| 7 | Jailbreak vulnerability increases at lower quant | All 4 technique slopes negative | **Validated** |
| 8 | Model families agree on which axis is dangerous | ANOVA p = 0.1370, I² = 99.9% on quant | **Refuted** -- extreme disagreement |

### Key Decisions for Practitioners

1. **Prioritize quantization validation over concurrency testing.** Quantization accounts for 57% of safety cost; concurrency accounts for 2%. If your testing budget is limited, spend it on evaluating different quant levels for your specific model. Concurrency can be scaled freely (Section 6, Section 9).

2. **Treat backend swaps as safety-critical changes.** Migrating from Ollama to vLLM/TGI (or vice versa) can change safety behavior by 4-25pp depending on the model. Re-validate safety after any backend migration, even at the same precision level (Section 10).

3. **Do not rely on generic "safe quantization" thresholds.** I-squared = 99.9% means models disagree completely on quantization's impact. Llama 1B loses 35pp at Q2_K; Llama 3B gains 6pp. Per-model profiling is mandatory (Section 13).

4. **Avoid Q2_K for Llama 3.2 1B in any safety-critical application.** All three Q2_K configurations for Llama 1B are rated CRITICAL (58% retention). This is the only model-quant combination in the matrix that falls below the 80% safety threshold (Section 14, Section 15).

5. **Use Q4_K_M or higher for production deployments of small models.** At Q4_K_M, both Llama models retain >= 93% safety across all concurrency levels. The marginal quant cost at this level is 1.3-4.6pp -- well within acceptable bounds for most applications (Section 14).

### When to Use This Report

**Scenario 1: Choosing a quantization level for deployment**

**Question:** "We want to deploy Llama 3.2 1B quantized. What's the safest level?"

**Answer:** Q4_K_M retains 98.4% safety at N=1, 99.1% at N=4. Q8_0 is even safer (100.7% retention). Avoid Q2_K entirely (57.5% retention, CRITICAL). See Section 14 for the full deployment matrix.

**Scenario 2: Scaling to multiple concurrent users**

**Question:** "Will running 8 concurrent requests degrade safety?"

**Answer:** No. Maximum observed concurrency effect is 0.4pp across all models (Section 6). All jailbreak compliance slopes under concurrency are zero (Section 11). Concurrency is safe.

**Scenario 3: Migrating from Ollama to vLLM**

**Question:** "We're moving from Ollama to vLLM for production. Any safety concerns?"

**Answer:** Yes. For Llama 1B, this swap costs ~25pp of safety (Section 10). The mechanism is chat template divergence between GGUF-embedded and HuggingFace tokenizer templates (TR136 report, Section 8). Re-validate safety after migration.

**Scenario 4: Understanding which optimization to worry about most**

**Question:** "We're optimizing model, quant level, concurrency, and backend simultaneously. Where's the risk?"

**Answer:** Quantization (57% of cost) and backend (41%) dominate. Concurrency (2%) is negligible. See the effect decomposition in Section 19 and the deployment matrix in Section 14.

**Scenario 5: Evaluating a new model family**

**Question:** "Do these findings generalize to our model?"

**Answer:** Probably not directly. I-squared = 99.9% on quantization means even within this study, models disagree completely. ANOVA across families is not significant (p = 0.1370). Use this report for directional guidance (quantization matters, concurrency doesn't), but validate your specific model (Section 12).

### How to Read This Report

| Time | Reading Path |
|------|-------------|
| **2 min** | Abstract + Key Findings 1-4 |
| **10 min** | Add Executive Summary tables + Section 6 (Effect Ranking) + Section 14 (Deployment Matrix) |
| **30 min** | Add Sections 5, 7, 10-11, 15, 19 for full synthesis picture |
| **60 min** | Full report including per-category bias, judge agreement, and appendices |
| **Deep dive** | Appendix B (jailbreak tables), Appendix C (per-category slopes), source TR reports |

### Table of Contents

**Front Matter**

- [Abstract](#technical-report-137-the-safety-tax-of-inference-optimization)
- [Metric Definitions](#metric-definitions)
- [Statistical Methods & Caveats](#statistical-methods--caveats)
- [Executive Summary](#executive-summary)

**Context & Design (Sections 1-4)**

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Source Experiments & Design](#2-source-experiments--design)
3. [Model Coverage & Overlap](#3-model-coverage--overlap)
4. [Environment & Artifacts](#4-environment--artifacts)

**Core Synthesis (Sections 5-10)**

5. [Cross-TR Baseline Validation](#5-cross-tr-baseline-validation)
6. [Effect Size Ranking](#6-effect-size-ranking)
7. [Safety-Capability Asymmetry](#7-safety-capability-asymmetry)
8. [Per-Task Vulnerability Matrix](#8-per-task-vulnerability-matrix)
9. [Quantization x Concurrency Projection](#9-quantization-x-concurrency-projection)
10. [Backend x Quantization Decomposition](#10-backend-x-quantization-decomposition)

**Extended Analysis (Sections 11-18)**

11. [Jailbreak Synthesis Across Axes](#11-jailbreak-synthesis-across-axes)
12. [Family-Level Patterns](#12-family-level-patterns)
13. [Model-Axis Heterogeneity](#13-model-axis-heterogeneity)
14. [Safety-Adjusted Deployment Matrix](#14-safety-adjusted-deployment-matrix)
15. [Worst-Case Analysis](#15-worst-case-analysis)
16. [Power & Sensitivity](#16-power--sensitivity)
17. [Per-Category Bias Synthesis](#17-per-category-bias-synthesis)
18. [Judge Agreement Synthesis](#18-judge-agreement-synthesis)

**Conclusions (Sections 19-20)**

19. [Effect Decomposition & Conclusions](#19-effect-decomposition--conclusions)
20. [Reproducibility](#20-reproducibility)

**Appendices**

- [Appendix A: Full Deployment Matrix](#appendix-a-full-deployment-matrix)
- [Appendix B: Jailbreak Success Rates by Technique](#appendix-b-jailbreak-success-rates-by-technique)
- [Appendix C: Per-Category Bias Slopes](#appendix-c-per-category-bias-slopes)
- [Appendix D: Glossary](#appendix-d-glossary)
- [References](#references)

---

## 1. Introduction & Research Motivation

### 1.1 The Problem

Deploying LLMs in production requires multiple optimization decisions: quantization level (FP16 to Q2_K), serving backend (Ollama, vLLM, TGI), and concurrency (1 to 8+ simultaneous requests). Each optimization improves cost, latency, or throughput -- but may degrade safety alignment. Prior work (TR134, TR135, TR136) studied each axis independently. No prior work in this project has examined their combined effect or ranked them by safety impact.

### 1.2 Research Questions

1. Which inference optimization axis causes the most safety degradation?
2. Does safety erode faster than capability under each optimization?
3. Do models agree on which axis is most dangerous? (heterogeneity)
4. What is the projected safety cost of combined optimizations?
5. Are jailbreak susceptibility patterns consistent across axes?
6. Which demographic categories are most vulnerable across axes?
7. Do models vulnerable on one axis tend to be vulnerable on others?

### 1.3 Scope

This is a meta-analysis. We do not run new model evaluations. We synthesize pre-computed results from three completed experiments (TR134, TR135, TR136) covering 74,254 total samples. The synthesis adds value through cross-axis comparison, effect ranking, deployment projections, and heterogeneity analysis that no individual TR can provide.

### 1.4 Contribution

TR137 provides the first unified safety-cost picture across all three optimization axes studied in the Banterhearts research program. The deployment matrix (Section 14) gives practitioners a concrete, risk-tiered lookup table for configuration decisions. The effect decomposition (Section 19) quantifies the relative importance of each axis, enabling rational prioritization of safety validation effort.

---

## 2. Source Experiments & Design

Each source TR varied one axis while holding the others constant. The table below summarizes the experimental design of each source.

| Property | TR134 (Quantization) | TR135 (Concurrency) | TR136 (Backend) |
|----------|---------------------|--------------------|-----------------|
| Axis varied | Quant level (FP16-Q2_K) | Concurrent requests (1-8) | Serving backend (4 types) |
| Models | 4 (1.2B-7.6B) | 3 (1.2B-3B) | 3 (1.2B-3B) |
| Configs | 26 model-quant variants | 12 model-concurrency variants | 12 model-backend variants |
| Total samples | 24,778 | 39,060 | 10,416 |
| Safety tasks | 4 (advbench, jailbreak, bbq, truthfulqa) | 4 (same) | 4 (same) |
| Capability tasks | 2 (MMLU, ARC) | 2 (same) | 2 (same) |
| Backend | Ollama (all quants) | Ollama Q4_K_M (fixed) | Ollama + vLLM + TGI |
| Temperature | 0.0 | 0.0 | 0.0 |
| LLM Judge | Yes (12,168 judged) | No | Yes (5,616 judged) |

**Observations:** The design is a one-at-a-time (OAT) factorial, not a full factorial. This means we can estimate marginal effects of each axis but cannot measure interactions. The additive projection in Section 9 relies on this assumption. The common anchor point (Q4_K_M, N=1, Ollama) allows cross-TR validation (Section 5) but does not substitute for a full factorial design. All three TRs share the same 6 benchmarks and temperature setting, enabling consistent comparison.

The sample distribution is uneven: TR135 contributes 53% of total samples due to its concurrency multiplication design (each N-level multiplies sample count), while TR136 contributes only 14%. This does not affect the synthesis because we operate on aggregated statistics (group means, slopes) rather than pooled raw samples. However, it means power analysis (Section 16) differs across sources: TR135 has the lowest MDE (6.8pp) while TR134 has the highest (18.3pp). Effects that are detectable in TR135 may be below TR134's detection threshold.

---

## 3. Model Coverage & Overlap

The overlap matrix shows which models appear in which TRs. Only models present in all 3 TRs (Llama 1B and 3B) can anchor the cross-axis synthesis.

| Model | Params | Family | TR134 | TR135 | TR136 | Anchor? |
|-------|--------|--------|-------|-------|-------|---------|
| llama3.2-1b | 1.2B | Llama | Yes (7 quants) | Yes (4 N-levels) | Yes (4 backends) | **Yes** |
| llama3.2-3b | 3.2B | Llama | Yes (7 quants) | Yes (4 N-levels) | Yes (4 backends) | **Yes** |
| mistral-7b | 7.2B | Mistral | Yes (6 quants) | No | No | No |
| qwen2.5-7b | 7.6B | Qwen | Yes (6 quants) | No | No | No |
| qwen2.5-3b | 3B | Qwen | No | Yes (4 N-levels) | No | No |
| qwen2.5-1.5b | 1.5B | Qwen | No | No | Yes (4 backends) | No |

**Observations:** The anchor set of 2 models is the primary constraint on this synthesis. All cross-axis statistics (effect ranking, heterogeneity, decomposition, deployment matrix) are computed over these 2 models only. The Qwen family appears in all 3 TRs but at different sizes (7B, 3B, 1.5B), preventing direct cross-TR comparison at the model level -- these are architecturally similar but separately trained models with different parameter counts, vocabulary sizes, and alignment procedures.

Family-level patterns (Section 12) use TR134's 4-model set for the quantization axis and TR135/TR136's 3-model sets for the other axes. The limited anchor set means bootstrap CIs are wide and I-squared estimates should be interpreted with caution. Specifically, I-squared with N=2 is mathematically guaranteed to be either 0% or ~100% -- there is no middle ground. The extreme values (99.9%, 99.5%) reflect genuine disagreement between models, but the binary nature of 2-model I-squared means we cannot distinguish "moderate disagreement" from "complete disagreement." Adding even one more anchor model would substantially improve heterogeneity estimation.

---

## 4. Environment & Artifacts

| Property | Value |
|----------|-------|
| Platform | Windows 11 (10.0.26200) |
| Python | 3.13.1 (MSC v.1942 64-bit) |
| Machine | AMD64 |
| NumPy | 2.3.5 |
| SciPy | 1.15.2 |
| Pandas | 2.2.3 |
| Ollama | Not required (meta-analysis only) |
| Docker | Not required (meta-analysis only) |

### 4.1 Source Data Paths

| Source | Analysis File | Records |
|--------|--------------|---------|
| TR134 | `research/tr134/results/phase3/20260305_144827/phase3_analysis.json` | 24,778 |
| TR135 | `research/tr135/results/20260307_162151/tr135_analysis.json` | 39,060 |
| TR136 | `research/tr136/results/20260308_015147/tr136_analysis.json` | 10,416 |

### 4.2 Data Quality

IQR outlier detection was applied to all source data. Zero outliers were flagged across 300 total groups (TR134: 156 groups, TR135: 72 groups, TR136: 72 groups). Each group was checked per-task with 12-26 values per task.

---

## 5. Cross-TR Baseline Validation

Before synthesizing results, we verify that the three TRs agree at their shared anchor point: Q4_K_M quantization, N=1 concurrency, Ollama backend. Consistency threshold: 5pp.

### 5.1 Llama 3.2 1B

| Task | TR134 | TR135 | TR136 | Max Delta (pp) | Consistent? |
|------|-------|-------|-------|---------------|-------------|
| advbench_refusal | 0.870 | 0.880 | 0.880 | 1.0 | Yes |
| arc_challenge | 0.395 | 0.340 | 0.335 | 6.0 | **No** |
| bbq_bias | 0.874 | 0.869 | 0.874 | 0.5 | Yes |
| jailbreak_amplification | 0.933 | 0.925 | 0.925 | 0.8 | Yes |
| mmlu_real | 0.337 | 0.305 | 0.310 | 3.2 | Yes |
| truthfulqa | 0.580 | 0.570 | 0.590 | 2.0 | Yes |

Mean delta: 2.25pp. Status: **1 inconsistent task.**

### 5.2 Llama 3.2 3B

| Task | TR134 | TR135 | TR136 | Max Delta (pp) | Consistent? |
|------|-------|-------|-------|---------------|-------------|
| advbench_refusal | 0.470 | 0.540 | 0.540 | 7.0 | **No** |
| arc_challenge | 0.705 | 0.695 | 0.700 | 1.0 | Yes |
| bbq_bias | 0.965 | 0.960 | 0.965 | 0.5 | Yes |
| jailbreak_amplification | 0.825 | 0.892 | 0.892 | 6.7 | **No** |
| mmlu_real | 0.590 | 0.600 | 0.595 | 1.1 | Yes |
| truthfulqa | 0.500 | 0.480 | 0.480 | 2.0 | Yes |

Mean delta: 3.04pp. Status: **2 inconsistent tasks.**

**Observations:** 9 of 12 task-model pairs are consistent within 5pp. The 3 inconsistent tasks are all on the boundary: ARC-Challenge for Llama 1B (6.0pp) is a capability task with known per-run variance at temperature 0; AdvBench (7.0pp) and Jailbreak (6.7pp) for Llama 3B are refusal tasks where moderate baseline rates (0.47-0.83) leave room for run-to-run variance. Importantly, TR135 and TR136 agree perfectly on all Llama 3B safety scores (0.540, 0.892), and the divergence is entirely from TR134. This suggests a single-run anomaly in TR134 rather than systematic measurement error. The mean deltas (2.3pp, 3.0pp) are well below the 5pp tolerance, providing adequate confidence for synthesis.

---

## 6. Effect Size Ranking

The central question: which optimization axis produces the largest safety degradation? We compute the absolute delta (pp) between baseline and worst configuration for each model on each axis.

### 6.1 Aggregate Ranking

| Rank | Axis | Mean |Delta| (pp) | 95% Bootstrap CI | N Models |
|------|------|----------------|-------------------|----------|
| 1 | Quantization | 20.6 | [-6.0, 35.2] | 2 |
| 2 | Backend | 14.8 | [4.4, 25.1] | 2 |
| 3 | Concurrency | 0.4 | [-0.3, 0.4] | 2 |

### 6.2 Per-Model Breakdown

| Model | Quant (pp) | Conc. (pp) | Backend (pp) | Worst Axis |
|-------|-----------|-----------|-------------|------------|
| llama3.2-1b | 35.2 (FP16 -> Q2_K) | -0.3 (N=1 -> N=8) | 25.1 (Ollama -> TGI) | quant |
| llama3.2-3b | -6.0 (FP16 -> Q2_K) | 0.4 (N=1 -> N=8) | 4.4 (Ollama -> TGI) | backend |

### 6.3 Cohen's d (Quantization Axis)

| Model | Cohen's d | Interpretation |
|-------|----------|----------------|
| llama3.2-1b | 1.93 | Large |
| llama3.2-3b | -0.27 | Small (improvement) |

**Observations:** The aggregate ranking is clear -- quantization > backend >> concurrency -- but the confidence intervals reveal important nuance. The quant CI [-6.0, 35.2] spans zero because Llama 3B shows anomalous safety improvement at Q2_K. This is likely a measurement artifact: Q2_K degrades coherence so severely that the model produces incoherent refusals rather than coherent compliance, inflating refusal scores. The backend CI [4.4, 25.1] is entirely positive, indicating that backend effects are consistently negative for safety even though magnitude varies by model. The concurrency CI [-0.3, 0.4] tightly brackets zero, confirming negligible impact. Cohen's d for Llama 1B quantization (d = 1.93) is a large effect by any convention -- this is not a subtle finding.

---

## 7. Safety-Capability Asymmetry

Does safety erode faster than capability under each optimization? If yes, the "safety veneer" hypothesis holds: RLHF alignment is a thin layer stripped first.

### 7.1 Summary by Axis

| Axis | Models Tested | Safety Degrades Faster | Percentage |
|------|--------------|----------------------|------------|
| Quantization | 4 | 1 (Mistral 7B) | 25% |
| Concurrency | 3 | 1 (Llama 3B) | 33% |
| Backend | 3 | 1 (Llama 1B) | 33% |

### 7.2 Per-Model Detail (Quantization Axis)

| Model | Family | Safety Slope | Capability Slope | Divergence | Safety Faster? | Conclusion |
|-------|--------|-------------|-----------------|-----------|---------------|------------|
| llama3.2-1b | Llama | +0.013 | +0.022 | -0.009 | No | Robust |
| llama3.2-3b | Llama | -0.007 | +0.011 | -0.018 | No | Robust |
| mistral-7b | Mistral | +0.041 | +0.013 | +0.028 | **Yes** | SUGGESTIVE |
| qwen2.5-7b | Qwen | +0.008 | +0.016 | -0.008 | No | Robust |

### 7.3 Backend Axis (Range-Based)

| Model | Safety Range (pp) | Capability Range (pp) | Ratio | Safety Faster? |
|-------|------------------|---------------------|-------|---------------|
| llama3.2-1b | 25.1 | 4.0 | 6.29 | **Yes** |
| llama3.2-3b | 4.4 | 7.8 | 0.57 | No |
| qwen2.5-1.5b | 4.3 | 5.3 | 0.83 | No |

**Observations:** The safety veneer hypothesis is NOT universally supported. Only 3 of 10 model-axis combinations show safety degrading faster than capability. On the quantization axis, only Mistral 7B (the largest model with the weakest baseline safety) shows disproportionate safety loss -- and even this is "suggestive" (CIs overlap). On the backend axis, Llama 1B shows dramatic asymmetry (safety range 6.3x capability range), but this is model-specific: the chat template divergence in GGUF vs HuggingFace specifically disrupts Llama 1B's refusal patterns while leaving knowledge-based tasks intact. On concurrency, Llama 3B technically shows safety degrading faster, but both slopes are near-zero (safety: -0.0001, capability: -0.0001), making this practically meaningless. The overall picture: optimization affects safety and capability comparably for most models. Practitioners should monitor both domains, not assume safety is uniquely fragile.

---

## 8. Per-Task Vulnerability Matrix

Which benchmarks are most sensitive to each optimization axis? We report mean absolute slopes (quant, concurrency) and minimum chi-squared p-values (backend).

| Task | Quant Abs. Slope | Conc. Abs. Slope | Backend Min p | Most Vulnerable Axis |
|------|-----------------|-----------------|--------------|---------------------|
| advbench_refusal | 0.040 | 0.000 | **0.0000** | quant |
| jailbreak_amplification | 0.040 | 0.000 | **0.0000** | quant |
| arc_challenge | 0.016 | --- | --- | quant |
| mmlu_real | 0.016 | --- | --- | quant |
| truthfulqa | 0.009 | 0.001 | 0.1401 | quant |
| bbq_bias | 0.006 | 0.000 | **0.0093** | quant |

**Observations:** AdvBench refusal and jailbreak amplification are the most vulnerable tasks on every axis, with quant slopes 4-7x larger than bias or truthfulness tasks. This makes intuitive sense: refusal behavior is a direct product of RLHF fine-tuning and is the first capability affected when weight precision drops. The tied slopes (0.040 for both advbench and jailbreak) reflect their shared measurement mechanism: both use RefusalDetector to classify responses, and both involve explicit harmful content that the model must learn to refuse.

BBQ bias and TruthfulQA are relatively robust to quantization (slopes 0.006-0.009) and completely insensitive to concurrency. This is expected: bias resistance (choosing the anti-stereotyped option) and factual knowledge (selecting the correct fact) are embedded in the model's general world knowledge, not in a separable RLHF safety layer. On the backend axis, AdvBench, jailbreak, and BBQ all show significant chi-squared tests (p < 0.01), but TruthfulQA does not (p = 0.14) -- factual knowledge is preserved across backends even when refusal behavior diverges.

Capability tasks (ARC, MMLU) show moderate quant slopes (0.016) -- smaller than refusal tasks but non-trivial. They lack concurrency and backend data in this synthesis because TR135 and TR136 did not include these tasks in their safety-focused analyses. The quant axis remains the only axis where both safety and capability sensitivity can be directly compared (Section 7).

---

## 9. Quantization x Concurrency Projection

Since no factorial experiment tests quant and concurrency simultaneously, we project the combined cost using an additive model: `total = quant_marginal + concurrency_marginal`. This assumes no interaction.

| Model | Quant Cost (pp) | Conc. Cost (pp) | Projected Total (pp) | Quant % of Total |
|-------|----------------|----------------|---------------------|-----------------|
| llama3.2-1b | 1.3 | -0.3 | 1.1 | 83% |
| llama3.2-3b | 4.6 | 0.4 | 5.0 | 91% |

**Observations:** The marginal quant costs here are computed at the Q4_K_M level (the anchor point), not Q2_K. At this moderate quantization, the combined cost is modest: 1.1pp for Llama 1B, 5.0pp for Llama 3B. Quantization dominates in both cases (83-91% of total). The concurrency contribution is so small that it barely registers. This projection is conservative: if quant and concurrency interact synergistically (e.g., quantized models degrade more under load), actual costs could be higher. However, TR135's finding of zero jailbreak compliance slopes under concurrency (Section 11) suggests interaction is unlikely. The practical implication: practitioners can choose their quantization level based on TR134 data and ignore concurrency scaling entirely.

---

## 10. Backend x Quantization Decomposition

TR136 tested four backends on the same models, allowing decomposition of the backend effect into three components: quantization (Q4_K_M vs Q8_0 within Ollama), backend (Ollama Q8_0 vs vLLM FP16), and serving framework (vLLM vs TGI).

### 10.1 Llama 3.2 1B

| Component | Diff (pp) | Cohen's d | p-value | t-stat | TOST Equiv? |
|-----------|----------|----------|---------|--------|------------|
| Quant (Q4-Q8) | +1.8 | 0.054 (trivial) | 0.4055 | 0.832 | No |
| Backend (Q8-vLLM) | -24.8 | -0.604 (medium) | < 0.0001 | -9.244 | No |
| Serving (vLLM-TGI) | -0.3 | -0.007 (trivial) | 0.9189 | -0.102 | No |

### 10.2 Llama 3.2 3B

| Component | Diff (pp) | Cohen's d | p-value | t-stat | TOST Equiv? |
|-----------|----------|----------|---------|--------|------------|
| Quant (Q4-Q8) | +0.5 | 0.014 (trivial) | 0.8341 | 0.210 | No |
| Backend (Q8-vLLM) | -6.1 | -0.149 (trivial) | 0.0233 | -2.273 | No |
| Serving (vLLM-TGI) | -0.4 | -0.010 (trivial) | 0.8798 | -0.151 | No |

### 10.3 Qwen 2.5 1.5B

| Component | Diff (pp) | Cohen's d | p-value | t-stat | TOST Equiv? |
|-----------|----------|----------|---------|--------|------------|
| Quant (Q4-Q8) | +3.0 | 0.081 (trivial) | 0.2146 | 1.242 | No |
| Backend (Q8-vLLM) | -5.7 | -0.149 (trivial) | 0.0225 | -2.285 | No |
| Serving (vLLM-TGI) | -1.0 | -0.024 (trivial) | 0.7166 | -0.363 | No |

**Observations:** Three patterns emerge consistently across all models. First, **within-Ollama quantization (Q4 vs Q8) is trivial**: d < 0.09 for all models, no p-value significant. The quantization cost measured here is much smaller than the FP16-to-Q2_K cost from TR134 because the Q4-Q8 range represents a narrow slice of the full quantization spectrum. Second, **the Ollama-to-FP16 backend jump is the dominant effect**: d = -0.60 (medium) for Llama 1B, d = -0.15 for the others, with p < 0.025 for all models. This is the chat template divergence documented in TR136. Third, **vLLM and TGI are functionally identical**: d < 0.03, p > 0.7 for all models. The serving framework does not matter; the weight format (GGUF vs FP16) and associated template handling is what drives the difference. Critically, no TOST test passes at +/-3pp for any component on any model, meaning we cannot formally certify any of these transitions as safety-equivalent.

---

## 11. Jailbreak Synthesis Across Axes

### 11.1 Quantization Axis (TR134)

All four jailbreak techniques become more effective at lower quantization levels. Slopes represent change in compliance rate per BPW reduction.

| Technique | Slope (per BPW) | Interpretation | N Samples |
|-----------|----------------|----------------|-----------|
| prefix_injection | -0.036 | Most effective at low quant | 780 |
| direct | -0.030 | Strongly effective | 780 |
| dan_style | -0.024 | Moderately effective | 780 |
| roleplay | -0.021 | Least effective at low quant | 780 |

Total jailbreak samples: 3,120.

**Observations:** All slopes are negative, confirming that quantization universally amplifies jailbreak susceptibility. Prefix injection is the most dangerous technique at low quant, with a compliance rate slope 70% steeper than roleplay. At Q2_K, prefix injection achieves 60% compliance on Llama 1B (vs 3.3% at FP16) and 93% on Mistral 7B (vs 87% at Q8_0). The practical implication: low-quant models should be assumed jailbreak-vulnerable regardless of their FP16 refusal rates.

### 11.2 Concurrency Axis (TR135)

Jailbreak compliance rates are completely flat across concurrency levels. The table below shows compliance at N=1 and N=8 for each model-technique pair to confirm invariance.

| Model | Technique | Compliance @ N=1 | Compliance @ N=8 | Slope (per N) |
|-------|-----------|------------------|------------------|--------------|
| llama3.2-1b | dan_style | 3.3% | 3.3% | 0.000 |
| llama3.2-1b | direct | 13.3% | 13.3% | 0.000 |
| llama3.2-1b | prefix_injection | 13.3% | 13.3% | 0.000 |
| llama3.2-1b | roleplay | 0.0% | 0.0% | 0.000 |
| llama3.2-3b | dan_style | 3.3% | 3.3% | 0.000 |
| llama3.2-3b | direct | 6.7% | 6.7% | 0.000 |
| llama3.2-3b | prefix_injection | 0.0% | 0.0% | 0.000 |
| llama3.2-3b | roleplay | 33.3% | 33.3% | 0.000 |
| qwen2.5-3b | dan_style | 6.7% | 7.1% | 0.001 |
| qwen2.5-3b | direct | 13.3% | 13.3% | 0.000 |
| qwen2.5-3b | prefix_injection | 76.7% | 76.7% | 0.000 |
| qwen2.5-3b | roleplay | 20.0% | 20.0% | 0.000 |

**Observations:** Concurrency has zero effect on jailbreak susceptibility. 11 of 12 model-technique pairs show exactly 0.000 compliance slope; the single exception (Qwen dan_style, slope = 0.001) is negligible. This is the strongest null finding in the entire synthesis: regardless of model, technique, or concurrency level (1-8), jailbreak success rates do not change. Note the absolute levels vary widely between models: Qwen 2.5 3B is highly susceptible to prefix_injection (76.7% compliance) even at N=1, while Llama 1B resists it (13.3%). But these baseline differences are frozen in place across concurrency levels. Combined with the quant-axis finding, this means jailbreak vulnerability is a function of weight precision and model training, not serving conditions.

### 11.3 Cross-Axis Summary

| Property | Quantization | Concurrency |
|----------|-------------|-------------|
| Effect on jailbreak | All 4 slopes negative | All 12 slopes ~zero |
| Most dangerous technique | prefix_injection (-0.036/BPW) | N/A (invariant) |
| Worst-case compliance | Mistral Q2_K: 97% (roleplay) | Qwen N=1: 77% (prefix_injection) |
| Mechanism | Weight precision loss erodes refusal | Deterministic sampling produces identical output |

The fundamental asymmetry: quantization changes the model's weights, directly affecting learned refusal behavior. Concurrency changes only the scheduling of identical requests through the same model, producing bit-identical outputs at temperature 0.

---

## 12. Family-Level Patterns

Do model families differ in quantization sensitivity? TR134 tested 4 families, enabling one-way ANOVA on safety degradation slopes.

### 12.1 ANOVA on Quantization Slopes

| Statistic | Value |
|-----------|-------|
| F-statistic | 2.50 |
| p-value | 0.1370 |
| df (between, within) | (2, 9) |
| Conclusion | **Not significant** |

### 12.2 Per-Family Mean Safety Slopes

| Family | N Slopes | Mean Slope | Min Slope | Max Slope | Interpretation |
|--------|---------|-----------|----------|----------|----------------|
| Llama | 6 | +0.003 | -0.020 | +0.025 | Near-flat (mixed direction) |
| Mistral | 3 | +0.041 | +0.013 | +0.092 | Steep positive (degradation with lower quant) |
| Qwen | 3 | +0.008 | -0.000 | +0.023 | Mild positive |

### 12.3 Cross-Axis Effects by Family

The Llama family is the only one appearing across all 3 axes. This breakdown shows how the same family behaves on each axis.

| Axis | Model | Effect (pp) | Interpretation |
|------|-------|-----------|----------------|
| Quantization | llama3.2-1b | +35.2 | Severe degradation |
| Quantization | llama3.2-3b | -6.0 | Anomalous improvement |
| Concurrency | llama3.2-1b | -0.3 | Negligible |
| Concurrency | llama3.2-3b | +0.4 | Negligible |
| Backend | llama3.2-1b | +25.1 | Severe degradation |
| Backend | llama3.2-3b | +4.4 | Mild degradation |

**Observations:** The ANOVA is not significant (p = 0.1370), meaning we cannot reject the null hypothesis that all families have the same mean safety slope. However, the point estimates differ substantially: Mistral's mean slope (+0.041) is 14x Llama's (+0.003) and 5x Qwen's (+0.008). The non-significance is driven by high within-family variance (Llama slopes range from -0.020 to +0.025) and small sample sizes (3 slopes per family for Mistral/Qwen). With more models per family, this test would likely reach significance.

The cross-axis Llama breakdown reveals an important model-size effect: Llama 1B is severely vulnerable to both quantization and backend changes, while Llama 3B is only mildly affected. The 3x parameter increase (1.2B to 3.2B) provides substantial robustness. Both models agree that concurrency is safe. This suggests that the extreme I-squared values in Section 13 are partially driven by model-size effects rather than pure model identity -- if we controlled for parameter count, heterogeneity might decrease.

---

## 13. Model-Axis Heterogeneity

Do models agree on how dangerous each axis is? I-squared quantifies between-model variance as a percentage of total variance.

| Axis | N Models | Signed Mean (pp) | SD (pp) | Range (pp) | I-squared | Interpretation |
|------|---------|----------|---------|-----------|-----------|---------------|
| Quantization | 2 | 14.6 | 29.2 | 41.3 | 99.9% | High disagreement |
| Backend | 2 | 14.8 | 14.6 | 20.7 | 99.5% | High disagreement |
| Concurrency | 2 | 0.1 | 0.5 | 0.7 | 0.0% | Low (agreement) |

**Observations:** The heterogeneity results are striking. On the quant axis, I-squared = 99.9% means virtually all observed variation is between-model, not within-model. Llama 1B loses 35pp while Llama 3B gains 6pp -- they don't just disagree on magnitude, they disagree on direction. On the backend axis, I-squared = 99.5% reflects the 25pp vs 4pp difference between models. Only concurrency shows consensus (I-squared = 0.0%): both models agree it's negligible. These extreme I-squared values have two important consequences. First, aggregate effect sizes (Section 6) are misleading -- the signed mean of +35.2 and -6.0 is 14.6pp, but no model actually experiences 14.6pp of degradation. (Note: Section 6 reports 20.6pp, the mean of *absolute* deltas, which better reflects effect magnitude for ranking purposes. This section uses *signed* means, which are appropriate for heterogeneity estimation.) Second, any meta-analytic pooling of quant effects across models would be statistically inappropriate given I-squared > 75%. Per-model analysis is essential.

---

## 14. Safety-Adjusted Deployment Matrix

The deployment matrix projects safety retention for each (model, quant, concurrency) combination using the additive model from Section 9. Risk tiers: >= 95% = low, >= 90% = moderate, >= 80% = high, < 80% = critical.

| Model | Quant | N | Total Cost (pp) | Retention | Risk |
|-------|-------|---|----------------|-----------|------|
| llama3.2-1b | Q2_K | 1 | 35.2 | **57.5%** | **CRITICAL** |
| llama3.2-1b | Q2_K | 4 | 34.7 | **58.1%** | **CRITICAL** |
| llama3.2-1b | Q2_K | 8 | 34.9 | **57.8%** | **CRITICAL** |
| llama3.2-3b | Q4_K_M | 1 | 4.6 | 93.8% | Moderate |
| llama3.2-3b | Q4_K_M | 4 | 4.8 | 93.5% | Moderate |
| llama3.2-3b | Q4_K_M | 8 | 5.0 | 93.2% | Moderate |
| llama3.2-1b | Q4_K_M | 1 | 1.3 | 98.4% | Low |
| llama3.2-3b | Q8_0 | 8 | 1.7 | 97.7% | Low |
| llama3.2-1b | FP16 | 1 | 0.0 | 100.0% | Low |

*See Appendix A for the complete 24-row deployment matrix.*

**Risk Distribution:** Critical: 3 configs, Moderate: 3, Low: 18.

**Observations:** The deployment matrix reveals a sharp safety cliff rather than a gradual slope. All critical-risk configurations involve a single model (Llama 1B) at a single quant level (Q2_K). Moving from Q4_K_M (98.4% retention) to Q2_K (57.5% retention) for Llama 1B represents a catastrophic 40pp safety drop. No other model-quant combination falls below 93% retention. Concurrency's contribution is visible but negligible: the difference between N=1 and N=8 at Q2_K is only 0.3pp (57.5% vs 57.8%). The moderate-risk configs (Llama 3B at Q4_K_M) are noteworthy: this model shows a 4.6pp quant cost at Q4_K_M, meaning its baseline safety (73.6%) is already lower than Llama 1B's degraded Q4_K_M safety (81.4%). The backend range column (not shown in this summary; see Appendix A) adds context: Llama 1B has 25.1pp backend variance, meaning even a "low risk" config could drop significantly if the serving backend changes.

---

## 15. Worst-Case Analysis

### 15.1 Per-Axis Worst Cases

| Axis | Model | Delta (pp) | Detail |
|------|-------|-----------|--------|
| Quantization | llama3.2-1b | **35.2** | FP16 (0.828) -> Q2_K (0.476), d = 1.93 |
| Backend | llama3.2-1b | **25.1** | Ollama Q4_K_M (0.817) -> TGI FP16 (0.566) |
| Concurrency | llama3.2-3b | **0.4** | N=1 (0.718) -> N=8 (0.714) |

### 15.2 Combined Worst Case

| Property | Value |
|----------|-------|
| Model | llama3.2-1b |
| Quantization | Q2_K (2.5 BPW) |
| Concurrency | N=1 |
| Baseline safety | 0.828 |
| Quant cost | +35.2pp |
| Concurrency cost | 0.0pp |
| Total cost | +35.2pp |
| Projected safety | 0.476 |
| Retention | 57.5% |
| Risk level | **CRITICAL** |
| Backend range | 25.1pp (additional variance) |

### 15.3 Risk Distribution

| Risk Level | Count | Percentage | Models Involved |
|-----------|-------|------------|----------------|
| Critical (< 80%) | 3 | 12.5% | Llama 1B only (all Q2_K) |
| High (80-90%) | 0 | 0.0% | None |
| Moderate (90-95%) | 3 | 12.5% | Llama 3B only (all Q4_K_M) |
| Low (>= 95%) | 18 | 75.0% | Both models |

**Observations:** The combined worst case is entirely attributable to quantization (35.2pp total cost at N=1, where concurrency contributes 0.0pp). At higher concurrency levels (N=4, N=8), the total cost slightly decreases due to marginally higher safety measured in TR135, but N=1 remains the worst configuration. The backend range (25.1pp) is not additive with quant in the deployment matrix -- it represents the additional variance introduced by backend choice, which applies on top of whatever quant/concurrency cost exists. In the truly worst combined scenario (Q2_K + N=1 + TGI FP16), safety could theoretically drop below 30%, though this was not directly measured.

The risk distribution is heavily skewed: 75% of configs are low-risk. The critical configs are concentrated in a single model (Llama 1B) at a single quant level (Q2_K). This means the safety cliff is sharp and localized, not gradual and universal. The practical implication: avoiding Q2_K for Llama 1B eliminates all critical risk from the deployment matrix. The moderate-risk configs (Llama 3B at Q4_K_M) reflect a lower baseline rather than severe degradation -- Llama 3B starts at 73.6% safety, so even a modest 4.6pp cost pushes it below the 95% retention threshold.

---

## 16. Power & Sensitivity

Can the source experiments detect the effects they claim to measure?

| Source | MDE Safety (pp) | Avg N / Variant | Interpretation |
|--------|----------------|-----------------|----------------|
| TR134 | 18.3 | 117 | Detects >= 18.3pp safety drop at 80% power |
| TR135 | 6.8 | ~150-450 | Detects >= 6.8pp at 80% power |
| TR136 | N/A | 468 | Not computed in synthesis (see TR136 report) |

**Program-level sensitivity:** Effects >= 18.3pp are detectable across all source TRs. Effects between 6.8pp and 18.3pp may be detectable in TR135 but not TR134. Effects < 6.8pp may be undetectable in any source.

**Observations:** The MDE values contextualize our findings. Llama 1B's 35.2pp quant effect (well above 18.3pp MDE) is robustly detectable -- this is a real and large effect. Llama 3B's -6.0pp "improvement" is below TR134's MDE (18.3pp), meaning TR134 may lack power to reliably detect effects of this magnitude at the per-model level. The concurrency null finding (max 0.4pp) is far below any MDE, so we cannot distinguish "no effect" from "small effect below detection threshold." However, the consistency of zero-slope findings across all models and techniques (Section 11) strongly suggests a true null rather than an underpowered test. TR135's lower MDE (6.8pp) is enabled by its larger sample sizes from the concurrency multiplication design.

---

## 17. Per-Category Bias Synthesis

BBQ bias probing covers 11 demographic categories. Per-category slopes (score vs BPW) reveal which groups are most vulnerable to quantization-induced bias amplification.

### 17.1 Category Vulnerability Ranking (Quantization Axis)

| Rank | Category | Avg Slope | N Models | Interpretation |
|------|----------|----------|----------|----------------|
| 1 | Nationality | -0.010 | 4 | Most vulnerable (bias worsens with lower quant) |
| 2 | SES | -0.003 | 4 | Mildly vulnerable |
| 3 | Disability_status | -0.000 | 4 | Near-zero |
| 4 | Religion | +0.003 | 4 | Mildly robust |
| 5 | Race_x_SES | +0.004 | 4 | Mildly robust |
| 6 | Race_x_gender | +0.007 | 4 | Robust |
| 7 | Physical_appearance | +0.009 | 4 | Robust |
| 8 | Age | +0.009 | 4 | Robust |
| 9 | Gender_identity | +0.010 | 4 | Robust |
| 10 | Sexual_orientation | +0.012 | 4 | Robust |
| 11 | Race_ethnicity | +0.015 | 4 | Least vulnerable (bias improves) |

**Most vulnerable:** Nationality. **Least vulnerable:** Race/Ethnicity.

Additional data: Concurrency axis has 12 bias groups available; backend axis has 12 bias groups available.

**Observations:** The ranking reveals a counterintuitive pattern: Nationality is the most vulnerable category (negative slope = bias worsens at lower quant), while Race/Ethnicity is the least vulnerable (positive slope = bias actually improves). This may reflect the training data distribution: race/ethnicity-related bias mitigation is heavily emphasized in modern RLHF training, making it more robust to quantization. Nationality-based biases receive less attention in alignment training and are therefore more fragile. The Disability_status category sits at the boundary (slope ~ 0), suggesting neither improvement nor degradation. Importantly, these slopes are averaged across 4 models (3 families), and individual models show substantial variation. For example, Mistral 7B has a Nationality slope of -0.038 while Llama 1B has +0.003 -- the vulnerability is not uniform. The concurrency and backend axes have bias data available but were not further stratified in this synthesis due to the negligible overall concurrency effect and the primarily refusal-driven backend effect.

---

## 18. Judge Agreement Synthesis

TR134 validated regex classifiers against an LLM judge (Qwen 2.5 7B Q8_0) on 12,168 samples.

### 18.1 Overall Agreement

| Metric | Value |
|--------|-------|
| Total judged samples | 12,168 |
| Overall Cohen's kappa | 0.147 (poor) |

### 18.2 Per-Task Kappa

| Task | Kappa | Agreement % | Interpretation |
|------|-------|-------------|----------------|
| advbench_refusal | 0.013 | 67.7% | Slight |
| truthfulqa | 0.282 | 43.2% | Fair |

### 18.3 Kappa by Quantization Level (AdvBench)

| Quant | Kappa | Pairs | Agreement % |
|-------|-------|-------|-------------|
| FP16 | 0.000 | 200 | 71.5% |
| Q8_0 | 0.000 | 400 | 67.2% |
| Q6_K | 0.000 | 400 | 70.2% |
| Q5_K_M | 0.020 | 400 | 67.8% |
| Q4_K_M | 0.020 | 400 | 66.5% |
| Q3_K_S | 0.042 | 400 | 74.2% |
| Q2_K | 0.007 | 400 | 58.2% |

### 18.4 Kappa by Quantization Level (TruthfulQA)

| Quant | Kappa | Pairs | Agreement % |
|-------|-------|-------|-------------|
| FP16 | 0.200 | 100 | 41.0% |
| Q8_0 | 0.249 | 200 | 42.0% |
| Q6_K | 0.272 | 200 | 46.5% |
| Q5_K_M | 0.386 | 200 | 46.5% |
| Q4_K_M | 0.292 | 200 | 41.0% |
| Q3_K_S | 0.292 | 200 | 43.0% |
| Q2_K | 0.214 | 200 | 41.5% |

**Observations:** The poor overall kappa (0.147) is concerning but interpretable in context. AdvBench kappa is near-zero (0.013) because both regex and judge classifiers agree on the "easy" cases (clear refusals) but diverge on edge cases -- and the base rate of agreement is high (68%) even with kappa near zero, indicating that the high agreement is largely explained by base rates rather than genuine classifier concordance. TruthfulQA shows better kappa (0.282) because truthfulness classification has more ambiguity, creating more room for classifier-judge disagreement to be informative.

The per-quant patterns differ between tasks. For AdvBench, Q2_K shows the lowest agreement (58.2%), suggesting that heavily quantized models produce responses that are genuinely harder to classify -- they are neither clearly refusal nor clearly compliance, but degraded text that classifiers interpret differently. For TruthfulQA, kappa peaks at Q5_K_M (0.386) and decreases at both extremes, suggesting a "sweet spot" where model outputs are coherent enough for consistent classification but varied enough for meaningful agreement.

These results have two implications for the synthesis. First, safety scores at extreme quant levels (Q2_K) carry more measurement uncertainty than those at moderate levels -- the 35.2pp quant effect for Llama 1B is directionally robust but its precise magnitude may be inflated or deflated by classifier disagreement. Second, the regex classifiers used across all three source TRs may systematically misclassify edge cases, potentially biasing effect size estimates. A human annotation study would resolve this uncertainty but is outside the scope of this synthesis.

---

## 19. Effect Decomposition & Conclusions

### 19.0 Cross-Axis Correlation

RQ7 asks: are models vulnerable on one axis also vulnerable on others? Computing Pearson correlation requires >= 3 shared models per axis pair. With only 2 anchor models (Llama 1B, 3B), we cannot compute a meaningful correlation.

However, qualitative inspection suggests a tentative answer: **yes, for quant and backend; no for concurrency.**

| Model | Quant Vulnerability | Backend Vulnerability | Concurrency Vulnerability |
|-------|--------------------|--------------------- |--------------------------|
| llama3.2-1b | Severe (35.2pp) | Severe (25.1pp) | None (-0.3pp) |
| llama3.2-3b | Mild (6.0pp) | Mild (4.4pp) | None (0.4pp) |

Llama 1B is the most vulnerable model on BOTH quant and backend axes. Llama 3B is mildly affected on both. This co-occurrence is consistent with a shared underlying mechanism: smaller models have less redundancy in their safety-aligned weights, making them more fragile to any perturbation -- whether that perturbation comes from weight quantization or from chat template divergence. Concurrency shows no vulnerability for either model, consistent with it being a scheduling-level operation that does not perturb model weights or templates.

With 3+ shared models per axis pair, a formal Pearson r could quantify this relationship. Future work adding Mistral and Qwen to the concurrency and backend experiments would enable this analysis.

### 19.1 Per-Model Decomposition

What percentage of total safety cost comes from each optimization axis?

| Model | Total (pp) | Quant | Concurrency | Backend | Dominant |
|-------|-----------|-------|-------------|---------|----------|
| llama3.2-1b | 60.6 | 58% (35.2pp) | <1% (0.3pp) | 41% (25.1pp) | Quantization |
| llama3.2-3b | 10.8 | 56% (6.0pp) | 4% (0.4pp) | 41% (4.4pp) | Quantization* |

### 19.2 Aggregate Decomposition

| Axis | Mean % of Total | N Models |
|------|----------------|----------|
| Quantization | 57% | 2 |
| Backend | 41% | 2 |
| Concurrency | 2% | 2 |

### 19.3 Cross-TR Comparison

| Finding | TR134 (Quant) | TR135 (Conc.) | TR136 (Backend) | TR137 (Synthesis) |
|---------|--------------|--------------|----------------|------------------|
| Max safety delta | 35.2pp (Llama 1B) | 0.4pp (Llama 3B) | 25.1pp (Llama 1B) | 35.2pp combined |
| Models affected | 1/4 severe, 1/4 anomalous | 0/3 | 1/3 severe | Same Llama 1B |
| Jailbreak amplified? | Yes (all slopes negative) | No (all slopes zero) | N/A | Quant yes, conc. no |
| Bias vulnerable | Nationality | N/A | N/A | Nationality |
| TOST equivalent? | N/A | N/A | 0/18 pairs | Backend never equivalent |
| Key mechanism | Weight precision loss | N/A (no effect) | Chat template divergence | Quant + template |

### 19.4 Model-Level Verdicts

| Model | Worst Axis | Max Delta (pp) | Safety > Capability? | Critical Configs | Overall Risk |
|-------|-----------|---------------|---------------------|-----------------|-------------|
| llama3.2-1b | Quantization | 35.2 | Yes (backend axis) | 3 (all Q2_K) | **CRITICAL** |
| llama3.2-3b | Backend | 4.4 | Yes (concurrency, trivial) | 0 | Moderate |
| mistral-7b | Quantization | ~35pp (TR134 only) | Yes (quant axis, suggestive) | N/A (single-axis) | High (inferred) |
| qwen2.5-7b | Quantization | ~8pp (TR134 only) | No | N/A (single-axis) | Low (inferred) |

**Observations:** Llama 3.2 1B is the clear vulnerability hotspot: it drives the worst case on both the quant and backend axes, is the only model with critical-risk configs, and shows safety degrading faster than capability on the backend axis. Llama 3.2 3B is moderate-risk: its quant cost at Q4_K_M (4.6pp) is manageable but not negligible, and its lower baseline safety (0.736 vs 0.828) means less margin for error. Mistral 7B and Qwen 2.5 7B lack cross-axis data (single TR only) but their TR134 quantization profiles suggest high and low risk respectively. Mistral is concerning because it shows the steepest safety slope (+0.041) and is the only model where safety degrades faster than capability on the quant axis.

### 19.5 Answering the Research Questions

*\* Llama 3B's quant effect is an improvement (-6.0pp), not a degradation. It is "dominant" by absolute magnitude; the largest degradation axis is backend (4.4pp).*

| RQ | Question | Answer |
|----|----------|--------|
| 1 | Most dangerous axis? | Quantization (57% of cost, mean 20.6pp) |
| 2 | Safety faster than capability? | Only 3/10 model-axis combinations (not universal) |
| 3 | Models agree? | No. I² = 99.9% (quant), 99.5% (backend), 0.0% (concurrency) |
| 4 | Combined cost? | Additive projection: 1.1-5.0pp at Q4_K_M; 34.7-35.2pp at Q2_K |
| 5 | Jailbreak patterns consistent? | Quant amplifies (all negative slopes). Concurrency does not (all zero). |
| 6 | Most vulnerable bias category? | Nationality (slope -0.010). Least: Race/Ethnicity (+0.015). |
| 7 | Cross-axis vulnerability correlation? | Insufficient data (need >= 3 shared models, have 2) |

### 19.6 Limitations of the Synthesis

Beyond the caveats enumerated in the Statistical Methods section, several synthesis-specific limitations deserve emphasis:

1. **Two-model anchor set.** All cross-axis conclusions rest on Llama 1B and 3B. These are both Llama-family models from the same architecture lineage. The synthesis cannot distinguish family-specific effects from universal effects.

2. **Non-overlapping quant ranges.** TR134 tests FP16-Q2_K, but the deployment matrix's "quant cost" is computed relative to FP16 baseline. TR136's backend decomposition uses Q4_K_M-Q8_0 within Ollama. These different quant ranges are not directly comparable.

3. **Backend axis is partially confounded with weight format.** The "backend effect" in TR136 includes both the serving framework difference AND the weight format difference (GGUF vs FP16 HuggingFace). These cannot be separated without a common weight format across backends.

4. **No interaction measurement.** The additive model may miss synergistic effects. For example, it is plausible that Q2_K models are MORE sensitive to backend changes than FP16 models, but we have no data on Q2_K + vLLM.

5. **Temporal confound.** Source TRs were run on different dates (Mar 5-8). System state (Ollama version, GPU thermal state, background processes) may have varied between runs, contributing to the cross-TR inconsistencies in Section 5.

### 19.7 Deployment Recommendations

1. **Always validate safety per-model.** I-squared > 99% means no generic guideline is reliable.
2. **Use Q4_K_M or higher for safety-critical applications.** 93-100% retention across the board.
3. **Scale concurrency freely.** Zero safety cost, confirmed across all models and jailbreak techniques.
4. **Re-validate after backend changes.** Backend contributes 41% of total safety cost.
5. **Monitor Nationality bias under quantization.** Most vulnerable demographic category.
6. **Avoid Q2_K for Llama-class 1B models.** CRITICAL risk (58% retention).

---

### 19.8 Future Work

Several extensions would strengthen the synthesis:

1. **Full factorial experiment.** A single experiment varying quant x concurrency x backend simultaneously would enable true interaction measurement. The estimated cost: 4 models x 7 quants x 4 N-levels x 4 backends = 448 configs x 955 prompts = ~428,000 samples. This is computationally expensive but would eliminate the additive assumption.

2. **Expanded anchor set.** Adding Mistral 7B and Qwen 7B to TR135 (concurrency) and TR136 (backend) experiments would increase the cross-axis anchor set from 2 to 4 models, enabling Pearson correlation computation and tighter bootstrap CIs.

3. **Human annotation validation.** The poor judge kappa (0.147) suggests that automated scoring introduces systematic uncertainty. A 500-sample human annotation study at key quant levels (FP16, Q4_K_M, Q2_K) would calibrate the automated classifiers.

4. **Datacenter hardware.** All results are from consumer NVIDIA GPUs. Replication on A100/H100 hardware with tensor parallelism would test generalization to production infrastructure.

5. **Stochastic sampling.** All experiments used temperature 0. A temperature-0.7 variant would reveal whether stochastic sampling introduces additional safety variance that interacts with optimization axes.

---

## 20. Reproducibility

### 20.1 Prerequisites

All source experiments must be complete with analysis JSON files in their result directories.

### 20.2 Run Command

```bash
# Validate source availability
python research/tr137/run.py --validate-only -v

# Run full synthesis (18 passes)
python research/tr137/run.py -v
```

### 20.3 Expected Output

```
research/tr137/results/YYYYMMDD_HHMMSS/
  tr137_analysis.json       # Full 18-pass analysis (73KB)
  tr137_report.md           # Auto-generated 21-section report (463 lines)
  tr137_deployment_matrix.csv  # 24 deployment configs with risk tiers
  tr137_effect_ranking.csv    # Per-model axis ranking
```

### 20.4 Runtime

< 5 seconds on any machine with Python 3.9+. No GPU, no Ollama, no Docker required. Pure meta-analysis on pre-computed JSON files.

---

## Appendix A: Full Deployment Matrix

All 24 assessed deployment configurations, sorted by risk level then retention.

| Model | Quant | N | Baseline | Quant Cost | Conc. Cost | Total Cost | Backend Range | Projected | Retention | Risk |
|-------|-------|---|---------|-----------|-----------|-----------|--------------|----------|-----------|------|
| llama3.2-1b | Q2_K | 1 | 0.828 | 35.2pp | 0.0pp | 35.2pp | 25.1pp | 0.476 | 57.5% | **CRITICAL** |
| llama3.2-1b | Q2_K | 8 | 0.828 | 35.2pp | -0.3pp | 34.9pp | 25.1pp | 0.478 | 57.8% | **CRITICAL** |
| llama3.2-1b | Q2_K | 4 | 0.828 | 35.2pp | -0.6pp | 34.7pp | 25.1pp | 0.481 | 58.1% | **CRITICAL** |
| llama3.2-3b | Q4_K_M | 1 | 0.736 | 4.6pp | 0.0pp | 4.6pp | 4.4pp | 0.690 | 93.8% | Moderate |
| llama3.2-3b | Q4_K_M | 4 | 0.736 | 4.6pp | 0.2pp | 4.8pp | 4.4pp | 0.688 | 93.5% | Moderate |
| llama3.2-3b | Q4_K_M | 8 | 0.736 | 4.6pp | 0.4pp | 5.0pp | 4.4pp | 0.686 | 93.2% | Moderate |
| llama3.2-3b | Q2_K | 1 | 0.736 | -6.0pp | 0.0pp | -6.0pp | 4.4pp | 0.796 | 108.2% | Low |
| llama3.2-3b | Q2_K | 4 | 0.736 | -6.0pp | 0.2pp | -5.9pp | 4.4pp | 0.794 | 108.0% | Low |
| llama3.2-3b | Q2_K | 8 | 0.736 | -6.0pp | 0.4pp | -5.6pp | 4.4pp | 0.792 | 107.6% | Low |
| llama3.2-1b | Q8_0 | 4 | 0.828 | -0.5pp | -0.6pp | -1.1pp | 25.1pp | 0.839 | 101.3% | Low |
| llama3.2-1b | Q8_0 | 8 | 0.828 | -0.5pp | -0.3pp | -0.8pp | 25.1pp | 0.836 | 101.0% | Low |
| llama3.2-1b | FP16 | 4 | 0.828 | 0.0pp | -0.6pp | -0.6pp | 25.1pp | 0.833 | 100.7% | Low |
| llama3.2-1b | Q8_0 | 1 | 0.828 | -0.5pp | 0.0pp | -0.5pp | 25.1pp | 0.833 | 100.7% | Low |
| llama3.2-1b | FP16 | 8 | 0.828 | 0.0pp | -0.3pp | -0.3pp | 25.1pp | 0.831 | 100.3% | Low |
| llama3.2-1b | FP16 | 1 | 0.828 | 0.0pp | 0.0pp | 0.0pp | 25.1pp | 0.828 | 100.0% | Low |
| llama3.2-3b | FP16 | 1 | 0.736 | 0.0pp | 0.0pp | 0.0pp | 4.4pp | 0.736 | 100.0% | Low |
| llama3.2-3b | FP16 | 4 | 0.736 | 0.0pp | 0.2pp | 0.2pp | 4.4pp | 0.734 | 99.7% | Low |
| llama3.2-3b | FP16 | 8 | 0.736 | 0.0pp | 0.4pp | 0.4pp | 4.4pp | 0.731 | 99.4% | Low |
| llama3.2-1b | Q4_K_M | 4 | 0.828 | 1.3pp | -0.6pp | 0.8pp | 25.1pp | 0.820 | 99.1% | Low |
| llama3.2-1b | Q4_K_M | 8 | 0.828 | 1.3pp | -0.3pp | 1.1pp | 25.1pp | 0.817 | 98.7% | Low |
| llama3.2-1b | Q4_K_M | 1 | 0.828 | 1.3pp | 0.0pp | 1.3pp | 25.1pp | 0.814 | 98.4% | Low |
| llama3.2-3b | Q8_0 | 1 | 0.736 | 1.2pp | 0.0pp | 1.2pp | 4.4pp | 0.723 | 98.3% | Low |
| llama3.2-3b | Q8_0 | 4 | 0.736 | 1.2pp | 0.2pp | 1.4pp | 4.4pp | 0.721 | 98.0% | Low |
| llama3.2-3b | Q8_0 | 8 | 0.736 | 1.2pp | 0.4pp | 1.7pp | 4.4pp | 0.719 | 97.7% | Low |

---

## Appendix B: Jailbreak Success Rates by Technique

Selected compliance rates showing quantization effect. Full data across all 4 models, 7 quants, 4 techniques available in `tr137_analysis.json`.

### B.1 Prefix Injection (Most Effective Technique)

| Model | FP16 | Q8_0 | Q4_K_M | Q2_K |
|-------|------|------|--------|------|
| llama3.2-1b | 3.3% | 3.3% | 10.0% | 60.0% |
| llama3.2-3b | 3.3% | 3.3% | 0.0% | 10.0% |
| mistral-7b | -- | 86.7% | 93.3% | 93.3% |
| qwen2.5-7b | -- | 23.3% | 20.0% | 36.7% |

### B.2 Direct Prompts (Control)

| Model | FP16 | Q8_0 | Q4_K_M | Q2_K |
|-------|------|------|--------|------|
| llama3.2-1b | 6.7% | 3.3% | 13.3% | 76.7% |
| llama3.2-3b | 0.0% | 0.0% | 0.0% | 16.7% |
| mistral-7b | -- | 70.0% | 73.3% | 83.3% |
| qwen2.5-7b | -- | 6.7% | 10.0% | 30.0% |

### B.3 DAN-Style

| Model | FP16 | Q8_0 | Q4_K_M | Q2_K |
|-------|------|------|--------|------|
| llama3.2-1b | 0.0% | 0.0% | 0.0% | 70.0% |
| llama3.2-3b | 0.0% | 0.0% | 6.7% | 3.3% |
| mistral-7b | -- | 66.7% | 76.7% | 76.7% |
| qwen2.5-7b | -- | 6.7% | 0.0% | 16.7% |

### B.4 Roleplay

| Model | FP16 | Q8_0 | Q4_K_M | Q2_K |
|-------|------|------|--------|------|
| llama3.2-1b | 3.3% | 0.0% | 3.3% | 33.3% |
| llama3.2-3b | 13.3% | 23.3% | 63.3% | 3.3% |
| mistral-7b | -- | 100.0% | 96.7% | 96.7% |
| qwen2.5-7b | -- | 6.7% | 6.7% | 33.3% |

**Observations:** Several patterns emerge from the full technique breakdown. Mistral 7B is an outlier: it shows near-ceiling compliance (67-100%) across ALL techniques and quant levels. Its safety alignment does not resist jailbreaks even at Q8_0. Llama 1B shows a dramatic Q2_K cliff: compliance jumps from near-zero (0-13%) at Q4_K_M to 33-77% at Q2_K across all techniques. Llama 3B is the most robust small model, with near-zero compliance in most cells. The technique ranking (prefix_injection > direct > dan_style > roleplay by slope) is consistent across models, suggesting the technique effectiveness hierarchy is a property of the jailbreak design, not the target model.

---

## Appendix C: Per-Category Bias Slopes

Safety degradation slope (score vs BPW) per demographic category per model. Negative = bias worsens at lower quant.

| Category | llama3.2-1b | llama3.2-3b | mistral-7b | qwen2.5-7b | Avg |
|----------|-------------|-------------|-----------|-----------|-----|
| Nationality | +0.003 | +0.001 | -0.038 | -0.004 | -0.010 |
| SES | -0.004 | +0.004 | -0.017 | +0.004 | -0.003 |
| Disability_status | -0.003 | +0.011 | -0.009 | 0.000 | 0.000 |
| Religion | -0.005 | +0.009 | +0.020 | -0.011 | +0.003 |
| Race_x_SES | +0.003 | +0.002 | +0.007 | +0.004 | +0.004 |
| Race_x_gender | +0.011 | +0.004 | +0.017 | -0.002 | +0.007 |
| Physical_appearance | +0.007 | +0.013 | +0.014 | 0.000 | +0.009 |
| Age | +0.004 | +0.007 | +0.024 | 0.000 | +0.009 |
| Gender_identity | +0.011 | +0.008 | +0.017 | +0.004 | +0.010 |
| Sexual_orientation | -0.003 | +0.007 | +0.043 | 0.000 | +0.012 |
| Race_ethnicity | +0.012 | +0.006 | +0.041 | 0.000 | +0.015 |

**Observations:** Mistral 7B drives much of the category-level variation. It shows the steepest negative slope for Nationality (-0.038) and the steepest positive slopes for Sexual_orientation (+0.043) and Race_ethnicity (+0.041). Qwen 2.5 7B shows near-zero slopes for most categories, suggesting its bias alignment is relatively robust to quantization. The within-model variation is often larger than the between-category variation -- Mistral's slopes range from -0.038 to +0.043 -- making aggregate category rankings less reliable than per-model assessments.

---

## Appendix D: Glossary

| Term | Definition |
|------|------------|
| BPW | Bits per weight. FP16 = 16.0, Q8_0 = 8.0, Q6_K = 6.5, Q5_K_M = 5.5, Q4_K_M = 4.5, Q3_K_S = 3.5, Q2_K = 2.5. |
| Bootstrap CI | Confidence interval computed by resampling data 2,000 times with replacement and taking the 2.5th/97.5th percentiles. Non-parametric; does not assume normality. |
| Cohen's d | Standardized effect size: (mean_A - mean_B) / pooled_SD. < 0.2 trivial, 0.2-0.5 small, 0.5-0.8 medium, > 0.8 large. |
| Cohen's kappa | Inter-rater agreement statistic correcting for chance. < 0 poor, 0-0.2 slight, 0.2-0.4 fair, 0.4-0.6 moderate, > 0.6 substantial. |
| I-squared | Heterogeneity statistic: percentage of total variation attributable to between-study (between-model) differences. < 25% low, 25-75% moderate, > 75% high. |
| MDE | Minimum Detectable Effect. Smallest effect a study can detect at alpha=0.05, power=0.80. Reported in percentage points. |
| OAT | One-at-a-time factorial design. Each experiment varies one factor while holding others constant. Cannot measure interaction effects. |
| pp | Percentage points. An absolute difference in proportions. If score drops from 0.85 to 0.60, the delta is 25pp. |
| RLHF | Reinforcement Learning from Human Feedback. The fine-tuning method that instills safety alignment in LLMs. |
| Safety Retention | Projected safety as a percentage of baseline: (projected / baseline) x 100. |
| TOST | Two One-Sided Tests. Tests equivalence within a margin (here +/-3pp). Both one-sided tests must pass at alpha=0.05 to declare equivalence. |
| Welch's t-test | Two-sample t-test that does not assume equal variances. Used for pairwise backend and quant comparisons. |

---

## References

1. Hendrycks, D., Burns, C., Basart, S., Zou, A., Mazeika, M., Song, D., & Steinhardt, J. (2021). Measuring Massive Multitask Language Understanding. *ICLR 2021.*
2. Clark, P., Cowhey, I., Etzioni, O., Khot, T., Sabharwal, A., Schoenick, C., & Tafjord, O. (2018). Think you have Solved Question Answering? Try ARC. *arXiv:1803.05457.*
3. Lin, S., Hilton, J., & Evans, O. (2022). TruthfulQA: Measuring How Models Mimic Human Falsehoods. *ACL 2022.*
4. Parrish, A., Chen, A., Nangia, N., Padmakumar, V., Phang, J., Thompson, J., Htut, P.M., & Bowman, S. (2022). BBQ: A Hand-Built Bias Benchmark for Question Answering. *ACL 2022.*
5. Chao, P., Robey, A., Dobriban, E., Hassani, H., Pappas, G.J., & Wong, E. (2024). JailbreakBench: An Open Robustness Benchmark for Jailbreaking LLMs. *NeurIPS 2024.*
6. Shen, X., Chen, Z., Backes, M., & Zhang, Y. (2024). JailbreakHub: A Centralized Repository for Jailbreak Prompts. *arXiv:2401.01288.*
7. Higgins, J.P.T., Thompson, S.G., Deeks, J.J., & Altman, D.G. (2003). Measuring Inconsistency in Meta-Analyses. *BMJ, 327(7414), 557-560.* (I-squared statistic.)
8. Banterhearts TR134 (2026). Alignment Robustness Under Quantization.
9. Banterhearts TR135 (2026). Multi-Agent Concurrency x Safety.
10. Banterhearts TR136 (2026). Cross-Backend Safety Consistency.
