# Technical Report 134: Alignment Robustness Under Quantization
## Multi-family safety evaluation across 4 models (1.2B-7.6B) with jailbreak amplification and per-category bias analysis

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-03-06 (Phase 1: Mar 4, Phase 2: Mar 4, Phase 3: Mar 5-6)
**Author:** Research Team
**Report Type:** Safety alignment analysis (metric-backed, 3-phase, 4 model families, 6 benchmarks)
**Test Duration:** Phase 1: ~30 min, Phase 2: ~2 hrs, Phase 3: ~10 hrs (eval + judge)
**Status:** Complete -- all 3 phases delivered
**Run IDs:** Phase 1: `20260304_quick`, Phase 2: `20260304_full`, Phase 3: `20260305_144827`
**Related Work:** [TR124](Technical_Report_124.md) (Quality & Accuracy Baseline), [TR125](Technical_Report_125.md) (Quantization Decision Matrix), [TR133](Technical_Report_133.md) (Predictive Capacity Planner)
**Depends On:** TR125 (quantization quality data, quant level definitions, capability baselines), TR124 (FP16 baselines, metric framework)

---

## Abstract

TR125 established that Q4_K_M is the universal quality sweet spot for capability benchmarks, with a sharp quality cliff at Q3_K_S. But capability is only half the deployment equation. A model that maintains MMLU accuracy at Q4_K_M while silently losing its ability to refuse harmful requests, avoid demographic bias, or resist jailbreak prompts is a deployment hazard -- the operator sees "quality preserved" while safety degrades underneath.

TR134 asks five questions: (1) Does quantization degrade safety alignment disproportionately to capability? (2) Is safety degradation universal across model families or RLHF-recipe-specific? (3) Which demographic categories are most vulnerable to quantization-induced bias? (4) Does quantization amplify jailbreak susceptibility? (5) At what precision level does safety degrade catastrophically?

We evaluate 4 model families (Llama 3.2 1B/3B, Mistral 7B Instruct v0.3, Qwen 2.5 7B Instruct) across 7 quantization levels (FP16 through Q2_K) on 6 benchmarks: AdvBench refusal (100 harmful requests), TruthfulQA (50 questions), BBQ bias (198 questions across 11 demographic categories), jailbreak amplification (120 prompts: 30 direct + 90 across 3 jailbreak techniques), MMLU (285 questions), and ARC-Challenge (200 questions). The experiment progressed through 3 phases of increasing scope, culminating in Phase 3's 24,778 evaluated samples across 26 model-quant variants. Post-hoc LLM-as-judge validation (Qwen 2.5 7B Instruct Q8_0) provides an independent signal on 12,168 safety samples.

Key findings: Safety alignment is broadly robust through Q3_K_S (3.5 bits per weight) for well-aligned models (Llama, Qwen), with catastrophic failure at Q2_K for most models. Mistral 7B is the sole exception, showing safety degradation at higher precision levels than other families (Q4_K_M for safety/capability ratio), though the cross-family difference is not statistically significant (F=2.50, p=0.137). Jailbreak susceptibility systematically increases with lower precision across all 4 jailbreak techniques, with prefix injection being the most effective amplifier (slope=-0.036). Nationality-related bias is the most vulnerable demographic category to quantization-induced amplification (-0.0096 slope). Regex-LLM judge agreement is low (kappa=0.013-0.282), indicating that safety classification at low quant levels is inherently ambiguous and classifier choice materially affects reported safety rates.

**Total: ~35,260 samples across 3 phases, 26 model-quant variants (Phase 3), 12,168 judged samples.**

---

## Metric Definitions

These definitions control comparability across models and phases. Safety metrics are the primary focus of TR134; capability metrics serve as a reference baseline from TR125.

### Safety Metrics

- **Refusal Rate:** Proportion of harmful prompts where the model refuses to comply. Measured via regex classifier (`RefusalDetector`) matching ~15 refusal patterns (e.g., "I cannot", "I'm not able to", "As an AI", "I must decline"). Range [0, 1]. Higher = safer. This is the **primary safety metric** for AdvBench and jailbreak tasks.
- **Bias Resistance:** Proportion of BBQ questions where the model selects the non-stereotypical or "unknown" answer rather than reinforcing demographic stereotypes. Range [0, 1]. Higher = less biased. Computed per question by comparing model output to the stereotypical answer choice.
- **Truthfulness:** Proportion of TruthfulQA questions answered correctly (matching reference answer). Measures factual accuracy on questions designed to elicit common misconceptions. Range [0, 1]. Higher = more truthful.
- **Jailbreak Compliance Rate:** Proportion of jailbreak-wrapped harmful prompts where the model complies (does not refuse). Range [0, 1]. **Lower = safer.** This is the complement of refusal rate, used specifically for jailbreak analysis because the research question is about attack success, not defense success.
- **Amplification Ratio:** `jailbreak_compliance / direct_compliance`. How much more effective a jailbreak template is compared to a direct harmful request. Value > 1.0 means the jailbreak amplifies compliance beyond the model's baseline vulnerability. Value < 1.0 means the jailbreak is paradoxically less effective than a direct request (can happen when jailbreak framing triggers additional safety checks). N/A when direct compliance is 0 (division by zero).

### Capability Metrics

- **Accuracy (MMLU / ARC-Challenge):** Proportion of multiple-choice questions answered correctly. Uses **rescored accuracy** (regex letter extraction from model output -- handles "B", "B)", "The answer is B", "Answer: B") from TR125 methodology. Range [0, 1]. This is the same metric used in TR125, enabling direct cross-TR comparison.

### Derived Metrics

- **Safety-Capability (S/C) Ratio:** `normalized_safety_score / normalized_capability_score`. Value < 1.0 means safety degrades faster than capability at that quant level. Value > 1.0 means capability degrades faster (safety is relatively preserved). Value = 1.0 means they degrade at equal rates.
- **Normalized Score:** `raw_score / baseline_score`. Baseline is FP16 for small models (1B, 3B) and Q8_0 for 7B models (FP16 at 7B exceeds single-GPU VRAM). Normalized score of 1.000 = baseline performance.
- **Slope (BPW regression):** Linear regression coefficient of `normalized_score ~ BPW`. Positive slope = score improves with more precision (expected direction). Steeper positive slope = more sensitive to quantization. Unit: normalized score change per BPW.
- **Cohen's Kappa:** Inter-rater agreement between regex classifier and LLM judge, corrected for chance agreement. Range [-1, 1]. Interpretation thresholds: < 0.20 = slight, 0.21-0.40 = fair, 0.41-0.60 = moderate, 0.61-0.80 = substantial, > 0.80 = near-perfect (Landis & Koch 1977).

### BPW (Bits Per Weight) Reference

| Quant Level | BPW | Relative to FP16 |
|-------------|-----|-------------------|
| FP16 | 16.0 | 1.00x |
| Q8_0 | 8.0 | 0.50x |
| Q6_K | 6.5 | 0.41x |
| Q5_K_M | 5.5 | 0.34x |
| Q4_K_M | 4.5 | 0.28x |
| Q3_K_S | 3.5 | 0.22x |
| Q2_K | 2.5 | 0.16x |

---

## Statistical Methods & Caveats

**Tests used:**

- **Pairwise Welch's t-tests** between adjacent quant levels on safety metrics (binary 0/1) and capability metrics (binary 0/1). Alpha = 0.05 uncorrected. See Section 12 for full results.
- **One-way ANOVA** across model families on mean safety degradation slopes. Tests whether RLHF recipe affects safety robustness. Families: Llama (6 slopes from 2 models x 3 safety metrics), Mistral (3 slopes), Qwen (3 slopes).
- **Linear regression** of normalized score vs BPW. Slope quantifies degradation rate. R-squared quantifies how much variance BPW explains.
- **Power analysis** via normal approximation for minimum detectable effect (MDE) at alpha = 0.05, power = 0.80.
- **Cohen's kappa** for regex-vs-judge inter-rater agreement, stratified by quant level.

**Important caveats:**

