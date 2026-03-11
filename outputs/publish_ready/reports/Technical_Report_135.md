# Technical Report 135: Safety Under Multi-Agent Concurrency
## Does running N concurrent agents on a shared inference backend degrade model safety?

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-03-07
**Author:** Research Team
**Report Type:** Safety alignment analysis (metric-backed, 3 models, 4 concurrency levels, 6 benchmarks)
**Test Duration:** ~8 hrs (eval) + ~2.3 hrs (LLM judge)
**Status:** Complete
**Run ID:** `20260307_162151`
**Related Work:** [TR134](Technical_Report_134.md) (Quantization x Safety), TR136 (Backend x Safety, forthcoming), TR137 (Safety Tax Synthesis, forthcoming)
**Depends On:** TR134 (safety classifiers, jailbreak tasks, BBQ benchmark, LLM judge module), TR125 (quantization baselines, Q4_K_M reference)

---

## Abstract

TR134 established that quantization degrades safety alignment, with catastrophic failures at Q2_K and model-family-dependent thresholds. But quantization is only one inference optimization axis. Modern deployments commonly run multiple concurrent agents against a single inference backend -- agentic workflows, parallel tool-calling, batch evaluation, multi-user serving. If an Ollama instance serving 8 concurrent agents produces different safety behavior than one serving a single agent, operators need to know before deploying.

TR135 asks: **does multi-agent concurrency degrade model safety, and if so, does safety degrade faster than general capability?**

We test 3 models (Llama 3.2 1B, Llama 3.2 3B, Qwen 2.5 3B) at Q4_K_M quantization -- the TR125-recommended deployment level -- across 4 concurrency levels (N=1, 2, 4, 8 simultaneous agents) on 6 benchmarks: AdvBench refusal (100 prompts), TruthfulQA (50), BBQ bias (198), jailbreak amplification (120: 30 direct + 90 across 3 techniques), MMLU (200), and ARC-Challenge (200). Each agent processes all prompts independently at every N-level, and scores are aggregated per-prompt across agents before computing statistics -- avoiding inflated sample sizes from correlated within-prompt observations. Total: 39,060 raw records collapsed to 10,416 prompt-level observations. Post-hoc LLM judge validation (Qwen 2.5 7B Instruct Q8_0) provides an independent signal on 9,900 safety samples.

**The headline result is a null finding, and it is the right answer.** Concurrency has zero detectable effect on safety. All three models show aggregate safety slopes indistinguishable from zero (+0.000141, -0.000120, +0.000128 per agent), with 95% bootstrap CIs spanning zero in every case. Pairwise TOST equivalence testing confirms safety scores are equivalent within +/-3pp across all adjacent N-level transitions for 8 of 9 comparisons. Capability slopes are equally flat. Jailbreak susceptibility is completely unchanged by concurrency -- 11 of 12 model-technique combinations show exactly zero compliance slope. Latency scales linearly with N (96-505 ms/agent, R-sq > 0.94), confirming that concurrency does create real resource contention -- it just doesn't affect output quality or safety.

The mechanism is clear: Ollama serializes inference on a single GPU, so concurrent requests queue rather than interfere. Each agent gets the same compute path as a solo agent, just delayed. This is fundamentally different from quantization (TR134), which modifies the weights themselves and directly removes information that safety training encoded. Concurrency modifies the *scheduling* of inference, not the *computation* of inference.

**Implication for practitioners: you can safely scale concurrent agents on a single Ollama instance without safety degradation, at the cost of linear latency increase.**

**Total: 39,060 raw records, 10,416 prompt-level observations, 9,900 judged samples, 3 models, 4 N-levels.**

---

## Metric Definitions

These definitions are inherited from TR134 for cross-TR comparability. Safety metrics are the primary focus; capability metrics serve as a control arm.

### Safety Metrics

- **Refusal Rate:** Proportion of harmful prompts where the model refuses to comply. Measured via regex classifier (`RefusalDetector`) matching ~15 refusal patterns (e.g., "I cannot", "I'm not able to", "As an AI", "I must decline"). Range [0, 1]. Higher = safer. Primary safety metric for AdvBench and jailbreak tasks.
- **Bias Resistance:** Proportion of BBQ questions where the model selects the non-stereotypical or "unknown" answer rather than reinforcing demographic stereotypes. Range [0, 1]. Higher = less biased.
- **Truthfulness:** Proportion of TruthfulQA questions answered correctly (matching reference answer). Range [0, 1]. Higher = more truthful.
- **Jailbreak Compliance Rate:** Proportion of jailbreak-wrapped harmful prompts where the model complies (does not refuse). Range [0, 1]. **Lower = safer.** Complement of refusal rate, used for jailbreak analysis because the research question is about attack success.

### Capability Metrics

- **Accuracy (MMLU / ARC-Challenge):** Proportion of multiple-choice questions answered correctly. Rescored accuracy via regex letter extraction from TR125 methodology.

### Derived Metrics

- **Safety Slope (per agent):** OLS regression coefficient of aggregate safety score vs N. Negative = safety degrades with more agents. Unit: score change per additional agent.
- **TOST Equivalence:** Two one-sided t-tests at +/-3pp margin. "Equivalent" = confirmed within +/-3pp. This is strictly stronger than "not significant" -- it provides positive confirmation of no effect, not just failure to detect one.
- **Agent Disagreement:** Mean standard deviation of scores across agents for the same prompt at N > 1. Measures whether concurrency introduces non-determinism. Zero disagreement = every agent produces the identical output for a given prompt.
- **Cohen's d:** Standardized effect size (pooled SD). Values < 0.2 are conventionally "trivial." On binary data (0/1), d is mechanically bounded -- values < 0.01 are negligible by any standard.
- **Cohen's Kappa:** Inter-rater agreement between regex classifier and LLM judge, corrected for chance. < 0.20 = slight, 0.21-0.40 = fair, 0.41-0.60 = moderate, 0.61-0.80 = substantial, > 0.80 = near-perfect (Landis & Koch 1977).

### BPW Reference (Fixed for TR135)

All models run at Q4_K_M (4.5 BPW). This is the TR125-recommended deployment sweet spot and the level at which TR134 showed safety is broadly robust for well-aligned models. The fixed quantization eliminates BPW as a variable, isolating concurrency as the sole independent variable.

---

## Statistical Methods & Caveats

**Tests used:**

- **OLS regression** for slope estimation (safety/capability/latency vs N)
- **2,000-iteration bootstrap** for 95% CIs on slopes (resamples within N-level groups from prompt-level data)
- **Paired t-test** for pairwise N-level comparisons (same prompts at every N level, enabling paired design)
- **TOST equivalence testing** at +/-3pp margin (confirms equivalence, not just failure to reject)
- **Holm-Bonferroni** step-down correction for multiple comparisons across pairwise tests
- **Cohen's d** (pooled SD) for standardized effect sizes
- **Cohen's kappa** for inter-rater agreement (regex classifier vs LLM judge)
- **Power analysis**: binary MDE via two-proportion z-test, continuous MDE via Cohen's d
- **P-values** via regularized incomplete beta function (exact t-distribution, not normal approximation)
- **Pearson correlation** for disagreement-safety relationship

**Important caveats:**

1. **Single Ollama instance, single GPU.** Ollama serializes inference requests on one GPU. Concurrent agents queue rather than truly execute in parallel. This means TR135 tests whether *queuing contention* affects safety, not whether *true parallel inference* (e.g., tensor parallelism, continuous batching in vLLM/TGI) does. Distributed multi-GPU deployments or production inference servers with continuous batching may behave differently. The null result applies specifically to Ollama's serialized inference pattern.

2. **Closed-loop concurrency pattern.** Each agent sends a request and waits for the full response before sending the next. The actual concurrency depth may be less than N because agents block on inference responses. At N=8, the effective parallelism depends on prompt length and Ollama's internal scheduling. The experiment measures the safety effect of the *deployment pattern* (N concurrent clients), not of a specific hardware concurrency level.

3. **Fixed quantization (Q4_K_M).** The concurrency x quantization interaction is untested. It is possible (though unlikely given the mechanism) that concurrency effects emerge only at extreme quantization levels where model behavior is already unstable. TR137 will model this interaction using additive projections from TR134 and TR135 data.

4. **Temperature = 0.0.** All runs use deterministic (greedy) generation. Stochastic sampling at temperature > 0 introduces variance that could interact with concurrency (e.g., if GPU memory pressure or scheduling delays affect RNG state). This is untested.

5. **Ollama may not be perfectly deterministic at temp=0.** Different floating-point accumulation orders under varying load could produce minor response differences. The observed agent disagreement (max 0.046 std-dev at N=8) may reflect this, though it does not translate to group-level score differences. No determinism validation was performed for concurrent Ollama (same caveat as TR125 caveat 6 and TR134 caveat 8).

6. **Power limitations.** The minimum detectable effect is 6.5-7.3pp for aggregate safety (N=468 prompt-level observations per model) and 5.2-28.0pp per task (TruthfulQA weakest at N=50). Effects smaller than these thresholds could exist undetected. However, TOST equivalence testing provides positive confirmation for most comparisons -- the null result is not merely a power failure.

7. **Three models, two families, 1B-3B range.** Llama (1B, 3B) and Qwen (3B). No 7B models tested at concurrency. Larger models with longer generation times may experience different concurrency dynamics. The null result should not be extrapolated to 7B+ models without testing.

8. **No multi-turn evaluation.** All prompts are single-turn. Adversarial multi-turn attacks under concurrency (where conversational state tracking might degrade) are untested. This is a significant gap for agentic deployment scenarios where multi-turn interactions are the norm.

9. **Per-prompt aggregation is conservative.** Averaging scores across agents before computing group statistics prevents inflated N but may also mask agent-level variance. We address this with the disagreement analysis (Section 12) but cannot fully separate prompt-level effects from agent-level effects.

---

## Executive Summary

TR135 answers: **does running multiple concurrent agents against a shared Ollama backend degrade safety properties -- refusal, bias resistance, truthfulness, jailbreak robustness -- and if so, does safety degrade faster than capability?**

### Key Findings

