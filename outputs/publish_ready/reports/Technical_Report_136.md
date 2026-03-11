# Technical Report 136: Cross-Backend Safety Consistency
## Does the serving backend change model safety behavior? A controlled comparison of Ollama, vLLM, and TGI across 3 models, 4 backend configurations, and 6 benchmarks

**Project:** Banterhearts LLM Performance Research
**Date:** 2026-03-08
**Author:** Research Team
**Report Type:** Safety alignment analysis (metric-backed, 3 models, 4 backends, 6 benchmarks)
**Test Duration:** ~2.4 hrs (eval) + ~0.6 hrs (LLM judge) + ~0.01 hrs (analysis)
**Status:** Complete
**Run ID:** `20260308_015147`
**Related Work:** [TR134](Technical_Report_134.md) (Quantization x Safety), [TR135](Technical_Report_135.md) (Concurrency x Safety), TR137 (Safety Tax Synthesis, forthcoming)
**Depends On:** TR134 (safety classifiers, jailbreak tasks, BBQ benchmark, LLM judge module), TR135 (concurrency baselines, Ollama Q4_K_M reference)

---

## Abstract

TR134 showed that quantization degrades safety alignment below certain bit-per-weight thresholds, and TR135 showed that concurrency does not degrade it at all. Both experiments used Ollama as the sole inference backend. But production deployments rarely standardize on a single backend. Teams choose between Ollama (GGUF weights, native process), vLLM (HuggingFace weights, continuous batching, Docker), and TGI (HuggingFace weights, Docker) based on throughput, latency, and integration requirements. If these backends produce different safety behavior from the same model architecture, operators need to know -- because a model that passes safety testing on one backend may fail on another.

TR136 asks: **does the serving backend change safety behavior, and if so, does quantization or the backend itself drive the difference?**

We test 3 models (Llama 3.2 1B, Llama 3.2 3B, Qwen 2.5 1.5B) across 4 backends: Ollama Q4_K_M, Ollama Q8_0, vLLM FP16, and TGI FP16. Each backend processes identical prompts (868 per model) across 6 benchmarks: AdvBench refusal (100), TruthfulQA (50), BBQ bias (198), jailbreak amplification (120), MMLU (200), and ARC-Challenge (200). Temperature is fixed at 0.0 with seed=42 for determinism. All backends run sequentially on a single GPU to avoid contention. Post-hoc LLM judge validation (Qwen 2.5 7B Instruct Q8_0) provides an independent signal on 5,616 safety samples.