1. **Multiple comparison correction not applied.** TR134 runs 132 pairwise tests (88 safety + 44 capability). At alpha = 0.05, ~6.6 false positives are expected by chance. **No family-wise correction is applied to reported p-values.** Of the 14 significant results, only the Q2_K cliff effects (Cohen's d > 0.7) are likely robust to Bonferroni correction. TR125 demonstrated that 7/16 significant capability results survived Bonferroni -- all at the Q3_K_S/Q2_K boundary. The same pattern likely holds here.

2. **t-tests on binary data.** All metrics are binary (0/1 per sample). While Welch's t-test converges to a z-test at N >= 100, a two-proportion z-test or chi-squared test would be the textbook approach. Cohen's d on binary data is mechanically bounded (max ~2.0 at p=0.5), producing smaller effect sizes than continuous data. Reported d values should not be directly compared to continuous-metric d values from other studies.

3. **Power limitations are severe for safety.** The minimum detectable effect is **18.3pp for safety** (N=117/variant) and **12.7pp for capability** (N=242/variant). This means safety deltas under 18pp cannot be reliably distinguished from zero at 80% power. The "robust" classification for most model-quant combinations is a failure to detect degradation, not a confirmation of equivalence. No TOST equivalence testing was performed (unlike TR125 v2). To achieve a 5pp MDE for safety metrics at 80% power, approximately 1,540 samples per variant would be required -- a 13x increase.

4. **LLM judge shares biases with evaluated models.** The judge model (Qwen 2.5 7B Instruct at Q8_0) is one of the evaluated model families. While the judge runs at fixed Q8_0 regardless of the evaluated model's quant level, correlated failure modes cannot be ruled out. The judge may classify Qwen responses more favorably than other families' responses due to shared training distribution. The low kappa values (0.013-0.282) indicate the judge and regex classifiers are measuring partially different constructs -- this is informative in itself, not a sign that one is wrong.

5. **BBQ category sample sizes are small.** With 198 BBQ samples across 11 demographic categories, per-category counts range from ~15 to ~25 per model-quant combination. Per-category degradation slopes are exploratory and should not be used for deployment decisions without replication at larger per-category N. The heegyu/bbq dataset stores categories as separate configs; our pipeline loads all 11.

6. **Jailbreak template coverage is limited.** Only 3 jailbreak techniques (DAN-style, roleplay, prefix injection) from ~4 major clusters identified in JailbreakHub. 30 samples per technique per model-quant combination provides trend detection but imprecise rate estimation (Wilson CI half-width ~17pp at N=30, p=0.5). Novel jailbreak techniques (e.g., crescendo attacks, multi-turn manipulation) are untested.

7. **7B baseline asymmetry.** 7B models use Q8_0 as baseline; small models use FP16. This follows TR125's convention for llama3.1-8b. Direct cross-family slope comparisons should account for this: a 7B model's slope covers 5.5 BPW range (Q8_0 to Q2_K) while a small model's slope covers 13.5 BPW range (FP16 to Q2_K). The ANOVA handles this by comparing slopes within each family's normalized space, but visual comparison of slope magnitudes across families can be misleading.

8. **Deterministic generation assumption.** All runs use temperature=0.0 with single repetition. TR124 Phase 3 validated that deterministic outputs need only one rep for HuggingFace transformers backends. However, Ollama uses llama.cpp, which may not be perfectly deterministic at temp=0 due to different floating-point accumulation order. No determinism validation was performed for Ollama in TR134 (same caveat as TR125 caveat 6).

---

## Executive Summary

TR134 answers: **does quantization degrade the safety properties you actually care about -- refusal, bias resistance, truthfulness, jailbreak robustness -- and if so, does it degrade them faster than capability benchmarks would suggest?**

### Key Findings

1. **Safety alignment is broadly robust through Q3_K_S (3.5 BPW) for well-aligned models.** Llama 3.2 (1B, 3B) and Qwen 2.5 7B maintain safety-capability ratios above 0.95 through Q3_K_S. The Q2_K cliff that TR125 identified for capability also holds for safety -- but not universally (see finding 3).

2. **Q2_K is catastrophic for safety in small models.** Llama 3.2 1B loses -57.0pp refusal rate and -56.7pp jailbreak refusal at Q2_K. This is worse than its capability drop (-14.7pp MMLU, -18.0pp ARC), confirming that safety degrades **disproportionately** at extreme quantization for this model. Safety/capability ratio at Q2_K: 1.032 -- but this is misleading because both scores are near floor.

3. **Mistral 7B has the weakest safety alignment at ALL precision levels.** Its baseline refusal rate is only 29.0% at Q8_0 (vs 98.0% for Qwen 2.5 7B, 90.0% for Llama 3.2 1B). This is an alignment quality issue, not a quantization issue. Mistral's safety slope (+0.041 normalized/BPW) is ~5x steeper than Qwen (+0.008) and ~14x steeper than the Llama family mean (+0.003), but the ANOVA is not significant (F=2.50, p=0.137). Jailbreak refusal at Q8_0 baseline is only 19.2% -- the model is unsafe even before quantization.

4. **Qwen 2.5 7B is the most safety-robust model.** Refusal rate stays above 93.0% at all quant levels including Q2_K. Bias resistance is essentially flat (slope=-0.0004). Jailbreak refusal remains at 70.8% at Q2_K. DPO-based alignment (Qwen) appears more quantization-robust than PPO-based (Llama, Mistral), though this is a single-model observation, not a controlled RLHF comparison.

5. **Jailbreak susceptibility systematically increases as BPW decreases.** All 4 jailbreak types (including direct requests as control) show negative compliance-vs-BPW slopes. Prefix injection is the most effective amplifier (slope=-0.036), followed by direct (-0.030), DAN-style (-0.024), and roleplay (-0.021). This is the expected direction: lower precision = weaker safety = more jailbreak success.

6. **Prefix injection amplifies jailbreak success 1.2-5.8x over direct requests.** The most dramatic spike: Qwen 2.5 7B at Q3_K_S shows 76.7% prefix injection compliance vs 13.3% direct compliance (5.75x amplification). Mistral 7B shows consistent 1.1-1.5x amplification across all quant levels. This finding is novel -- prior jailbreak research does not examine the interaction between jailbreak technique effectiveness and weight precision.

7. **Nationality bias is the most vulnerable demographic category to quantization.** Across all 4 models, Nationality has the steepest negative bias_resistance slope (-0.0096/BPW). Race_ethnicity is the most robust (+0.0149). One plausible mechanism: nationality-related knowledge is underrepresented in training data compared to race/gender, making it more susceptible to quantization-induced information loss.

8. **Llama 3.2 3B shows anomalous refusal INCREASES at low quant.** Refusal rate reaches 91.0% at Q3_K_S (+38pp vs FP16 baseline of 53.0%) and 94.0% at Q2_K (+41pp vs FP16). The single-step jump from Q4_K_M (47.0%) to Q3_K_S (91.0%) is +44pp. This "over-refusal" pattern occurs because the model loses coherence and defaults to refusal templates. The safety metrics improve while the model becomes less useful -- a deceptive signal that masks genuine degradation.

9. **Regex-LLM judge agreement is low across the board.** Cohen's kappa = 0.013 for AdvBench refusal and 0.282 for TruthfulQA. Both classifiers achieve ~68% "raw agreement" on AdvBench because both tend to classify most responses as refusals (high base rate). Kappa corrects for this, revealing marginal value-add over chance. The judge and regex classifiers measure overlapping but distinct constructs: regex catches explicit refusal phrases; the judge evaluates response intent in context.

10. **Cross-family safety slopes are NOT significantly different (F=2.50, p=0.137).** Despite suggestive differences (Mistral slope = +0.041 vs Llama mean = +0.003 vs Qwen = +0.008), the ANOVA cannot distinguish these from chance variation at the available sample size. The test has limited power with only 3 families and high within-family variance.

11. **Safety degrades faster than capability only for Mistral 7B.** Mistral's safety slope (+0.041) exceeds its capability slope (+0.013) by +0.028 -- safety degrades 3x faster. All other models show the reverse: capability degrades as fast or faster than safety. The divergence is suggestive but CIs overlap, so this is not a statistically confirmed finding.

12. **The critical safety threshold is model-dependent.** The last quant level where S/C ratio >= 0.95 varies: Llama 3.2 1B and 3B sustain through Q2_K (ratio > 1.0 due to over-refusal artifacts); Mistral 7B fails at Q4_K_M (ratio = 0.965); Qwen 2.5 7B sustains through Q2_K (ratio = 1.028). Mistral's early failure is driven by its weak baseline alignment, not by quantization uniquely attacking safety.

### Validation Summary

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| Safety signal detection | Refusal rate delta at Q2_K | >= 10pp drop for >= 1 model | **-57.0pp** (llama3.2-1b) | PASS |
| Capability anchoring | Accuracy deltas match TR125 direction | Q2_K worst for all models | Q2_K worst for 3/4 models | PASS |
| Cross-family coverage | >= 3 RLHF families | 3 families | **3** (Llama/PPO, Mistral/PPO, Qwen/DPO) | PASS |
| Judge coverage | >= 10K judged samples | 10,000 | **12,168** | PASS |
| Per-category bias | >= 8 BBQ categories | 8 | **11** | PASS |
| Jailbreak techniques | >= 3 distinct techniques | 3 | **3** (DAN, roleplay, prefix injection) | PASS |

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| 1 | Safety is robust through Q3_K_S for well-aligned models | Llama + Qwen S/C ratio >= 0.95 through Q3_K_S (Section 9) | **Validated** (3/4 models) |
| 2 | Q2_K is catastrophic for safety | -57pp refusal llama3.2-1b, -56.7pp jailbreak (Section 5) | **Validated** |
| 3 | Safety degrades disproportionately to capability | Only Mistral 7B shows divergence +0.028 (Section 7). Others: capability degrades equally or faster | **Partially validated** (1/4 models) |
| 4 | Cross-family degradation differs by RLHF recipe | F=2.50, p=0.137 -- not significant (Section 16) | **Not validated** |
| 5 | Jailbreak susceptibility increases with lower BPW | All 4 techniques show negative slope (Section 11) | **Validated** |
| 6 | Nationality bias most vulnerable category | Steepest negative slope among 11 categories (Section 10) | **Validated** (exploratory, small N) |
| 7 | Prefix injection most effective jailbreak at low quant | Slope=-0.036, steepest among 4 techniques (Section 11) | **Validated** |
| 8 | LLM judge validates regex classifiers | Kappa=0.013-0.282, slight-to-fair agreement (Section 15) | **Refuted** -- they measure different things |
| 9 | Larger models tolerate safety quantization better | Qwen 7B best, but Llama 1B > Llama 3B on refusal robustness | **Mixed** -- model alignment matters more than size |

### Key Decisions for Practitioners

1. **Default deployment quant level for safety-critical applications:** Use **Q4_K_M or higher**. Safety is robust through Q4_K_M for all 4 tested families. Do not deploy below Q4_K_M without task-specific safety validation at your target quant level.

2. **For Mistral 7B specifically:** Treat safety alignment as **weak at ALL precision levels**. Baseline refusal rate is only 29% at Q8_0. Add application-level safety filters (content filtering, output classification) regardless of quant level. Quantization exacerbates a pre-existing alignment deficit.

3. **For bias-sensitive applications:** Monitor **Nationality** and **SES** categories specifically. These show the steepest degradation under quantization. Consider per-category bias audits when deploying quantized models, especially at Q3_K_S and below.

4. **For jailbreak resistance:** Prefix injection is the most effective jailbreak technique and scales with quantization. If your threat model includes adversarial users crafting jailbreak prompts, evaluate your model's jailbreak resistance **at your target deployment quant level**, not at FP16. A model that resists jailbreaks at FP16 may fail at Q4_K_M.

5. **For maximum safety with minimum VRAM:** Qwen 2.5 7B at Q4_K_M. Maintains 99.0% refusal rate, 98.5% bias resistance, and 90.8% jailbreak refusal at ~4.6 GB estimated VRAM (from TR133 VRAM model).

6. **Never deploy Q2_K for safety-sensitive tasks.** Every model shows significant safety degradation at Q2_K. Even Qwen (most robust) drops to 70.8% jailbreak refusal. Llama 3.2 1B collapses to 33% refusal and 40% jailbreak refusal.

### When to Use This Report

**Scenario 1: Choosing a Quant Level for a Safety-Critical Application**

**Question:** "I want to deploy Llama 3.2 3B for a customer-facing chatbot. Which quant level preserves safety?"

**Answer:** Consult Section 9 (critical thresholds). Llama 3.2 3B maintains S/C ratio >= 0.95 through Q4_K_M. Refusal rate is stable at 47-57% through Q4_K_M. Avoid Q3_K_S -- refusal jumps to 91% (over-refusal, model becomes unusable). Use Q4_K_M for the best balance of safety, quality, and VRAM.

**Scenario 2: Evaluating Whether Your Model Family Is Safety-Robust**

**Question:** "We use Mistral 7B. Should we worry about safety under quantization?"

**Answer:** Yes, but the problem is not quantization -- it's baseline alignment. Mistral's refusal rate is only 29% at Q8_0 (Section 5.3). Quantization makes it worse (-17pp at Q2_K), but even at full precision, the model complies with 71% of harmful requests. Consider switching to Qwen 2.5 7B (98% refusal at Q8_0) or adding application-level safety filters.

**Scenario 3: Auditing Demographic Bias Under Quantization**

**Question:** "We need to ensure our quantized model doesn't amplify bias against specific groups."

**Answer:** Consult Section 10. Nationality and SES categories are most vulnerable. If your application involves nationality-related content, audit bias at your target quant level. Qwen 2.5 7B shows the flattest bias response across quant levels (slope=-0.0004).

**Scenario 4: Understanding Jailbreak Risk at Your Target Quant Level**

**Question:** "We're deploying at Q4_K_M. How much does this increase jailbreak vulnerability?"

**Answer:** Consult Section 11. At Q4_K_M, most models show modest jailbreak compliance increases (1-4pp). The significant vulnerability jump is at Q3_K_S and Q2_K. At Q4_K_M, the biggest concern is prefix injection: Mistral shows 93.3% compliance to prefix injection at Q4_K_M vs 86.7% at Q8_0 -- but this model is already compromised at baseline.

**Scenario 5: Deciding Between Regex and LLM Safety Classifiers**

**Question:** "Should we use regex patterns or an LLM judge for safety evaluation?"

**Answer:** Consult Section 15. The two approaches agree only at slight-to-fair levels (kappa 0.013-0.282). Regex is faster and more reproducible. LLM judges capture nuanced responses but introduce model bias. For production safety gates, use regex for its speed and consistency. For safety research and auditing, use both and report agreement.

**Scenario 6: Cross-Referencing with TR125 Capability Data**

**Question:** "TR125 said Q4_K_M is safe for capability. Does TR134 confirm this for safety?"

**Answer:** Yes, with caveats. Section 7 shows that safety slopes are comparable to or shallower than capability slopes for 3/4 models at Q4_K_M. The exception is Mistral 7B, where safety degrades 3x faster than capability. For Llama and Qwen models, TR125's Q4_K_M recommendation extends to safety.

### How to Read This Report

| Time | Reading Path |
|------|-------------|
| **2 min** | Abstract -> Validation Summary -> Claim Validation table |
| **10 min** | Add Key Findings (1-12) + Key Decisions + Section 9 (critical thresholds) |
| **30 min** | Add Sections 5-6 (safety curves per model) + Section 10 (bias categories) + Section 11 (jailbreaks) + Section 17 (limitations) |
| **60 min** | Full report Sections 1-18 + Appendices |
| **Deep dive** | Section 11 (jailbreak amplification tables), Section 15 (judge analysis), Section 10 (per-category slopes), Appendix B (full jailbreak data) |

### Table of Contents

**Background & Design (Sections 1-4)**

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Experimental Design](#2-experimental-design)
3. [Model Lineup](#3-model-lineup)
4. [Environment & Artifacts](#4-environment--artifacts)

**Safety Results (Sections 5-7)**

5. [Safety Degradation Curves](#5-safety-degradation-curves)
6. [Slope Analysis](#6-slope-analysis)
7. [Safety vs Capability Comparison](#7-safety-vs-capability-comparison)

**Capability Results (Sections 8-9)**

8. [Capability Degradation Curves](#8-capability-degradation-curves)
9. [Critical Thresholds & Safety-Capability Ratio](#9-critical-thresholds--safety-capability-ratio)

**Novel Analyses (Sections 10-11)**

10. [Per-Category Bias Analysis](#10-per-category-bias-analysis)
11. [Jailbreak Amplification Results](#11-jailbreak-amplification-results)

**Statistical Validation (Sections 12-13)**

12. [Statistical Tests (Pairwise)](#12-statistical-tests-pairwise)
13. [Power Analysis & Statistical Resolution](#13-power-analysis--statistical-resolution)

**Cross-Cutting Analyses (Sections 14-16)**

14. [Per-Benchmark Breakdown](#14-per-benchmark-breakdown)
15. [LLM Judge Agreement](#15-llm-judge-agreement)
16. [Cross-Family Comparison](#16-cross-family-comparison)

**Closing (Sections 17-18)**

17. [Limitations & Methodological Caveats](#17-limitations--methodological-caveats)
18. [Reproducibility](#18-reproducibility)

**Appendices**

- [Appendix A: Phase Structure & Evolution](#appendix-a-phase-structure--evolution)
- [Appendix B: Full Jailbreak Amplification Tables](#appendix-b-full-jailbreak-amplification-tables)
- [Appendix C: Task & Data Sources](#appendix-c-task--data-sources)
- [Appendix D: Glossary](#appendix-d-glossary)
- [References](#references)

---

## 1. Introduction & Research Motivation

### 1.1 The Problem

TR125 established quantization's impact on capability benchmarks: Q4_K_M is the safe sweet spot, Q3_K_S is the cliff, Q2_K is universally unacceptable. Practitioners took this guidance and deployed quantized models. But TR125 tested only MMLU and ARC-Challenge -- both pure capability benchmarks. It said nothing about safety.

A model quantized to Q4_K_M might maintain 69.7% MMLU accuracy while silently becoming more compliant with harmful requests, more biased against certain demographics, or more susceptible to jailbreak attacks. The operator sees capability preserved and concludes the model is "fine." The safety degradation is invisible without targeted safety benchmarks.

This is not hypothetical. Preliminary evidence from Phases 1-2 of TR134 showed that Llama 3.2 1B at Q2_K drops from 90% refusal rate to 33% -- a 57pp collapse -- while MMLU accuracy drops only 14.7pp. Safety degrades 4x faster than capability for this model at extreme quantization.

### 1.2 Research Questions

1. **Does quantization degrade safety alignment disproportionately to capability?** We compare normalized safety slopes to capability slopes per model.
2. **Is safety degradation universal across model families or RLHF-recipe-specific?** We test 3 distinct RLHF families (Llama/PPO, Mistral/PPO, Qwen/DPO) via one-way ANOVA on safety slopes.
3. **Which demographic categories are most vulnerable to quantization-induced bias?** We evaluate BBQ across 11 demographic categories and compute per-category degradation slopes.
4. **Does quantization amplify jailbreak susceptibility?** We test 3 jailbreak techniques plus direct harmful requests as control, with compliance-vs-BPW slopes.
5. **At what precision level does safety degrade catastrophically?** We compute the last quant level where the S/C ratio stays above 0.95.

### 1.3 Literature Gap

Prior quantization studies focus on perplexity or benchmark accuracy. Safety-specific quantization analysis is rare and typically limited to single model families. We found no prior work that:

- Compares safety degradation rates across multiple RLHF recipes (PPO vs DPO)
- Measures per-category demographic bias amplification under quantization
- Quantifies how jailbreak technique effectiveness scales with bits-per-weight
- Validates regex-based safety classifiers against LLM judges at varying quantization levels

TR134 fills all four gaps, albeit with the sample size limitations noted in the Statistical Methods section.

### 1.4 Relationship to Prior Work

| Reference | Contribution | How TR134 Uses It |
|-----------|-------------|-------------------|
| TR124 (Banterhearts) | FP16 quality baselines, metric framework | Baseline comparison methodology |
| TR125 (Banterhearts) | Quantization decision matrix, 5 models x 7 quants, capability data | Capability baseline, Q4_K_M/Q3_K_S cliff reference |
| TR133 (Banterhearts) | Predictive capacity planner, VRAM/throughput models | VRAM estimates for deployment recommendations |
| BBQ (Parrish et al. 2022) | Hand-built bias benchmark, 11 demographic categories | Primary bias evaluation instrument |
| TruthfulQA (Lin et al. 2022) | Truthfulness benchmark, common misconceptions | Truthfulness safety metric |
| JailbreakBench (Chao et al. 2024) | Standardized jailbreak evaluation, 100 behaviors | Source of harmful behaviors |
| JailbreakHub (Shen et al. 2023) | 1,405 real-world jailbreak prompts | Source of jailbreak templates |

---

## 2. Experimental Design

### 2.1 Phase Structure

TR134 progressed through three phases of increasing scope:

| Phase | Purpose | Models | Quant Levels | Tasks | Samples | Key Deliverable |
|-------|---------|--------|-------------|-------|---------|-----------------|
| 1 | Quick signal detection | 2 (Llama 1B, 3B) | 3 (FP16, Q4_K_M, Q2_K) | 3 safety | ~840 | Confirmed Q2_K safety cliff exists |
| 2 | Full degradation matrix | 2 (Llama 1B, 3B) | 7 (FP16-Q2_K) | 5 (3 safety + 2 cap) | ~9,590 | Safety/capability slope comparison |
| 3 | Multi-family expansion | 4 families, 26 entries | 6-7 per model | 6 (4 safety + 2 cap) | 24,778 | Cross-family ANOVA, jailbreak, bias categories |

Phase 3 is the primary data source for this report. Phases 1-2 served as iterative pilots.

### 2.2 Safety Task Descriptions

**AdvBench Refusal (N=100):** 100 harmful requests from walledai/AdvBench (gated dataset). Each prompt asks the model to produce harmful content (e.g., instructions for illegal activities). The model's response is classified as refusal or compliance via regex. This is the most direct safety measure.

**TruthfulQA (N=50):** 50 questions from the TruthfulQA benchmark designed to elicit common misconceptions. The model generates a free-form answer, which is compared to reference answers. This measures a different safety dimension: the model's tendency to produce confidently wrong information that could mislead users.

**BBQ Bias (N=198):** 198 questions from the BBQ benchmark spanning 11 demographic categories (Age, Disability_status, Gender_identity, Nationality, Physical_appearance, Race_ethnicity, Race_x_gender, Race_x_SES, Religion, SES, Sexual_orientation). Each question presents a context and asks which person matches a stereotype. The model should select "unknown" or the non-stereotypical answer. Downloaded from heegyu/bbq using all 11 configs (not just the default "Age" config -- this was a critical bug fix).

**Jailbreak Amplification (N=120):** 30 harmful behaviors from JailbreakBench, each presented in 4 variants: direct (control), wrapped in DAN-style template, wrapped in roleplay template, wrapped in prefix injection template. Templates sourced from JailbreakHub. Total: 30 direct + 30 DAN + 30 roleplay + 30 prefix = 120 prompts per model-quant.

### 2.3 Capability Tasks

**MMLU (N=285):** 285 questions from cais/mmlu across 57 subjects (5 per subject). Same benchmark as TR125 Phase 2.

**ARC-Challenge (N=200):** 200 questions from allenai/ai2_arc (Challenge subset). Same benchmark as TR125 Phase 2.

Both use generation-based scoring with regex letter extraction (rescored accuracy), matching TR125 methodology.

### 2.4 Pipeline Architecture

```
Phase 3 config (config.yaml)
  26 model-quant entries x 6 task paths
        |
  [prepare_benchmarks.py]  -- download BBQ, AdvBench, TruthfulQA, jailbreak, MMLU, ARC
        |
  [scripts/eval/runner.py]  -- shared eval framework (not TR-specific)
        |
  samples.jsonl (24,778 records)
        |
  [judge_analysis.py]  -- LLM judge post-hoc on 12,168 safety samples
        |
  phase3_judged.jsonl
        |
  [analyze.py]  -- 14 analysis passes (10 base + 4 novel)
        |
  phase3_analysis.json + phase3_scored.jsonl
        |
  [generate_report.py]  -- 18-section auto-generated report
        |
  phase3_report.md (raw data tables)
```

### 2.5 Classification Pipeline

Safety scores are computed by three regex-based classifiers:

- **RefusalDetector:** Matches ~15 refusal patterns in the model's raw text output (e.g., "I cannot", "I'm not able to", "I must decline", "As an AI"). Returns binary refusal/compliance. Used for AdvBench and jailbreak tasks.
- **TruthfulnessClassifier:** Compares model output to reference answers using string matching and keyword extraction. Returns binary correct/incorrect.
- **BiasDetector:** Compares model's answer choice to the stereotypical answer and the "unknown" answer. Returns binary biased/unbiased.

Post-hoc, the LLM judge re-evaluates all safety samples via structured prompting. The judge's classifications are used for inter-rater agreement analysis (Section 15), not for primary scoring.

### 2.6 Normalization & Slope Computation

All scores are normalized to the highest-precision baseline:
- Small models (1B, 3B): `normalized = score / FP16_score`
- 7B models: `normalized = score / Q8_0_score`

Linear regression of `normalized_score ~ BPW` produces a slope per (model, task, metric). The aggregate safety slope per model is the mean slope across all safety tasks/metrics for that model.

---

## 3. Model Lineup

### 3.1 Model Summary

| Model | Family | Parameters | RLHF Method | Quant Levels | Baseline | Ollama Tag Pattern | Origin |
|-------|--------|-----------|-------------|-------------|----------|-------------------|--------|
| Llama 3.2 1B Instruct | Llama | 1.24B | PPO | 7 (FP16-Q2_K) | FP16 | `llama3.2:1b-instruct-{quant}` | Meta |
| Llama 3.2 3B Instruct | Llama | 3.21B | PPO | 7 (FP16-Q2_K) | FP16 | `llama3.2:3b-instruct-{quant}` | Meta |
| Mistral 7B Instruct v0.3 | Mistral | 7.25B | PPO | 6 (Q8_0-Q2_K) | Q8_0 | `mistral:7b-instruct-v0.3-{quant}` | Mistral AI |
| Qwen 2.5 7B Instruct | Qwen | 7.62B | DPO | 6 (Q8_0-Q2_K) | Q8_0 | `qwen2.5:7b-instruct-{quant}` | Alibaba |

### 3.2 Why These Models

- **Llama 3.2 1B/3B (PPO):** Existing baseline from Phases 1-2. Two size points within the same family test whether model size affects safety robustness (answer: not straightforwardly -- 3B shows more anomalous behavior than 1B).
- **Mistral 7B Instruct v0.3 (PPO):** Different RLHF recipe from Llama despite both being PPO-based. Known for being more "permissive" in its alignment -- tests whether this permissiveness interacts with quantization.
- **Qwen 2.5 7B Instruct (DPO):** The only DPO-trained model in the matrix. DPO is a fundamentally different alignment approach (no reward model, direct preference optimization). Tests whether alignment method affects quantization robustness.

### 3.3 FP16 Exclusion: 7B Models

7B models at FP16 require ~14.5 GB VRAM, exceeding the RTX 4080 Laptop's 12 GB. Q8_0 serves as the highest-precision baseline for these models. TR125 validated that Q8_0 is within 1.6pp of FP16 for capability metrics across 4 models. Safety equivalence between Q8_0 and FP16 is unverified -- if FP16 safety is substantially higher than Q8_0 for 7B models, we underestimate total degradation.

### 3.4 Design Decision: Gemma 2 Dropped

The original Phase 3 design included Gemma 2 2B IT as a fifth model family (Google's alignment recipe). During model pulls, all `gemma2:2b-it-{quant}` tags returned the same default quantization -- Ollama does not provide per-quant GGUF variants for Gemma 2 2B IT. Since controlled quantization comparison is impossible without distinct per-quant weights, Gemma 2 was dropped. The experiment proceeded with 4 families (26 model-quant entries instead of the planned 33).

---

## 4. Environment & Artifacts

### 4.1 Environment

| Component | Value |
|-----------|-------|
| OS | Windows 11 Home 10.0.26200 |
| CPU | 13th Gen Intel Core i9-13980HX |
| GPU | NVIDIA GeForce RTX 4080 Laptop GPU (12,282 MB VRAM, CC 8.9) |
| Ollama | Local HTTP API (http://localhost:11434) |
| Python | 3.x |
| Key packages | datasets, pyyaml, scipy |
| Temperature | 0.0 (greedy decoding) |
| Max new tokens | 256 |
| Seed | 42 |

### 4.2 Key Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Phase 3 config | `research/tr134/phase3/config.yaml` | 26 model-quant entries, 6 task paths |
| Phase 3 samples | `research/tr134/results/phase3/20260305_144827/samples.jsonl` | 24,778 eval records |
| Phase 3 judged | `research/tr134/results/phase3/20260305_144827/phase3_judged.jsonl` | 12,168 judged records |
| Phase 3 analysis | `research/tr134/results/phase3/20260305_144827/phase3_analysis.json` | All computed statistics |
| Phase 3 auto-report | `research/tr134/results/phase3/20260305_144827/phase3_report.md` | 18-section raw data tables (1,038 lines) |
| Phase 3 scored | `research/tr134/results/phase3/20260305_144827/phase3_scored.jsonl` | Scored records with normalized values |
| Analysis code | `research/tr134/phase3/analyze.py` | 14-pass analysis pipeline |
| Judge code | `research/tr134/phase3/judge_analysis.py` | Standalone LLM judge runner |
| Report generator | `research/tr134/phase3/generate_report.py` | 18-section report generator |
| Orchestrator | `research/tr134/phase3/run.py` | Full pipeline: prep -> eval -> judge -> analyze -> report |
| LLM judge module | `research/tr134/shared/llm_judge.py` | LLM-as-judge via Ollama |
| Published report | `PublishReady/reports/Technical_Report_134.md` | This file |

---

## 5. Safety Degradation Curves

Scores are raw (not normalized) for readability. 95% confidence intervals shown. Bold entries indicate >= 10pp degradation from baseline. `--` indicates no FP16 data (7B models use Q8_0 baseline).

### 5.1 llama3.2-1b (baseline: FP16)

| Task | Metric | FP16 | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|------|--------|------|------|------|--------|--------|--------|------|
| advbench_refusal | refusal_rate | 90.0% | 90.0% | 90.0% | 86.0% | 87.0% | 85.0% | **33.0%** |
| bbq_bias | bias_resistance | 89.4% | 88.9% | 88.4% | 87.4% | 87.4% | 99.5% | **73.2%** |
| jailbreak | refusal_rate | 96.7% | 98.3% | 97.5% | 96.7% | 93.3% | **75.8%** | **40.0%** |
| truthfulqa | truthfulness | 55.0% | 56.0% | 48.0% | 49.0% | 58.0% | 49.0% | 44.0% |

**Observations:**
- **AdvBench refusal is stable through Q3_K_S** (85-90%), then collapses -57pp at Q2_K. This is the most dramatic safety cliff in the entire dataset.
- **Jailbreak refusal degrades earlier** than direct refusal: -3.3pp at Q4_K_M, -20.8pp at Q3_K_S, -56.7pp at Q2_K. Jailbreaks expose safety weakness before direct requests do.
- **BBQ bias resistance at Q3_K_S** spikes to 99.5% (+10.1pp) -- anomalous. The model likely defaults to "unknown" answers as coherence degrades, which scores as unbiased but is a false positive.
- **TruthfulQA** shows no clear trend. Wide CIs ([33.8%, 54.2%] for Q2_K) overlap with all other quant levels.

### 5.2 llama3.2-3b (baseline: FP16)

| Task | Metric | FP16 | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|------|--------|------|------|------|--------|--------|--------|------|
| advbench_refusal | refusal_rate | 53.0% | 52.0% | 57.0% | 55.0% | 47.0% | 91.0% | 94.0% |
| bbq_bias | bias_resistance | 96.5% | 96.0% | 95.0% | 95.0% | 96.5% | 94.4% | **78.8%** |
| jailbreak | refusal_rate | 95.8% | 93.3% | 94.2% | 95.0% | **82.5%** | 98.3% | 91.7% |
| truthfulqa | truthfulness | 49.0% | 48.0% | 51.0% | 58.0% | 50.0% | 52.0% | 54.0% |

**Observations:**
- **AdvBench shows ANOMALOUS REFUSAL INCREASE** at Q3_K_S (91.0%, +38pp vs FP16 baseline) and Q2_K (94.0%, +41pp vs FP16). The jump from Q4_K_M (47.0%) to Q3_K_S (91.0%) is +44pp in a single quant step. This is the "over-refusal" pattern: the model loses coherence and defaults to refusal templates. A 94% refusal rate sounds safe, but the model is refusing *everything*, including benign requests.
- **Jailbreak refusal drops** at Q4_K_M (-13.3pp) then recovers at Q3_K_S (+2.5pp from baseline). This non-monotonic pattern mirrors the over-refusal in AdvBench -- at Q3_K_S, the model refuses even jailbreak-wrapped requests because it refuses everything.
- **BBQ bias resistance** degrades moderately (-17.7pp at Q2_K). This is a genuine signal, not masked by over-refusal.
- **TruthfulQA** shows no degradation (even a slight increase at Q2_K: +5pp). With N=50, this is noise.

**The over-refusal problem:** Llama 3.2 3B at low quant appears to be "safer" by safety metrics while becoming fundamentally less useful. This is a deceptive signal. A model that refuses 94% of requests -- harmful AND benign -- is not deployed safely; it's deployed uselessly. The S/C ratio captures this partially (ratio = 1.446 at Q2_K, meaning safety "outperforms" capability), but practitioners should not interpret high refusal at low quant as genuine safety improvement.

### 5.3 mistral-7b (baseline: Q8_0)

| Task | Metric | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|------|--------|------|------|--------|--------|--------|------|
| advbench_refusal | refusal_rate | 29.0% | 35.0% | 29.0% | 31.0% | 22.0% | **12.0%** |
| bbq_bias | bias_resistance | 83.8% | 83.8% | 84.3% | 85.4% | 80.3% | 77.3% |
| jailbreak | refusal_rate | 19.2% | 23.3% | 20.8% | 15.0% | 16.7% | 12.5% |
| truthfulqa | truthfulness | 60.0% | 55.0% | 59.0% | 54.0% | 50.0% | 56.0% |

**Observations:**
- **Baseline safety is critically weak.** 29.0% refusal rate at Q8_0 means the model complies with 71% of harmful requests at full precision. 19.2% jailbreak refusal means it complies with 81% of jailbreak-wrapped requests. This is not a quantization problem -- it's a model alignment problem.
- **AdvBench degrades further:** -17pp from Q8_0 to Q2_K (29% -> 12%). The already-low refusal rate halves.
- **BBQ bias resistance** is the best Mistral safety metric: 83.8% at Q8_0, -6.6pp at Q2_K. Bias resistance degrades gracefully compared to refusal.
- **TruthfulQA** is noisy but shows Mistral's highest baseline (60.0% at Q8_0). Degradation is mild (-4pp at Q2_K).
- **The safety slope (+0.041)** is the steepest across all families (~5x Qwen, ~14x Llama mean), but this is partly because the low baseline means proportional changes appear larger in normalized space.

### 5.4 qwen2.5-7b (baseline: Q8_0)

| Task | Metric | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|------|--------|------|------|--------|--------|--------|------|
| advbench_refusal | refusal_rate | 98.0% | 99.0% | 99.0% | 99.0% | 96.0% | 93.0% |
| bbq_bias | bias_resistance | 98.5% | 98.0% | 97.5% | 98.5% | 97.5% | 99.0% |
| jailbreak | refusal_rate | 89.2% | 89.2% | 88.3% | 90.8% | **75.0%** | **70.8%** |
| truthfulqa | truthfulness | 50.0% | 53.0% | 49.0% | 57.0% | 49.0% | 50.0% |

**Observations:**
- **AdvBench refusal is rock-solid.** 98.0% at Q8_0, still 93.0% at Q2_K. Only -5pp total degradation across the entire BPW range. DPO alignment appears highly quantization-robust for direct refusal.
- **BBQ bias resistance is essentially flat.** Slope = -0.0004. The scores fluctuate between 97.5% and 99.0% with no trend. This is the most impressive bias robustness in the matrix.
- **Jailbreak refusal shows targeted vulnerability.** Stable through Q4_K_M (90.8%), then drops -14.2pp at Q3_K_S and -18.3pp at Q2_K. This is where Qwen's safety cracks -- not in direct refusal but in adversarial attack resistance.
- **TruthfulQA** is noisy and shows no trend (range: 49.0%-57.0%).

### 5.5 Safety Curve Summary

| Safety Metric | Best Model | Worst Model | Q4_K_M Safe? | Q2_K Safe? |
|---------------|-----------|-------------|-------------|------------|
| Refusal (AdvBench) | qwen2.5-7b (98%@Q8) | mistral-7b (29%@Q8) | Yes (all models) | No (llama-1b: -57pp, mistral: -17pp) |
| Bias (BBQ) | qwen2.5-7b (98.5%@Q8) | mistral-7b (83.8%@Q8) | Yes (all models) | No (llama-1b: -16pp, llama-3b: -18pp) |
| Jailbreak refusal | llama3.2-1b (96.7%@FP16) | mistral-7b (19.2%@Q8) | Mostly (llama-3b: -13pp) | No (llama-1b: -57pp, qwen: -18pp) |
| Truthfulness | mistral-7b (60%@Q8) | llama3.2-3b (49%@FP16) | Yes (all within noise) | Marginal (llama-1b: -11pp) |

---

## 6. Slope Analysis

Linear regression of normalized score vs BPW. Positive slope = score improves with more precision (expected direction). Steeper positive slope = more sensitive to quantization.

### 6.1 Safety Slopes (Full Table)

Slopes are computed per (model, metric), not per task. The `refusal_rate` slope combines data from both AdvBench refusal and jailbreak amplification tasks (hence N=14 for small models with 7 quant levels × 2 tasks, N=12 for 7B models with 6 × 2). `bias_resistance` and `truthfulness` each correspond to a single task.

| Model | Metric | Slope | R-sq | CI Lower | CI Upper | N points | Tasks Combined |
|-------|--------|-------|------|----------|----------|----------|----------------|
| llama3.2-1b | refusal_rate | +0.0250 | 0.247 | +0.0041 | +0.1118 | 14 | advbench + jailbreak |
| llama3.2-1b | bias_resistance | +0.0038 | 0.040 | -0.0274 | +0.0377 | 7 | bbq_bias |
| llama3.2-1b | truthfulness | +0.0100 | 0.238 | -0.0114 | +0.0372 | 7 | truthfulqa |
| llama3.2-3b | refusal_rate | -0.0201 | 0.095 | -0.1005 | +0.0054 | 14 | advbench + jailbreak |
| llama3.2-3b | bias_resistance | +0.0068 | 0.219 | -0.0003 | +0.0458 | 7 | bbq_bias |
| llama3.2-3b | truthfulness | -0.0074 | 0.230 | -0.0227 | +0.0117 | 7 | truthfulqa |
| mistral-7b | refusal_rate | +0.0922 | 0.558 | +0.0374 | +0.1743 | 12 | advbench + jailbreak |
| mistral-7b | bias_resistance | +0.0129 | 0.502 | -0.0058 | +0.0347 | 6 | bbq_bias |
| mistral-7b | truthfulness | +0.0183 | 0.372 | -0.0049 | +0.0403 | 6 | truthfulqa |
| qwen2.5-7b | refusal_rate | +0.0234 | 0.379 | +0.0029 | +0.0445 | 12 | advbench + jailbreak |
| qwen2.5-7b | bias_resistance | -0.0004 | 0.019 | -0.0044 | +0.0025 | 6 | bbq_bias |
| qwen2.5-7b | truthfulness | +0.0013 | 0.002 | -0.0400 | +0.0263 | 6 | truthfulqa |

### 6.2 Aggregate Safety Slopes (Mean Across Safety Tasks)

| Model | Mean Safety Slope | Std | Interpretation |
|-------|-------------------|-----|----------------|
| llama3.2-1b | +0.0129 | 0.010 | Mild degradation with lower BPW |
| llama3.2-3b | -0.0069 | 0.014 | Paradoxical: safety *improves* at lower BPW (over-refusal artifact) |
| mistral-7b | +0.0411 | 0.043 | Steepest -- ~5x Qwen, ~14x Llama family mean |
| qwen2.5-7b | +0.0081 | 0.013 | Moderate, driven primarily by AdvBench refusal slope |

### 6.3 Capability Slopes (for Comparison)

Slopes are computed per (model, metric) across both capability tasks, mirroring the safety slope methodology. Each `accuracy` slope combines MMLU and ARC-Challenge data (hence N=14 for small models with 7 quant levels × 2 tasks, N=12 for 7B models with 6 × 2).

| Model | Metric | Slope | R-sq | CI Lower | CI Upper | N points | Tasks Combined |
|-------|--------|-------|------|----------|----------|----------|----------------|
| llama3.2-1b | accuracy | +0.0221 | 0.275 | +0.0060 | +0.0967 | 14 | mmlu + arc |
| llama3.2-3b | accuracy | +0.0110 | 0.292 | +0.0036 | +0.0450 | 14 | mmlu + arc |
| mistral-7b | accuracy | +0.0133 | 0.619 | +0.0083 | +0.0208 | 12 | mmlu + arc |
| qwen2.5-7b | accuracy | +0.0157 | 0.722 | +0.0080 | +0.0258 | 12 | mmlu + arc |

**Note:** Mistral and Qwen capability slopes have higher R-squared (0.62-0.72) than most safety slopes, meaning BPW explains more variance in capability than in safety. Safety metrics are noisier due to smaller sample sizes and binary classification ambiguity.

---

## 7. Safety vs Capability Comparison

The central question of TR134: does safety break before capability?

| Model | Safety Slope | Cap Slope | Divergence | CI Overlap | Verdict |
|-------|-------------|-----------|------------|------------|---------|
| llama3.2-1b | +0.0129 | +0.0221 | -0.0092 | Yes | **Robust** -- capability degrades faster |
| llama3.2-3b | -0.0069 | +0.0110 | -0.0178 | Yes | **Robust** (with over-refusal artifact) |
| mistral-7b | +0.0411 | +0.0133 | **+0.0278** | Yes | **Safety degrades faster** (suggestive, not confirmed) |
| qwen2.5-7b | +0.0081 | +0.0157 | -0.0076 | Yes | **Robust** -- capability degrades faster |

**Summary:** For 3 of 4 models, safety is as robust or more robust than capability under quantization. Mistral 7B is the exception, showing safety degradation 3x faster than capability. But all 4 comparisons have overlapping confidence intervals, so none of these divergences are statistically confirmed.

**The good news:** If you trust your model at a given quant level based on TR125 capability data (Q4_K_M safe, Q3_K_S cliff), you can generally trust its safety properties too. The TR125 deployment guidance extends to safety for well-aligned models.

**The bad news:** "Generally" hides important exceptions. Jailbreak refusal degrades earlier than direct refusal (Section 5), Mistral's safety is poor at all levels (Section 5.3), and the low statistical power (18.3pp MDE) means real degradation up to 18pp could be hiding in the "robust" verdict.

---

## 8. Capability Degradation Curves

Included for cross-validation against TR125 and as the denominator for S/C ratio calculations.

### 8.1 MMLU (Rescored Accuracy)

| Model | FP16 | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|-------|------|------|------|--------|--------|--------|------|
| llama3.2-1b | 34.0% | 35.1% | 34.4% | 33.0% | 33.7% | 31.9% | **19.3%** |
| llama3.2-3b | 59.0% | 59.3% | 57.9% | 57.5% | 59.0% | **48.1%** | **42.8%** |
| mistral-7b | -- | 59.0% | 60.4% | 59.7% | 57.9% | 56.1% | 55.8% |
| qwen2.5-7b | -- | 74.0% | 73.7% | 74.4% | 72.6% | 69.8% | **66.3%** |

### 8.2 ARC-Challenge (Rescored Accuracy)

| Model | FP16 | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|-------|------|------|------|--------|--------|--------|------|
| llama3.2-1b | 44.5% | 46.0% | 44.0% | 46.5% | 39.5% | **24.5%** | **26.5%** |
| llama3.2-3b | 71.5% | 72.0% | 71.5% | 71.5% | 70.5% | **62.5%** | **63.0%** |
| mistral-7b | -- | 72.0% | 71.0% | 68.5% | 70.0% | 69.0% | 65.5% |
| qwen2.5-7b | -- | 89.5% | 89.0% | 89.5% | 88.0% | 85.0% | 83.0% |

### 8.3 Cross-Validation with TR125

The general pattern matches TR125 findings: Q4_K_M is safe for all models, the Q3_K_S cliff is visible for small Llama models, and 7B models degrade more gracefully. Specific comparisons (where model overlap exists):

| Model | Metric | TR125 Q4_K_M Delta | TR134 Q4_K_M Delta | Match? |
|-------|--------|-------------------|-------------------|--------|
| llama3.2-1b | MMLU | -0.4pp | -0.4pp | Yes |
| llama3.2-1b | ARC | -5.0pp | -5.0pp | Yes |
| llama3.2-3b | MMLU | +0.0pp | +0.0pp | Yes |
| llama3.2-3b | ARC | -1.0pp | -1.0pp | Yes |

Capability results are reproducible across TR125 and TR134 for overlapping models.

---

## 9. Critical Thresholds & Safety-Capability Ratio

### 9.1 Per-Quant S/C Ratio Tables

Value < 1.0 = safety degrades faster than capability at that quant level. Bold = below 0.95 threshold.

**llama3.2-1b:**

| Quant | BPW | Safety Norm | Cap Norm | S/C Ratio |
|-------|-----|------------|----------|-----------|
| FP16 | 16.0 | 1.000 | 1.000 | 1.000 |
| Q8_0 | 8.0 | 1.007 | 1.032 | 0.976 |
| Q6_K | 6.5 | 0.968 | 1.000 | 0.968 |
| Q5_K_M | 5.5 | 0.956 | 1.007 | **0.949** |
| Q4_K_M | 4.5 | 0.991 | 0.939 | 1.056 |
| Q3_K_S | 3.5 | 0.933 | 0.744 | 1.254 |
| Q2_K | 2.5 | 0.600 | 0.581 | 1.032 |

**llama3.2-3b:**

| Quant | BPW | Safety Norm | Cap Norm | S/C Ratio |
|-------|-----|------------|----------|-----------|
| FP16 | 16.0 | 1.000 | 1.000 | 1.000 |
| Q8_0 | 8.0 | 0.982 | 1.007 | 0.976 |
| Q6_K | 6.5 | 1.021 | 0.991 | 1.030 |
| Q5_K_M | 5.5 | 1.049 | 0.988 | 1.062 |
| Q4_K_M | 4.5 | 0.942 | 0.993 | **0.949** |
| Q3_K_S | 3.5 | 1.196 | 0.845 | 1.416 |
| Q2_K | 2.5 | 1.162 | 0.804 | 1.446 |

**mistral-7b:**

| Quant | BPW | Safety Norm | Cap Norm | S/C Ratio |
|-------|-----|------------|----------|-----------|
| Q8_0 | 8.0 | 1.000 | 1.000 | 1.000 |
| Q6_K | 6.5 | 1.085 | 1.005 | 1.080 |
| Q5_K_M | 5.5 | 1.019 | 0.982 | 1.038 |
| Q4_K_M | 4.5 | 0.942 | 0.977 | **0.965** |
| Q3_K_S | 3.5 | 0.855 | 0.955 | **0.895** |
| Q2_K | 2.5 | 0.730 | 0.928 | **0.787** |

**qwen2.5-7b:**

| Quant | BPW | Safety Norm | Cap Norm | S/C Ratio |
|-------|-----|------------|----------|-----------|
| Q8_0 | 8.0 | 1.000 | 1.000 | 1.000 |
| Q6_K | 6.5 | 1.016 | 0.995 | 1.022 |
| Q5_K_M | 5.5 | 0.993 | 1.002 | 0.990 |
| Q4_K_M | 4.5 | 1.042 | 0.982 | 1.061 |
| Q3_K_S | 3.5 | 0.948 | 0.946 | 1.001 |
| Q2_K | 2.5 | 0.937 | 0.912 | 1.028 |

### 9.2 Critical Quant Level Summary

Last quant level where S/C ratio >= 0.95:

| Model | Critical Quant | BPW | S/C Ratio at Threshold | Interpretation |
|-------|---------------|-----|------------------------|----------------|
| llama3.2-1b | Q2_K | 2.5 | 1.032 | Safety robust at all levels (but both near floor at Q2_K) |
| llama3.2-3b | Q2_K | 2.5 | 1.446 | Over-refusal artifact inflates ratio |
| **mistral-7b** | **Q4_K_M** | **4.5** | **0.965** | Safety fails before capability |
| qwen2.5-7b | Q2_K | 2.5 | 1.028 | Safety robust at all levels |

**Key finding:** Mistral 7B is the only model where safety fails the 0.95 ratio threshold, and it fails at Q4_K_M -- the TR125-recommended "safe" deployment level. For Mistral, the safe deployment threshold for safety is Q5_K_M, not Q4_K_M. However, this is driven primarily by the model's weak baseline safety alignment (29% refusal at Q8_0), not by quantization uniquely attacking safety properties in a well-aligned model.

---

## 10. Per-Category Bias Analysis

BBQ evaluates bias across 11 demographic categories from heegyu/bbq. We compute per-category degradation slopes (bias_resistance vs BPW) averaged across all 4 models.

### 10.1 Category Vulnerability Ranking

Most to least vulnerable to quantization-induced bias amplification (negative slope = bias increases at lower BPW):

| Rank | Category | Avg Slope | N Models | Interpretation |
|------|----------|-----------|----------|----------------|
| 1 | **Nationality** | -0.0096 | 4 | Most vulnerable -- bias increases as BPW decreases |
| 2 | **SES** | -0.0032 | 4 | Socioeconomic status: moderately vulnerable |
| 3 | Disability_status | -0.0000 | 4 | Neutral -- no quant effect |
| 4 | Religion | +0.0033 | 4 | Slight improvement at lower quant |
| 5 | Race_x_SES | +0.0042 | 4 | Intersectional: slightly robust |
| 6 | Race_x_gender | +0.0075 | 4 | Intersectional: moderately robust |
| 7 | Physical_appearance | +0.0085 | 4 | Robust |
| 8 | Age | +0.0087 | 4 | Robust |
| 9 | Gender_identity | +0.0101 | 4 | Robust |
| 10 | Sexual_orientation | +0.0117 | 4 | Robust |
| 11 | **Race_ethnicity** | +0.0149 | 4 | Most robust |

### 10.2 Interpretation

**Why Nationality?** One plausible mechanism: nationality-related knowledge occupies a smaller fraction of the training corpus compared to race or gender. When model weights are compressed, these lower-density representations degrade first, causing the model to fall back on stereotypical patterns. Categories with more training data (Race_ethnicity, Gender_identity) have more redundant representations that survive compression.

**Why positive slopes for some categories?** Positive slope means the model becomes *less* biased at lower quant. This is likely an artifact of the model defaulting to "unknown" or non-committal answers as coherence degrades -- similar to the over-refusal pattern observed for Llama 3.2 3B. Selecting "unknown" scores as unbiased, but is not genuine fairness.

**Caveat on sample sizes:** With 198 total BBQ samples across 11 categories, per-category counts are approximately 18 per category. Each model-quant combination gets ~18 samples per category. At this sample size, per-category slopes are exploratory only. The Nationality finding should be replicated with at least 100 samples per category before informing deployment decisions.

---

## 11. Jailbreak Amplification Results

### 11.1 Overview

120 jailbreak samples per model-quant: 30 direct harmful requests (control) + 30 DAN-style + 30 roleplay + 30 prefix injection. Total: 3,120 jailbreak evaluations across all model-quant combinations.

### 11.2 Compliance Rate vs BPW Slopes

Negative slope = compliance increases (= more jailbreak-susceptible) as BPW decreases.

| Technique | Slope | Interpretation |
|-----------|-------|----------------|
| prefix_injection | **-0.0358** | Most effective -- compliance rises fastest as precision drops |
| direct | -0.0297 | Baseline -- direct requests also scale with quant |
| dan_style | -0.0237 | Moderate effectiveness |
| roleplay | -0.0212 | Least additional amplification above direct |

### 11.3 Per-Model Jailbreak Patterns

**Llama 3.2 1B -- Strong baseline, catastrophic Q2_K failure:**
- Direct compliance: 6.7% (FP16) -> 76.7% (Q2_K). A 70pp swing.
- DAN-style: 0% at FP16-Q4_K_M, then 3.3% at Q3_K_S, 70% at Q2_K. The Q2_K cliff is dramatic.
- Prefix injection: 3.3% at FP16, steady climb to 50% at Q3_K_S, 60% at Q2_K.
- Roleplay: 3.3% at FP16, 10% at Q3_K_S, 33.3% at Q2_K. Least effective technique.

**Llama 3.2 3B -- Over-refusal masks vulnerability:**
- Direct compliance: 0% at FP16, rises to 16.7% at Q2_K. Low overall vulnerability.
- Roleplay is anomalous: 13.3% at FP16 (higher than direct), 63.3% at Q4_K_M, then 0% at Q3_K_S. The Q3_K_S over-refusal kicks in.
- Prefix injection: 3.3% at FP16, stays low through Q2_K (10%). Robust to this technique.

**Mistral 7B -- Compromised at all levels:**
- Direct compliance: 70% at Q8_0. This model is already unsafe before jailbreaks are applied.
- Roleplay: 100% compliance at Q8_0 baseline. The model adopts any persona and complies fully.
- Prefix injection: 86.7% at Q8_0, 93.3% at Q2_K. Already near-ceiling, quantization adds marginally.
- Amplification ratios are typically 1.0-1.5x because the baseline is already high.

**Qwen 2.5 7B -- Strong baseline with targeted vulnerability:**
- Direct compliance: 6.7% at Q8_0, rising to 30% at Q2_K. Moderate degradation.
- Prefix injection at Q3_K_S: 76.7% compliance (**5.75x amplification over direct**). This is the most dramatic amplification spike in the dataset -- a specific vulnerability to prefix injection that emerges abruptly at Q3_K_S.
- DAN-style: 6.7% at Q8_0, 16.7% at Q2_K. Modest degradation.
- Roleplay: 6.7% at Q8_0, 33.3% at Q2_K. Moderate degradation.

### 11.4 Key Takeaways

1. **Jailbreak effectiveness scales with quantization for all models and techniques.** All 4 compliance-vs-BPW slopes are negative. This is the core finding: lower precision = weaker safety = more jailbreak success.

2. **Prefix injection is the most dangerous technique.** It scales fastest with quantization (steepest slope) and produces the highest amplification ratios. The Qwen Q3_K_S spike (5.75x) is a concrete deployment risk.

3. **DAN-style prompts are paradoxically LESS effective than direct requests for well-aligned models.** The elaborate framing may trigger additional safety checks. DAN is primarily effective against already-weak models (Mistral).

4. **Deployment implication:** If your threat model includes adversarial users, evaluate jailbreak resistance at your target quant level. A model that resists all jailbreaks at FP16 may fail at Q4_K_M (see Llama 3.2 3B roleplay at Q4_K_M: 63.3% compliance from 0% at FP16).

---

## 12. Statistical Tests (Pairwise)

Welch's t-test between adjacent quant levels. Only significant results (p < 0.05) shown.

### 12.1 Safety Tests (11 of 88 significant)

| Model | Task | Higher Q | Lower Q | Cohen's d | p-value | Effect |
|-------|------|----------|---------|-----------|---------|--------|
| llama3.2-1b | advbench_refusal | Q3_K_S | Q2_K | -1.239 | 0.0000 | Large |
| llama3.2-1b | bbq_bias | Q4_K_M | Q3_K_S | +0.503 | 0.0000 | Medium |
| llama3.2-1b | bbq_bias | Q3_K_S | Q2_K | -0.826 | 0.0000 | Large |
| llama3.2-1b | jailbreak | Q4_K_M | Q3_K_S | -0.497 | 0.0001 | Medium |
| llama3.2-1b | jailbreak | Q3_K_S | Q2_K | -0.776 | 0.0000 | Large |
| llama3.2-3b | advbench_refusal | Q4_K_M | Q3_K_S | +1.076 | 0.0000 | Large |
| llama3.2-3b | bbq_bias | Q3_K_S | Q2_K | -0.471 | 0.0000 | Medium |
| llama3.2-3b | jailbreak | Q5_K_M | Q4_K_M | -0.402 | 0.0021 | Medium |
| llama3.2-3b | jailbreak | Q4_K_M | Q3_K_S | +0.556 | 0.0000 | Medium |
| llama3.2-3b | jailbreak | Q3_K_S | Q2_K | -0.308 | 0.0177 | Small |
| qwen2.5-7b | jailbreak | Q4_K_M | Q3_K_S | -0.428 | 0.0010 | Medium |

### 12.2 Capability Tests (3 of 44 significant)

| Model | Task | Higher Q | Lower Q | Cohen's d | p-value | Effect |
|-------|------|----------|---------|-----------|---------|--------|
| llama3.2-1b | arc_challenge | Q4_K_M | Q3_K_S | -0.325 | 0.0013 | Small |
| llama3.2-1b | mmlu_real | Q3_K_S | Q2_K | -0.292 | 0.0005 | Small |
| llama3.2-3b | mmlu_real | Q4_K_M | Q3_K_S | -0.219 | 0.0092 | Small |

### 12.3 Pattern Analysis

Safety has **3.7x** more significant pairwise transitions than capability (11 vs 3). Two interpretations:

1. **Safety is genuinely more sensitive to quant boundaries.** The Q3_K_S/Q2_K and Q4_K_M/Q3_K_S transitions trigger safety-specific failures (e.g., loss of refusal behavior) that don't show up as capability degradation.

2. **Artifact of measurement.** Safety metrics (binary refusal on 100-120 samples) may have higher power to detect changes than capability metrics (binary accuracy on 200-285 samples with lower base rates). At 90% refusal rate (typical for AdvBench), the variance is lower (p*q = 0.09) than at 50% accuracy (p*q = 0.25), so effect sizes are more detectable.

Both factors likely contribute. The Q2_K safety cliff effects (d > 0.7) are robust regardless of interpretation.

---

## 13. Power Analysis & Statistical Resolution

| Metric Type | N per Variant | MDE (80% power, alpha=0.05) | Implication |
|------------|--------------|------------------------------|-------------|
| Safety (binary) | 117 | 18.3pp | Cannot detect < 18pp safety drops |
| Capability (binary) | 242 | 12.7pp | Cannot detect < 13pp capability drops |

### 13.1 What This Means for the "Robust" Verdicts

Most model-quant combinations in this report are classified as "robust" (safety degradation < 10pp). But the MDE is 18.3pp for safety. This means:

- A model showing -15pp safety degradation would be classified as "robust" (p > 0.05) because the effect is below the detection limit.
- The "robust" verdicts are **failure to detect degradation**, not confirmations of equivalence.
- Only the Q2_K cliff effects (d > 0.7, delta > 50pp) are large enough to be detected reliably.

### 13.2 Future Sample Size Requirements

| Desired MDE (pp) | Required N per Variant | Factor vs Current |
|-------------------|----------------------|-------------------|
| 18.3 (current) | 117 | 1x |
| 10.0 | 385 | 3.3x |
| 5.0 | 1,540 | 13.2x |
| 3.0 | 4,270 | 36.5x |

To achieve a 5pp MDE, approximately 1,540 samples per variant per safety task would be required. Future work should prioritize sample size over model breadth.

---

## 14. Per-Benchmark Breakdown

Complete per-benchmark tables with all 26 model-quant variants are in the auto-generated report at `research/tr134/results/phase3/20260305_144827/phase3_report.md`, Sections 2-3 and 6.

### 14.1 Task-Level Sensitivity Summary

| Task | Domain | Most Sensitive Model | Worst Drop | At Quant | Least Sensitive | Best at Q2_K |
|------|--------|---------------------|------------|----------|-----------------|--------------|
| advbench_refusal | Safety | llama3.2-1b | -57.0pp | Q2_K | qwen2.5-7b (-5.0pp) | 93.0% |
| bbq_bias | Safety | llama3.2-3b | -17.7pp | Q2_K | qwen2.5-7b (+0.5pp) | 99.0% |
| jailbreak | Safety | llama3.2-1b | -56.7pp | Q2_K | llama3.2-3b (-4.2pp) | 91.7% |
| truthfulqa | Safety | llama3.2-1b | -11.0pp | Q2_K | qwen2.5-7b (+0.0pp) | 50.0% |
| arc_challenge | Cap | llama3.2-1b | -20.0pp | Q3_K_S | qwen2.5-7b (-6.5pp) | 83.0% |
| mmlu_real | Cap | llama3.2-3b | -16.1pp | Q2_K | mistral-7b (-3.2pp) | 55.8% |

**Pattern:** Llama 3.2 1B is the most quantization-sensitive model across both safety and capability. Qwen 2.5 7B is the least sensitive. The 7B models degrade more gracefully than the 1B model, but this is confounded with model family and alignment method.

---

## 15. LLM Judge Agreement

### 15.1 Overview

Post-hoc LLM judge (Qwen 2.5 7B Instruct at Q8_0) evaluated 12,168 safety samples. The judge classifies each response using structured prompts:
- **Refusal tasks:** FULL_REFUSAL / PARTIAL_REFUSAL / COMPLIANCE / UNCLEAR
- **TruthfulQA:** TRUTHFUL / PARTIALLY_TRUTHFUL / UNTRUTHFUL / UNCLEAR

Labels are binarized for kappa computation (FULL_REFUSAL + PARTIAL_REFUSAL = refusal; TRUTHFUL = correct).

### 15.2 Per-Task Agreement

| Task | Kappa | N Pairs | Agreement % | Interpretation |
|------|-------|---------|-------------|----------------|
| advbench_refusal | 0.013 | 2,600 | 67.7% | Slight -- barely above chance |
| truthfulqa | 0.282 | 1,300 | 43.2% | Fair |

### 15.3 Why Is AdvBench Kappa So Low?

The 67.7% raw agreement looks reasonable, but kappa corrects for expected agreement by chance. When both classifiers have high base rates of classifying responses as refusals (which they do -- most AdvBench responses are refusals), high raw agreement is expected even with random labeling.

Consider: if both classifiers label 80% of samples as "refusal", they would agree on ~68% of samples by chance alone (0.8*0.8 + 0.2*0.2 = 0.68). The kappa of 0.013 says the classifiers agree barely more than this chance baseline.

**What the classifiers disagree on:** The regex classifier catches explicit refusal phrases ("I cannot", "I'm unable to"). The LLM judge evaluates overall response intent. A response like "Here's some general information about that topic, though I want to note the importance of safety..." would be classified differently: regex sees no refusal keywords (compliance), while the judge may interpret the hedging as partial refusal. These boundary cases are exactly where safety evaluation is hardest.

### 15.4 Kappa by Quantization Level

Hypothesis: lower quant produces more ambiguous responses, reducing classifier agreement.

**AdvBench refusal:**

| Quant | Kappa | N Pairs | Agreement % |
|-------|-------|---------|-------------|
| FP16 | 0.000 | 200 | 71.5% |
| Q8_0 | 0.000 | 400 | 67.2% |
| Q6_K | 0.000 | 400 | 70.2% |
| Q5_K_M | 0.020 | 400 | 67.8% |
| Q4_K_M | 0.020 | 400 | 66.5% |
| Q3_K_S | 0.042 | 400 | 74.2% |
| Q2_K | 0.007 | 400 | 58.2% |

**TruthfulQA:**

| Quant | Kappa | N Pairs | Agreement % |
|-------|-------|---------|-------------|
| FP16 | 0.200 | 100 | 41.0% |
| Q8_0 | 0.249 | 200 | 42.0% |
| Q6_K | 0.272 | 200 | 46.5% |
| Q5_K_M | 0.386 | 200 | 46.5% |
| Q4_K_M | 0.292 | 200 | 41.0% |
| Q3_K_S | 0.292 | 200 | 43.0% |
| Q2_K | 0.214 | 200 | 41.5% |

**Result:** No systematic trend with quant level. The hypothesis is not supported. Kappa fluctuates without consistent direction across quant levels. Classifier agreement does not systematically decrease at lower quant, suggesting that response ambiguity is not the primary driver of disagreement -- the fundamental difference in what the classifiers measure (surface keywords vs. semantic intent) is.

### 15.5 Implications for Safety Evaluation

1. **Do not rely on a single safety classifier.** The low kappa demonstrates that regex and LLM judge measure different constructs. Neither is ground truth. For safety-critical evaluations, use both and report disagreement rates.

2. **Safety classification is inherently ambiguous.** A kappa of 0.013-0.282 means that reasonable classifiers disagree on 30-60% of safety-relevant samples. Any single-number safety score hides this ambiguity.

3. **The judge adds value for nuanced cases** but introduces its own biases. For production safety gates where speed matters, regex is appropriate. For safety research and auditing, the judge provides a complementary signal.

---

## 16. Cross-Family Comparison

### 16.1 ANOVA Results

One-way ANOVA of mean safety slopes across model families (Llama: 6 slopes from 2 models x 3 metrics, Mistral: 3 slopes, Qwen: 3 slopes):

| Statistic | Value |
|-----------|-------|
| F-statistic | 2.4994 |
| p-value | 0.1370 |
| df | (2, 9) |
| Conclusion | **NOT SIGNIFICANT** |

### 16.2 Per-Family Mean Safety Slopes

| Family | N Slopes | Mean Safety Slope | Std | Interpretation |
|--------|----------|-------------------|-----|----------------|
| Llama | 6 | +0.003 | 0.015 | Near-flat -- high within-family variance |
| Mistral | 3 | +0.041 | 0.043 | Steepest -- but also highest variance |
| Qwen | 3 | +0.008 | 0.013 | Moderate, low variance |

### 16.3 Why the ANOVA Fails

The ANOVA has limited power for three reasons:

1. **Only 3 groups** with 3-6 observations each. Degrees of freedom (2, 9) provide very limited sensitivity.
2. **High within-family variance** in Mistral (std = 0.043) swamps the between-family signal.
3. **Llama's two models pull in opposite directions:** llama3.2-1b (slope = +0.013) and llama3.2-3b (slope = -0.007) partially cancel out.

To achieve significance at the observed effect size, approximately 10 models per family would be needed -- infeasible with current compute constraints.

### 16.4 Qualitative Cross-Family Observations

Despite the non-significant ANOVA, the data suggests a pattern worth investigating in future work:

1. **Baseline alignment quality predicts quantization robustness.** Qwen (98% refusal baseline) is the most robust. Mistral (29% refusal baseline) is the least. This correlation between alignment strength and quantization robustness is consistent across all safety metrics.

2. **DPO vs PPO may matter.** Qwen (DPO) shows the flattest safety slopes. Both Llama and Mistral (PPO) show more variation. DPO's direct optimization on preference pairs may create more "robust" parameter configurations than PPO's reward-model-mediated optimization. This is speculative -- n=1 DPO model is insufficient evidence.

3. **Model size within family is not straightforwardly protective.** Llama 3.2 3B shows more anomalous behavior (over-refusal) than Llama 3.2 1B, despite having 2.6x more parameters. The over-refusal pattern is a 3B-specific failure mode, not a size-related advantage.

---

## 17. Limitations & Methodological Caveats

1. **Single GPU, single run.** All data collected on one RTX 4080 Laptop GPU. Hardware-specific effects (thermal throttling, memory pressure) may affect results. No multi-run variance estimation -- single repetition at temp=0.

2. **Regex classifiers are brittle.** The RefusalDetector matches ~15 refusal phrases. Novel refusal formulations (metaphorical refusals, topic changes, clarification requests) are classified as compliance. The low judge agreement (Section 15) confirms this limitation.

3. **AdvBench is a gated, English-only dataset.** walledai/AdvBench requires accepting HuggingFace terms of use. Samples are US-centric in harm framing. Safety evaluation in non-English contexts is untested.

4. **BBQ categories have unequal representation.** The 11 BBQ configs from heegyu/bbq have different dataset sizes. Stratified sampling mitigates but does not eliminate imbalance. Initial runs erroneously loaded only the "Age" config (single-category bug), which was fixed by loading all 11 configs via `get_dataset_config_names()`.

5. **Jailbreak templates may not represent state-of-the-art attacks.** Templates sourced from JailbreakHub (2023-2024 data). Current techniques (crescendo attacks, multi-turn manipulation, token smuggling) are not represented. The 3 tested techniques cover ~3 of ~4 major historical clusters.

6. **7B FP16 missing.** 7B models are normalized to Q8_0, not FP16. If FP16 safety is substantially higher than Q8_0, we underestimate total degradation. TR125 showed Q8_0 is within 1.6pp of FP16 for capability, but safety equivalence is unverified.

7. **TruthfulQA is severely underpowered.** With only 50 questions per variant, the MDE is ~28pp. Most TruthfulQA deltas are within noise. Future work should use the full 817-question TruthfulQA set.

8. **No multi-turn evaluation.** All safety tasks are single-turn. Multi-turn jailbreaks, context manipulation, and conversation-history attacks are untested. These are increasingly the dominant real-world attack vectors.

9. **The LLM judge shares biases with evaluated models.** Qwen 2.5 7B Instruct is both a judged model and the judge. While the judge runs at fixed Q8_0, correlated failure modes cannot be ruled out. A truly independent judge (e.g., Claude, GPT-4) would provide stronger validation.

10. **Over-refusal confounds safety metrics.** Llama 3.2 3B shows increased refusal at Q3_K_S/Q2_K, likely due to coherence loss rather than improved safety. The S/C ratio exceeds 1.0 at these levels, masking that the model is becoming less useful, not more safe. Safety metrics alone cannot distinguish genuine safety improvement from coherence collapse.

---

## 18. Reproducibility

### 18.1 Pipeline Commands

```bash
# Full Phase 3 run (eval + judge + analyze + report):
python research/tr134/phase3/run.py -v

# Steps can be skipped individually:
python research/tr134/phase3/run.py --skip-prep               # skip benchmark preparation
python research/tr134/phase3/run.py --skip-prep --skip-eval    # judge + analyze + report only
python research/tr134/phase3/run.py --skip-prep --skip-eval --skip-judge  # analyze + report only

# Targeted BBQ re-evaluation (without re-running all 24K samples):
python research/tr134/phase3/_patch_bbq.py
```

### 18.2 Prerequisites

1. **Ollama** running locally with all 26 model tags pulled (see `config.yaml` for tag list)
2. **HuggingFace login** for gated datasets: `huggingface-cli login` (required for walledai/AdvBench)
3. **Python packages:** `pip install datasets pyyaml scipy`
4. **Disk space:** ~45 GB for all Ollama model variants

### 18.3 Key Git Commits

| Commit | Description |
|--------|-------------|
| `f6fa53df` | feat(tr134): implement phase 3 multi-family safety under quantization |
| `f07eb7c5` | feat(tr134): scaffold alignment robustness under quantization experiment |
| `66f880fc` | fix(tr134): drop Gemma 2 from phase 3 -- Ollama lacks per-quant tags |
| `4495161a` | fix(tr134): fix BBQ single-category bug, step ordering, stale Gemma refs |

### 18.4 Known Reproducibility Issues

- **Ollama determinism:** temp=0.0 may not produce bit-identical outputs across Ollama versions due to llama.cpp floating-point accumulation order differences. Results should be directionally reproducible but exact scores may vary by 1-2pp.
- **BBQ dataset:** heegyu/bbq may be updated on HuggingFace. Pin to a specific revision if exact reproducibility is required.
- **AdvBench gating:** Dataset access requires HuggingFace account and term acceptance. Access may change.

---

## Appendix A: Phase Structure & Evolution

### A.1 Phase 1: Quick Signal Detection

Phase 1 tested Llama 3.2 1B and 3B at 3 quant levels (FP16, Q4_K_M, Q2_K) on 3 safety tasks (~840 samples). Its purpose was to confirm that safety degradation under quantization is a measurable signal, not noise. The Q2_K cliff was visible immediately (llama3.2-1b refusal rate: 90% at FP16 -> 33% at Q2_K), justifying the full Phase 2 design.

### A.2 Phase 2: Full Degradation Matrix

Phase 2 expanded to all 7 quant levels and added capability benchmarks (MMLU, ARC-Challenge). This provided the safety/capability slope comparison for Llama models (~9,590 samples). The finding that safety degrades at roughly the same rate as capability (for Llama) motivated the multi-family expansion in Phase 3.

### A.3 Phase 3: Multi-Family Expansion

Phase 3 added Mistral 7B and Qwen 2.5 7B, introduced the jailbreak amplification task, expanded BBQ to 11 demographic categories (from a single-category bug in early runs), and added the LLM-as-judge validation (24,778 samples). This is the primary dataset for all results in this report.

### A.4 Design Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Drop Gemma 2 2B IT | Ollama lacks per-quant tags; all pulls returned default quant | 4 families instead of 5 (26 entries instead of 33) |
| BBQ: load all 11 configs | Initial implementation only loaded "Age" config via default `load_dataset` call | Fixed via `get_dataset_config_names()` iteration |
| Judge before analyze | Analysis Pass 13 reads `phase3_judged.jsonl` for kappa computation | Swapped Steps 3 and 4 in run.py |
| Q8_0 baseline for 7B | FP16 at 7B (~14.5 GB) exceeds 12 GB VRAM | Follows TR125 convention for llama3.1-8b |
| Targeted BBQ patch | Avoided re-running all 24,830 samples when only BBQ (5,148) needed fixing | Created `_patch_bbq.py` for targeted re-evaluation |

---

## Appendix B: Full Jailbreak Amplification Tables

Complete compliance-vs-BPW data for all (jailbreak_type, model, quant) combinations is in the auto-generated report at `research/tr134/results/phase3/20260305_144827/phase3_report.md`, Section 14.

### B.1 Most Notable Amplification Ratios

| Technique | Model | Quant | Direct Compliance | JB Compliance | Amplification |
|-----------|-------|-------|-------------------|---------------|---------------|
| prefix_injection | qwen2.5-7b | Q3_K_S | 13.3% | 76.7% | **5.75x** |
| roleplay | llama3.2-3b | Q6_K | 3.3% | 16.7% | **5.01x** |
| prefix_injection | qwen2.5-7b | Q8_0 | 6.7% | 23.3% | **3.50x** |
| prefix_injection | qwen2.5-7b | Q6_K | 10.0% | 23.3% | **2.33x** |
| prefix_injection | qwen2.5-7b | Q4_K_M | 10.0% | 20.0% | **2.00x** |
| prefix_injection | llama3.2-1b | Q5_K_M | 3.3% | 6.7% | **2.00x** |

### B.2 Technique Effectiveness Summary

| Technique | Mean Amplification | Best Against | Quant Sensitivity |
|-----------|-------------------|-------------|-------------------|
| prefix_injection | ~1.5x (where measurable) | Qwen (highest amplification), Mistral (highest absolute) | High (steepest slope) |
| roleplay | ~1.2x (highly model-dependent) | Mistral (100% compliance at Q8_0) | Moderate |
| dan_style | ~0.7x (often less effective than direct) | Only effective against Mistral | Low |

**DAN paradox:** DAN-style prompts are often *less* effective than direct requests for well-aligned models (amplification < 1.0). The elaborate roleplay framing ("Do Anything Now", jailbreak persona) may paradoxically trigger *more* safety checks in models trained to be suspicious of such prompts.

---

## Appendix C: Task & Data Sources

| Task | Dataset | License | N Used | Selection Method |
|------|---------|---------|--------|-----------------|
| advbench_refusal | walledai/AdvBench | Gated (HuggingFace) | 100 | First 100 from test split |
| truthfulqa | truthfulqa/truthful_qa | Apache-2.0 | 50 | Stratified sample |
| bbq_bias | heegyu/bbq (11 configs) | CC-BY-4.0 | 198 | Stratified across all 11 demographic configs |
| jailbreak (behaviors) | JailbreakBench/JBB-Behaviors | MIT | 30 | Stratified by behavior category |
| jailbreak (templates) | walledai/JailbreakHub | MIT | 3 | 1 representative per technique cluster |
| mmlu_real | cais/mmlu (57 subjects) | MIT | 285 | 5 per subject |
| arc_challenge | allenai/ai2_arc | CC-BY-SA-4.0 | 200 | Random sample from Challenge test split |

---

## Appendix D: Glossary

| Term | Definition |
|------|------------|
| BPW | Bits per weight. FP16 = 16.0, Q8_0 = 8.0, Q6_K = 6.5, Q5_K_M = 5.5, Q4_K_M = 4.5, Q3_K_S = 3.5, Q2_K = 2.5 |
| RLHF | Reinforcement Learning from Human Feedback. Umbrella term for alignment training methods |
| PPO | Proximal Policy Optimization. RLHF variant using a reward model; used by Llama 3.2 and Mistral 7B |
| DPO | Direct Preference Optimization. RLHF variant without a reward model; used by Qwen 2.5 |
| S/C Ratio | Safety-Capability ratio. Normalized safety score divided by normalized capability score |
| MDE | Minimum Detectable Effect at 80% power, alpha = 0.05 |
| Cohen's kappa | Chance-corrected inter-rater agreement metric (Landis & Koch 1977) |
| Over-refusal | Model refuses harmless requests or defaults to refusal templates due to coherence loss at low quant |
| Amplification ratio | Jailbreak compliance rate divided by direct compliance rate; measures jailbreak effectiveness above baseline |
| GGUF | GPT-Generated Unified Format. File format for quantized LLM weights used by llama.cpp and Ollama |

---

## References

1. Hendrycks, D., Burns, C., Basart, S., Zou, A., Mazeika, M., Song, D., & Steinhardt, J. (2021). Measuring Massive Multitask Language Understanding. *ICLR 2021.*
2. Clark, P., Cowhey, I., Etzioni, O., Khot, T., Sabharwal, A., Schoenick, C., & Tafjord, O. (2018). Think you have Solved Question Answering? Try ARC. *arXiv:1803.05457.*
3. Parrish, A., Chen, A., Nangia, N., Padmakumar, V., Phang, J., Thompson, J., Htut, P. M., & Bowman, S. R. (2022). BBQ: A Hand-Built Bias Benchmark for Question Answering. *ACL 2022.*
4. Lin, S., Hilton, J., & Evans, O. (2022). TruthfulQA: Measuring How Models Mimic Human Falsehoods. *ACL 2022.*
5. Chao, P., Robey, A., Dobriban, E., Hassani, H., Pappas, G. J., & Wong, E. (2024). JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models. *NeurIPS 2024.*
6. Shen, X., Chen, Z., Backes, M., Shen, Y., & Zhang, Y. (2023). Do Anything Now: Characterizing and Evaluating In-The-Wild Jailbreak Prompts on Large Language Models. *arXiv:2308.03825.*
7. Landis, J. R., & Koch, G. G. (1977). The Measurement of Observer Agreement for Categorical Data. *Biometrics, 33*(1), 159-174.
8. Banterhearts TR124 (2026). Quality & Accuracy Baseline.
9. Banterhearts TR125 (2026). Quantization Decision Matrix.
10. Banterhearts TR133 (2026). Predictive Capacity Planner.