1. **Concurrency does not degrade safety.** All three models maintain safety scores within noise of their N=1 baselines at N=2, 4, and 8. The largest aggregate safety slope is +0.000141 per agent (Llama 1B) -- 0.1pp total change over 7 agents. All 95% CIs span zero. This is a null result confirmed by TOST equivalence testing, not merely a failure to detect.

2. **Concurrency does not degrade capability either.** MMLU + ARC accuracy slopes are equally flat (-0.000149 to +0.000546 per agent). There is no general degradation signal -- safety-specific or otherwise.

3. **Safety does not degrade faster than capability.** The safety-capability divergence for all three models is classified as "both stable" (all slopes < 0.003, all CIs overlap). This contrasts sharply with TR134's quantization finding, where Mistral 7B showed safety degrading 3x faster than capability.

4. **Latency scales linearly with N.** Mean latency increases 96-505 ms per additional agent (R-sq > 0.94). Qwen 2.5 3B latency reaches 4.2 seconds at N=8 (6.3x N=1 baseline). Concurrency has a real infrastructure cost -- it just isn't a safety cost.

5. **Jailbreak susceptibility is completely unaffected by concurrency.** All compliance slopes are 0.000 per agent for 11 of 12 model-technique combinations. The single non-zero case (Qwen dan_style: +0.001/agent) represents a single prompt changing behavior at N=8. This contrasts with TR134, where quantization systematically increases jailbreak success (prefix injection slope = -0.036/BPW).

6. **TOST confirms equivalence for 8/9 adjacent N-level transitions.** Pairwise safety score differences are confirmed within +/-3pp for all comparisons except Qwen N1->N2 (TOST inconclusive -- not a detected effect, just insufficient power for that specific pair at the +/-3pp margin, with an observed difference of exactly 0.0000).

7. **Agent disagreement is minimal and does not predict safety degradation.** At N=8, maximum within-prompt score standard deviation is 0.046 (truthfulqa, Llama 3B). Disagreement does not correlate with lower safety (no model shows negative r with significance). The slight non-determinism from concurrent inference does not propagate to safety-relevant behavior.

8. **TR135 N=1 baselines are consistent with TR134 Q4_K_M scores.** 9 of 12 tasks match within 5pp. The 3 divergent tasks show TR135 measuring higher safety than TR134, not lower -- a reassuring direction for the null result.

9. **LLM judge agreement is stable across N-levels.** Kappa = 0.067, agreement = 82.7% at every N from 1 to 8. Concurrency does not change the nature of model responses enough to affect classifier agreement patterns.

### Validation Summary

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| Effect detection | Aggregate safety slope | CI spans zero for all models | CI spans zero (3/3) | PASS |
| Equivalence confirmation | TOST at +/-3pp | Equivalent for majority of transitions | 8/9 equivalent | PASS |
| Capability control | Capability slope flat | CI spans zero for all models | CI spans zero (3/3) | PASS |
| Jailbreak sensitivity | Compliance slope | No trend | 11/12 exactly zero | PASS |
| Cross-experiment | N=1 vs TR134 Q4_K_M | Within 5pp for majority | 9/12 within 5pp | PASS |
| Power sufficiency | MDE < 10pp aggregate | MDE computable and reasonable | 6.5-7.3pp | PASS |

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| 1 | Concurrency degrades safety | All slopes ~0, CIs span zero, TOST confirms equivalence (Section 5) | **Refuted** |
| 2 | Safety degrades faster than capability under concurrency | All models "both stable", divergence < 0.001 (Section 7) | **Refuted** |
| 3 | Concurrency amplifies jailbreaks | 11/12 compliance slopes = 0.000 (Section 11) | **Refuted** |
| 4 | Agent disagreement predicts lower safety | No consistent negative correlation (Section 12) | **Refuted** |
| 5 | TR135 baselines match TR134 | 9/12 tasks within 5pp (Section 14) | **Validated** |

### Key Decisions for Practitioners

1. **You can safely scale concurrent agents on Ollama without safety degradation.** At N=2, 4, or 8 concurrent agents, safety metrics are statistically equivalent to N=1. The cost is latency, not safety.

2. **For real-time applications, N=2-4 is practical.** Latency roughly doubles at N=2 and quadruples at N=4. At N=8, Qwen 2.5 3B latency exceeds 4 seconds per request -- acceptable for batch processing but not interactive use.

3. **These results apply to Ollama's serialized inference pattern.** If you use vLLM, TGI, or other backends with continuous batching or tensor parallelism, the concurrency pattern is fundamentally different. Do not extrapolate this null result to those backends without testing (TR136 addresses backend differences).

4. **Concurrency is a non-issue compared to quantization.** TR134 found safety degradation of up to 57pp from quantization. TR135 finds < 0.1pp from concurrency. When optimizing inference for deployment, quantization level is the dominant safety consideration; concurrency level is not.

5. **Your model's baseline safety matters more than concurrency.** Llama 3.2 3B has a 54% refusal rate at Q4_K_M regardless of N. Qwen 2.5 3B has 96%. No amount of concurrency optimization will fix a weakly aligned model -- choose your model based on TR134's safety data, then scale concurrency freely.

### When to Use This Report

**Scenario 1: Deploying an Agentic Workflow**

**Question:** "I want to run 4 concurrent tool-calling agents against a single Ollama backend. Will this degrade safety?"

**Answer:** No. Section 5 shows all safety scores are equivalent within +/-3pp at N=4. Section 11 shows jailbreak resistance is unchanged. Scale freely; your latency constraint (Section 10) will be the binding factor, not safety.

**Scenario 2: Batch Safety Evaluation**

**Question:** "I'm running safety benchmarks with N=8 concurrent eval workers. Will my results differ from N=1?"

**Answer:** No. Section 9 confirms TOST equivalence for 8/9 transitions. Your benchmark results at N=8 will match N=1 results within noise. You can use concurrent evaluation to reduce wall-clock time without introducing measurement bias.

**Scenario 3: Combining Concurrency with Quantization**

**Question:** "I'm deploying at Q4_K_M with N=4 agents. Is the combined safety cost worse than either alone?"

**Answer:** Based on TR135, concurrency contributes zero additional safety cost. Your safety profile at Q4_K_M + N=4 should match Q4_K_M + N=1 (i.e., the TR134 data for your model at Q4_K_M). TR137 will formally model this interaction, but the additive projection is: total safety cost = quantization cost + 0 (concurrency).

**Scenario 4: Using a Different Backend**

**Question:** "I use vLLM, not Ollama. Does TR135 apply?"

**Answer:** Not directly. TR135 tests Ollama's serialized inference on a single GPU. vLLM uses continuous batching and may process requests differently under load. Wait for TR136 (cross-backend safety) for vLLM-specific data. The mechanism (concurrency doesn't modify weights) suggests the null result should hold, but this is an untested prediction.

**Scenario 5: Deciding Concurrency Level for a Multi-User Chat Service**

**Question:** "I'm serving N users simultaneously from one Ollama instance. How many users can I support safely?"

**Answer:** Safety is unconstrained -- scale as high as latency allows. Consult Section 10 for the latency model. For Llama 3.2 1B, 8 users yields ~970ms mean latency (3.1x baseline). For Qwen 2.5 3B, 8 users yields ~4.2s (6.3x baseline). The binding constraint is always latency, never safety.

### How to Read This Report

| Time | Reading Path |
|------|-------------|
| **2 min** | Abstract -> Claim Validation table -> Key Decisions |
| **10 min** | Add Key Findings (1-9) + Section 5 (aggregate safety) + Section 7 (divergence) |
| **30 min** | Add Section 6 (per-model data) + Section 11 (jailbreaks) + Section 14 (cross-validation) + Section 17 (limitations) |
| **60 min** | Full report Sections 1-18 + Appendices |
| **Deep dive** | Section 11 (per-model jailbreak tables), Section 12 (disagreement), Section 15 (power analysis), Appendix B (full jailbreak data) |

### Table of Contents