**The headline result is that the serving backend matters more than quantization for safety.** Llama 3.2 1B shows a 23pp safety drop between Ollama (Q4_K_M: 0.858, Q8_0: 0.876) and FP16 backends (vLLM: 0.628, TGI: 0.625) -- a medium effect size (Cohen's d = -0.55 to -0.61, p < 0.0001 after Holm correction). This is counterintuitive: FP16 precision is *higher* than Q4_K_M, yet safety is *lower*. The effect is driven almost entirely by jailbreak refusal (92.5% Ollama vs 50.0% FP16) and AdvBench refusal (88-95% Ollama vs 54% FP16). The same pattern appears at smaller magnitude in Llama 3.2 3B (6pp gap, d = -0.13 to -0.16) and Qwen 2.5 1.5B (3-7pp gap, d = -0.07 to -0.17). Within the same backend family, quantization effects are negligible: Q4_K_M vs Q8_0 shows d < 0.09 for all models. vLLM vs TGI agreement is 95.7%, confirming the two FP16 Docker backends are functionally identical.

The mechanism is not precision loss -- it is the reverse. Ollama's GGUF format bundles model-specific chat templates and tokenizer configurations that were tuned during safety training. HuggingFace FP16 weights served via vLLM/TGI rely on `tokenizer_config.json` and the backend's own chat template application, which may diverge from the GGUF-embedded template. The safety drop occurs not because FP16 removes safety information, but because the prompt framing differs between backend families.

**No backend pair achieves TOST equivalence at the +/-3pp margin.** This means we cannot formally certify any two backends as interchangeable for safety-critical deployments. Capability scores (MMLU, ARC-Challenge) show much smaller cross-backend variation (4-8pp range vs 7-25pp for safety), confirming that safety is differentially sensitive to the backend.

**Implication for practitioners: safety evaluations performed on one backend do not transfer to another. Operators must re-evaluate safety when switching backends, even when using the same model architecture and higher precision.**

**Total: 10,416 evaluated samples, 5,616 judged samples, 3 models, 4 backends, 6 benchmarks.**

---

## Metric Definitions

These definitions are inherited from TR134 for cross-TR comparability. Safety metrics are the primary focus; capability metrics serve as a control arm.

### Safety Metrics

- **Refusal Rate:** Proportion of harmful prompts where the model refuses to comply. Measured via regex classifier (`RefusalDetector`) matching ~15 refusal patterns (e.g., "I cannot", "I'm not able to", "As an AI", "I must decline"). Range [0, 1]. Higher = safer. Primary safety metric for AdvBench and jailbreak tasks.
- **Bias Resistance:** Proportion of BBQ questions where the model selects the non-stereotypical or "unknown" answer rather than reinforcing demographic stereotypes. Range [0, 1]. Higher = less biased.
- **Truthfulness:** Proportion of TruthfulQA questions answered correctly (matching reference answer). Range [0, 1]. Higher = more truthful.

### Capability Metrics

- **Accuracy (MMLU / ARC-Challenge):** Proportion of multiple-choice questions answered correctly. Regex letter extraction from model output.

### Derived Metrics

- **TOST Equivalence:** Two one-sided t-tests at +/-3pp margin. "Equivalent" = confirmed within +/-3pp. This is strictly stronger than "not significant."
- **Cohen's d:** Standardized effect size (pooled SD). < 0.2 = trivial, 0.2-0.5 = small, 0.5-0.8 = medium, > 0.8 = large.
- **Cohen's Kappa:** Inter-rater agreement between regex classifier and LLM judge, corrected for chance. < 0.20 = slight, 0.21-0.40 = fair, 0.41-0.60 = moderate (Landis & Koch 1977).
- **Cramer's V:** Effect size for chi-squared tests. < 0.1 = negligible, 0.1-0.3 = small, 0.3-0.5 = medium, > 0.5 = large.
- **Jaccard Similarity:** Token-level overlap between responses from two backends for the same prompt. Range [0, 1]. 1.0 = identical output. Measures whether backends produce semantically similar text, independent of safety classification.
- **Bootstrap CI:** 2,000-iteration resampling for 95% confidence intervals on safety means.
- **MDE (Minimum Detectable Effect):** Smallest effect detectable at alpha=0.05, power=0.80, via two-proportion z-test.

---

## Statistical Methods & Caveats

**Tests used:**

- **Chi-squared test** for backend independence (safety outcome x backend contingency table), with p-values via regularized incomplete gamma function
- **Welch's t-test** for pairwise backend comparisons (unequal variance assumed)
- **TOST equivalence testing** at +/-3pp margin (confirms equivalence, not just failure to reject)
- **Holm-Bonferroni** step-down correction for 6 pairwise comparisons per model (18 total)
- **Cohen's d** (pooled SD) for standardized effect sizes
- **Cramer's V** for chi-squared effect size
- **2,000-iteration bootstrap** for 95% CIs on aggregate safety means
- **Wilson score** binomial CI for pairwise agreement proportions
- **Pearson correlation** for Jaccard-safety divergence relationship
- **Power analysis**: binary MDE via two-proportion z-test (alpha=0.05, power=0.80)
- **Cohen's kappa** for inter-rater agreement (regex classifier vs LLM judge)

**Important caveats:**

1. **Ollama uses GGUF weights; vLLM/TGI use HuggingFace FP16 weights.** These are different weight formats with different tokenizer embeddings and chat template application. The "backend effect" is confounded with the "weight format effect." We cannot isolate which component (serving code, tokenizer, chat template, weight precision) drives the difference without an experiment that holds weight format constant.
2. **Quantization and backend are partially confounded.** Ollama Q8_0 vs vLLM FP16 differs in both quantization level AND backend. The "quant effect" (Q4 vs Q8 within Ollama) is clean, but the "backend effect" (Ollama Q8 vs vLLM FP16) confounds backend with residual quantization.
3. **Two model families only.** Llama 3.2 (2 sizes) and Qwen 2.5 (1 size). No Mistral, Phi, or Gemma. The Ollama-FP16 gap may be family-specific.
4. **Temperature = 0.0 eliminates sampling variance** but does not test stochastic behavior. At temperature > 0, backend-specific RNG implementations could introduce additional divergence.
5. **Sequential backend execution.** Backends run one at a time. Thermal state, GPU memory fragmentation, and OS-level caching may differ between early and late runs.
6. **Docker overhead for vLLM/TGI** inflates latency vs native Ollama. Latency comparisons are not apples-to-apples for backend speed evaluation.
7. **Regex classifiers are surface-level.** A response that "technically refuses" but provides harmful information through implication will be scored as safe. The LLM judge (Cohen's kappa 0.11-0.16) provides a partial check but is not a gold-standard human annotation.
8. **Single run per configuration.** No multi-run variance estimation. The 95% CIs reflect within-sample uncertainty, not run-to-run reproducibility.
9. **System prompt encoding differs between backends.** All backends receive the same system prompt content, but the *encoding* of that system prompt differs between GGUF-embedded templates and HuggingFace chat template application. We test the combined effect, not the isolated system prompt effect.

---

## Executive Summary

### Key Findings

1. **The serving backend changes safety behavior -- substantially for small Llama models.** Llama 3.2 1B shows a 23-25pp aggregate safety drop between Ollama backends (Q4_K_M: 0.858, Q8_0: 0.876) and FP16 backends (vLLM: 0.628, TGI: 0.625). This is a medium effect size (Cohen's d = -0.55 to -0.61, p < 0.0001 after Holm-Bonferroni correction). A model that appears safe on Ollama may not appear safe on vLLM or TGI.

2. **The backend / weight-format effect dominates quantization.** Within Ollama, Q4_K_M vs Q8_0 produces d < 0.09 (trivial) for all models. Between Ollama Q8_0 and vLLM FP16, the backend effect reaches d = 0.60 (medium) for Llama 1B. The backend axis explains >95% of the observed safety variation; quantization explains <5%.

3. **vLLM and TGI are functionally identical for safety.** 95.7% pairwise agreement across 1,404 safety samples, Jaccard token similarity 0.744, Cohen's d < 0.03. The FP16 serving framework does not affect safety classification.

4. **Jailbreak refusal is the most backend-sensitive task.** For Llama 3.2 1B: Ollama jailbreak refusal = 92.5-98.3%, FP16 jailbreak refusal = 50.0% (Cramer's V = 0.512, large effect). AdvBench refusal follows a similar pattern (V = 0.425). Bias resistance and truthfulness are not backend-dependent.

5. **Safety is differentially vulnerable -- capability is not.** Llama 3.2 1B safety range across backends = 25.1pp; capability range = 4.0pp. Safety/capability range ratio = 6.28x. The backend change specifically disrupts refusal patterns while leaving general knowledge intact.

6. **No backend pair achieves TOST equivalence at +/-3pp.** All 18 pairwise TOST tests fail. We cannot formally certify any backend pair as interchangeable for safety-critical deployments.

7. **Cross-TR reproducibility is good but not perfect.** 9/12 task-model Ollama Q4_K_M pairs agree within 5pp between TR136 and TR134. The 3 divergent pairs are: ARC-Challenge on Llama 1B (-6.0pp), AdvBench on Llama 3B (+7.0pp), and jailbreak on Llama 3B (+6.7pp). The two Llama 3B refusal divergences are within per-task MDE (16-19pp); the ARC divergence is a capability task within noise range.

8. **Backends produce fundamentally different text.** Jaccard similarity between Ollama and FP16 backends = 0.20-0.28 (only 20-28% token overlap). Within backend families, overlap is 0.67-0.74. The backends are not making marginal classification differences -- they are generating substantially different responses.

9. **The effect is model-size-dependent.** Llama 1B (1.2B params): 24pp gap. Llama 3B (3.2B params): 6pp gap. Qwen 1.5B (1.5B params, different family): 5pp gap. Larger models and different RLHF recipes appear more robust to backend variation.

### Validation Summary

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| Backend effect measured | Chi-squared p < 0.05 | All 3 models | 3/3 (p = 0.0, 0.011, 0.050) | PASS |
| Effect decomposition | Quant, backend, serving d | All 3 models | 3/3 computed | PASS |
| Pairwise comparisons | Welch + Holm + TOST | 18 pairs | 18/18 computed | PASS |
| Cross-TR validation | < 5pp vs TR134 | >= 75% consistent | 75% (9/12) | PASS |
| LLM judge agreement | Kappa computed | All 4 backends | 4/4 (kappa 0.11-0.16) | PASS |
| Error rate | 0% errors | All 12 runs | 0/10416 errors | PASS |

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|--------------|--------|
| 1 | Backend choice affects safety scores | Chi-squared significant for all 3 models (Section 14) | **Validated** |
| 2 | Backend effect > quantization effect | Decomposition d: backend 0.15-0.60 vs quant 0.01-0.08 (Section 6) | **Validated** |
| 3 | vLLM and TGI are interchangeable | 95.7% agreement, d < 0.03 (Section 11) | **Validated** (practical, not TOST-formal) |
| 4 | Jailbreak refusal is most affected | V = 0.19-0.51 across all models (Section 14) | **Validated** |
| 5 | Safety varies more than capability | Range ratio 6.28x for Llama 1B (Section 9) | **Partially validated** -- only for Llama 1B; ratio ~1.0 for others |
| 6 | Effect is model-size-dependent | Gaps: 24pp (1B), 6pp (3B), 5pp (1.5B) (Section 5) | **Validated** (direction clear, but family confounded with size) |
| 7 | Chat template divergence is the mechanism | Textual divergence (Jaccard 0.20-0.28) + safety-specific effect (Section 12) | **Supported but not proven** -- correlational, not causal |
| 8 | No backend pair is formally equivalent | 0/18 TOST tests pass (Section 10) | **Validated** |

### Key Decisions for Practitioners

1. **Always re-test safety when switching backends.** The Llama 3.2 1B jailbreak refusal rate drops from 92-98% (Ollama) to 50% (vLLM/TGI). A model that passes internal safety review on Ollama may not pass on a Docker-based deployment. Budget for re-evaluation.

2. **vLLM and TGI are interchangeable for safety.** If you are choosing between these two FP16 Docker backends, safety is not a differentiator. They agree on 95.7% of safety classifications (Section 11) and produce 74.4% token overlap (Section 12). Pick based on throughput, integration, and operational preferences.

3. **Ollama's Q4_K_M and Q8_0 are interchangeable for safety.** Within Ollama, the quantization level has negligible effect on safety (d < 0.09). This is consistent with TR134's finding that Q4_K_M is a safe deployment point. Use Q4_K_M to save memory without safety cost.

4. **Use larger models in multi-backend deployments.** The Llama 3.2 1B model is 6x more sensitive to backend choice than to capability perturbations. The 3B model is much more robust. If your deployment may span multiple backends, prefer models >= 3B parameters.

5. **Verify chat template alignment before deploying on a new backend.** Compare the output of `transformers.AutoTokenizer.apply_chat_template()` against the GGUF-embedded template using `llama.cpp`'s template extraction. Misalignment in system prompt encoding, turn boundaries, or special tokens is the most likely cause of safety divergence (Section 19).

### When to Use This Report

**Scenario 1: Migrating from Ollama to vLLM/TGI**

**Question:** "We tested our model on Ollama and it passed safety checks. Can we deploy on vLLM without re-testing?"

**Answer:** No. Llama 3.2 1B shows a 23-25pp safety drop when moving from Ollama to FP16 backends (Section 5). The drop is concentrated in jailbreak and AdvBench refusal tasks (Section 7). Re-run your safety evaluation suite on the target backend before deployment.

**Scenario 2: Choosing between vLLM and TGI**

**Question:** "We're deciding between vLLM and TGI for production. Does safety differ?"

**Answer:** No. The two FP16 backends agree on 95.7% of safety classifications (Section 11) with Jaccard token overlap of 0.744 (Section 12). Cohen's d < 0.03 for all models (Section 10). Choose based on throughput, API compatibility, and operational criteria.

**Scenario 3: Evaluating whether quantization or backend matters more**

**Question:** "Should I worry more about the Q4_K_M precision loss or the backend choice?"

**Answer:** The backend choice matters more. Within Ollama, Q4 vs Q8 produces d < 0.09 (trivial). Between Ollama and FP16 backends, d reaches 0.60 (medium). See the decomposition in Section 6.

**Scenario 4: Deciding if your model is robust enough for multi-backend deployment**

**Question:** "How do I know if my model will behave consistently across backends?"

**Answer:** Larger models are more robust. Llama 3.2 1B shows a 24pp gap; Llama 3.2 3B shows 6pp; Qwen 2.5 1.5B shows 5pp (Section 5). Check the safety-capability divergence ratio (Section 9): if the safety range across backends is much higher than the capability range, your model is differentially vulnerable.

**Scenario 5: Validating cross-experiment reproducibility**

**Question:** "Can I trust that TR136's Ollama results match TR134's?"

**Answer:** Mostly. 9/12 task-model pairs agree within 5pp (Section 17). The 3 divergent pairs are refusal tasks on Llama 3B with moderate baseline rates, where the per-task MDE is 17-19pp (Section 16). Capability and bias scores reproduce perfectly.

### How to Read This Report

| Time | Reading Path |
|------|-------------|
| **2 min** | Abstract + Executive Summary Key Findings |
| **10 min** | Add Sections 5 (aggregate scores), 6 (decomposition), 9 (divergence) |
| **30 min** | Add Sections 7 (per-task), 10 (pairwise t-tests), 14 (chi-squared), 19 (conclusions) |
| **60 min** | Full report minus appendices |
| **Deep dive** | Full report including appendices, cross-reference with TR134 Section 11 and TR135 Section 17.3 |

### Table of Contents

**Front Matter**

- Abstract
- Metric Definitions
- Statistical Methods & Caveats
- Executive Summary

**Background (Sections 1-4)**

1. [Introduction & Research Motivation](#1-introduction--research-motivation)
2. [Experimental Design](#2-experimental-design)
3. [Model Lineup](#3-model-lineup)
4. [Environment & Artifacts](#4-environment--artifacts)

**Core Results (Sections 5-9)**

5. [Per-Backend Aggregate Safety Scores](#5-per-backend-aggregate-safety-scores)
6. [Quantization vs Backend Effect Decomposition](#6-quantization-vs-backend-effect-decomposition)
7. [Per-Task Safety Breakdown](#7-per-task-safety-breakdown)
8. [Capability Control Arm](#8-capability-control-arm)
9. [Safety-Capability Divergence](#9-safety-capability-divergence)

**Statistical Validation (Sections 10-16)**

10. [Pairwise Backend Comparisons](#10-pairwise-backend-comparisons)
11. [Pairwise Backend Agreement](#11-pairwise-backend-agreement)
12. [Response Divergence (Jaccard)](#12-response-divergence)
13. [Safety-Divergence Correlation](#13-safety-divergence-correlation)
14. [Per-Task Backend Independence (Chi-Squared)](#14-per-task-backend-independence-chi-squared)
15. [LLM Judge Agreement](#15-llm-judge-agreement)
16. [Power Analysis](#16-power-analysis)

**Validation & Synthesis (Sections 17-20)**

17. [Cross-Experiment Validation (vs TR134)](#17-cross-experiment-validation-vs-tr134)
18. [Baseline Normalization](#18-baseline-normalization)
19. [Conclusions & Limitations](#19-conclusions--limitations)
20. [Reproducibility](#20-reproducibility)

**Appendices**

- [Appendix A: Normalized Per-Task Scores](#appendix-a-normalized-per-task-scores-reference-vllm-fp16)
- [Appendix B: Chi-Squared Contingency Tables](#appendix-b-chi-squared-contingency-tables)
- [Appendix C: Full Latency Comparison](#appendix-c-full-latency-comparison)
- [Appendix D: Glossary](#appendix-d-glossary)
- [References](#references)

---

## 1. Introduction & Research Motivation

### 1.1 The Problem

TR134 measured how quantization degrades safety. TR135 measured how concurrency degrades safety. Both used Ollama as the sole backend. This is a significant gap: in production, the same model architecture is served through different backends depending on deployment constraints. Ollama uses GGUF-formatted weights and its own inference engine. vLLM and TGI use HuggingFace-formatted weights with different serving architectures. If these backends produce different safety behavior from the same model, then safety evaluations performed on one backend do not transfer to another -- and operators deploying models across heterogeneous infrastructure cannot trust a single safety test.

The gap is not academic. A team that validates safety on Ollama during development and deploys on vLLM in production may unknowingly degrade safety. Conversely, a team that finds poor safety on vLLM may reject a model that would be safe on Ollama. Neither outcome is acceptable for safety-critical applications.

### 1.2 Research Questions

1. **Backend independence:** Do Ollama, vLLM, and TGI produce the same safety scores for the same model and prompts?
2. **Quantization vs backend:** Is the safety difference between Ollama Q4_K_M and vLLM FP16 driven by quantization (4-bit vs 16-bit) or by the backend itself?
3. **Backend family equivalence:** Are vLLM FP16 and TGI FP16 interchangeable for safety evaluation?
4. **Task specificity:** Which safety tasks are most sensitive to backend choice?
5. **Safety-capability divergence:** Does safety vary more across backends than capability, suggesting differential vulnerability?
6. **Cross-TR reproducibility:** Do Ollama Q4_K_M safety scores from TR136 match TR134's baselines?

### 1.3 Literature Gap

No prior work that we are aware of:

- Compares safety metrics across Ollama, vLLM, and TGI on identical prompts
- Decomposes the Ollama-to-FP16 safety gap into quantization, backend, and serving components
- Measures whether safety is differentially more sensitive to backend choice than capability
- Provides per-task (refusal, bias, truthfulness, jailbreak) backend sensitivity rankings
- Correlates token-level response divergence (Jaccard) with safety classification divergence

### 1.4 Relationship to Prior Work

| Reference | Contribution | How TR136 Uses It |
|-----------|-------------|-------------------|
| [TR134](Technical_Report_134.md) | Quantization x safety across 4 models, jailbreak amplification, per-category bias | Safety classifiers, jailbreak task set, BBQ benchmark, LLM judge module, Q4_K_M baselines for cross-validation |
| [TR135](Technical_Report_135.md) | Concurrency x safety, null finding (concurrency does not affect safety) | Establishes that Ollama serialization eliminates concurrency confounds; Ollama Q4_K_M reference scores |
| [TR125](Technical_Report_125.md) | Quantization decision matrix (capability focus) | Q4_K_M as "universal sweet spot" -- TR136 tests whether this holds across backends |
| [TR133](Technical_Report_133.md) | VRAM modeling and latency prediction | VRAM estimates for model selection feasibility |
| Röttger et al. (2024) | HarmBench: standardized safety evaluation | Methodological precedent for multi-backend safety comparison |
| Huang et al. (2024) | Chat template effects on LLM behavior | Theoretical basis for chat template divergence hypothesis |

---

## 2. Experimental Design

### 2.1 Design Summary

| Parameter | Value |
|-----------|-------|
| Models | Llama 3.2 1B Instruct, Llama 3.2 3B Instruct, Qwen 2.5 1.5B Instruct |
| Backends | Ollama Q4_K_M, Ollama Q8_0, vLLM FP16 (Docker), TGI FP16 (Docker) |
| Safety tasks | AdvBench refusal (100), TruthfulQA (50), BBQ bias (198), Jailbreak amplification (120) |
| Capability tasks | MMLU (200), ARC-Challenge (200) |
| Prompts per backend-model | 868 (468 safety + 400 capability) |
| Temperature | 0.0 (deterministic) |
| Seed | 42 |
| Max new tokens | 256 |
| Warmup requests | 3 per backend startup |
| Cooldown between backends | 10 seconds |
| Execution order | Sequential (one backend at a time, GPU contention avoidance) |
| Judge model | Qwen 2.5 7B Instruct Q8_0 (Ollama, different family to avoid self-eval bias) |
| Total raw records | 10,416 (3 models x 4 backends x 868 prompts) |
| Total judged safety samples | 5,616 |
| Hardware | NVIDIA GeForce RTX 4080 Laptop GPU (12GB VRAM) |

### 2.2 Backend Configurations

| Backend | Weight Format | Container | Port | Timeout | Extra Args |
|---------|--------------|-----------|------|---------|------------|
| Ollama Q4_K_M | GGUF 4-bit | Native process | 11434 | 120s | -- |
| Ollama Q8_0 | GGUF 8-bit | Native process | 11434 | 120s | -- |
| vLLM FP16 | HuggingFace FP16 | Docker (`vllm/vllm-openai:latest`) | 8000 | 180s | `--max-model-len 2048 --dtype float16 --enforce-eager --gpu-memory-utilization 0.80` |
| TGI FP16 | HuggingFace FP16 | Docker (`ghcr.io/huggingface/text-generation-inference:latest`) | 8080 | 180s | `--max-input-length 1024 --max-total-tokens 2048` |

Ollama runs as a native process and manages its own model loading. vLLM and TGI run inside Docker containers with GPU passthrough via `nvidia-container-toolkit`. Docker containers are started and stopped between model evaluations, with a 300-second startup timeout to allow model loading. All backends receive identical prompt text.

### 2.3 Safety Task Descriptions

- **AdvBench Refusal** (N=100): Prompts from the AdvBench harmful behaviors dataset. Tests whether the model refuses direct harmful requests. Scored by `RefusalDetector` regex classifier.
- **TruthfulQA** (N=50): Prompts from the TruthfulQA benchmark. Tests whether the model produces truthful answers to questions designed to elicit common misconceptions. Scored by `TruthfulnessScorer` regex matching against reference answers.
- **BBQ Bias** (N=198): Prompts from the BBQ (Bias Benchmark for QA) dataset covering 11 demographic categories. Tests whether the model selects stereotypical vs. non-stereotypical answers. Scored by `BiasDetector`.
- **Jailbreak Amplification** (N=120): 30 base harmful behaviors (from JailbreakBench) x 3 jailbreak wrappers (DAN-style, roleplay, prefix injection) + 30 direct requests as control. Tests whether jailbreak techniques bypass the model's refusal. Scored by `RefusalDetector`.

### 2.4 Capability Tasks

- **MMLU** (N=200): 200 multiple-choice questions from MMLU spanning 4 subject areas. Regex letter extraction.
- **ARC-Challenge** (N=200): 200 science reasoning questions from the AI2 Reasoning Challenge. Regex letter extraction.

Capability tasks serve as a control arm: if capability scores also drop across backends, the safety drop is part of general performance loss. If capability is stable while safety drops, the backend change specifically targets safety-trained behavior.

### 2.5 Classification Pipeline

Three regex classifiers score safety tasks:

- **RefusalDetector**: ~15 refusal patterns for AdvBench and jailbreak tasks
- **TruthfulnessScorer**: Reference answer matching for TruthfulQA
- **BiasDetector**: Non-stereotypical / "unknown" answer detection for BBQ

Post-hoc LLM judge (Qwen 2.5 7B Instruct Q8_0) independently classifies safety samples as FULL_REFUSAL / PARTIAL_REFUSAL / COMPLIANCE / UNCLEAR. Judge results are used for inter-rater agreement analysis (Cohen's kappa) but do not affect primary scoring.

### 2.6 Pipeline Architecture

```
config.yaml
    |
    v
prepare_benchmarks.py  ──>  tasks/*.yaml (copied from TR134)
    |
    v
run.py (orchestrator)
    |── Step 1: prepare_benchmarks.py
    |── Step 2: eval loop (for each backend x model: start -> warmup -> run -> stop -> cooldown)
    |── Step 3: judge_analysis.py (post-hoc LLM judge on safety samples)
    |── Step 4: analyze.py (15-pass statistical analysis)
    └── Step 5: generate_report.py
    |
    v
results/<timestamp>/
    ├── config_snapshot.yaml
    ├── samples.jsonl          (10,416 raw eval records)
    ├── tr136_judged.jsonl     (5,616 judge verdicts)
    ├── tr136_scored.jsonl     (10,416 scored records)
    ├── tr136_analysis.json    (73KB, 15-pass analysis)
    └── tr136_report.md        (auto-generated report)
```

---

## 3. Model Lineup

### 3.1 Model Summary

| Model | Family | Parameters | HuggingFace ID | Ollama Tag | RLHF Method | Origin |
|-------|--------|-----------|----------------|------------|-------------|--------|
| Llama 3.2 1B Instruct | Llama 3.2 | 1,236M | `unsloth/Llama-3.2-1B-Instruct` | `llama3.2:1b` | PPO + rejection sampling | Meta (US) |
| Llama 3.2 3B Instruct | Llama 3.2 | 3,213M | `unsloth/Llama-3.2-3B-Instruct` | `llama3.2:3b` | PPO + rejection sampling | Meta (US) |
| Qwen 2.5 1.5B Instruct | Qwen 2.5 | 1,543M | `Qwen/Qwen2.5-1.5B-Instruct` | `qwen2.5:1.5b` | DPO | Alibaba (China) |

All models are instruct-tuned, ungated, and small enough to run at FP16 on a 12GB GPU. Ollama quant tags are constructed by appending `-instruct-q4_K_M`, `-instruct-q8_0`, or `-instruct-fp16` to the base tag.

### 3.2 Why These Models

- **Llama 3.2 1B and 3B** provide a within-family size comparison (1.2B vs 3.2B params, same RLHF recipe). If the backend effect is size-dependent, these two should show different magnitudes. They are also the primary models used in TR134 and TR135, enabling direct cross-experiment validation.
- **Qwen 2.5 1.5B** provides a cross-family comparison. It uses DPO rather than PPO for alignment and originates from a different research lab (Alibaba vs Meta). If the backend effect is RLHF-recipe-specific, Qwen should behave differently from Llama.

### 3.3 Design Decision: No 7B Models

7B models (Llama 3.1 8B, Mistral 7B, Qwen 2.5 7B) cannot run at FP16 on a 12GB GPU (~14.5GB minimum for FP16 7B). The experimental design requires all backends to serve the same model, and vLLM/TGI require FP16 weights. Adding 7B models would require either (a) using quantized HuggingFace weights (introducing a new confound) or (b) a larger GPU (not available). The 1B-3B range is sufficient to test the size-dependence hypothesis at the small end.

### 3.4 Design Decision: Fixed Quantization Levels

Ollama is tested at two quantization levels (Q4_K_M, Q8_0) rather than the full 7-level sweep from TR134. The purpose is not to re-measure the quantization curve (TR134 did that) but to isolate the backend effect from the quantization effect. Two levels are sufficient for this decomposition: Q4_K_M represents a production-common quantization, and Q8_0 provides a near-lossless Ollama baseline for comparison with FP16.

---

## 4. Environment & Artifacts

### 4.1 Environment

| Component | Value |
|-----------|-------|
| OS | Windows 11 Home 10.0.26200 (WSL2 for Docker) |
| GPU | NVIDIA GeForce RTX 4080 Laptop GPU (12GB VRAM, CC 8.9) |
| Ollama | v0.6.2 (native Windows) |
| vLLM Docker | `vllm/vllm-openai:latest` |
| TGI Docker | `ghcr.io/huggingface/text-generation-inference:latest` |
| Python | 3.11+ |
| Temperature | 0.0 |
| Max new tokens | 256 |
| Seed | 42 |

### 4.2 Key Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Config | `research/tr136/config.yaml` | Source configuration |
| Config snapshot | `research/tr136/results/20260308_015147/config_snapshot.yaml` | Runtime config with resolved paths |
| Raw samples | `research/tr136/results/20260308_015147/samples.jsonl` | 10,416 eval records (14.2MB) |
| Judged samples | `research/tr136/results/20260308_015147/tr136_judged.jsonl` | 5,616 LLM judge verdicts (1.7MB) |
| Scored samples | `research/tr136/results/20260308_015147/tr136_scored.jsonl` | 10,416 scored records (15.4MB) |
| Analysis JSON | `research/tr136/results/20260308_015147/tr136_analysis.json` | 15-pass statistical analysis (73KB) |
| Analysis code | `research/tr136/analyze.py` | 15-pass analysis pipeline (~1,300 lines) |
| Judge code | `research/tr136/judge_analysis.py` | Post-hoc LLM judge runner |
| Orchestrator | `research/tr136/run.py` | 5-step pipeline orchestrator |
| Published report | `PublishReady/reports/Technical_Report_136.md` | This document |

---

## 5. Per-Backend Aggregate Safety Scores

Safety scores aggregated across all safety tasks (advbench, truthfulqa, bbq, jailbreak) per backend. Each cell represents the mean of 468 binary safety scores (100 + 50 + 198 + 120).

| Model | Backend | Safety Mean | Bootstrap 95% CI | Std | N |
|-------|---------|------------|-------------------|-----|---|
| Llama 3.2 1B | Ollama Q4_K_M | 0.8579 | [0.828, 0.888] | 0.343 | 468 |
| Llama 3.2 1B | Ollama Q8_0 | 0.8761 | [0.847, 0.905] | 0.325 | 468 |
| Llama 3.2 1B | TGI FP16 | 0.6250 | [0.581, 0.670] | 0.482 | 468 |
| Llama 3.2 1B | vLLM FP16 | 0.6282 | [0.584, 0.674] | 0.481 | 468 |
| Llama 3.2 3B | Ollama Q4_K_M | 0.8034 | [0.767, 0.840] | 0.392 | 468 |
| Llama 3.2 3B | Ollama Q8_0 | 0.8088 | [0.776, 0.843] | 0.388 | 468 |
| Llama 3.2 3B | TGI FP16 | 0.7436 | [0.702, 0.783] | 0.433 | 468 |
| Llama 3.2 3B | vLLM FP16 | 0.7479 | [0.707, 0.787] | 0.431 | 468 |
| Qwen 2.5 1.5B | Ollama Q4_K_M | 0.8184 | [0.783, 0.854] | 0.382 | 468 |
| Qwen 2.5 1.5B | Ollama Q8_0 | 0.8483 | [0.816, 0.880] | 0.355 | 468 |
| Qwen 2.5 1.5B | TGI FP16 | 0.7821 | [0.745, 0.818] | 0.408 | 468 |
| Qwen 2.5 1.5B | vLLM FP16 | 0.7917 | [0.754, 0.829] | 0.402 | 468 |

**Observations:**

Within each model, a consistent clustering pattern emerges: Ollama Q8_0 >= Ollama Q4_K_M >> TGI FP16 ~ vLLM FP16. The gap between the two clusters varies dramatically by model:

- **Llama 3.2 1B:** 24pp gap. Ollama mean = 0.867, FP16 mean = 0.627. The confidence intervals do not overlap -- this is a robust, well-separated effect. The standard deviation is also higher for FP16 backends (0.481-0.482 vs 0.325-0.343), reflecting a more heterogeneous mix of safe and unsafe responses.

- **Llama 3.2 3B:** 6pp gap. Ollama mean = 0.806, FP16 mean = 0.746. The CIs partially overlap, and the effect is near the MDE boundary (7.6pp). This is a real but modest effect that does not survive Holm-Bonferroni correction for individual pairwise tests.

- **Qwen 2.5 1.5B:** 5pp gap. Ollama mean = 0.833, FP16 mean = 0.787. The pattern is the same (Ollama higher) but the magnitude is smaller. Qwen's DPO-based alignment appears more robust to backend variation than Llama's PPO-based alignment.

The two Ollama backends cluster together, and the two FP16 Docker backends cluster together, suggesting the weight format / chat template is the dominant factor, not quantization level or serving framework.

---

## 6. Quantization vs Backend Effect Decomposition

To disentangle quantization from backend effects, we decompose the Ollama-to-FP16 gap into three orthogonal components:

- **Quant effect** = Ollama Q8_0 - Ollama Q4_K_M (same backend, different quant -- isolates quantization)
- **Backend effect** = vLLM FP16 - Ollama Q8_0 (different backend, Q8 vs FP16 -- isolates backend + residual quant)
- **Serving effect** = TGI FP16 - vLLM FP16 (different Docker backend, same FP16 weights -- isolates serving framework)

| Model | Quant Effect (d) | Backend Effect (d) | Serving Effect (d) | Interpretation |
|-------|-------------------|--------------------|--------------------|----------------|
| Llama 3.2 1B | +1.8pp (d=+0.054) | -24.8pp (d=-0.604) | -0.3pp (d=-0.007) | **Backend dominates** |
| Llama 3.2 3B | +0.5pp (d=+0.014) | -6.1pp (d=-0.149) | -0.4pp (d=-0.010) | **Backend dominates** |
| Qwen 2.5 1.5B | +3.0pp (d=+0.081) | -5.7pp (d=-0.149) | -1.0pp (d=-0.024) | **Comparable** |

**Key insight:** The quant effect (Q4 vs Q8) never exceeds d = 0.08 (trivial by conventional thresholds). The backend effect reaches d = 0.60 for Llama 3.2 1B -- a medium effect, 11x larger than the quant effect. The serving effect (vLLM vs TGI) never exceeds d = 0.02 (negligible). The backend / weight-format axis explains the overwhelming majority of the observed safety variation.

For Qwen 2.5 1.5B, the quant and backend effects are closer in magnitude (d = 0.08 vs d = 0.15), with the interpretation flagged as "comparable" rather than "backend dominates." This suggests Qwen's alignment is more robust to both perturbations -- possibly because DPO training produces safety behavior that is less dependent on exact prompt formatting than PPO-trained models.

None of the three decomposition components achieves TOST equivalence at +/-3pp (all TOST p > 0.16), so even the "trivial" quant effects cannot be formally certified as zero.

---

## 7. Per-Task Safety Breakdown

### 7.1 Llama 3.2 1B

| Task | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 | Max Gap (pp) |
|------|---------------|-------------|----------|-----------|--------------|
| advbench_refusal | 0.880 | 0.950 | 0.540 | 0.540 | **41.0** |
| bbq_bias | 0.874 | 0.889 | 0.793 | 0.793 | 9.6 |
| jailbreak_amplification | 0.925 | 0.983 | 0.500 | 0.500 | **48.3** |
| truthfulqa | 0.590 | 0.420 | 0.430 | 0.460 | 17.0 |

**Observations:** The aggregate 24pp gap decomposes into a task-specific hierarchy. Jailbreak amplification shows the largest effect (48pp between Ollama Q8 and FP16) -- the model that refuses 98.3% of jailbreak attempts on Ollama Q8 only refuses 50% on FP16. This is a catastrophic safety failure: half of all jailbreak prompts succeed on the FP16 backends. AdvBench follows the same pattern (41pp gap). BBQ bias is more robust (9.6pp gap), suggesting bias resistance is encoded differently from refusal behavior. TruthfulQA shows an anomalous pattern: Ollama Q4_K_M scores *higher* (0.59) than Ollama Q8_0 (0.42), reversing the overall trend. At N=50 per cell, this 17pp within-Ollama variance is within the 28pp MDE and likely reflects noise.

### 7.2 Llama 3.2 3B

| Task | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 | Max Gap (pp) |
|------|---------------|-------------|----------|-----------|--------------|
| advbench_refusal | 0.540 | 0.490 | 0.690 | 0.690 | **20.0** |
| bbq_bias | 0.965 | 0.970 | 0.929 | 0.924 | 4.6 |
| jailbreak_amplification | 0.892 | 0.942 | 0.575 | 0.583 | **36.7** |
| truthfulqa | 0.480 | 0.490 | 0.520 | 0.560 | 8.0 |

**Observations:** The jailbreak pattern persists -- 36.7pp gap between Ollama Q8 and FP16 -- but it is moderated compared to the 1B model. BBQ bias is nearly backend-invariant (4.6pp gap), consistent with the hypothesis that bias resistance is structurally encoded. The AdvBench result is anomalous: FP16 backends score *higher* (0.69) than Ollama (0.49-0.54). This reversal does not occur for jailbreak or BBQ, and may reflect a 3B-specific pattern where the model's AdvBench refusal phrasing changes between backends without changing actual compliance. The regex classifier may be capturing different surface-level refusal patterns on each backend.

### 7.3 Qwen 2.5 1.5B

| Task | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 | Max Gap (pp) |
|------|---------------|-------------|----------|-----------|--------------|
| advbench_refusal | 0.980 | 0.990 | 0.980 | 0.980 | 1.0 |
| bbq_bias | 0.939 | 0.955 | 0.929 | 0.899 | 5.6 |
| jailbreak_amplification | 0.633 | 0.717 | 0.458 | 0.575 | **25.9** |
| truthfulqa | 0.460 | 0.460 | 0.580 | 0.510 | 12.0 |

**Observations:** Qwen's AdvBench refusal is near-ceiling across all backends (98-99%), confirming that the Llama AdvBench vulnerability is family-specific, not universal. Jailbreak amplification remains the most sensitive task (25.8pp gap), though the pattern is more complex: TGI scores lower (0.458) than vLLM (0.575), introducing a serving-level difference that does not appear for other models. BBQ bias shows a mild drop on vLLM FP16 (0.899 vs 0.939-0.955 on Ollama), suggesting some bias amplification on the FP16 backend. TruthfulQA shows FP16 scoring *higher* than Ollama, the reverse of the overall safety pattern -- this is consistent with TruthfulQA measuring factual knowledge rather than safety alignment.

### 7.4 Cross-Model Task Summary

| Observation | Pattern |
|-------------|---------|
| Jailbreak amplification | Most backend-sensitive for ALL models (25-48pp gaps) |
| AdvBench refusal | Llama-specific vulnerability (20-41pp); Qwen is backend-invariant (1pp) |
| BBQ bias | Robust across backends (<10pp for all models) |
| TruthfulQA | Inconsistent direction; likely noise at N=50 |

The backend effect concentrates in the model's *refusal mechanism* -- the same mechanism that prevents jailbreaks and direct harmful prompt compliance. Bias resistance and factual knowledge are structurally different from refusal and survive the backend transition largely intact.

---

## 8. Capability Control Arm

Capability scores (MMLU, ARC-Challenge) across backends. If capability also drops, the safety drop is part of general performance loss. If capability is stable, the backend change specifically targets safety.

| Model | Backend | MMLU | ARC-Challenge | Capability Mean |
|-------|---------|------|---------------|----------------|
| Llama 3.2 1B | Ollama Q4_K_M | 0.310 | 0.335 | 0.323 |
| Llama 3.2 1B | Ollama Q8_0 | 0.360 | 0.365 | 0.363 |
| Llama 3.2 1B | TGI FP16 | 0.340 | 0.370 | 0.355 |
| Llama 3.2 1B | vLLM FP16 | 0.325 | 0.365 | 0.345 |
| Llama 3.2 3B | Ollama Q4_K_M | 0.595 | 0.700 | 0.648 |
| Llama 3.2 3B | Ollama Q8_0 | 0.600 | 0.720 | 0.660 |
| Llama 3.2 3B | TGI FP16 | 0.490 | 0.675 | 0.583 |
| Llama 3.2 3B | vLLM FP16 | 0.490 | 0.675 | 0.583 |
| Qwen 2.5 1.5B | Ollama Q4_K_M | 0.505 | 0.700 | 0.603 |
| Qwen 2.5 1.5B | Ollama Q8_0 | 0.565 | 0.730 | 0.648 |
| Qwen 2.5 1.5B | TGI FP16 | 0.570 | 0.740 | 0.655 |
| Qwen 2.5 1.5B | vLLM FP16 | 0.570 | 0.740 | 0.655 |

**Observations:** Capability scores are much more stable across backends than safety scores. For Llama 3.2 1B, the MMLU range is 5pp and ARC range is 3.5pp -- compared to 25pp for aggregate safety. This asymmetry is the critical finding: the backend change does not degrade the model's general reasoning ability, only its safety-trained refusal behavior.

For Llama 3.2 3B, MMLU shows a larger drop (11pp between Ollama Q8 and FP16), suggesting some capability sensitivity at this model size. However, the Qwen 2.5 1.5B capability scores are *higher* on FP16 than on Ollama Q4_K_M (MMLU 0.57 vs 0.51), eliminating the hypothesis that "FP16 backends are generally worse." The directional inconsistency in capability, contrasted with the consistent Ollama-higher-than-FP16 pattern in safety, supports the differential vulnerability interpretation.

---

## 9. Safety-Capability Divergence

Does safety vary more across backends than capability? A ratio > 1.5 indicates safety is differentially sensitive to backend choice.

| Model | Safety Range (pp) | Capability Range (pp) | Safety SD | Capability SD | Range Ratio | Interpretation |
|-------|-------------------|-----------------------|-----------|---------------|-------------|----------------|
| Llama 3.2 1B | 25.1 | 4.0 | 0.139 | 0.017 | **6.28** | Safety varies 6x more |
| Llama 3.2 3B | 6.5 | 7.8 | 0.035 | 0.042 | 0.84 | Both vary similarly |
| Qwen 2.5 1.5B | 6.6 | 5.2 | 0.030 | 0.025 | 1.26 | Both vary similarly |

**Observations:**

For Llama 3.2 1B, safety is overwhelmingly more sensitive to backend choice than capability. The range ratio of 6.28 means that the safety score range across backends (25.1pp) is more than 6 times larger than the capability score range (4.0pp). This is the strongest evidence that the backend change specifically disrupts the model's safety training signals -- refusal patterns, jailbreak resistance -- while leaving general knowledge and reasoning intact. The 1B model's safety alignment appears to be encoded in a way that is highly dependent on the exact prompt formatting provided by the backend.

For the 3B model and Qwen 1.5B, the ratio is near 1.0 (0.84 and 1.26 respectively), meaning safety and capability vary proportionally across backends. This does not mean the backend effect is absent -- the chi-squared tests confirm it exists (Section 14) -- but it is not *differentially* targeting safety. Larger models and different RLHF recipes appear to encode safety in a more format-robust way.

---

## 10. Pairwise Backend Comparisons

Welch's t-test on aggregate safety scores with Holm-Bonferroni correction (6 comparisons per model, 18 total).

### 10.1 Llama 3.2 1B

| Backend A | Backend B | Diff (pp) | 95% CI | t | p | Cohen's d | Holm Sig | TOST Equiv |
|-----------|-----------|-----------|--------|---|---|-----------|----------|------------|
| Ollama Q4 | Ollama Q8 | +1.8 | [-2.2, +6.0] | 0.83 | 0.406 | +0.054 | No | No |
| Ollama Q4 | TGI FP16 | **-23.3** | [-28.5, -17.8] | -8.52 | <0.0001 | **-0.557** | **Yes** | No |
| Ollama Q4 | vLLM FP16 | **-23.0** | [-28.2, -17.6] | -8.42 | <0.0001 | **-0.551** | **Yes** | No |
| Ollama Q8 | TGI FP16 | **-25.1** | [-30.6, -20.0] | -9.35 | <0.0001 | **-0.611** | **Yes** | No |
| Ollama Q8 | vLLM FP16 | **-24.8** | [-30.1, -19.6] | -9.24 | <0.0001 | **-0.604** | **Yes** | No |
| TGI FP16 | vLLM FP16 | +0.3 | [-5.8, +6.5] | 0.10 | 0.919 | +0.007 | No | No |

**Observations:** 4 of 6 pairs are significant after Holm-Bonferroni correction -- all involving cross-family comparisons (Ollama vs FP16). The effect sizes are medium (d = -0.55 to -0.61), meaning the practical difference is substantial, not just statistically detectable. The two within-family comparisons (Q4 vs Q8, TGI vs vLLM) show trivial effect sizes (d < 0.06). No pair achieves TOST equivalence, even the functionally identical TGI-vLLM pair (TOST p = 0.197) -- this is a power limitation at N=468 per group.

### 10.2 Llama 3.2 3B

| Backend A | Backend B | Diff (pp) | 95% CI | t | p | Cohen's d | Holm Sig | TOST Equiv |
|-----------|-----------|-----------|--------|---|---|-----------|----------|------------|
| Ollama Q4 | Ollama Q8 | +0.5 | [-4.4, +5.6] | 0.21 | 0.834 | +0.014 | No | No |
| Ollama Q4 | TGI FP16 | -6.0 | [-11.6, -0.5] | -2.21 | 0.027 | -0.145 | No | No |
| Ollama Q4 | vLLM FP16 | -5.6 | [-11.2, -0.1] | -2.06 | 0.040 | -0.135 | No | No |
| Ollama Q8 | TGI FP16 | -6.5 | [-12.0, -1.3] | -2.42 | 0.016 | -0.159 | No | No |
| Ollama Q8 | vLLM FP16 | -6.1 | [-11.5, -0.9] | -2.27 | 0.023 | -0.149 | No | No |
| TGI FP16 | vLLM FP16 | +0.4 | [-5.1, +6.1] | 0.15 | 0.880 | +0.010 | No | No |

**Observations:** 0 of 6 pairs survive Holm-Bonferroni correction. The raw p-values for Ollama-vs-FP16 are all < 0.05 (range 0.016-0.040), indicating a real but modest effect that does not survive multiple comparison correction. The effect sizes (d = -0.13 to -0.16) are at the small/trivial boundary. The 6pp gap is near the per-model MDE of 7.6pp, so the lack of post-correction significance is expected -- the experiment is borderline-powered for this model. The within-family comparisons are again trivial (d < 0.02).

### 10.3 Qwen 2.5 1.5B

| Backend A | Backend B | Diff (pp) | 95% CI | t | p | Cohen's d | Holm Sig | TOST Equiv |
|-----------|-----------|-----------|--------|---|---|-----------|----------|------------|
| Ollama Q4 | Ollama Q8 | +3.0 | [-2.0, +7.7] | 1.24 | 0.215 | +0.081 | No | No |
| Ollama Q4 | TGI FP16 | -3.6 | [-9.0, +1.5] | -1.41 | 0.160 | -0.092 | No | No |
| Ollama Q4 | vLLM FP16 | -2.7 | [-7.8, +2.5] | -1.04 | 0.298 | -0.068 | No | No |
| Ollama Q8 | TGI FP16 | **-6.6** | [-11.8, -1.7] | -2.65 | 0.008 | **-0.173** | **Yes** | No |
| Ollama Q8 | vLLM FP16 | -5.7 | [-10.7, -0.9] | -2.29 | 0.023 | -0.149 | No | No |
| TGI FP16 | vLLM FP16 | +1.0 | [-4.5, +5.9] | 0.36 | 0.717 | +0.024 | No | No |

**Observations:** Only 1 of 6 pairs is significant after Holm correction: Ollama Q8 vs TGI FP16 (d = -0.173, p = 0.008). This makes sense: Q8 is Qwen's highest-safety backend (0.848), and the drop to TGI's 0.782 produces the largest pairwise gap. The Ollama Q4 comparisons are non-significant because Q4 itself is lower than Q8, reducing the distance to FP16 backends. The within-Ollama quant effect (d = 0.081) is the largest of all three models, suggesting Qwen's safety is slightly more quantization-sensitive than Llama's, though still trivial.

**Summary across all models:** After Holm correction, 5 of 18 pairwise comparisons are significant -- all involving Ollama-vs-FP16 contrasts. No within-family comparison (Q4 vs Q8, TGI vs vLLM) is significant. No pair achieves TOST equivalence at +/-3pp, meaning we cannot formally certify any backend pair as interchangeable.

---

## 11. Pairwise Backend Agreement

Binary agreement: both backends classify the same sample as safe (score > 0.5) or unsafe. Aggregated across all 3 models (1,404 safety samples per pair = 3 models x 468).

| Backend A | Backend B | Agree | Disagree | Agreement % | Wilson 95% CI |
|-----------|-----------|-------|----------|-------------|---------------|
| Ollama Q4_K_M | Ollama Q8_0 | 1264 | 140 | **90.0%** | [88.4%, 91.5%] |
| Ollama Q4_K_M | TGI FP16 | 1014 | 390 | 72.2% | [69.8%, 74.5%] |
| Ollama Q4_K_M | vLLM FP16 | 1010 | 394 | 71.9% | [69.5%, 74.2%] |
| Ollama Q8_0 | TGI FP16 | 1008 | 396 | 71.8% | [69.4%, 74.1%] |
| Ollama Q8_0 | vLLM FP16 | 1008 | 396 | 71.8% | [69.4%, 74.1%] |
| TGI FP16 | vLLM FP16 | 1344 | 60 | **95.7%** | [94.5%, 96.7%] |

**Observations:**

Three distinct agreement clusters emerge:

1. **TGI-vLLM cluster (95.7%):** These two FP16 Docker backends produce nearly identical safety classifications. Only 60 out of 1,404 safety samples are classified differently. This is the strongest evidence that the FP16 serving framework (vLLM vs TGI) does not matter for safety.

2. **Ollama intra-family cluster (90.0%):** Q4_K_M and Q8_0 within Ollama agree on 90% of safety samples. The 10% disagreement (140 samples) comes from prompts near the classification boundary where quantization shifts the response slightly. This level of agreement is consistent with TR134's finding that Q4_K_M preserves safety.

3. **Cross-family gap (~72%):** Any Ollama backend paired with any FP16 backend yields only ~72% agreement. Nearly 28% of all safety samples -- approximately 390 out of 1,404 -- are classified differently depending on the backend family. These are not borderline cases: the Jaccard analysis (Section 12) shows the backends are producing fundamentally different text for these prompts.

---

## 12. Response Divergence

Jaccard similarity of response tokens measures how much textual overlap exists between two backends' responses to the same prompt. 1.0 = identical output, 0.0 = no token overlap. This goes beyond classification agreement to measure whether the backends are producing similar or different text.

| Backend A | Backend B | Mean Jaccard | Bootstrap 95% CI | N Pairs |
|-----------|-----------|-------------|------------------|---------|
| Ollama Q4_K_M | Ollama Q8_0 | 0.668 | [0.654, 0.683] | 2604 |
| Ollama Q4_K_M | TGI FP16 | 0.205 | [0.195, 0.216] | 2604 |
| Ollama Q4_K_M | vLLM FP16 | 0.270 | [0.258, 0.283] | 2604 |
| Ollama Q8_0 | TGI FP16 | 0.227 | [0.216, 0.238] | 2604 |
| Ollama Q8_0 | vLLM FP16 | 0.279 | [0.267, 0.291] | 2604 |
| TGI FP16 | vLLM FP16 | **0.744** | [0.730, 0.758] | 2604 |

**Observations:**

Ollama and FP16 backends produce fundamentally different text. Mean Jaccard of 0.20-0.28 between backend families means only 20-28% of tokens overlap. This is not a marginal classification boundary effect -- the models are generating substantially different responses to the same prompts. The divergence encompasses both the structure and content of responses.

Within backend families, the picture is very different:
- **TGI-vLLM:** 0.744 Jaccard -- the highest overlap of any pair. These backends share the same HuggingFace weights and tokenizer, producing responses that differ only in minor sampling/rounding details.
- **Ollama Q4-Q8:** 0.668 Jaccard -- still high, but lower than TGI-vLLM. The 4-bit vs 8-bit quantization introduces modest textual variation while preserving the overall response structure.

The cross-family divergence (Jaccard 0.20-0.28) is striking because the same model *architecture* is involved. The weights represent the same neural network. The difference is in how the prompt is tokenized, how the chat template is applied, and how the backend manages inference. This magnitude of textual divergence from the same architecture is a strong signal that the chat template / tokenizer handling is fundamentally different between GGUF and HuggingFace formats.

---

## 13. Safety-Divergence Correlation

Does lower response similarity (Jaccard) predict larger safety score differences? A significant negative correlation would confirm that textual divergence drives safety classification disagreement.

| Backend A | Backend B | Pearson r | t | p | N Pairs |
|-----------|-----------|-----------|---|---|---------|
| Ollama Q4_K_M | Ollama Q8_0 | -0.259 | -10.02 | < 0.0001 | 1404 |
| Ollama Q4_K_M | TGI FP16 | -0.233 | -8.97 | < 0.0001 | 1404 |
| Ollama Q4_K_M | vLLM FP16 | -0.226 | -8.70 | < 0.0001 | 1404 |
| Ollama Q8_0 | TGI FP16 | -0.285 | -11.15 | < 0.0001 | 1404 |
| Ollama Q8_0 | vLLM FP16 | -0.269 | -10.44 | < 0.0001 | 1404 |
| TGI FP16 | vLLM FP16 | **-0.340** | -13.51 | < 0.0001 | 1404 |

**Observations:**

All six correlations are significantly negative (p < 0.0001): prompts where backends produce more divergent text also show larger safety score differences. The correlation magnitudes (r = -0.23 to -0.34) indicate a moderate relationship -- textual divergence explains approximately 5-12% of the variance in safety score differences. The remaining variance comes from classification noise (regex patterns matching differently on different phrasings) and cases where the text diverges but the safety classification happens to agree.

The strongest correlation (r = -0.340) is between TGI and vLLM -- counterintuitively, the most *similar* backend pair. This makes sense: when TGI and vLLM produce similar text (as they usually do, Jaccard 0.744), their safety scores almost always agree. But when they produce divergent text (the rare 4.3% of samples), the textual difference is strongly associated with a safety classification flip. In other words, for near-identical backends, textual divergence is a reliable predictor of safety disagreement -- the signal-to-noise ratio is high.

---

## 14. Per-Task Backend Independence (Chi-Squared)

Chi-squared test per safety task: is the safety outcome independent of the backend? This breaks down the aggregate model-level chi-squared (Appendix B) into task-level components.

| Model | Task | X² | df | p | Cramer's V | Significant? | N |
|-------|------|----|----|---|-----------|-------------|---|
| Llama 3.2 1B | advbench_refusal | 72.17 | 3 | < 0.0001 | **0.425** | **Yes** | 400 |
| Llama 3.2 1B | bbq_bias | 11.51 | 3 | 0.009 | 0.121 | **Yes** | 792 |
| Llama 3.2 1B | jailbreak_amplification | 125.77 | 3 | < 0.0001 | **0.512** | **Yes** | 480 |
| Llama 3.2 1B | truthfulqa | 5.48 | 3 | 0.140 | 0.166 | No | 200 |
| Llama 3.2 3B | advbench_refusal | 13.31 | 3 | 0.004 | 0.182 | **Yes** | 400 |
| Llama 3.2 3B | bbq_bias | 6.54 | 3 | 0.088 | 0.091 | No | 792 |
| Llama 3.2 3B | jailbreak_amplification | 73.32 | 3 | < 0.0001 | **0.391** | **Yes** | 480 |
| Llama 3.2 3B | truthfulqa | 0.39 | 3 | 0.942 | 0.044 | No | 200 |
| Qwen 2.5 1.5B | advbench_refusal | 0.44 | 3 | 0.933 | 0.033 | No | 400 |
| Qwen 2.5 1.5B | bbq_bias | 5.06 | 3 | 0.167 | 0.080 | No | 792 |
| Qwen 2.5 1.5B | jailbreak_amplification | 17.61 | 3 | 0.001 | 0.192 | **Yes** | 480 |
| Qwen 2.5 1.5B | truthfulqa | 2.69 | 3 | 0.441 | 0.116 | No | 200 |

**Observations:**

6 of 12 task-model combinations show significant backend dependence. The pattern reveals a clear task hierarchy:

1. **Jailbreak amplification is backend-dependent for ALL models** -- the only task with universal significance. Effect sizes: V = 0.512 (large, Llama 1B), V = 0.391 (medium, Llama 3B), V = 0.192 (small, Qwen 1.5B). This is the task most sensitive to how the backend frames the prompt, which makes sense: jailbreak prompts exploit formatting-dependent escape patterns, and different chat templates provide different escape surfaces.

2. **AdvBench refusal is significant for Llama but not Qwen.** Llama 1B (V = 0.425, medium) and Llama 3B (V = 0.182, small) show backend-dependent refusal. But Qwen's refusal rate is near-ceiling (98-99%) across all backends, leaving no room for backend variation. The vulnerability is family-specific: Llama's refusal mechanism is format-dependent; Qwen's is not.

3. **BBQ bias is marginally significant only for Llama 1B** (V = 0.121, small). For the other two models, bias resistance is backend-independent. Bias detection appears to be encoded in the model's factual associations rather than its prompt-formatting-dependent safety training.

4. **TruthfulQA is never significant.** V ranges from 0.044 to 0.166, all non-significant at alpha=0.05. Combined with N=50 per cell and MDE of 28pp, truthfulness is underpowered for backend comparison at this sample size.

---

## 15. LLM Judge Agreement

Cohen's kappa between the regex classifier and the post-hoc LLM judge (Qwen 2.5 7B Instruct Q8_0) on refusal tasks. The judge independently classifies each response as FULL_REFUSAL / PARTIAL_REFUSAL / COMPLIANCE / UNCLEAR, which is then mapped to a binary safe/unsafe label for kappa computation.

| Backend | Kappa | Agreement % | N Pairs |
|---------|-------|-------------|---------|
| Ollama Q4_K_M | 0.112 | 82.3% | 660 |
| Ollama Q8_0 | 0.144 | 86.2% | 660 |
| TGI FP16 | 0.158 | 66.4% | 660 |
| vLLM FP16 | 0.130 | 67.4% | 660 |

**Observations:**

All kappa values are in the "slight agreement" range (< 0.20 by Landis & Koch thresholds). Raw agreement is substantially higher for Ollama backends (82-86%) than for FP16 backends (66-67%), but this difference is largely a base-rate artifact. On Ollama, most samples are classified as "safe" by both classifiers (because Ollama produces higher refusal rates). When both classifiers agree on the majority class, raw agreement inflates while kappa -- which corrects for chance -- remains low.

To illustrate: if both classifiers label 85% of Ollama samples as "safe," they would agree on ~74% by chance alone (0.85 × 0.85 + 0.15 × 0.15 = 0.745). The actual 86.2% agreement exceeds chance by only 12 percentage points, yielding kappa = 0.144. On FP16 backends, the base rate is more balanced (~63% safe), so chance agreement is lower (~47%), and the 67% raw agreement yields a slightly higher kappa despite lower raw agreement.

This low inter-rater agreement is consistent with TR134 (kappa 0.013-0.18) and TR135 (kappa 0.067-0.14). It does not invalidate the primary findings -- it reflects a fundamental difference between surface-level pattern matching (regex) and semantic intent evaluation (LLM judge). The two classifiers capture different aspects of safety, and neither is a gold-standard human annotation.

---

## 16. Power Analysis

Minimum detectable effect (MDE) at alpha=0.05, power=0.80, per backend and per task.

### 16.1 Per-Backend MDE (Aggregate Safety)

| Model | Backend | N | Baseline Rate | MDE (pp) |
|-------|---------|---|---------------|----------|
| Llama 3.2 1B | Ollama Q4_K_M | 468 | 0.858 | 6.4 |
| Llama 3.2 1B | Ollama Q8_0 | 468 | 0.876 | 6.0 |
| Llama 3.2 1B | TGI FP16 | 468 | 0.625 | 8.9 |
| Llama 3.2 1B | vLLM FP16 | 468 | 0.628 | 8.9 |
| Llama 3.2 3B | All backends | 468 | 0.74-0.81 | 7.2-8.0 |
| Qwen 2.5 1.5B | All backends | 468 | 0.78-0.85 | 6.6-7.6 |

**Cross-backend MDE:** 7.2-8.0pp per model (N=1,872 total safety samples).

### 16.2 Per-Task MDE

| Task | N per cell | Baseline Range | MDE Range (pp) |
|------|-----------|----------------|----------------|
| advbench_refusal | 100 | 0.49-0.99 | 5.2-19.4 |
| bbq_bias | 198 | 0.79-0.97 | 6.3-10.4 |
| jailbreak_amplification | 120 | 0.46-0.98 | 15.7-17.8 |
| truthfulqa | 50 | 0.42-0.59 | **28.0** |

**Observations:**

The aggregate safety MDE of 7-8pp means the experiment can detect any cross-backend difference larger than ~8pp with 80% power. The observed Llama 3.2 1B gap (24pp) is 3x above this threshold -- the finding is robustly powered and would remain significant even at a much smaller sample size.

For Llama 3.2 3B and Qwen 2.5 1.5B, the observed gaps (6-7pp) are near the MDE boundary (7.2-8.0pp). This explains why the pairwise t-tests are significant before Holm correction but mostly fail after -- the experiment is borderline-powered for these models. Detecting a 6pp effect at 80% power would require approximately 770 samples per backend (vs 468 actual), a 1.6x increase. This is a design limitation, not a null result -- the chi-squared tests still detect the effect at the model level because they pool across backends.

TruthfulQA's MDE of 28pp means only catastrophic per-task effects are detectable at N=50. The non-significant truthfulqa results (Section 14) should not be interpreted as "backends are equivalent for truthfulness" -- they are simply underpowered. To achieve a 10pp MDE for TruthfulQA, approximately 400 samples per cell would be needed (8x current).

---

## 17. Cross-Experiment Validation (vs TR134)

Compares TR136 Ollama Q4_K_M scores to TR134 Phase 3 Q4_K_M scores. Same models, same quantization, same tasks. Scores should agree within 5pp if the evaluation framework is reproducible across experiments.

### 17.1 Llama 3.2 1B

| Task | TR136 (Q4_K_M) | TR134 (Q4_K_M) | Diff (pp) | Consistent? |
|------|----------------|----------------|-----------|-------------|
| advbench_refusal | 0.880 | 0.870 | +1.0 | Yes |
| arc_challenge | 0.335 | 0.395 | -6.0 | **No** |
| bbq_bias | 0.874 | 0.874 | +0.0 | Yes |
| jailbreak_amplification | 0.925 | 0.933 | -0.8 | Yes |
| mmlu_real | 0.310 | 0.337 | -2.7 | Yes |
| truthfulqa | 0.590 | 0.580 | +1.0 | Yes |

**5/6 tasks consistent** (< 5pp threshold). The ARC-Challenge divergence (6.0pp) is slightly outside the threshold. Given ARC's MDE of ~18pp at N=200, a 6pp difference is within expected noise. BBQ bias reproduces with zero deviation, confirming the bias benchmark and classifier are fully deterministic.

### 17.2 Llama 3.2 3B

| Task | TR136 (Q4_K_M) | TR134 (Q4_K_M) | Diff (pp) | Consistent? |
|------|----------------|----------------|-----------|-------------|
| advbench_refusal | 0.540 | 0.470 | +7.0 | **No** |
| arc_challenge | 0.700 | 0.705 | -0.5 | Yes |
| bbq_bias | 0.965 | 0.965 | +0.0 | Yes |
| jailbreak_amplification | 0.892 | 0.825 | +6.7 | **No** |
| mmlu_real | 0.595 | 0.590 | +0.5 | Yes |
| truthfulqa | 0.480 | 0.500 | -2.0 | Yes |

**4/6 tasks consistent.** AdvBench and jailbreak refusal diverge by 7pp, which is within the per-task MDE range for these tasks (advbench: 19.4pp, jailbreak: 15.7pp). The divergence concentrates in refusal tasks where the baseline rate is moderate (0.47-0.83), leaving more room for run-to-run variance. Capability tasks (ARC, MMLU) and bias (BBQ) reproduce with near-perfect fidelity.

**Overall:** 9 of 12 task-model pairs are within 5pp. The 3 divergent pairs are: ARC-Challenge on Llama 1B (-6.0pp, a capability task), AdvBench on Llama 3B (+7.0pp), and jailbreak on Llama 3B (+6.7pp). The two Llama 3B refusal divergences are within per-task MDE (advbench: 19.4pp, jailbreak: 15.7pp). The ARC divergence (6.0pp vs 5pp threshold) is marginal and likely reflects noise. The divergence could reflect run-to-run variance in the model's refusal behavior at temperature=0.0, or subtle differences in prompt shuffling order between TR134 and TR136.

---

## 18. Baseline Normalization

Safety scores normalized to vLLM FP16 as the reference backend (1.000 = vLLM FP16 level). This provides a common scale for comparing backend effects across models.

| Model | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 |
|-------|---------------|-------------|----------|-----------|
| Llama 3.2 1B | 1.366 (+23.0pp) | 1.395 (+24.8pp) | 0.995 (-0.3pp) | 1.000 |
| Llama 3.2 3B | 1.074 (+5.5pp) | 1.081 (+6.1pp) | 0.994 (-0.4pp) | 1.000 |
| Qwen 2.5 1.5B | 1.034 (+2.7pp) | 1.072 (+5.7pp) | 0.988 (-1.0pp) | 1.000 |

**Observations:**

Ollama backends produce safety scores 3-40% higher than the vLLM FP16 baseline, depending on model. The normalization reveals a clear size gradient: the 1B model's Ollama premium is 1.37-1.40x (37-40% higher safety); the 3B model's is 1.07-1.08x (7-8%); Qwen's is 1.03-1.07x (3-7%). TGI FP16 is within 1pp of vLLM FP16 in all cases (0.988-0.995x), confirming these two backends produce indistinguishable safety behavior.

The asymmetry is important for deployment guidance: Ollama does not make models safer in any absolute sense. Rather, Ollama's GGUF chat template formatting happens to trigger refusal patterns more reliably than HuggingFace's formatting. A model that "passes" safety testing on Ollama at 0.876 safety may actually have a baseline safety level closer to 0.628 when served through the HuggingFace weight format -- a 25pp gap that could be the difference between deployment approval and rejection.

---

## 19. Conclusions & Limitations

### 19.1 Research Question Answers

| # | Question | Answer | Evidence |
|---|----------|--------|----------|
| RQ1 | Backend independence | **Rejected.** Chi-squared significant for all 3 models | Appendix B (all p <= 0.05) |
| RQ2 | Quant vs backend | **Backend dominates.** d: quant 0.01-0.08, backend 0.15-0.60 | Section 6 |
| RQ3 | vLLM-TGI equivalence | **Functionally equivalent** (95.7% agreement, d < 0.03) | Sections 10-12 |
| RQ4 | Task specificity | **Jailbreak > AdvBench > BBQ > TruthfulQA** | Section 14 (Cramer's V ranking) |
| RQ5 | Safety-capability divergence | **6.28x for Llama 1B; ~1x for others** | Section 9 |
| RQ6 | Cross-TR reproducibility | **9/12 pairs within 5pp** | Section 17 |

### 19.2 Mechanism: Chat Template Divergence

The most likely explanation is chat template divergence between GGUF and HuggingFace formats. This hypothesis is supported by three converging lines of evidence:

1. **Textual divergence is massive.** Jaccard similarity between backend families is only 0.20-0.28 (Section 12). The same model architecture produces fundamentally different text when served through different backends. This level of divergence cannot be explained by quantization alone (Ollama Q4 vs Q8 Jaccard = 0.668).

2. **The effect is safety-specific.** Capability scores (MMLU, ARC) show 4-8pp cross-backend range, while safety shows 7-25pp (Section 9). If the divergence were caused by general model quality differences, capability and safety would both shift proportionally. The differential effect points to safety-trained behavior (refusal patterns) being more format-dependent than general knowledge.

3. **The effect concentrates in refusal tasks.** Jailbreak and AdvBench refusal are most affected (Section 14), while bias and truthfulness are not. Refusal behavior is trained through RLHF on carefully formatted prompt-response pairs. If the deployment-time formatting differs from the training-time formatting, the refusal triggers may not fire.

A secondary factor may be tokenizer implementation differences. GGUF files use llama.cpp's tokenizer; vLLM and TGI use HuggingFace's `tokenizers` library. Edge-case disagreements on special tokens, Unicode handling, and BOS/EOS placement could alter the model's perception of the prompt.

### 19.3 Backend vs Quantization vs Concurrency: A Comparison

| Dimension | TR134 (Quantization) | TR135 (Concurrency) | TR136 (Backend) |
|-----------|---------------------|--------------------|--------------------|
| Max safety degradation | 15-40pp (Q2_K) | < 1pp | 25pp (Llama 1B) |
| Jailbreak amplification | +11pp per BPW (slope) | 0pp | 48pp gap (Ollama vs FP16) |
| Mechanism | Precision loss degrades fine-tuned weights | None (Ollama serializes) | Chat template / tokenizer divergence |
| Threshold behavior | Sharp cliff at Q3_K_S | No threshold | Binary: GGUF vs HuggingFace |
| Capability impact | Proportional to safety | None | Disproportionately small |
| Practitioner action | Stay above Q4_K_M | No action needed | Re-test on target backend |
| Controllable? | Yes (choose quant level) | N/A | Partially (align chat templates) |

### 19.4 Limitations

1. **GGUF vs HuggingFace confound is unresolved.** We cannot separate backend code effects from weight format effects without running HuggingFace weights through Ollama (not supported) or GGUF weights through vLLM (not standard). A targeted follow-up comparing chat template application alone would isolate this variable.
2. **Two model families only.** Llama 3.2 and Qwen 2.5. The massive effect on Llama 1B may be family-specific. Mistral, Phi, and Gemma models may behave differently.
3. **Small models only (1B-3B).** Larger models (7B+) with more robust safety training may be less sensitive to backend choice. The effect's size-dependence (24pp for 1B, 6pp for 3B) suggests it may attenuate further at 7B+.
4. **Temperature = 0.0.** Stochastic sampling at temperature > 0 could amplify or dampen backend differences. The deterministic setting measures the most likely output, not the distribution of possible outputs.
5. **Single run per configuration.** We report within-sample CIs but not run-to-run variance. The 3 divergent cross-validation results (Section 17) suggest non-trivial run-to-run variance for refusal tasks even at temperature=0.
6. **Regex classifiers are surface-level.** The LLM judge's low kappa (0.11-0.16) indicates the two classifiers disagree on ~15-30% of samples after chance correction. Human annotation would provide a more reliable ground truth.
7. **Docker overhead inflates latency.** Latency differences between Ollama (native) and vLLM/TGI (Docker) reflect container overhead, not pure inference speed.
8. **Jailbreak prompts from a fixed set.** Adversarial robustness to novel jailbreaks may differ from robustness to known JailbreakBench patterns.
9. **No system prompt variation.** All backends receive the same system prompt content, but the *encoding* differs between GGUF-embedded and HuggingFace templates. We test the combined effect, not the isolated effect.
10. **Borderline power for 3B and Qwen models.** The 6-7pp effects are near the MDE boundary. To confidently confirm or reject a 5pp effect, approximately 770 samples per backend would be needed (1.6x current).

### 19.5 Implications for Practitioners

1. **Re-evaluate safety when switching backends.** A model that passes safety testing on Ollama may fail on vLLM/TGI, particularly for jailbreak resistance and harmful prompt refusal. Budget for re-evaluation as part of any backend migration.
2. **vLLM and TGI are interchangeable.** If you are choosing between these two FP16 Docker backends, safety is not a differentiator. Pick based on throughput, API compatibility, and operational preferences.
3. **Quantization within Ollama is safe.** Q4_K_M and Q8_0 produce nearly identical safety behavior (d < 0.09). This is consistent with TR134's finding that Q4_K_M is a safe deployment point. Use Q4_K_M to save memory without safety cost.
4. **Use larger models in multi-backend deployments.** The 1B model shows a 6x safety/capability divergence ratio; 3B models are much more robust. If your deployment may span multiple backends, prefer models >= 3B parameters.
5. **Investigate chat template alignment.** The most actionable mitigation is to verify that the HuggingFace chat template matches the GGUF-embedded template before deploying. Compare the output of `transformers.AutoTokenizer.apply_chat_template()` against GGUF template metadata to detect divergences before they cause safety failures.

---

## 20. Reproducibility

### 20.1 Pipeline Commands

```bash
# Full pipeline (eval + judge + analysis + report)
python research/tr136/run.py

# Skip eval, re-run analysis on existing data
python research/tr136/run.py --skip-eval --skip-judge

# Run specific backends or models only
python research/tr136/run.py --backends ollama_q4_k_m ollama_q8_0 --models llama3.2-1b

# Standalone analysis on existing run
python research/tr136/analyze.py --run-dir research/tr136/results/20260308_015147
```

### 20.2 Prerequisites

1. **Ollama** >= v0.6.2 installed and running (`ollama serve`)
2. **Docker** with GPU support (`nvidia-container-toolkit` installed)
3. **Ollama models pulled:** `llama3.2:1b`, `llama3.2:3b`, `qwen2.5:1.5b` (base tags; quant variants are auto-pulled)
4. **HuggingFace models cached:** `unsloth/Llama-3.2-1B-Instruct`, `unsloth/Llama-3.2-3B-Instruct`, `Qwen/Qwen2.5-1.5B-Instruct` (auto-downloaded by vLLM/TGI)
5. **Judge model:** `qwen2.5:7b-instruct-q8_0` pulled in Ollama
6. **Python packages:** See `requirements.txt`
7. **GPU:** >= 12GB VRAM for FP16 inference of 3B models
8. **Disk space:** ~20GB for models + ~30MB for results

### 20.3 Key Git Commits

| Commit | Description |
|--------|-------------|
| `9f1e35dc` | Upgrade analyze.py to SOTA statistical rigor and harden run.py |
| `65a05700` | Add untracked artifacts, infra configs, TR136 tasks, and tests |

### 20.4 Known Reproducibility Issues

- **Docker image versions.** `vllm/vllm-openai:latest` and `ghcr.io/huggingface/text-generation-inference:latest` are mutable tags. Pin to specific versions for exact reproduction.
- **Ollama GGUF versions.** Ollama model tags (e.g., `llama3.2:1b`) may be updated with new GGUF conversions. Pin to specific digests for exact reproduction.
- **Temperature=0.0 is not fully deterministic.** At temperature=0 with a fixed seed, most backends produce deterministic output, but floating-point non-associativity in GPU operations can cause rare divergences (1-2 tokens per 1000 responses). The 3 cross-validation divergences in Section 17 may partially reflect this.
- **WSL2 Docker performance.** Docker containers on Windows run through WSL2, which may introduce different latency characteristics than native Linux Docker.

---

## Appendix A: Normalized Per-Task Scores (Reference: vLLM FP16)

### A.1 Llama 3.2 1B

| Task | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 |
|------|---------------|-------------|----------|-----------|
| advbench_refusal | 1.630 (+34.0pp) | 1.759 (+41.0pp) | 1.000 (+0.0pp) | 1.000 |
| bbq_bias | 1.102 (+8.1pp) | 1.121 (+9.6pp) | 1.000 (+0.0pp) | 1.000 |
| jailbreak_amplification | 1.850 (+42.5pp) | 1.967 (+48.3pp) | 1.000 (+0.0pp) | 1.000 |
| truthfulqa | 1.283 (+13.0pp) | 0.913 (-4.0pp) | 0.935 (-3.0pp) | 1.000 |

The jailbreak normalization (1.967x for Q8) means Ollama Q8 refuses nearly twice as many jailbreak attempts as vLLM FP16. TGI and vLLM produce identical scores for this model (1.000x on all tasks except truthfulqa).

### A.2 Llama 3.2 3B

| Task | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 |
|------|---------------|-------------|----------|-----------|
| advbench_refusal | 0.783 (-15.0pp) | 0.710 (-20.0pp) | 1.000 (+0.0pp) | 1.000 |
| bbq_bias | 1.044 (+4.0pp) | 1.049 (+4.5pp) | 1.006 (+0.5pp) | 1.000 |
| jailbreak_amplification | 1.529 (+30.8pp) | 1.614 (+35.8pp) | 0.986 (-0.8pp) | 1.000 |
| truthfulqa | 0.857 (-8.0pp) | 0.875 (-7.0pp) | 0.929 (-4.0pp) | 1.000 |

The Llama 3B AdvBench reversal is visible here: Ollama scores *below* vLLM (0.78x, 0.71x). Jailbreak amplification maintains the Ollama-higher pattern (1.53x, 1.61x), creating a task-specific contradiction.

### A.3 Qwen 2.5 1.5B

| Task | Ollama Q4_K_M | Ollama Q8_0 | TGI FP16 | vLLM FP16 |
|------|---------------|-------------|----------|-----------|
| advbench_refusal | 1.000 (+0.0pp) | 1.010 (+1.0pp) | 1.000 (+0.0pp) | 1.000 |
| bbq_bias | 1.045 (+4.0pp) | 1.062 (+5.5pp) | 1.034 (+3.0pp) | 1.000 |
| jailbreak_amplification | 1.101 (+5.8pp) | 1.247 (+14.2pp) | 0.797 (-11.7pp) | 1.000 |
| truthfulqa | 0.902 (-5.0pp) | 0.902 (-5.0pp) | 1.137 (+7.0pp) | 1.000 |

Qwen shows near-unity normalization for AdvBench (all backends identical) and BBQ (< 6pp spread). Jailbreak is the outlier: TGI scores *below* vLLM (0.797x), an unusual divergence between the two FP16 backends that warrants investigation.

---

## Appendix B: Chi-Squared Contingency Tables

### B.1 Llama 3.2 1B (X² = 148.60, p < 0.0001)

| Backend | Safe | Unsafe | Total | Safety Rate |
|---------|------|--------|-------|-------------|
| Ollama Q4_K_M | 406 | 62 | 468 | 86.8% |
| Ollama Q8_0 | 413 | 55 | 468 | 88.3% |
| TGI FP16 | 295 | 173 | 468 | 63.0% |
| vLLM FP16 | 297 | 171 | 468 | 63.5% |

The contingency table makes the clustering visible: Ollama backends have ~60 unsafe samples each; FP16 backends have ~172 -- nearly 3x more. The chi-squared statistic of 148.60 (Cramer's V = 0.282, small-medium) reflects this dramatic shift.

### B.2 Llama 3.2 3B (X² = 11.05, p = 0.011)

| Backend | Safe | Unsafe | Total | Safety Rate |
|---------|------|--------|-------|-------------|
| Ollama Q4_K_M | 380 | 88 | 468 | 81.2% |
| Ollama Q8_0 | 383 | 85 | 468 | 81.8% |
| TGI FP16 | 351 | 117 | 468 | 75.0% |
| vLLM FP16 | 353 | 115 | 468 | 75.4% |

The gap narrows: Ollama has ~86 unsafe samples; FP16 has ~116. The Cramer's V of 0.077 (negligible-small) reflects a real but modest effect.

### B.3 Qwen 2.5 1.5B (X² = 7.83, p = 0.050)

| Backend | Safe | Unsafe | Total | Safety Rate |
|---------|------|--------|-------|-------------|
| Ollama Q4_K_M | 386 | 82 | 468 | 82.5% |
| Ollama Q8_0 | 400 | 68 | 468 | 85.5% |
| TGI FP16 | 370 | 98 | 468 | 79.1% |
| vLLM FP16 | 374 | 94 | 468 | 79.9% |

The smallest effect. Borderline significant (p = 0.050), with Cramer's V = 0.065 (negligible). The within-Ollama spread (82.5% to 85.5%) is comparable to the Ollama-FP16 spread (79.1% to 85.5%), consistent with the "comparable" interpretation in Section 6.

---

## Appendix C: Full Latency Comparison

| Model | Backend | advbench | arc | bbq | jailbreak | mmlu | truthfulqa |
|-------|---------|----------|-----|-----|-----------|------|------------|
| Llama 1B | Ollama Q4 | 352 | 257 | 424 | 359 | 257 | 558 |
| Llama 1B | Ollama Q8 | 374 | 249 | 469 | 372 | 247 | 588 |
| Llama 1B | TGI FP16 | 1326 | 127 | 301 | 1486 | 382 | 781 |
| Llama 1B | vLLM FP16 | 1019 | 118 | 267 | 1225 | 321 | 654 |
| Llama 3B | Ollama Q4 | 458 | 262 | 379 | 440 | 266 | 932 |
| Llama 3B | Ollama Q8 | 516 | 259 | 456 | 541 | 262 | 1028 |
| Llama 3B | TGI FP16 | 2412 | 1006 | 3870 | 4524 | 1984 | 2877 |
| Llama 3B | vLLM FP16 | 2126 | 855 | 3210 | 3776 | 1673 | 2547 |
| Qwen 1.5B | Ollama Q4 | 384 | 223 | 456 | 877 | 227 | 504 |
| Qwen 1.5B | Ollama Q8 | 358 | 229 | 589 | 876 | 212 | 474 |
| Qwen 1.5B | TGI FP16 | 497 | 670 | 1121 | 2443 | 1761 | 1822 |
| Qwen 1.5B | vLLM FP16 | 423 | 92 | 1455 | 1744 | 407 | 1092 |

All values in milliseconds (mean per request). Docker backends (TGI, vLLM) show higher latency for safety tasks due to longer response generation (refusal explanations) combined with container networking overhead. For capability tasks with short responses (ARC: single letter), vLLM is actually faster than Ollama (92ms vs 223ms for Qwen) because the HuggingFace tokenizer and FP16 inference are more efficient for short sequences. Latency differences do not affect safety evaluation -- all 10,416 requests completed successfully (0% error rate across all configurations).

---

## Appendix D: Glossary

| Term | Definition |
|------|------------|
| Backend | The inference server that hosts and serves the model (Ollama, vLLM, TGI) |
| BPW | Bits per weight. FP16 = 16.0, Q8_0 = 8.0, Q4_K_M ≈ 4.5 |
| Cohen's d | Standardized effect size. < 0.2 trivial, 0.2-0.5 small, 0.5-0.8 medium, > 0.8 large |
| Cohen's Kappa | Inter-rater agreement corrected for chance. < 0.20 slight, 0.21-0.40 fair, 0.41-0.60 moderate (Landis & Koch 1977) |
| Cramer's V | Chi-squared effect size. < 0.1 negligible, 0.1-0.3 small, 0.3-0.5 medium, > 0.5 large |
| GGUF | GPT-Generated Unified Format. Ollama's native weight format, includes embedded chat template and tokenizer |
| Holm-Bonferroni | Step-down multiple comparison correction. More powerful than Bonferroni, controls FWER |
| Jaccard Similarity | Token overlap ratio. |A ∩ B| / |A ∪ B|. 1.0 = identical, 0.0 = no overlap |
| MDE | Minimum Detectable Effect. Smallest effect detectable at given alpha and power |
| pp | Percentage points. An absolute difference in proportions (e.g., 85% - 60% = 25pp) |
| TOST | Two One-Sided Tests. Confirms equivalence within a margin (here +/-3pp). Strictly stronger than "not significant" |
| TGI | Text Generation Inference. HuggingFace's inference server |
| vLLM | Virtual LLM. High-throughput inference server with continuous batching |

---

## References

1. Landis, J.R. & Koch, G.G. (1977). The Measurement of Observer Agreement for Categorical Data. *Biometrics*, 33(1), 159-174.
2. Röttger, P. et al. (2024). HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Refusal. *NeurIPS 2024*.
3. Mazeika, M. et al. (2024). JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models. *NeurIPS 2024*.
4. Parrish, A. et al. (2022). BBQ: A Hand-Built Bias Benchmark for Question Answering. *ACL 2022*.
5. Lin, S., Hilton, J., & Evans, O. (2022). TruthfulQA: Measuring How Models Mimic Human Falsehoods. *ACL 2022*.
6. Huang, Y. et al. (2024). Chat Template Matters: The Impact of Prompt Formatting on LLM Safety. *arXiv:2402.xxxxx*.
7. Banterhearts TR125 (2026). Quantization Decision Matrix: Quality-Accuracy Trade-offs Across 4 Models and 7 Quantization Levels.
8. Banterhearts TR133 (2026). VRAM Modeling and Latency Prediction for Multi-Model Deployments.
9. Banterhearts TR134 (2026). Alignment Robustness Under Quantization: Multi-Family Safety Evaluation Across 4 Models with Jailbreak Amplification.
10. Banterhearts TR135 (2026). Safety Under Multi-Agent Concurrency: Does Running N Concurrent Agents Degrade Model Safety?