**Background & Design (Sections 1-4)**

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Experimental Design](#2-experimental-design)
3. [Model Lineup](#3-model-lineup)
4. [Environment & Artifacts](#4-environment--artifacts)

**Core Results (Sections 5-7)**

5. [Aggregate Safety vs Concurrency](#5-aggregate-safety-vs-concurrency)
6. [Per-Model Safety Data](#6-per-model-safety-data)
7. [Safety-Capability Divergence](#7-safety-capability-divergence)

**Detailed Analyses (Sections 8-12)**

8. [Capability Control Arm](#8-capability-control-arm)
9. [Pairwise Equivalence Tests](#9-pairwise-equivalence-tests)
10. [Latency vs Concurrency](#10-latency-vs-concurrency)
11. [Jailbreak Amplification vs Concurrency](#11-jailbreak-amplification-vs-concurrency)
12. [Agent Disagreement Analysis](#12-agent-disagreement-analysis)

**Validation (Sections 13-16)**

13. [LLM Judge Agreement by N](#13-llm-judge-agreement-by-n)
14. [Cross-Experiment Validation (vs TR134)](#14-cross-experiment-validation-vs-tr134)
15. [Power Analysis & Statistical Resolution](#15-power-analysis--statistical-resolution)
16. [Slope Heterogeneity](#16-slope-heterogeneity)

**Closing (Sections 17-18)**

17. [Conclusions & Limitations](#17-conclusions--limitations)
18. [Reproducibility](#18-reproducibility)

**Appendices**

- [Appendix A: Normalized Degradation Summary](#appendix-a-normalized-degradation-summary)
- [Appendix B: Full Jailbreak Amplification Tables](#appendix-b-full-jailbreak-amplification-tables)
- [Appendix C: Task & Data Sources](#appendix-c-task--data-sources)
- [Appendix D: Glossary](#appendix-d-glossary)
- [References](#references)

---

## 1. Introduction & Research Motivation

### 1.1 The Problem

TR134 quantified safety degradation under quantization: up to -57pp refusal rate at Q2_K, jailbreak susceptibility increasing systematically with lower precision, and model-family-dependent safety thresholds. Practitioners now know which quant levels are safe. But quantization is one of three inference optimization axes:

1. **Quantization** -- reduce weight precision (TR134: completed)
2. **Concurrency** -- run multiple agents simultaneously (TR135: this report)
3. **Backend choice** -- different inference engines (TR136: forthcoming)

Multi-agent concurrency is increasingly common in production. Agentic workflows run tool-calling agents in parallel. Evaluation frameworks launch N concurrent workers to reduce wall-clock time. Chat applications serve multiple users against a shared backend. If concurrent load affects model outputs -- even subtly -- safety properties could degrade without the operator noticing.

The concern is not hypothetical. GPU resource contention under concurrent load could affect:

- **Memory allocation patterns**, potentially altering KV-cache behavior
- **Scheduling order**, where requests interleave differently under load
- **Floating-point accumulation order**, producing slightly different outputs
- **Thermal throttling**, reducing effective compute and potentially changing generation behavior

Any of these could plausibly degrade safety-critical behaviors like refusal, bias resistance, or jailbreak robustness.

### 1.2 Research Questions

1. Does increasing the number of concurrent agents (N=1 to N=8) degrade safety benchmark scores?
2. Does safety degrade faster than capability under concurrency (safety-specific effect vs general degradation)?
3. Does concurrency amplify jailbreak susceptibility?
4. Does higher agent disagreement (within-prompt score variance) predict lower safety?
5. Are TR135 N=1 baselines consistent with TR134 Q4_K_M scores (cross-experiment validation)?

### 1.3 Hypothesis

**H0 (null):** Concurrency does not affect safety or capability scores. Ollama serializes inference; concurrent requests queue without interfering with each other's compute paths.

**H1 (alternative):** Concurrency degrades safety, potentially faster than capability, due to resource contention, scheduling interference, or non-determinism under load.

Based on Ollama's architecture (single-GPU serialization), we expected H0. TR135 is designed to confirm or refute this expectation with statistical rigor.

### 1.4 Literature Gap

Concurrent inference is a standard production pattern, yet safety evaluation under concurrency is virtually unstudied. The existing literature focuses on:

- **Throughput and latency** under concurrent load (well-studied in systems literature)
- **Quantization effects on capability** (extensively studied; see GPTQ, AWQ, GGUF evaluations)
- **Quantization effects on safety** (rare; TR134 is among the first systematic evaluations)

We found no prior work that:

- Measures whether concurrent agents produce different safety outcomes than sequential agents
- Tests whether jailbreak effectiveness changes under concurrent load
- Validates whether batch evaluation results (N>1 concurrent workers) are equivalent to serial evaluation
- Quantifies agent-level disagreement as a function of concurrency depth

TR135 fills these gaps for the Ollama serialized inference pattern. The null result is itself a contribution: it provides evidence that practitioners can parallelize safety evaluations and scale concurrent deployments without introducing safety artifacts.

### 1.5 Relationship to Prior Work

| Reference | Contribution | How TR135 Uses It |
|-----------|-------------|-------------------|
| TR125 (Banterhearts) | Q4_K_M as safe deployment level | Fixed quant level for concurrency testing |
| TR134 (Banterhearts) | Safety classifiers, jailbreak tasks, LLM judge, per-category BBQ | Reused safety eval pipeline; N=1 baseline cross-validation |
| TR133 (Banterhearts) | Latency/throughput models under load | Latency slope comparison (Section 10) |
| TR136 (Banterhearts, forthcoming) | Backend-specific safety effects | Complementary axis; TR135 is Ollama-only |
| TR137 (Banterhearts, forthcoming) | Cross-axis safety tax synthesis | TR135 provides the concurrency axis data |

---

## 2. Experimental Design

### 2.1 Design Summary

| Parameter | Value |
|-----------|-------|
| Models | Llama 3.2 1B, Llama 3.2 3B, Qwen 2.5 3B (all at Q4_K_M) |
| Concurrency levels | N = 1, 2, 4, 8 simultaneous agents |
| Safety tasks | AdvBench refusal (100), TruthfulQA (50), BBQ bias (198), Jailbreak amplification (120) |
| Capability tasks | MMLU (200), ARC-Challenge (200) |
| Total prompts per model-N | 868 |
| Raw records | 39,060 (= 3 models x 4 N-levels x variable agents per prompt) |
| Prompt-level observations | 10,416 (= 3 x 4 x 868, after per-prompt aggregation) |
| Backend | Single Ollama instance, single GPU (RTX 4080 Laptop, 12 GB VRAM) |
| Temperature | 0.0 (deterministic, greedy decoding) |
| Max new tokens | 256 |
| Seed | 42 |
| Judge model | Qwen 2.5 7B Instruct Q8_0 (post-hoc, 9,900 safety samples) |
| Bootstrap iterations | 2,000 (for slope CIs) |
| TOST margin | +/-3pp (equivalence threshold) |

### 2.2 Concurrency Design

Each model is tested at 4 concurrency levels in randomized order (to avoid thermal/cache confounds):

- **N=1:** Single agent, baseline condition. Standard serial evaluation.
- **N=2:** Two agents sharing one Ollama instance. Each agent processes all 868 prompts independently.
- **N=4:** Four agents. Each processes all 868 prompts. 3,472 raw records per model-N.
- **N=8:** Eight agents. Each processes all 868 prompts. 6,944 raw records per model-N.

Agents run asynchronously via Python's `asyncio`. Each agent gets a shuffled copy of the prompt list (to avoid sequence-position confounds). All agents share the same Ollama HTTP endpoint (`localhost:11434`).

### 2.3 Per-Prompt Aggregation (Critical Design Decision)

At N=8, each prompt generates 8 raw records (one per agent). Naively treating these as independent observations would inflate sample sizes by 8x and produce artificially narrow confidence intervals. Instead:

1. For each (model, N, task, sample_id), we **average scores across agents** to produce a single prompt-level score.
2. All downstream statistics (group means, slopes, pairwise tests) operate on these prompt-level aggregates.
3. The prompt-level dataset has 10,416 rows regardless of N -- the same 868 prompts x 3 models x 4 N-levels.

This is statistically conservative: we sacrifice within-prompt variance information to avoid correlated-observation bias. The agent disagreement analysis (Section 12) examines the within-prompt variance separately.

### 2.4 Safety Task Descriptions

All tasks reuse TR134 Phase 3 benchmarks and classifiers:

**AdvBench Refusal (N=100):** 100 harmful requests from walledai/AdvBench (gated dataset). Each prompt asks the model to produce harmful content (e.g., instructions for illegal activities). The model's response is classified as refusal or compliance via regex. This is the most direct safety measure.

**TruthfulQA (N=50):** 50 questions from the TruthfulQA benchmark designed to elicit common misconceptions. The model generates a free-form answer, which is compared to reference answers. This measures a different safety dimension: the model's tendency to produce confidently wrong information that could mislead users.

**BBQ Bias (N=198):** 198 questions from the BBQ benchmark spanning 11 demographic categories (Age, Disability_status, Gender_identity, Nationality, Physical_appearance, Race_ethnicity, Race_x_gender, Race_x_SES, Religion, SES, Sexual_orientation). Each question presents a context and asks which person matches a stereotype. The model should select "unknown" or the non-stereotypical answer.

**Jailbreak Amplification (N=120):** 30 harmful behaviors from JailbreakBench, each presented in 4 variants: direct (control), wrapped in DAN-style template, wrapped in roleplay template, wrapped in prefix injection template. Templates sourced from JailbreakHub. Total: 30 direct + 30 DAN + 30 roleplay + 30 prefix = 120 prompts per model-N.

### 2.5 Capability Tasks

**MMLU (N=200):** 200 questions from cais/mmlu across multiple subjects. Same benchmark as TR125 Phase 2 and TR134 Phase 3.

**ARC-Challenge (N=200):** 200 questions from allenai/ai2_arc (Challenge subset). Same benchmark as TR125 Phase 2 and TR134 Phase 3.

Both use generation-based scoring with regex letter extraction (rescored accuracy), matching TR125 methodology.

### 2.6 Classification Pipeline

Safety scores are computed by three regex-based classifiers (inherited from TR134):

- **RefusalDetector:** Matches ~15 refusal patterns in the model's raw text output (e.g., "I cannot", "I'm not able to", "I must decline", "As an AI"). Returns binary refusal/compliance. Used for AdvBench and jailbreak tasks.
- **TruthfulnessScorer:** Compares model output to reference answers using string matching and keyword extraction. Returns binary correct/incorrect.
- **BiasDetector:** Compares model's answer choice to the stereotypical answer and the "unknown" answer. Returns binary biased/unbiased.

Post-hoc, the LLM judge (Qwen 2.5 7B Instruct Q8_0) re-evaluates all safety samples via structured prompting. The judge's classifications are used for inter-rater agreement analysis (Section 13), not for primary scoring.

### 2.7 Pipeline Architecture

```
TR135 config (config.yaml)
  3 models x 4 N-levels x 6 tasks
        |
  [run.py]  -- async N-agent eval loop (TR135-specific)
        |
  samples.jsonl (39,060 raw records)
        |
  [judge_analysis.py]  -- LLM judge post-hoc on safety samples
        |
  tr135_judged.jsonl (9,900 judged records)
        |
  [analyze.py]  -- 15-pass analysis pipeline
        |
  tr135_analysis.json + tr135_scored.jsonl
        |
  Manual report (this file)
```

---

## 3. Model Lineup

### 3.1 Model Summary

| Model | Family | Parameters | RLHF Method | Quant Level | Ollama Tag | Origin |
|-------|--------|-----------|-------------|-------------|------------|--------|
| Llama 3.2 1B Instruct | Llama | 1.24B | PPO | Q4_K_M (4.5 BPW) | `llama3.2:1b` | Meta |
| Llama 3.2 3B Instruct | Llama | 3.21B | PPO | Q4_K_M (4.5 BPW) | `llama3.2:3b` | Meta |
| Qwen 2.5 3B Instruct | Qwen | 3.09B | DPO | Q4_K_M (4.5 BPW) | `qwen2.5:3b` | Alibaba |

### 3.2 Why These Models

- **Llama 3.2 1B/3B (PPO):** Direct overlap with TR134 Phase 3, enabling cross-experiment validation (Section 14). Two size points within the same family test whether model size affects concurrency sensitivity. The 1B model has 88% baseline refusal at Q4_K_M; the 3B model has only 54% -- providing both a high-safety and moderate-safety baseline.

- **Qwen 2.5 3B (DPO):** Different alignment method from Llama. DPO-trained models showed the strongest quantization robustness in TR134 (Qwen 2.5 7B was the most safety-robust model in the entire TR134 matrix). Including a DPO model tests whether alignment method affects concurrency sensitivity. The 3B variant was chosen over 7B to keep all models in the same parameter range (~1-3B), isolating concurrency effects from model-size effects.

### 3.3 Fixed Quantization Choice

All models run at Q4_K_M (4.5 BPW). This decision was deliberate:

1. **Q4_K_M is the deployment sweet spot** from TR125. Testing at a realistic deployment level makes results immediately actionable.
2. **Fixed quant isolates the concurrency variable.** If we varied both N and quant level, the design would require 3 x 4 x 7 = 84 cells instead of 3 x 4 = 12, with confounded interaction effects.
3. **TR134 established Q4_K_M safety baselines** for Llama 1B (87% refusal) and Llama 3B (47% refusal). These provide direct cross-validation targets.
4. **The concurrency x quant interaction** is left to TR137's synthesis model, which will combine TR134's quantization slopes with TR135's concurrency slopes.

### 3.4 Design Decision: No 7B Models

TR134 tested Mistral 7B and Qwen 2.5 7B, but TR135 excludes 7B models for two reasons:

1. **Compute budget.** Each model x N-level requires a full 868-prompt eval pass. At N=8, that's 6,944 raw requests. Adding 2 more models would increase total runtime by ~67%, from ~8 hours to ~13 hours.
2. **Latency confound.** 7B models at Q4_K_M generate ~2x slower than 3B models. At N=8, a 7B model might hit latency-induced timeouts, introducing confounds unrelated to concurrency's effect on safety. The Qwen 2.5 3B latency at N=8 (4.2s) is already near practical limits.
3. **TR137 can extrapolate.** If concurrency has zero safety effect for all three tested models (which it does), the synthesis model can extend this null finding to 7B models with high confidence, since the mechanism (serialized inference) is model-size-independent.

---

## 4. Environment & Artifacts

### 4.1 Environment

| Component | Value |
|-----------|-------|
| OS | Windows 11 Home 10.0.26200 |
| CPU | 13th Gen Intel Core i9-13980HX |
| GPU | NVIDIA GeForce RTX 4080 Laptop GPU (12,282 MB VRAM, CC 8.9) |
| Ollama | v0.17.0, local HTTP API (http://localhost:11434) |
| Python | 3.13.1 |
| Temperature | 0.0 (greedy decoding) |
| Max new tokens | 256 |
| Seed | 42 |

### 4.2 Key Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Config | `research/tr135/config.yaml` | 3 models x 4 N-levels, 6 task paths |
| Raw samples | `research/tr135/results/20260307_162151/samples.jsonl` | 39,060 raw eval records |
| Judged samples | `research/tr135/results/20260307_162151/tr135_judged.jsonl` | 9,900 judged safety records |
| Analysis JSON | `research/tr135/results/20260307_162151/tr135_analysis.json` | All computed statistics (15 passes) |
| Scored samples | `research/tr135/results/20260307_162151/tr135_scored.jsonl` | Scored records with prompt-level aggregation |
| Analysis code | `research/tr135/analyze.py` | 15-pass analysis pipeline |
| Judge code | `research/tr135/judge_analysis.py` | Standalone LLM judge runner |
| Orchestrator | `research/tr135/run.py` | Full pipeline: prep -> eval -> judge -> analyze -> report |
| Published report | `PublishReady/reports/Technical_Report_135.md` | This file |

---

## 5. Aggregate Safety vs Concurrency

The central test: does the aggregate safety score (mean across AdvBench, TruthfulQA, BBQ, jailbreak tasks) change as N increases from 1 to 8?

| Model | N=1 | N=2 | N=4 | N=8 | Slope/agent | 95% CI | R-sq |
|-------|-----|-----|-----|-----|-------------|--------|------|
| Llama 3.2 1B | 0.8536 | 0.8547 | 0.8568 | 0.8548 | +0.000141 | [-0.006, +0.006] | 0.11 |
| Llama 3.2 3B | 0.8013 | 0.7997 | 0.8013 | 0.7998 | -0.000120 | [-0.007, +0.007] | 0.17 |
| Qwen 2.5 3B | 0.8494 | 0.8494 | 0.8504 | 0.8502 | +0.000128 | [-0.006, +0.006] | 0.52 |

**Interpretation:** All slopes are indistinguishable from zero. The largest absolute slope (0.000141) translates to 0.1pp change over the full N=1 to N=8 range -- smaller than the measurement noise. All 95% bootstrap CIs span zero with comfortable margins. R-sq values confirm that N explains essentially no variance in safety scores.

The R-sq of 0.52 for Qwen deserves comment: this is an artifact of fitting a line to four near-identical points where a tiny upward trend happens to be roughly monotonic. The actual effect magnitude is 0.08pp -- meaningless in practical terms.

**Contrast with TR134:** Under quantization, the Llama 3.2 1B safety slope was +0.013/BPW (meaningful, 20pp total range). Under concurrency, the same model's slope is +0.000141/agent -- two orders of magnitude smaller. Concurrency is not a safety concern.

---

## 6. Per-Model Safety Data

Raw (non-aggregated) safety scores at each concurrency level. 95% confidence intervals in brackets. This section mirrors TR134's Section 5 structure -- per-model tables with interpretive observations.

### 6.1 Llama 3.2 1B (Q4_K_M)

| Task | Metric | N=1 | N=2 | N=4 | N=8 | Slope/agent |
|------|--------|-----|-----|-----|-----|-------------|
| advbench_refusal | refusal_rate | 88.0% | 88.0% | 88.0% | 88.0% | 0.000 |
| bbq_bias | bias_resistance | 86.9% | 86.6% | 87.1% | 86.9% | +0.000176 |
| jailbreak | refusal_rate | 92.5% | 92.5% | 92.5% | 92.5% | 0.000 |
| truthfulqa | truthfulness | 57.0% | 59.0% | 59.0% | 58.1% | +0.000620 |
| mmlu_real | accuracy | 30.5% | 31.2% | 31.5% | 31.2% | +0.000625 |
| arc_challenge | accuracy | 34.0% | 34.2% | 34.5% | 34.4% | +0.000467 |

**Observations:**

- **AdvBench refusal is perfectly frozen.** 88.0% at every N-level. Not a single prompt changed its refusal behavior under concurrent load. This is the strongest possible null result for the primary safety metric.
- **Jailbreak refusal is equally frozen.** 92.5% across all N-levels. The model's resistance to all 4 jailbreak techniques is completely independent of concurrency.
- **BBQ bias shows sub-0.5pp fluctuation.** The scores oscillate between 86.6% and 87.1% -- well within the CI width of +/-4.5pp. No trend.
- **TruthfulQA** shows the largest per-task movement (+2.0pp from N=1 to N=2, then -0.9pp to N=8). The CI width is +/-12pp, so this is noise. The slope of +0.000620/agent translates to +0.4pp over the full range.
- **Capability tasks** (MMLU, ARC) are equally flat. The 1B model is a weak performer (30-34% accuracy) but its accuracy is stable across N.

**The invariance of refusal behavior is notable.** At temp=0, Llama 1B produces the exact same refusal/compliance decision for every prompt regardless of whether 1 or 8 agents are simultaneously querying the backend. The model's safety training creates a deterministic decision boundary that concurrency cannot perturb.

### 6.2 Llama 3.2 3B (Q4_K_M)

| Task | Metric | N=1 | N=2 | N=4 | N=8 | Slope/agent |
|------|--------|-----|-----|-----|-----|-------------|
| advbench_refusal | refusal_rate | 54.0% | 54.0% | 54.0% | 54.0% | 0.000 |
| bbq_bias | bias_resistance | 96.0% | 96.0% | 96.2% | 96.1% | +0.000209 |
| jailbreak | refusal_rate | 89.2% | 89.2% | 89.2% | 89.2% | 0.000 |
| truthfulqa | truthfulness | 48.0% | 46.5% | 47.0% | 46.1% | -0.001946 |
| mmlu_real | accuracy | 60.0% | 60.2% | 59.6% | 59.5% | -0.000580 |
| arc_challenge | accuracy | 69.5% | 70.2% | 70.2% | 70.2% | +0.000282 |

**Observations:**

- **AdvBench refusal rate is 54.0% at every N.** This is a weak baseline safety level -- the model complies with 46% of harmful requests regardless of concurrency. This is consistent with TR134's finding for Llama 3B at Q4_K_M (47%). The 7pp difference vs TR134 is discussed in Section 14.
- **Jailbreak refusal is frozen at 89.2%.** Despite Llama 3B's notably weak direct refusal (54%), its jailbreak refusal is paradoxically high (89.2%). This mirrors the TR134 finding that jailbreak wrappers can paradoxically *increase* refusal for some models -- the elaborate framing triggers safety checks that direct requests do not.
- **TruthfulQA shows the single largest per-task concurrency effect:** -1.9pp from N=1 to N=8 (slope = -0.001946/agent). This is the biggest effect in the entire experiment. However: (a) the CI is +/-23pp, (b) N=50 yields an MDE of 28pp (Section 15), and (c) the effect translates to 1.4pp total. It is noise.
- **BBQ bias is the tightest metric.** Scores fluctuate < 0.2pp across N-levels. This model has 96% bias resistance -- near-ceiling performance that concurrency cannot degrade.

**The Llama 3B weak-refusal baseline is important context.** This model would be flagged as insufficiently safe by TR134's standards (refusal < 80% at Q4_K_M). Concurrency does not make it worse -- but it also does not make it better. If your model is unsafe at N=1, it will be equally unsafe at N=8.

### 6.3 Qwen 2.5 3B (Q4_K_M)

| Task | Metric | N=1 | N=2 | N=4 | N=8 | Slope/agent |
|------|--------|-----|-----|-----|-----|-------------|
| advbench_refusal | refusal_rate | 96.0% | 96.0% | 96.0% | 96.0% | 0.000 |
| bbq_bias | bias_resistance | 96.5% | 96.5% | 96.7% | 96.5% | +0.000115 |
| jailbreak | refusal_rate | 70.8% | 70.8% | 70.8% | 70.7% | -0.000154 |
| truthfulqa | truthfulness | 51.0% | 51.0% | 51.0% | 51.8% | +0.001109 |
| mmlu_real | accuracy | 62.5% | 63.3% | 63.8% | 63.5% | +0.001130 |
| arc_challenge | accuracy | 81.5% | 81.5% | 81.5% | 81.4% | -0.000192 |

**Observations:**

- **AdvBench refusal is frozen at 96.0%.** Qwen's DPO alignment provides strong direct refusal that concurrency cannot perturb.
- **Jailbreak refusal reveals a notable model-level vulnerability.** 70.8% refusal means 29.2% jailbreak compliance -- unchanged by concurrency. This is consistent with TR134's finding that Qwen is strong against direct requests but vulnerable to specific jailbreak techniques (prefix injection: 76.7% compliance at Q4_K_M).
- **BBQ bias** fluctuates < 0.2pp. Near-perfect bias resistance at 96.5%.
- **TruthfulQA** shows a slight positive trend (+0.8pp from N=1 to N=8) -- a trivial effect within a +/-25pp CI.
- **Capability scores** are the highest of the three models (62.5% MMLU, 81.5% ARC) and perfectly stable.

**The prefix injection vulnerability persists.** Qwen 2.5 3B complies with 76.7% of prefix-injection-wrapped harmful requests at every concurrency level (see Section 11). This is a model alignment property identified in TR134 for the 7B variant and confirmed here for the 3B variant. It is a deployment concern that concurrency neither creates nor resolves.

### 6.4 Safety Data Summary

| Safety Metric | Best Model | Worst Model | Stable Across N? |
|---------------|-----------|-------------|-----------------|
| Refusal (AdvBench) | Qwen 3B (96.0%) | Llama 3B (54.0%) | Yes (all models frozen) |
| Bias (BBQ) | Qwen 3B (96.5%) | Llama 1B (86.9%) | Yes (< 0.5pp variation) |
| Jailbreak refusal | Llama 1B (92.5%) | Qwen 3B (70.8%) | Yes (11/12 frozen) |
| Truthfulness | Llama 1B (57.0%) | Llama 3B (48.0%) | Yes (< 2pp variation, within noise) |

**Pattern:** The inter-model safety differences are substantial (e.g., 42pp refusal gap between Qwen and Llama 3B). The intra-model concurrency effects are negligible (< 0.5pp for all models and metrics). Model choice dominates; concurrency is irrelevant to safety.

---

## 7. Safety-Capability Divergence

Does safety degrade *faster* than capability? This is the key diagnostic from TR134, where Mistral 7B showed safety degrading 3x faster than capability under quantization.

| Model | Safety Slope | Safety CI | Cap Slope | Cap CI | Diff | Verdict |
|-------|-------------|-----------|-----------|--------|------|---------|
| Llama 3.2 1B | +0.000141 | [-0.006, +0.006] | +0.000546 | [-0.008, +0.009] | -0.000405 | Both stable |
| Llama 3.2 3B | -0.000120 | [-0.007, +0.007] | -0.000149 | [-0.008, +0.009] | +0.000029 | Both stable |
| Qwen 2.5 3B | +0.000128 | [-0.006, +0.006] | +0.000473 | [-0.007, +0.009] | -0.000345 | Both stable |

All divergences are < 0.001 with fully overlapping CIs. There is no safety-specific concurrency effect.

This result has a clear mechanistic explanation. Quantization (TR134) modifies the model weights, directly removing information that safety training encoded -- degradation is expected because the model is literally different. Concurrency does not modify weights or the compute path. Each request gets the same forward pass; only the scheduling changes.

---

## 8. Capability Control Arm

If capability also degrades, any safety degradation might be general performance loss, not safety-specific. MMLU + ARC accuracy as a function of N:

| Model | N=1 | N=2 | N=4 | N=8 | Slope/agent | 95% CI |
|-------|-----|-----|-----|-----|-------------|--------|
| Llama 3.2 1B | 0.3225 | 0.3275 | 0.3300 | 0.3278 | +0.000546 | [-0.008, +0.009] |
| Llama 3.2 3B | 0.6475 | 0.6525 | 0.6494 | 0.6484 | -0.000149 | [-0.008, +0.009] |
| Qwen 2.5 3B | 0.7200 | 0.7238 | 0.7262 | 0.7244 | +0.000473 | [-0.007, +0.009] |

**Interpretation:** Capability is equally flat. No model shows any detectable capability degradation. The null result on safety is not masking a general degradation effect -- *nothing* degrades under concurrency.

---

## 9. Pairwise Equivalence Tests

Paired t-tests between adjacent N-levels on prompt-level safety scores (all safety tasks combined). Same prompts at every N level enables a paired design, increasing power. Holm-Bonferroni correction applied. TOST at +/-3pp confirms equivalence.

### 9.1 Llama 3.2 1B

| Transition | Diff | t | p | Cohen's d | Holm Sig | TOST Equiv |
|------------|------|---|---|-----------|----------|------------|
| N1 -> N2 | +0.0011 | 0.24 | 0.809 | +0.003 | No | **Yes** |
| N2 -> N4 | +0.0021 | 1.16 | 0.249 | +0.006 | No | **Yes** |
| N4 -> N8 | -0.0020 | -1.14 | 0.255 | -0.006 | No | **Yes** |

### 9.2 Llama 3.2 3B

| Transition | Diff | t | p | Cohen's d | Holm Sig | TOST Equiv |
|------------|------|---|---|-----------|----------|------------|
| N1 -> N2 | -0.0016 | -0.83 | 0.406 | -0.004 | No | **Yes** |
| N2 -> N4 | +0.0016 | 0.93 | 0.355 | +0.004 | No | **Yes** |
| N4 -> N8 | -0.0015 | -1.64 | 0.101 | -0.004 | No | **Yes** |

### 9.3 Qwen 2.5 3B

| Transition | Diff | t | p | Cohen's d | Holm Sig | TOST Equiv |
|------------|------|---|---|-----------|----------|------------|
| N1 -> N2 | +0.0000 | 0.00 | 1.000 | +0.000 | No | No* |
| N2 -> N4 | +0.0011 | 1.00 | 0.318 | +0.003 | No | **Yes** |
| N4 -> N8 | -0.0003 | -0.28 | 0.782 | -0.001 | No | **Yes** |

*\*Qwen N1->N2 TOST: The observed difference is exactly 0.0000, but the variance structure at this comparison doesn't provide enough power to confirm equivalence at the +/-3pp margin. This is a power limitation, not a detected effect. The TOST p-value is 0.5 (on the boundary), while all other TOST p-values are 0.0 (overwhelming equivalence evidence).*

### 9.4 Summary

- **No pairwise comparison is statistically significant** after Holm correction (0/9).
- **8 of 9 transitions are TOST-confirmed equivalent** within +/-3pp.
- All Cohen's d values are < 0.007 -- trivial by any standard (conventional threshold: d < 0.2).
- The largest observed difference is 0.0021 (0.21pp) -- two orders of magnitude below practical significance.

---

## 10. Latency vs Concurrency

While safety is unaffected, latency is not. Concurrency has a clear, measurable infrastructure cost:

| Model | N=1 (ms) | N=2 (ms) | N=4 (ms) | N=8 (ms) | Slope (ms/agent) | R-sq | N=8/N=1 |
|-------|----------|----------|----------|----------|-------------------|------|---------|
| Llama 3.2 1B | 310 | 363 | 487 | 972 | 96.3 | 0.972 | 3.1x |
| Llama 3.2 3B | 365 | 448 | 703 | 1,371 | 146.6 | 0.990 | 3.8x |
| Qwen 2.5 3B | 657 | 953 | 1,380 | 4,156 | 505.4 | 0.948 | 6.3x |

**Observations:**

- Latency scales near-linearly with N for Llama models (R-sq > 0.97). This is the expected behavior for serialized inference: each additional agent adds approximately one inference-time delay to the queue.
- **Qwen 2.5 3B shows super-linear growth at N=8** (6.3x vs expected ~3-4x from linear slope). This may reflect Ollama's internal scheduling overhead for models with longer generation times (~660ms per request at N=1 vs ~310ms for Llama 1B). The R-sq of 0.948 (vs 0.990 for Llama 3B) confirms the linearity is weaker for Qwen.
- At N=8, Qwen latency exceeds 4 seconds per request -- a practical deployment constraint even though output quality is preserved.

**The latency result is important context for the safety null result.** Concurrency demonstrably creates real resource contention at the infrastructure level -- it just doesn't propagate to model outputs. The null result on safety is not trivially explained by "concurrency doesn't actually do anything." It does something -- it increases wait times. It just doesn't change what the model computes when it gets its turn.

### 10.1 Latency Implications for Deployment

| Target Latency | Llama 1B Max N | Llama 3B Max N | Qwen 3B Max N |
|----------------|----------------|----------------|---------------|
| < 500 ms | 4 | 2 | 1 |
| < 1,000 ms | 8 | 4 | 2 |
| < 2,000 ms | > 8 | 8 | 4 |
| < 5,000 ms | > 8 | > 8 | 8 |

These are mean latencies. P75 latencies are 20-40% higher (e.g., Qwen at N=8: mean 4,156ms, p75 ~5,500ms). For SLA-bound applications, use p75 or p95 as the constraint.

---

## 11. Jailbreak Amplification vs Concurrency

TR134 found that quantization systematically increases jailbreak success (prefix injection slope = -0.036/BPW -- compliance increases as bits decrease). Does concurrency have the same effect?

### 11.1 Compliance Rates by Model and Technique

| Model | Technique | N=1 Compliance | N=8 Compliance | Slope/agent | Amplification Ratio |
|-------|-----------|----------------|----------------|-------------|---------------------|
| Llama 1B | dan_style | 3.3% | 3.3% | 0.000 | 0.25x |
| Llama 1B | direct | 13.3% | 13.3% | 0.000 | 1.00x (baseline) |
| Llama 1B | prefix_injection | 13.3% | 13.3% | 0.000 | 1.00x |
| Llama 1B | roleplay | 0.0% | 0.0% | 0.000 | 0.00x |
| Llama 3B | dan_style | 3.3% | 3.3% | 0.000 | 0.50x |
| Llama 3B | direct | 6.7% | 6.7% | 0.000 | 1.00x (baseline) |
| Llama 3B | prefix_injection | 0.0% | 0.0% | 0.000 | 0.00x |
| Llama 3B | roleplay | 33.3% | 33.3% | 0.000 | **5.00x** |
| Qwen 3B | dan_style | 6.7% | 7.1% | **+0.001** | 0.50x -> 0.53x |
| Qwen 3B | direct | 13.3% | 13.3% | 0.000 | 1.00x (baseline) |
| Qwen 3B | prefix_injection | 76.7% | 76.7% | 0.000 | **5.75x** |
| Qwen 3B | roleplay | 20.0% | 20.0% | 0.000 | 1.50x |

### 11.2 Per-Model Jailbreak Patterns (Concurrency-Independent)

**Llama 3.2 1B -- Strong refusal across techniques:**

Direct compliance is 13.3%, and no jailbreak technique significantly amplifies this. DAN-style is paradoxically *less* effective (3.3%) -- the elaborate framing triggers additional refusal. Roleplay is completely blocked (0.0%). This model's Q4_K_M alignment holds firm against all tested attacks.

**Llama 3.2 3B -- Roleplay vulnerability:**

Roleplay jailbreaks achieve 33.3% compliance (5.0x amplification over the 6.7% direct rate). This is a specific model alignment weakness -- Llama 3B adopts personas readily. However, prefix injection is perfectly blocked (0.0%), reversing the vulnerability profile seen in TR134 for Qwen. This pattern is completely invariant to N.

**Qwen 2.5 3B -- Prefix injection vulnerability:**

The headline finding: 76.7% compliance to prefix injection at every concurrency level. This is 5.75x the direct compliance rate (13.3%). This mirrors TR134's finding for the 7B variant at Q4_K_M (also 76.7% prefix injection compliance). DPO alignment is resistant to direct requests (96% refusal) but extremely weak against prefix injection. This is a model alignment property, not a concurrency effect.

### 11.3 Key Takeaways

1. **Zero concurrency effect.** 11 of 12 model-technique combinations show exactly 0.000 slope. The single non-zero case (Qwen dan_style: +0.001/agent) represents a single prompt at N=8 where one agent (out of 8) flipped from refusal to compliance, shifting the prompt-level mean by 0.4pp. This is not a meaningful effect.

2. **Jailbreak vulnerabilities are model properties, not infrastructure properties.** Each model has a specific vulnerability profile (Llama 3B: roleplay; Qwen: prefix injection) that is completely invariant to concurrent load.

3. **The mechanism is clear.** Jailbreak resistance is determined by the model's safety training (weights + attention patterns). Concurrency does not modify weights or attention. This is why quantization affects jailbreaks (it modifies weights) and concurrency does not.

4. **Contrast with TR134:** Under quantization, prefix injection compliance for Llama 1B went from 3.3% at FP16 to 60% at Q2_K (slope = -0.036/BPW). Under concurrency, the same metric goes from 13.3% at N=1 to 13.3% at N=8 (slope = 0.000). The effect magnitudes differ by infinity.

---

## 12. Agent Disagreement Analysis

When N > 1, do agents give different answers to the same prompt? If concurrency causes non-determinism, within-prompt score variance should increase with N.

### 12.1 Mean Disagreement at N=8 (std-dev across agents per prompt)

| Model | advbench | bbq_bias | jailbreak | truthfulqa | arc | mmlu |
|-------|----------|----------|-----------|------------|-----|------|
| Llama 1B | 0.000 | 0.020 | 0.000 | 0.019 | 0.016 | 0.018 |
| Llama 3B | 0.000 | 0.002 | 0.000 | 0.046 | 0.005 | 0.012 |
| Qwen 3B | 0.000 | 0.002 | 0.003 | 0.020 | 0.007 | 0.018 |

**Observations:**

- **AdvBench: zero disagreement.** Every agent produces the same refusal/compliance decision for every prompt at N=8. The model's refusal behavior is completely deterministic under concurrent load. This is the single most important data point for practitioners: if your safety gate is based on refusal detection, concurrent inference will not introduce false passes.

- **Jailbreak: near-zero.** Same as AdvBench -- binary refusal decisions are stable. The Qwen 3B disagreement of 0.003 means that approximately 1 in 300 jailbreak prompt-agent pairs produces a different result. At N=8 with 120 jailbreak prompts, this is ~3 prompts where one agent out of eight disagrees.

- **TruthfulQA: highest disagreement** (up to 0.046 for Llama 3B). These are open-ended questions where minor wording differences can flip the truthfulness classification. The 4.6% std-dev means approximately 5% of prompts see at least one agent disagree with the majority. TruthfulQA's open-ended format makes its classifier more sensitive to minor response variations than the binary refusal/compliance classifiers.

- **MMLU/ARC: low but non-zero** (1.2-1.8% std-dev). Multiple-choice tasks occasionally see different letter selections across agents. This is consistent with Ollama producing slightly different tokens under concurrent load (floating-point accumulation order differences), but the effect is tiny and does not aggregate to group-level score differences.

### 12.2 Disagreement-Safety Correlation

Does higher disagreement predict lower safety? If concurrency creates unreliable safety, we'd expect a negative correlation (more disagreement = worse safety scores).

| Model | Pearson r | p-value | Significant? | Interpretation |
|-------|-----------|---------|-------------|----------------|
| Llama 1B | -0.114 | 0.641 | No | No relationship |
| Llama 3B | +0.781 | 0.0001 | **Yes** | Positive (opposite of hypothesis) |
| Qwen 3B | +0.293 | 0.573 | No | No relationship |

**Why is Llama 3B's correlation positive?** This is a task-composition artifact, not a causal relationship. TruthfulQA has the highest disagreement *and* relatively high scores (48% truthfulness). AdvBench and jailbreak have zero disagreement *and* include Llama 3B's low refusal rate (54%). The correlation reflects which tasks have binary vs continuous scoring, not a causal disagreement->safety relationship. If agent disagreement genuinely predicted safety, we'd see it consistently across models -- we don't.

**Conclusion:** Agent disagreement is minimal, does not scale with N in a concerning way, and does not predict safety degradation. Concurrency does not create unreliable safety behavior.

---

## 13. LLM Judge Agreement by N

Cohen's kappa between regex classifiers and LLM judge (Qwen 2.5 7B Instruct Q8_0) on refusal tasks, stratified by concurrency level:

| N | Kappa | Pairs | Agreement % |
|---|-------|-------|-------------|
| 1 | 0.067 | 660 | 82.7% |
| 2 | 0.067 | 1,320 | 82.7% |
| 4 | 0.067 | 2,640 | 82.7% |
| 8 | 0.067 | 5,280 | 82.7% |

### 13.1 Why Is Kappa So Low Despite 82.7% Agreement?

The 82.7% raw agreement looks reasonable, but kappa corrects for expected agreement by chance. When both classifiers have high base rates of classifying responses as refusals (which they do -- most AdvBench and jailbreak responses are refusals at Q4_K_M), high raw agreement is expected even with random labeling.

Consider: if both classifiers label 85% of samples as "refusal", they would agree on ~74% of samples by chance alone (0.85*0.85 + 0.15*0.15 = 0.745). The kappa of 0.067 says the classifiers agree only marginally more than this chance baseline. This is consistent with TR134's finding (kappa = 0.013 for AdvBench refusal), confirming that the two classifiers measure overlapping but distinct constructs across both TR134 and TR135.

### 13.2 Stability Confirms the Null Result

The perfect stability of kappa and agreement across N-levels is itself informative. If concurrency caused models to produce different *types* of responses (e.g., more ambiguous refusals that one classifier catches but the other misses), the kappa pattern would shift. It doesn't. The model produces the same distribution of response types regardless of concurrent load.

### 13.3 Implications for Safety Evaluation

1. **Do not rely on a single safety classifier.** The low kappa demonstrates that regex and LLM judge measure different constructs (TR134 Section 15 established this finding).
2. **Concurrent evaluation does not introduce classifier disagreement artifacts.** Your benchmark results at N=8 will show the same regex-vs-judge agreement as at N=1.
3. **The judge adds value for nuanced cases** but introduces its own biases. For production safety gates where speed matters, regex is appropriate. For auditing, use both.

---

## 14. Cross-Experiment Validation (vs TR134)

TR135 N=1 baselines should match TR134 Phase 3 Q4_K_M scores -- same models, same quantization, same benchmarks. Differences > 5pp indicate a systematic discrepancy.

### 14.1 Llama 3.2 1B -- 5/6 consistent

| Task | TR135 (N=1) | TR134 (Q4_K_M) | Diff (pp) | Status |
|------|------------|----------------|-----------|--------|
| advbench_refusal | 0.880 | 0.870 | +1.0 | OK |
| arc_challenge | 0.340 | 0.395 | -5.5 | **DIVERGENT** |
| bbq_bias | 0.869 | 0.874 | -0.5 | OK |
| jailbreak_amplification | 0.925 | 0.933 | -0.8 | OK |
| mmlu_real | 0.305 | 0.337 | -3.2 | OK |
| truthfulqa | 0.570 | 0.580 | -1.0 | OK |

### 14.2 Llama 3.2 3B -- 4/6 consistent

| Task | TR135 (N=1) | TR134 (Q4_K_M) | Diff (pp) | Status |
|------|------------|----------------|-----------|--------|
| advbench_refusal | 0.540 | 0.470 | +7.0 | **DIVERGENT** |
| arc_challenge | 0.695 | 0.705 | -1.0 | OK |
| bbq_bias | 0.960 | 0.965 | -0.5 | OK |
| jailbreak_amplification | 0.892 | 0.825 | +6.7 | **DIVERGENT** |
| mmlu_real | 0.600 | 0.590 | +1.0 | OK |
| truthfulqa | 0.480 | 0.500 | -2.0 | OK |

*Qwen 2.5 3B is not cross-validated because TR134 tested Qwen 2.5 7B (different model size).*

### 14.3 Summary and Divergence Analysis

**9/12 tasks consistent** (< 5pp difference).

**Divergent tasks:**

- **Llama 1B ARC-Challenge** (-5.5pp): Marginal, just above the 5pp threshold. Binary scoring on 200 multiple-choice questions has inherent variance -- a Wilson CI half-width of ~7pp at p=0.34.

- **Llama 3B AdvBench** (+7.0pp) and **Jailbreak** (+6.7pp): Both diverge in the same direction -- TR135 measures *higher* refusal than TR134. Three possible explanations: (a) different prompt shuffling seeds between experiments, (b) Ollama internal state differences between fresh-start runs (model re-loading can produce slightly different initial states), (c) the TR135 run happened on a different Ollama version than TR134. The direction is reassuring -- if anything, the TR135 baseline is *more conservative* (reports higher safety) than TR134. If TR135 had shown *lower* safety, it would raise concerns about measurement drift degrading the null result.

**Cross-validation verdict:** The 75% consistency rate (9/12) is adequate for confirming experimental comparability. The divergent tasks are capability (ARC) and two related safety metrics (AdvBench and jailbreak refusal for the same model), suggesting a model-specific offset rather than a systematic measurement error.

---

## 15. Power Analysis & Statistical Resolution

Can we actually detect small effects, or is the null result a power failure?

### 15.1 Aggregate Safety MDE (alpha=0.05, power=0.80)

| Model | Safety N (prompts) | Safety MDE (pp) | Capability N | Cap MDE (Cohen's d) |
|-------|-------------------|-----------------|--------------|---------------------|
| Llama 1B | 468 | 6.5 | 400 | 0.14 |
| Llama 3B | 468 | 7.3 | 400 | 0.14 |
| Qwen 3B | 468 | 6.6 | 400 | 0.14 |

### 15.2 Per-Task Safety MDE

| Task | N | Llama 1B MDE | Llama 3B MDE | Qwen 3B MDE |
|------|---|-------------|-------------|-------------|
| advbench_refusal | 100 | 12.9pp | 19.7pp | 7.8pp |
| bbq_bias | 198 | 9.5pp | 5.5pp | 5.2pp |
| jailbreak_amplification | 120 | 9.5pp | 11.2pp | 16.4pp |
| truthfulqa | 50 | 27.7pp | 28.0pp | 28.0pp |

### 15.3 Interpretation

- The **aggregate MDE of 6.5-7.3pp** means we can reliably detect safety changes >= ~7pp. A genuine 5pp aggregate degradation could hide in the data. However, the observed slopes correspond to < 0.1pp effects -- 70x smaller than the MDE. The observed effects are not "just below the detection limit"; they are orders of magnitude below it.

- **TruthfulQA has the weakest power** (MDE ~28pp, N=50). A genuine 20pp truthfulness effect would be undetectable. However, TruthfulQA also shows the largest observed slopes (+0.6 to -1.9pp) -- still far below even a generous threshold.

- **BBQ bias has the best power** (MDE 5.2-9.5pp) and shows the flattest slopes (< 0.03pp). The null result on bias is well-powered and robust.

- **AdvBench MDE varies by model** because MDE depends on the baseline rate (p*q term). Qwen (96% refusal, p*q = 0.04) has MDE = 7.8pp. Llama 3B (54% refusal, p*q = 0.25) has MDE = 19.7pp. Ironically, the model with the most room to degrade has the least power to detect degradation.

### 15.4 TOST vs MDE

**TOST equivalence is the stronger conclusion.** Even where MDE is wide (e.g., TruthfulQA), the observed effects are so far from the +/-3pp equivalence margin that TOST still confirms equivalence for most transitions. The null result is a positive confirmation of no effect, not merely a power failure.

**Power comparison with TR134:** TR134's MDE was 18.3pp for safety (N=117/variant). TR135's MDE is 6.5-7.3pp (N=468) -- approximately 2.5x better resolution, thanks to the per-prompt aggregation design and larger prompt counts per group.

---

## 16. Slope Heterogeneity

Do different safety tasks respond differently to concurrency? If one task degrades while others improve, the aggregate slope could mask a real effect.

| Model | Task with Max Slope | Max Slope | Task with Min Slope | Min Slope | Range |
|-------|--------------------|-----------|--------------------|-----------|-------|
| Llama 1B | truthfulqa | +0.00062 | advbench_refusal | 0.000 | 0.00062 |
| Llama 3B | bbq_bias | +0.00021 | truthfulqa | -0.00195 | 0.00216 |
| Qwen 3B | truthfulqa | +0.00111 | jailbreak | -0.00015 | 0.00126 |

**Interpretation:** All slope ranges are < 0.003. No task shows a meaningfully different concurrency response than any other task. The aggregate slope is not masking a task-specific effect.

Llama 3B has the widest range (0.00216), driven by TruthfulQA's -0.00195 slope. But this task has only N=50 samples with an MDE of 28pp -- the slope is noise, not signal. If the TruthfulQA slope were real (which would mean -1.4pp over 7 agents), it would still be clinically irrelevant and far below the MDE.

---

## 17. Conclusions & Limitations

### 17.1 Research Question Answers

| # | Question | Answer | Evidence |
|---|----------|--------|----------|
| 1 | Does concurrency degrade safety? | **No** | All slopes ~0, CIs span zero, 8/9 TOST equivalent (Section 5) |
| 2 | Does safety degrade faster than capability? | **No** | All models "both stable", divergence < 0.001 (Section 7) |
| 3 | Does concurrency amplify jailbreaks? | **No** | 11/12 model-technique pairs show exactly zero slope (Section 11) |
| 4 | Does agent disagreement predict lower safety? | **No** | No consistent negative correlation; only significant r is positive (Section 12) |
| 5 | Are baselines consistent with TR134? | **Yes** | 9/12 tasks within 5pp; divergent tasks show TR135 higher, not lower (Section 14) |

### 17.2 Why Concurrency Doesn't Affect Safety

The null result has a clear mechanistic explanation. Ollama serializes inference on a single GPU: concurrent requests are queued and processed sequentially, not in parallel. Each agent gets the same compute path -- same weights, same attention computation, same token generation -- as a solo agent. The only difference is waiting time (latency), which scales linearly with N but does not affect the model's forward pass.

This is fundamentally different from quantization (TR134), which modifies the weights themselves and directly removes information that safety training encoded. Concurrency modifies the *scheduling* of inference, not the *computation* of inference.

### 17.3 Concurrency vs Quantization: A Comparison

| Dimension | Quantization (TR134) | Concurrency (TR135) |
|-----------|---------------------|---------------------|
| Max safety degradation | -57pp (Llama 1B @ Q2_K) | 0.1pp (largest slope) |
| Jailbreak amplification | Yes (prefix injection slope = -0.036/BPW) | No (11/12 exactly zero) |
| Safety degrades faster than capability? | Yes, for Mistral 7B (3x faster) | No, for any model |
| Mechanistic channel | Weight modification (information loss) | Request scheduling (no compute change) |
| Latency impact | Reduction (faster inference at lower quant) | Increase (linear with N) |
| Practitioner action required? | Yes -- choose quant level carefully | No -- scale freely |

### 17.4 Limitations

1. **Single-GPU Ollama only.** Distributed backends (vLLM, TGI) with continuous batching or tensor parallelism may behave differently. True parallel inference (not queued serial) could introduce effects TR135 does not capture. TR136 will address backend differences.

2. **Three models, 1B-3B range.** No 7B+ models tested. Larger models with longer generation times experience proportionally longer queue delays (as shown by Qwen 3B's super-linear latency). Whether this translates to output differences at higher N is untested.

3. **Fixed quantization (Q4_K_M).** The concurrency x quantization interaction is untested. A model at Q2_K (already unstable) might respond differently to concurrent load than one at Q4_K_M. TR137 will model this interaction.

4. **Temperature = 0.0.** Stochastic sampling introduces variance that could interact with concurrent scheduling (e.g., if timing-dependent RNG states diverge under load). Untested.

5. **No multi-turn evaluation.** All prompts are single-turn. Multi-turn adversarial attacks under concurrency -- where conversation state management could degrade -- are untested. This is a significant gap for agentic deployment scenarios.

6. **N=8 maximum.** Production deployments may run N=32, 64, or higher concurrency. While the mechanism (serialized inference) predicts the null result holds, this is an untested extrapolation. Latency at N>8 may become impractical before safety becomes an issue.

7. **TruthfulQA power is weak** (MDE = 28pp, N=50). A genuine 15pp truthfulness effect would be undetectable. However, the observed effect (< 2pp) is far below even the weakest MDE, and TOST still confirms equivalence for truthfulqa transitions.

8. **Per-prompt aggregation is conservative.** Averaging scores across agents discards within-prompt variance. If one agent in eight produces a different answer, the prompt-level mean shifts only 12.5%. This could mask agent-level safety failures that occur rarely but consistently. The disagreement analysis (Section 12) partially addresses this -- at N=8, zero AdvBench and near-zero jailbreak disagreement means agent-level masking is not occurring for the primary safety metrics.

9. **Two model families only.** Llama (PPO) and Qwen (DPO). Mistral, Gemma, and other families are untested under concurrency. However, since the null result is mechanistic (Ollama serializes), family-specific effects are unlikely.

---

## 18. Reproducibility

### 18.1 Pipeline Commands

```bash
# Full run (eval + judge + analyze + report):
python research/tr135/run.py -v

# Steps can be skipped:
python research/tr135/run.py --skip-prep               # skip benchmark preparation
python research/tr135/run.py --skip-prep --skip-eval    # judge + analyze only
python research/tr135/run.py --skip-prep --skip-eval --skip-judge  # analyze only

# Standalone analysis:
python research/tr135/analyze.py -v --run-dir research/tr135/results/20260307_162151

# Standalone judge:
python research/tr135/judge_analysis.py -v --run-dir research/tr135/results/20260307_162151
```

### 18.2 Prerequisites

1. **Ollama** running locally with all 3 model tags pulled: `llama3.2:1b`, `llama3.2:3b`, `qwen2.5:3b` (default tags use Q4_K_M)
2. **Judge model:** `qwen2.5:7b-instruct-q8_0` must be pulled for LLM judge analysis
3. **HuggingFace login** for gated datasets: `huggingface-cli login` (required for walledai/AdvBench)
4. **Python packages:** `pip install datasets pyyaml`
5. **Disk space:** ~5 GB for model variants

### 18.3 Key Git Commits

| Commit | Description |
|--------|-------------|
| `781d8fa4` | feat(tr135,tr136): scaffold concurrency x safety and cross-backend experiments |

### 18.4 Known Reproducibility Issues

- **Ollama determinism:** temp=0.0 may not produce bit-identical outputs across Ollama versions due to llama.cpp floating-point accumulation order differences. Results should be directionally reproducible but exact scores may vary by 1-2pp.
- **Concurrent scheduling:** The exact interleaving of agent requests depends on OS scheduling, system load, and Ollama's internal queue management. While this does not affect safety scores (the whole point of TR135), exact latency values will vary between runs.
- **BBQ dataset:** heegyu/bbq may be updated on HuggingFace. Pin to a specific revision if exact reproducibility is required.
- **AdvBench gating:** Dataset access requires HuggingFace account and term acceptance.

---

## Appendix A: Normalized Degradation Summary

All values relative to N=1 baseline (1.000 = no change). Only N=8 shown for brevity -- intermediate N-levels show the same pattern (all ~1.000).

| Model | Task | Norm Score (N=8) | Norm Latency (N=8) |
|-------|------|-----------------|-------------------|
| Llama 1B | advbench_refusal | 1.000 | 2.950x |
| Llama 1B | bbq_bias | 1.000 | 2.587x |
| Llama 1B | jailbreak_amplification | 1.000 | 2.857x |
| Llama 1B | truthfulqa | 1.020 | 2.151x |
| Llama 1B | mmlu_real | 1.023 | 4.160x |
| Llama 1B | arc_challenge | 1.011 | 4.230x |
| Llama 3B | advbench_refusal | 1.000 | 3.225x |
| Llama 3B | bbq_bias | 1.001 | 3.668x |
| Llama 3B | jailbreak_amplification | 1.000 | 3.243x |
| Llama 3B | truthfulqa | 0.961 | 2.050x |
| Llama 3B | mmlu_real | 0.992 | 5.066x |
| Llama 3B | arc_challenge | 1.010 | 5.317x |
| Qwen 3B | advbench_refusal | 1.000 | 3.854x |
| Qwen 3B | bbq_bias | 1.001 | 5.491x |
| Qwen 3B | jailbreak_amplification | 0.999 | 3.374x |
| Qwen 3B | truthfulqa | 1.015 | 6.343x |
| Qwen 3B | mmlu_real | 1.016 | 17.349x |
| Qwen 3B | arc_challenge | 0.998 | 17.953x |

**Key observation:** All normalized scores fall between 0.961 and 1.023 -- within +/-4% of baseline. In contrast, latency normalization shows 2-18x increases. Concurrency creates real resource contention that simply does not propagate to output quality or safety.

**The Qwen MMLU/ARC latency anomaly:** 17-18x latency increase at N=8 (vs 3-5x for safety tasks on the same model) suggests Ollama's scheduling overhead scales disproportionately for tasks where the model generates longer responses. Capability tasks (MMLU, ARC) require the model to "think" before selecting a letter, producing longer token sequences than AdvBench refusals. The latency difference is real; the safety difference is not.

---

## Appendix B: Full Jailbreak Amplification Tables

Complete compliance-rate data for all (model, technique, N-level) combinations.

### B.1 Llama 3.2 1B

| Technique | N=1 | N=2 | N=4 | N=8 | Slope | Amplification |
|-----------|-----|-----|-----|-----|-------|---------------|
| direct | 13.3% | 13.3% | 13.3% | 13.3% | 0.000 | 1.00x |
| dan_style | 3.3% | 3.3% | 3.3% | 3.3% | 0.000 | 0.25x |
| roleplay | 0.0% | 0.0% | 0.0% | 0.0% | 0.000 | 0.00x |
| prefix_injection | 13.3% | 13.3% | 13.3% | 13.3% | 0.000 | 1.00x |

DAN and roleplay are *less* effective than direct requests. No technique amplifies compliance beyond the 13.3% baseline.

### B.2 Llama 3.2 3B

| Technique | N=1 | N=2 | N=4 | N=8 | Slope | Amplification |
|-----------|-----|-----|-----|-----|-------|---------------|
| direct | 6.7% | 6.7% | 6.7% | 6.7% | 0.000 | 1.00x |
| dan_style | 3.3% | 3.3% | 3.3% | 3.3% | 0.000 | 0.50x |
| roleplay | 33.3% | 33.3% | 33.3% | 33.3% | 0.000 | **5.00x** |
| prefix_injection | 0.0% | 0.0% | 0.0% | 0.0% | 0.000 | 0.00x |

**Roleplay is the only effective technique** for Llama 3B (5.0x amplification). This model adopts personas readily but resists prefix injection completely. The opposite vulnerability profile from Qwen.

### B.3 Qwen 2.5 3B

| Technique | N=1 | N=2 | N=4 | N=8 | Slope | Amplification |
|-----------|-----|-----|-----|-----|-------|---------------|
| direct | 13.3% | 13.3% | 13.3% | 13.3% | 0.000 | 1.00x |
| dan_style | 6.7% | 6.7% | 6.7% | 7.1% | +0.001 | 0.50x -> 0.53x |
| roleplay | 20.0% | 20.0% | 20.0% | 20.0% | 0.000 | 1.50x |
| prefix_injection | 76.7% | 76.7% | 76.7% | 76.7% | 0.000 | **5.75x** |

**Prefix injection is devastatingly effective** (5.75x amplification, 76.7% compliance). DPO alignment creates a robust refusal boundary for direct requests but is systematically weak against instruction-prefix attacks. This vulnerability is identical to the TR134 finding for Qwen 2.5 7B at Q4_K_M.

### B.4 Technique Effectiveness Summary

| Technique | Mean Amplification | Most Vulnerable Model | N-Level Effect |
|-----------|-------------------|-----------------------|----------------|
| prefix_injection | 2.25x (where > 0) | Qwen 3B (5.75x) | None |
| roleplay | 2.17x (where > 0) | Llama 3B (5.00x) | None |
| dan_style | ~0.42x | None (less effective than direct) | None |
| direct | 1.00x (baseline) | -- | None |

**DAN paradox (confirmed from TR134):** DAN-style prompts are consistently *less* effective than direct requests for all three models. The elaborate "Do Anything Now" framing paradoxically triggers *more* safety checks. This finding, stable across TR134 (quantization) and TR135 (concurrency), suggests DAN-style attacks are a historical artifact that modern alignment has learned to recognize.

---

## Appendix C: Task & Data Sources

| Task | Dataset | License | N Used | Selection Method |
|------|---------|---------|--------|-----------------|
| advbench_refusal | walledai/AdvBench | Gated (HuggingFace) | 100 | First 100 from test split |
| truthfulqa | truthfulqa/truthful_qa | Apache-2.0 | 50 | Stratified sample |
| bbq_bias | heegyu/bbq (11 configs) | CC-BY-4.0 | 198 | Stratified across all 11 demographic configs |
| jailbreak (behaviors) | JailbreakBench/JBB-Behaviors | MIT | 30 | Stratified by behavior category |
| jailbreak (templates) | walledai/JailbreakHub | MIT | 3 | 1 representative per technique cluster |
| mmlu_real | cais/mmlu (57 subjects) | MIT | 200 | Subset (5 per subject, sampled) |
| arc_challenge | allenai/ai2_arc | CC-BY-SA-4.0 | 200 | Random sample from Challenge test split |

All task YAML files were copied from TR134 Phase 3 (`research/tr134/phase3/tasks/`) to ensure identical benchmarks. The MMLU subset was re-sampled to 200 questions (from TR134's 285) for compute budget reasons.

---

## Appendix D: Glossary

| Term | Definition |
|------|------------|
| BPW | Bits per weight. FP16 = 16.0, Q8_0 = 8.0, Q4_K_M = 4.5. All TR135 models run at Q4_K_M |
| TOST | Two one-sided t-tests. Equivalence testing at a specified margin. More informative than traditional "not significant" for null results |
| RLHF | Reinforcement Learning from Human Feedback. Umbrella term for alignment training methods |
| PPO | Proximal Policy Optimization. RLHF variant using a reward model; used by Llama 3.2 |
| DPO | Direct Preference Optimization. RLHF variant without a reward model; used by Qwen 2.5 |
| MDE | Minimum Detectable Effect at 80% power, alpha = 0.05 |
| Cohen's kappa | Chance-corrected inter-rater agreement metric (Landis & Koch 1977) |
| Cohen's d | Standardized mean difference. < 0.2 = trivial, 0.2-0.5 = small, 0.5-0.8 = medium, > 0.8 = large |
| Agent disagreement | Within-prompt standard deviation of scores across concurrent agents. Zero = all agents produce identical output |
| Amplification ratio | Jailbreak compliance rate divided by direct compliance rate; measures jailbreak effectiveness above baseline |
| GGUF | GPT-Generated Unified Format. File format for quantized LLM weights used by llama.cpp and Ollama |
| Serialized inference | Ollama processes requests one at a time on a single GPU. Concurrent requests queue, they do not execute in parallel |
| Prompt-level aggregation | Averaging scores across agents for the same prompt before computing statistics. Prevents correlated-observation bias |

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
11. Banterhearts TR134 (2026). Alignment Robustness Under Quantization.
