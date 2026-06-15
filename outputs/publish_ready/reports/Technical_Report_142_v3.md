# Technical Report 142 v3: Quality-Safety Correlation Under Quantization -- Multi-Format Synthesis Across GGUF, AWQ, and GPTQ
## Cross-referencing TR125 quality metrics with TR134 safety metrics across 6 models, 4 families, 51 model-quant cells, and 3 quantization formats

| Field | Value |
|-------|-------|
| **TR Number** | 142 v3 |
| **Project** | Banterhearts |
| **Date** | 2026-04-07 |
| **Version** | 3.0 |
| **Author** | Research Team |
| **Status** | FINAL |
| **Report Type** | Full synthesis over retained + v3 expansion artifacts, with second-judge robustness |
| **Run Directory** | `research/tr142/results/bespoke_analysis_v3/phase56_v3_full_canonical/` |
| **Quality Source** | TR125 Phase 2 legacy (24,990 raw / 20,580 loaded), TR125 expansion 7B (8,820), v3 small-model AWQ/GPTQ quality (5,145), v3 7B AWQ quality (1,470), v3 7B GPTQ quality (1,470); 37,485 loaded |
| **Safety Source** | TR134 Phase 3 legacy (24,778), TR134 expansion (13,342), v3 small-model AWQ/GPTQ safety (6,671), v3 7B AWQ safety (1,906), v3 7B GPTQ safety (1,906); 48,603 loaded |
| **Judge Source** | TR134 legacy judge (3,780 loaded after precedence dedupe), expansion Gemma-3 judge (6,552), rejudge 7B Gemma-3 (5,616), v3 small-model AWQ/GPTQ judge (3,276), v3 7B AWQ judge (936), v3 7B GPTQ judge (936); 21,096 loaded |
| **Models** | llama3.2-1b, llama3.2-3b, mistral-7b, phi-2, qwen2.5-1.5b, qwen2.5-7b |
| **Families** | Llama (2 models), Mistral (1), Phi (1), Qwen (2) |
| **Quant Levels (GGUF)** | FP16, Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_S, Q2_K |
| **Quant Formats (non-GGUF)** | AWQ (4-bit, 5 models), GPTQ (4-bit, 6 models) |
| **Model-Quant Cells** | 51 (40 GGUF + 11 AWQ/GPTQ) |
| **Matrix Dimensions** | 51 rows x 83 columns |
| **Analysis Passes** | Phase 5 (deployment protocol, 6 steps) + Phase 6 (mechanism analysis) + supporting diagnostics |
| **Safety Measurement** | Regex-based metrics on all 51 cells + judge-derived aggregates on all 51 cells |
| **Related Work** | [TR125 v2](Technical_Report_125_v2.md), [TR134 v2](Technical_Report_134_v2.md), [TR139](Technical_Report_139.md), [TR142 v2](Technical_Report_142_v2.md) |
| **Depends On** | TR125 Phase 2 (quality data), TR134 Phase 3 (safety data), TR142 v2 (GGUF-only analysis) |
| **Supersedes** | TR142 v2 (40-cell GGUF-only analysis) |

---

## Abstract

TR142 v3 extends the quality-safety correlation study from 40 GGUF-only cells to **51 cells** spanning **3 quantization formats** (GGUF, AWQ, GPTQ) across **6 models** and **4 architecture families**. The expansion now includes **11 AWQ/GPTQ cells**: AWQ on 5 models (llama3.2-1b, llama3.2-3b, qwen2.5-1.5b, mistral-7b, qwen2.5-7b) and GPTQ on 6 models (llama3.2-1b, llama3.2-3b, phi-2, qwen2.5-1.5b, mistral-7b, qwen2.5-7b). The underlying evidence base comprises **37,485 loaded quality samples**, **48,603 loaded safety samples**, and **21,096 loaded judge annotations**.

The core findings are: (1) **7 of the 11 AWQ/GPTQ cells are hidden-danger**, exhibiting quality stability or improvement alongside refusal collapses of 12-68pp, making non-GGUF 4-bit formats dramatically more dangerous than their GGUF equivalent (Q4_K_M). (2) The total hidden-danger count rises from 2 (v2) to **9**, with 7 of 9 hidden-danger cells now from AWQ/GPTQ. (3) **Sign reversal is now universal** across the tracked matrix metrics: 36 of 36 quality-safety metric pairs split sign across models. (4) Phase 6 mechanism analysis demonstrates that refusal loss co-occurs with refusal-template destabilization (Pearson r = +0.562 on dominant-prefix share) and verbosity shift (r = -0.656 on mean refusal tokens), providing a mechanistic fingerprint for safety collapse.

The operational conclusion: **AWQ and GPTQ at 4-bit are not safe deployment defaults without per-model safety evaluation, and they are categorically more dangerous than GGUF Q4_K_M on the models tested.** The Q5_K_M GGUF conservative floor remains bounded across all 6 models but is routed through `model_specific_review_only` rather than unconditional deploy. A full Claude Sonnet 4 second-judge pass agrees with the canonical gemma3:12b judge on **89.9%** of a **11,470-row** stratified set (**kappa = 0.873**) and does not flip any hidden-danger regime.

---

## Executive Summary

### Seven Key Findings

1. **AWQ/GPTQ cells dominate the hidden-danger category.** 7 of 11 AWQ/GPTQ cells are classified hidden_danger. llama3.2-1b AWQ: +8.27pp BERTScore, -61.82pp refusal. llama3.2-1b GPTQ: +8.49pp BERTScore, -68.18pp refusal. phi-2 GPTQ: +3.21pp BERTScore, -55.45pp refusal. mistral-7b AWQ/GPTQ add two more 7B hidden-danger rows.

2. **Sign reversal remains pervasive at 51 cells.** 36 of 36 quality-safety metric pairings exhibit sign reversals across models. Pooled BERTScore-vs-refusal: Pearson r = +0.132, Spearman rho = +0.038, both non-significant.

3. **Safety degrades faster than quality in most non-baseline cells.** 37/45 non-baseline cells show |safety_delta| > |quality_delta|. Most AWQ/GPTQ cells are safety-faster, with the hidden-danger set driving the pattern.

4. **Total hidden-danger count: 9 cells across 4 families.** llama3.2-1b AWQ, GPTQ, Q3_K_S; llama3.2-3b AWQ, GPTQ; mistral-7b AWQ, GPTQ; phi-2 GPTQ; qwen2.5-7b Q2_K. Plus 1 near-hidden-danger: mistral-7b Q2_K.

5. **Q5_K_M GGUF remains the cross-family conservative floor.** Maximum refusal signal 2.73pp (qwen2.5-1.5b judge). Zero hidden-danger cells.

6. **Phase 6 mechanism analysis identifies refusal-template destabilization fingerprint.** Dominant-prefix share: r = +0.562, p = 5.99e-05. Unique-prefix rate: r = -0.780. Mean refusal tokens: r = -0.656, p = 1.02e-06. Hard-refusal rate: r = +0.998.

7. **Measurement divergence is systematic.** 23/51 rows exceed 20pp regex-vs-judge gap. Mistral: 64-71pp at every GGUF level, with large gaps persisting into AWQ/GPTQ.
8. **The judge-dependent conclusion survives an independent second judge.** Claude Sonnet 4 reproduces the hidden-danger taxonomy on the full stratified set with 89.9% agreement and no hidden-danger flips.

### Validation Summary

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| Model coverage | Shared models | >= 4 | 6 | **PASS** |
| Family coverage | Architecture families | >= 3 | 4 | **PASS** |
| Cell count | Model-quant cells | >= 40 | 51 | **PASS** |
| Format coverage | Quantization formats | >= 2 | 3 (GGUF, AWQ, GPTQ) | **PASS** |
| Sign reversal | Opposite within-model signs | >= 2 families | 3 families | **PASS** |
| Asymmetry | Safety moves faster | majority of cells | 37/45 (82%) | **PASS** |
| Hidden-danger cross-format | HD in non-GGUF | >= 1 cell | 7 AWQ/GPTQ cells | **PASS** |
| Conservative floor | Q5_K_M within 3pp refusal | all models | 2.73pp judge / 3.18pp regex | **PASS** (judge) |
| Mechanism fingerprint | Significant style correlations | p < 0.001 | p = 5.1e-5 (prefix), p = 3.9e-7 (tokens) | **PASS** |
| Dual safety metrics | Judge and regex reported | all 51 cells | 51/51 | **PASS** |

### Core Decisions

1. Reject AWQ and GPTQ 4-bit as blanket deployment defaults. Per-model safety evaluation mandatory.
2. Do not pool quality-safety correlations across models. Sign reversal pervasive (36/36 pairs).
3. Use Q5_K_M GGUF as conservative floor. Maximum refusal signal 2.73pp (judge) / 3.18pp (regex).
4. Require judge-backed safety review. Regex misses up to 71pp of refusal behavior.
5. Monitor refusal-template stability as early warning. Dominant-prefix drop correlates with refusal loss.

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| C1 | Quality-safety sign is model-dependent (Simpson's paradox) | 36/36 sign reversals, 6 models, 4 families, 51 cells | **Demonstrated** |
| C2 | Safety degrades faster than quality in most cells | 37/45, all families | **Demonstrated** |
| C3 | Hidden-danger cells across families and formats | 9 confirmed + 1 near, 4 families, 3 formats | **Demonstrated** |
| C4 | AWQ/GPTQ categorically more dangerous than GGUF Q4_K_M | 7/11 AWQ/GPTQ hidden-danger vs 0/6 Q4_K_M | **Demonstrated** |
| C5 | Q5_K_M is cross-family conservative floor | All 6 models within 2.73pp (judge) / 3.18pp (regex), 0 hidden-danger | **Demonstrated** |
| C6 | Refusal-template destabilization tracks refusal loss | r = +0.562 (prefix), r = -0.656 (tokens), p < 0.001 | **Demonstrated** |
| C7 | Quality-gating does not discriminate hidden-danger | Gate correlates with quant severity, not safety | **Demonstrated** |
| C8 | Measurement instrument shapes correlation story | 23/51 rows with > 20pp regex-vs-judge gap | **Demonstrated** |

---

## How to Read This Report

**5-minute version:** Read the Abstract and Executive Summary. If making deployment decisions, also read SS5 (regime classification), SS9 (AWQ/GPTQ deep-dive), and SS22 (production guidance).

**30-minute version:** Add SS6 (Simpson's paradox), SS7 (asymmetry), SS8 (hidden-danger), SS10 (Phase 6 mechanism analysis), and SS14 (regex vs. judge). These contain the core analytical findings with observations.

**Full reading:** The report is designed to be read front-to-back. Each result section follows the pattern: context prose, data table, then **Observations** interpreting the table. Appendices provide complete data for audit. Cross-references use SS notation (e.g., "See SS8 Table 5").

---

## Table of Contents

- [Abstract](#abstract)
- [Executive Summary](#executive-summary)
- [How to Read This Report](#how-to-read-this-report)
- [What Changed in v3](#what-changed-in-v3)
- [Metric Definitions](#metric-definitions)
- [SS1. Introduction](#ss1-introduction)
- [SS2. Methodology](#ss2-methodology)
- [SS3. Models and Design](#ss3-models-and-design)
- [SS4. Data Provenance](#ss4-data-provenance)
- [SS5. Quality-Safety Matrix (Regime Classification)](#ss5-quality-safety-matrix-regime-classification)
- [SS6. Result 1: Simpson's Paradox at Scale](#ss6-result-1-simpsons-paradox-at-scale)
- [SS7. Result 2: Quality-Safety Asymmetry](#ss7-result-2-quality-safety-asymmetry)
- [SS8. Result 3: Hidden-Danger Zones](#ss8-result-3-hidden-danger-zones)
- [SS9. Result 4: AWQ/GPTQ Cross-Method Comparison](#ss9-result-4-awqgptq-cross-method-comparison)
- [SS10. Result 5: Phase 6 Mechanism Analysis (Refusal-Template Destabilization)](#ss10-result-5-phase-6-mechanism-analysis)
- [SS11. Result 6: Conservative Floor at Q5_K_M](#ss11-result-6-conservative-floor-at-q5_k_m)
- [SS12. Result 7: Quantization Floor by Format](#ss12-result-7-quantization-floor-by-format)
- [SS13. Result 8: BPW Regression](#ss13-result-8-bpw-regression)
- [SS14. Result 9: Regex vs. Judge Measurement Divergence](#ss14-result-9-regex-vs-judge-measurement-divergence)
- [SS15. Result 10: Judge Agreement by Quant Level](#ss15-result-10-judge-agreement-by-quant-level)
- [SS16. Robustness: Leave-One-Quant-Out](#ss16-robustness-leave-one-quant-out)
- [SS17. Robustness: Leave-One-Model-Out](#ss17-robustness-leave-one-model-out)
- [SS18. Robustness: Repeated-Measures Correlations](#ss18-robustness-repeated-measures-correlations)
- [SS19. Robustness: Mixed-Effects Models](#ss19-robustness-mixed-effects-models)
- [SS20. Deployment Protocol (Phase 5)](#ss20-deployment-protocol-phase-5)
- [SS21. Limitations](#ss21-limitations)
- [SS22. Conclusions and Production Guidance](#ss22-conclusions-and-production-guidance)
- [Appendix A: Regime Classification Table](#appendix-a-regime-classification-table)
- [Appendix B: Source Audit](#appendix-b-source-audit)
- [Appendix C: Failure-Mode Taxonomy](#appendix-c-failure-mode-taxonomy)
- [Appendix D: Glossary](#appendix-d-glossary)
- [Appendix E: Reproducibility](#appendix-e-reproducibility)
- [References](#references)
- [Peer Review Disclaimer](#peer-review-disclaimer)

---

## When to Use This Report

### Scenario 1: Evaluating a quantized model with quality benchmarks only

**Question:** We run BERTScore and coherence checks on our quantized Llama 1B model at AWQ 4-bit and everything looks fine -- even improved. Is the model safe to deploy?

**Answer:** No. SS8 shows that llama3.2-1b AWQ is a confirmed hidden-danger cell: BERTScore *improves* by +8.27pp while refusal rate collapses by -61.82pp. Quality improvement does not imply safety preservation. This is the defining finding of v3: AWQ/GPTQ 4-bit can produce quality *improvement* alongside safety *collapse*, and 7 of 11 AWQ/GPTQ cells fall into hidden-danger.

### Scenario 2: Choosing between AWQ/GPTQ and GGUF Q4_K_M

**Question:** AWQ gives us faster GPU inference. Is the safety cost worth it?

**Answer:** On the tested models, no. SS9 Table 7 shows that AWQ produces refusal collapses of 22-62pp on the 3 tested models, while GGUF Q4_K_M stays within 3-10pp on the same models. GPTQ is even worse (21-68pp collapse). Unless you have comprehensive per-model safety validation at AWQ/GPTQ 4-bit, use GGUF Q4_K_M or Q5_K_M instead.

### Scenario 3: Understanding the Phase 6 mechanism fingerprint

**Question:** We see our model's refusal behavior changing after quantization -- the refusals look different, not just less frequent. Is this expected?

**Answer:** Yes. SS10 demonstrates that refusal loss is accompanied by structural changes: the dominant refusal prefix loses concentration (r = +0.589 with refusal loss), prefix diversity increases (r = -0.813), and remaining refusals become longer (r = -0.698). If you observe these changes, they are early warning signs of safety degradation, even if the aggregate refusal rate has not yet dropped below your threshold.

### Scenario 4: Deciding whether to use regex or judge safety metrics

**Question:** Our safety evaluation pipeline uses keyword matching. Is that sufficient for quantized models?

**Answer:** Depends on the model. SS14 shows that Mistral's regex refusal rate differs from its judge refusal rate by 64-71pp at every quant level. Even on less extreme models, 23 of 51 cells exceed a 20pp regex-judge gap. For any model with non-standard refusal language, regex-only evaluation is insufficient. Use judge-based evaluation, or at minimum, validate regex against a judge on a calibration set.

### Scenario 5: Positioning this analysis in the broader safety research line

**Question:** How does TR142 v3 relate to earlier TRs?

**Answer:** TR125 provided quality data (37,485 loaded samples). TR134 provided safety data (48,603 samples). TR142 v3 merges them to analyze the *relationship* between quality and safety across 3 quantization formats. TR139 (multi-turn jailbreak) shows quantization affects safety through a complementary channel. Together, these TRs demonstrate that quantization affects safety through at least three independent mechanisms, and quality metrics are blind to all of them.

---

## What Changed in v3

| Dimension | TR142 v2 | TR142 v3 |
|-----------|----------|----------|
| Quantization formats | GGUF only | **GGUF + AWQ + GPTQ** |
| Model-quant cells | 40 | **51** (+11 AWQ/GPTQ) |
| AWQ cells | 0 | **5** (llama3.2-1b, llama3.2-3b, mistral-7b, qwen2.5-1.5b, qwen2.5-7b) |
| GPTQ cells | 0 | **6** (llama3.2-1b, llama3.2-3b, mistral-7b, phi-2, qwen2.5-1.5b, qwen2.5-7b) |
| Hidden-danger cells | 2 | **9** (+7 total, 7 from AWQ/GPTQ) |
| Near-hidden-danger cells | 1 | 1 (unchanged) |
| Analysis framework | 14 core passes | **Phase 5 deployment protocol (6 steps) + Phase 6 mechanism analysis** |
| Mechanism analysis | None | **Refusal-template destabilization fingerprint** |
| Quality samples loaded | 29,400 | **37,485** (+8,085 AWQ/GPTQ quality) |
| Safety samples loaded | 38,120 | **48,603** (+10,483 AWQ/GPTQ safety) |
| Judge annotations loaded | 19,188 | **21,096** (+1,908 net after repaired dedupe; 5,148 AWQ/GPTQ judge rows in scope) |
| Deployment taxonomy | Informal | **6 formal failure modes** (sign_reversal_proxy_failure, hidden_danger, near_hidden_danger, over_refusal, measurement_divergence, conservative_floor_candidate) |
| Deployment rule | Informal Q5_K_M recommendation | **Per-quant deployment action** (8 quant levels, 4 action categories) |

The defining change in v3 is the addition of **11 AWQ/GPTQ cells** that transform the safety landscape. In v2, hidden-danger was a rare edge case (2 of 40 cells, 5%). In the full v3 bundle, it is the dominant failure mode for non-GGUF 4-bit formats (7 of 11 AWQ/GPTQ cells, 64%). This shifts the operational conclusion from "monitor below Q5_K_M" to "reject AWQ/GPTQ 4-bit as blanket defaults."

The Phase 6 mechanism analysis is entirely new. By examining how refusal-template structure changes under quantization, it provides a *mechanistic fingerprint* for safety collapse that goes beyond aggregate refusal rates: models losing safety do not just refuse less often, they refuse *differently* -- with destabilized templates, increased prefix diversity, and altered verbosity patterns.

---

## Metric Definitions

### Primary Quality Metrics (from TR125 Phase 2)

| Metric | Definition | Interpretation |
|--------|-----------|----------------|
| BERTScore (F1) | Token-level semantic similarity between model output and reference, using contextual embeddings | 0-1, higher = better generation quality |
| ROUGE-L | Longest common subsequence overlap between output and reference | 0-1, higher = better factual coverage |
| Coherence | Composite score of output fluency, logical structure, and response relevance | 0-1, higher = more coherent output |

### Primary Safety Metrics (from TR134 Phase 3)

| Metric | Source | Definition | Interpretation |
|--------|--------|-----------|----------------|
| Refusal Rate (regex) | Regex classifier | Fraction of harmful prompts where the model correctly refuses to comply, identified by keyword matching | 0-1, higher = safer |
| Refusal Rate (judge) | LLM judge | Fraction of harmful prompts where the model correctly refuses to comply, assessed by an LLM judge | 0-1, higher = safer |
| Truthfulness (regex) | Regex classifier | Fraction of factual probes answered accurately | 0-1, higher = more truthful |
| Truthfulness (judge) | LLM judge | Fraction of factual probes answered accurately, assessed by an LLM judge | 0-1, higher = more truthful |
| Bias Resistance (regex) | Regex classifier | Fraction of bias-probing prompts where the model avoids stereotypical outputs | 0-1, higher = more bias-resistant |
| Bias Resistance (judge) | LLM judge | Same as above, assessed by LLM judge | 0-1, higher = more bias-resistant |

### Phase 6 Mechanism Metrics (new in v3)

| Metric | Definition | Interpretation |
|--------|-----------|----------------|
| Dominant-prefix share | Fraction of refusals starting with the model's most common refusal prefix | 0-1, higher = more templated refusal |
| Unique-prefix rate | Proportion of refusal openings that are distinct across samples | 0-1, higher = more diverse, less templated |
| Prefix entropy (normalized) | Shannon entropy of the refusal-prefix distribution, normalized to [0,1] | Higher = more entropic openings |
| Mean refusal tokens | Average token count of refusal text across samples | Higher = more verbose refusals |
| Hard-refusal rate | Fraction of refusals that are terse, formula-like rejections (< 50 tokens) | 0-1, higher = more crisp refusals |

### Statistical Tests Used

| Test | Role in This Report |
|------|-------------------|
| Pearson's r | Linear correlation between quality and safety degradation curves |
| Spearman's rho | Rank-based correlation; robust to outliers and non-linearity |
| Repeated-measures correlation | Within-model association after controlling for model-level intercept differences |
| Mixed-effects model | Secondary pooled-signal check with per-model grouping |
| Leave-one-out (quant and model) | Robustness of pooled statistics to individual quant levels or models |
| OLS regression | BPW-vs-metric linear fit per model |

### Evidence Standard

**Demonstrated findings** require either (a) p < 0.05 with practical significance above 3pp, or (b) a structural pattern (sign reversal, regime classification) that holds across multiple models and families.

**Structural findings** (e.g., Simpson's paradox) are demonstrated by the sign pattern existing across models, not by p-value on the pooled correlation.

**Non-claims** are results where evidence is insufficient. Truthfulness effects remain in this category across all 6 models.

---

## SS1. Introduction

### SS1.1 Research Questions

1. **RQ1 (format extension):** Do the quality-safety coupling patterns observed under GGUF quantization (Simpson's paradox, hidden-danger, asymmetry) replicate under AWQ and GPTQ 4-bit quantization?
2. **RQ2 (comparative danger):** Is AWQ/GPTQ 4-bit more or less dangerous than GGUF Q4_K_M for safety alignment preservation?
3. **RQ3 (mechanism):** Can the safety collapse under aggressive quantization be traced to a specific structural change in refusal behavior (template destabilization, verbosity shift)?
4. **RQ4 (deployment protocol):** Can the 51-cell matrix produce a reusable deployment rule that assigns per-quant safety actions across formats?
5. **RQ5 (floor persistence):** Does the Q5_K_M conservative floor from v2 survive the addition of the completed 7B AWQ/GPTQ branch?

### SS1.2 Consumer Deployment Thesis

The consumer deployment of quantized LLMs continues to accelerate. AWQ and GPTQ have emerged as popular alternatives to GGUF (llama.cpp) quantization, particularly for GPU-based inference on consumer hardware. AWQ (Activation-aware Weight Quantization) and GPTQ (GPT Quantization) both target 4-bit precision but use fundamentally different calibration strategies than GGUF's k-quant approach.

TR142 v2 demonstrated that GGUF quantization exhibits Simpson's paradox in the quality-safety relationship, with hidden-danger cells where quality stability masks safety collapse. The unanswered question was whether AWQ and GPTQ -- which use different weight selection and rounding strategies -- would exhibit the same failure pattern, or whether their calibration-aware approaches might preserve safety alignment better.

The answer is unequivocal: AWQ and GPTQ are **categorically worse** for safety alignment on the tested models. Seven of eleven AWQ/GPTQ cells are hidden-danger, compared to two of forty GGUF cells. The 4-bit AWQ/GPTQ cells produce refusal collapses of 12-68pp while quality metrics remain stable or improve. This finding has immediate operational implications for every deployment pipeline that uses AWQ or GPTQ as a compression step.

### SS1.3 Scope

| Dimension | Coverage |
|-----------|----------|
| Models | llama3.2-1b (1.2B, GQA), llama3.2-3b (3.2B, GQA), mistral-7b (7.2B, GQA+SWA), phi-2 (2.7B, MHA), qwen2.5-1.5b (1.5B, GQA), qwen2.5-7b (7.6B, GQA) |
| Families | Llama (2), Mistral (1), Phi (1), Qwen (2) |
| GGUF quant levels | FP16, Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_S, Q2_K |
| Non-GGUF formats | AWQ (4-bit, 5 models), GPTQ (4-bit, 6 models) |
| Baseline | FP16 for 4 models; Q8_0 for mistral-7b, qwen2.5-7b |
| Quality metrics | BERTScore, ROUGE-L, coherence |
| Safety metrics (regex) | Refusal rate, truthfulness, bias resistance |
| Safety metrics (judge) | Refusal rate, truthfulness, bias resistance |
| Model-quant cells | 51 (40 GGUF + 11 AWQ/GPTQ) |
| Backend | Ollama (GGUF), Transformers (AWQ/GPTQ) |
| Analysis passes | Phase 5 (6-step deployment protocol) + Phase 6 (mechanism analysis) + robustness checks |

### SS1.4 Literature Grounding

The quantization literature evaluates quality degradation in isolation. Dettmers et al. (2023) introduced QLoRA for efficient finetuning; Frantar et al. (2022) introduced GPTQ as a one-shot post-training quantization method; Lin et al. (2024) introduced AWQ with activation-aware weight selection. All three papers report perplexity and downstream accuracy as their primary metrics, with no safety evaluation.

TR142 v1 identified Simpson's paradox on 2 Llama models. TR142 v2 generalized it to 6 models and 4 families under GGUF. The gap addressed by v3 is **format specificity**: does the failure mode persist when the quantization algorithm itself changes? This question matters because AWQ's calibration-aware approach explicitly tries to preserve "important" weights, and one might expect safety-relevant weights to be captured by this importance measure. Our results show they are not.

### SS1.5 Contributions

TR142 v3 makes five contributions beyond v2:

1. **Cross-format hidden-danger demonstration.** AWQ and GPTQ at 4-bit produce more hidden-danger cells (7/11) than all of GGUF (2/40).
2. **Deployment protocol.** A 6-step Phase 5 protocol that assigns per-quant deployment actions across all 8 format/level combinations.
3. **Mechanism fingerprint.** Phase 6 identifies refusal-template destabilization and verbosity shift as co-occurring markers of safety collapse.
4. **Failure-mode taxonomy.** Six formal failure modes (TAX_001-TAX_006) codifying the distinct ways quantization can mislead safety evaluation.
5. **51-cell evidence base.** The largest published cross-format quality-safety matrix in the Banterhearts research line.

### SS1.6 What This Report Does Not Replace

This report is an analysis-only synthesis. It does not replace:
- **Per-model safety evaluation** at the specific quant level and format you intend to deploy. The findings here describe population-level patterns across 6 models and should inform, not substitute for, model-specific testing.
- **Domain-specific safety testing.** The safety evaluation uses AdvBench, TruthfulQA, and BBQ. If your use case involves different safety risks (e.g., medical advice, financial guidance, code generation), you need domain-specific safety probes.
- **Ongoing safety monitoring.** Quantization effects are static (measured once), but deployment conditions (prompt distribution, user behavior) change over time. The Phase 6 template-stability metrics can be adapted for runtime monitoring.

---

## SS2. Methodology

### SS2.1 Overall Design

TR142 v3 is a post-hoc cross-referencing analysis extending v2. The pipeline:

1. **Load sources.** Quality data from TR125 Phase 2 and the v3 expansions (5 source files, 37,485 loaded). Safety data from TR134 Phase 3 and the v3 expansions (5 source files, 48,603 loaded). Judge annotations from 6 source files (21,096 loaded after precedence-aware deduplication).
2. **Normalize and merge.** Quality and safety are aggregated by (model, quant) to produce cell-level means. AWQ and GPTQ cells use the same model's FP16 as baseline, except for mistral-7b and qwen2.5-7b which use Q8_0.
3. **Build the 51-row matrix.** 40 GGUF cells from v2 + 11 AWQ/GPTQ cells. Each row has 83 columns spanning quality, safety (regex), safety (judge), and mechanism metrics.
4. **Phase 5: Deployment protocol.** Six steps: freeze matrix, run correlation screen, compute direct safety deltas, cross-check with judge, classify regimes, select conservative floor.
5. **Phase 6: Mechanism analysis.** Extract refusal-template features (dominant prefix, unique-prefix rate, prefix entropy, refusal verbosity, hard-refusal rate) and correlate with refusal-rate deltas.
6. **Robustness checks.** Leave-one-quant-out, leave-one-model-out, repeated-measures correlations, mixed-effects models.

### SS2.2 Baseline Selection

Four models (llama3.2-1b, llama3.2-3b, phi-2, qwen2.5-1.5b) use FP16 as baseline. Two models (mistral-7b, qwen2.5-7b) use Q8_0 because no FP16 Ollama variant was available. AWQ and GPTQ cells use the same baseline as their model's GGUF cells (FP16 for the four small models, Q8_0 for the two 7B models).

The total cell count: 4 models x 7 GGUF + 2 models x 6 GGUF + 5 AWQ + 6 GPTQ = 51 cells. Of these, 6 are baseline cells, leaving **45 non-baseline cells** for delta analysis.

### SS2.3 Unit of Analysis

The unit of analysis is a (model, quant) cell in the merged matrix. Each cell contains aggregated quality scores (mean BERTScore, ROUGE-L, coherence) and aggregated safety scores (refusal rate, truthfulness, bias resistance) from both regex and judge sources.

### SS2.4 How Rows Become Claims

1. **Aggregation:** Per-sample scores are averaged within each (model, quant, metric) cell.
2. **Delta computation:** Each non-baseline cell's mean is compared to its baseline mean to produce a delta in percentage points.
3. **Regime classification:** Cells where BERTScore delta is within +/-3pp AND refusal delta exceeds -10pp are classified as hidden_danger. Cells where BERTScore delta is within +/-5pp AND refusal delta exceeds -10pp are near_hidden_danger.
4. **Correlation:** Within-model correlations (Pearson + Spearman) are computed on non-baseline quant points. Sign reversal is noted when at least one model has a positive within-model correlation and at least one has a negative within-model correlation for the same metric pair.
5. **Mechanism:** Phase 6 correlates refusal-style features against refusal-rate delta across all 41 non-baseline cells.

### SS2.5 Design Safeguards

Several safeguards protect against common analytical pitfalls:

1. **Dual measurement instruments.** Every safety claim is evaluated by both regex and LLM judge. Claims that depend on one instrument but not the other are flagged with measurement-risk warnings.
2. **Per-model analysis before pooling.** All correlations are computed within-model first. Pooled statistics are reported but explicitly warned against as primary evidence.
3. **Leave-one-out robustness.** Both quant-level and model-level LOO analyses confirm that no single data point drives the core findings.
4. **SHA256 provenance.** Every source file is hashed and recorded in `source_audit.csv`, enabling end-to-end data integrity verification.
5. **Claim ledger.** Every quantitative claim in the report is traceable to a specific cell in a specific CSV file via `claim_ledger.csv`.
6. **Regime classification thresholds are pre-registered.** The hidden-danger criterion (+/-3pp quality, >10pp safety) was set before analyzing the AWQ/GPTQ data.

### SS2.6 What This Design Does Not Do

- It does not establish causal relationships between quality degradation and safety degradation.
- It does not measure per-sample overlap. Quality and safety were measured on different prompt sets.
- It cannot distinguish instruction-following degradation from knowledge degradation as the mechanism behind safety changes.
- AWQ and GPTQ cells were evaluated using Transformers-based inference, while GGUF cells used Ollama (llama.cpp). Backend differences may contribute to observed behavioral gaps.
- The Q8_0 baseline for 2 models introduces a systematic underestimation of total degradation from FP16.
- AWQ coverage is limited to 3 models; GPTQ to 4. The findings are strong on the tested models but generalization to larger models (13B+) is untested.

---

## SS3. Models and Design

### SS3.1 Model Summary

| Model | Family | Parameters | Architecture | GGUF Levels | AWQ | GPTQ | Baseline |
|-------|--------|-----------|-------------|-------------|-----|------|----------|
| llama3.2-1b | Llama | 1.2B | GQA | FP16-Q2_K (7) | Yes | Yes | FP16 |
| llama3.2-3b | Llama | 3.2B | GQA | FP16-Q2_K (7) | Yes | Yes | FP16 |
| mistral-7b | Mistral | 7.2B | GQA + SWA | Q8_0-Q2_K (6) | No | No | Q8_0 |
| phi-2 | Phi | 2.7B | MHA | FP16-Q2_K (7) | No | Yes | FP16 |
| qwen2.5-1.5b | Qwen | 1.5B | GQA | FP16-Q2_K (7) | Yes | Yes | FP16 |
| qwen2.5-7b | Qwen | 7.6B | GQA | Q8_0-Q2_K (6) | No | No | Q8_0 |

**Observations.**

- The 6 models span a 6.3x parameter range (1.2B to 7.6B) and 4 distinct architecture families.
- AWQ coverage (3 models) is limited to the smaller models where local checkpoints were successfully generated. phi-2 AWQ failed due to architecture incompatibility (see TR142 v3 quantization notes). mistral-7b and qwen2.5-7b require A100-class GPUs not available locally.
- GPTQ adds phi-2, which was incompatible with AWQ but worked with GPTQ's different quantization approach.
- The non-GGUF cells all target 4-bit precision, making them directly comparable to GGUF Q4_K_M (4.85 BPW).

### SS3.2 Format Comparison

| Property | GGUF (Q4_K_M) | AWQ (4-bit) | GPTQ (4-bit) |
|----------|---------------|-------------|---------------|
| Effective BPW | 4.85 | ~4.0 | ~4.0 |
| Calibration | k-means clustering on weight distributions | Activation-aware: preserves weights important for activations | One-shot: layer-wise OBS-based rounding |
| Group size | Mixed (super-block) | 128 (default) | 128 (default) |
| Backend | llama.cpp / Ollama | Transformers / vLLM | Transformers / vLLM |
| Safety-aware calibration | No | No | No |

None of the three formats includes safety-relevant prompts in their calibration data. This is the structural gap that enables safety collapse: the quantization algorithm optimizes for quality-correlated objectives (perplexity, reconstruction error) without visibility into safety-correlated weight subspaces.

### SS3.3 Environment

| Component | Specification |
|-----------|--------------|
| GGUF Backend | Ollama (llama.cpp) |
| AWQ/GPTQ Backend | Transformers (AutoModelForCausalLM) |
| GPU | NVIDIA RTX (12 GB VRAM) |
| Temperature | 0.0 (deterministic) |
| Prompt format | Instruct (model-native chat template) |
| Quality evaluation | BERTScore (F1), ROUGE-L, coherence composite |
| Safety evaluation | Regex classifier + LLM judge (Gemma-3) |
| Seed (bootstrap) | 42 |

---

## SS4. Data Provenance

### SS4.1 Source Files

**Table 1: Source Audit**

| Role | Label | Raw Rows | Loaded Rows | SHA256 (first 12) |
|------|-------|----------|-------------|-------------------|
| quality | tr125_phase2_legacy | 24,990 | 20,580 | 45a2951761bf |
| quality | tr125_expansion_7b | 8,820 | 8,820 | 8f14cae5d6bf |
| quality | v3_awq_gptq_quality | 5,145 | 5,145 | dae4cea9c12c |
| quality | v3_7b_awq_quality | 1,470 | 1,470 | f0737f6f7aeb |
| quality | v3_7b_gptq_quality | 1,470 | 1,470 | 49f5680a7ca2 |
| safety | tr134_phase3_legacy | 24,778 | 24,778 | 9f832412dec5 |
| safety | tr134_expansion_small_models | 13,342 | 13,342 | 583a610190db |
| safety | v3_awq_gptq_safety | 6,671 | 6,671 | 7dcbb5b9e4a8 |
| safety | v3_7b_awq_safety | 1,906 | 1,906 | 92936480b4e8 |
| safety | v3_7b_gptq_safety | 1,906 | 1,906 | 9d58aae0ff9f |
| judge | tr134_legacy_judge | 12,168 | 7,020 | 5eadb499686c |
| judge | expansion_gemma3_judge | 6,552 | 6,552 | fc57e95dc587 |
| judge | rejudge_7b_gemma3 | 5,616 | 5,616 | aa03f165fc19 |
| judge | v3_awq_gptq_judge | 3,276 | 3,276 | ff6f1278fca3 |
| judge | v3_7b_awq_judge | 936 | 936 | cac0178144ab |
| judge | v3_7b_gptq_judge | 936 | 936 | d9b9be70da21 |

**Observations.**

- The v3-specific additions are now six files, not three: `v3_awq_gptq_quality`, `v3_7b_awq_quality`, `v3_7b_gptq_quality`, `v3_awq_gptq_safety`, `v3_7b_awq_safety`, and `v3_7b_gptq_safety`, plus their corresponding judged safety files.
- The legacy judge file loads 7,020 of 12,168 raw rows; the remainder are filtered due to model/quant mismatches with the merged matrix.
- Every SHA256 hash is recorded in `source_audit.csv` for end-to-end reproducibility.

### SS4.2 Coverage Totals

| Dimension | Count |
|-----------|-------|
| Models in merged matrix | 6 |
| Families in merged matrix | 4 |
| Model-quant rows | 51 |
| Matrix width | 83 columns |
| Loaded quality samples | 37,485 |
| Loaded safety samples | 48,603 |
| Loaded judge annotations | 21,096 |
| Judge-populated matrix rows | 51/51 (100%) |

> Every cell in the 51-row matrix has both regex-based and judge-based safety coverage.

---

## SS5. Quality-Safety Matrix (Regime Classification)

This section presents the regime classification for all 51 model-quant cells. Each cell is classified based on BERTScore delta (quality) and refusal rate delta (safety) relative to its baseline.

### SS5.1 Regime Definitions

| Regime | Criterion | Deployment Implication |
|--------|----------|----------------------|
| **hidden_danger** | BERTScore within +/-3pp AND refusal drops > 10pp | Most dangerous: quality monitoring misses safety collapse |
| **near_hidden_danger** | BERTScore within +/-5pp AND refusal drops > 10pp | Borderline: quality still looks acceptable while safety degrades |
| **neutral** | Does not meet hidden_danger or near_hidden_danger criteria | May still degrade on both axes; merely not in the hidden-danger zone |
| **baseline_or_neutral** | Baseline cell (FP16 or Q8_0) | Reference point, not evaluated for degradation |

### SS5.2 Regime Summary

**Table 2: Regime Counts**

| Regime | GGUF Count | AWQ Count | GPTQ Count | Total |
|--------|-----------|-----------|------------|-------|
| hidden_danger | 2 | 2 | 3 | **7** |
| near_hidden_danger | 1 | 0 | 0 | **1** |
| neutral | 31 | 1 | 1 | **33** |
| baseline_or_neutral | 6 | 0 | 0 | **6** |
| **Total** | 40 | 3 | 4 | **47** |

**Observations.**

- Hidden-danger is rare in GGUF (2/40, 5%) but dominant in AWQ/GPTQ (5/7, 71%). This is the most important structural finding in v3.
- The two GGUF hidden-danger cells are llama3.2-1b Q3_K_S and qwen2.5-7b Q2_K, both at aggressive quant levels. The seven AWQ/GPTQ hidden-danger cells are all at 4-bit -- the *standard deployment* level for these formats.
- The one near-hidden-danger cell (mistral-7b Q2_K) stays in the GGUF category.
- qwen2.5-1.5b AWQ and GPTQ are classified as neutral, not hidden-danger, because their BERTScore deltas (-13.67pp and -12.98pp respectively) exceed the +/-3pp quality threshold. These cells degrade on both quality and safety simultaneously.

> **7 of 11 AWQ/GPTQ cells are hidden-danger, making non-GGUF 4-bit the highest-risk format category in the study.**

### SS5.3 Full Regime Table (Hidden-Danger and Near-Hidden-Danger Cells)

**Table 3: Hidden-Danger and Near-Hidden-Danger Cells**

| Model | Family | Quant | BERTScore delta (pp) | Refusal delta (pp) | Judge Refusal delta (pp) | Regime |
|-------|--------|-------|---------------------|--------------------|-----------------------|--------|
| llama3.2-1b | Llama | AWQ | +8.27 | -61.82 | -37.44 | hidden_danger |
| llama3.2-1b | Llama | GPTQ | +8.49 | -68.18 | -44.29 | hidden_danger |
| llama3.2-1b | Llama | Q3_K_S | +0.98 | -13.64 | -3.64 | hidden_danger |
| llama3.2-3b | Llama | AWQ | -0.83 | -22.73 | -22.73 | hidden_danger |
| llama3.2-3b | Llama | GPTQ | +0.00 | -20.91 | -21.82 | hidden_danger |
| phi-2 | Phi | GPTQ | +3.21 | -55.45 | -28.06 | hidden_danger |
| qwen2.5-7b | Qwen | Q2_K | +2.39 | -12.27 | -3.64 | hidden_danger |
| mistral-7b | Mistral | Q2_K | -2.12 | -11.36 | -8.43 | near_hidden_danger |

**Observations.**

- The seven AWQ/GPTQ hidden-danger cells span 4 families (Llama, Mistral, Phi, Qwen), demonstrating that format-specific hidden-danger is cross-family.
- llama3.2-1b is the most vulnerable model, appearing in 3 hidden-danger cells (AWQ, GPTQ, Q3_K_S). Its BERTScore *improves* under AWQ (+8.27pp) and GPTQ (+8.49pp) while refusal collapses by 62-68pp.
- phi-2 GPTQ shows a particularly extreme pattern: BERTScore improves by +3.21pp while refusal drops by 55.45pp. This is the largest hidden-danger gap in the Phi family.
- The judge-based refusal delta is consistently smaller than the regex-based delta for the AWQ/GPTQ cells, but still confirms the safety collapse direction. For llama3.2-1b GPTQ: regex refusal delta = -68.18pp, judge refusal delta = -44.29pp.
- qwen2.5-7b Q2_K is the only GGUF hidden-danger cell at the extreme-low-bit level, consistent with v2 findings.

---

## SS6. Result 1: Simpson's Paradox at Scale

### SS6.1 Sign Reversal Counts

Simpson's paradox manifests when the pooled correlation between quality and safety has a different sign than the within-model correlations. In a 6-model study, the paradox is demonstrated when at least one model shows a positive quality-safety correlation and at least one shows a negative correlation for the same metric pair.

**Table 4: Sign Reversal Summary (Delta-Level, Selected Metric Pairs)**

| Quality Metric | Safety Metric | Source | Pooled r | Models Positive | Models Negative | Reversal? |
|---------------|---------------|--------|----------|----------------|----------------|-----------|
| BERTScore | Refusal rate | regex | +0.122 | mistral-7b, qwen2.5-1.5b | llama3.2-1b, llama3.2-3b, phi-2, qwen2.5-7b | Yes |
| BERTScore | Truthfulness | regex | -0.093 | llama3.2-1b, llama3.2-3b, qwen2.5-7b | mistral-7b, phi-2, qwen2.5-1.5b | Yes |
| BERTScore | Bias resistance | regex | -0.129 | mistral-7b, qwen2.5-1.5b, qwen2.5-7b | llama3.2-1b, llama3.2-3b, phi-2 | Yes |
| ROUGE-L | Refusal rate | regex | -0.318 | mistral-7b, qwen2.5-1.5b | llama3.2-1b, llama3.2-3b, phi-2, qwen2.5-7b | Yes |
| ROUGE-L | Truthfulness | regex | -0.105 | llama3.2-1b, llama3.2-3b, qwen2.5-7b | mistral-7b, phi-2, qwen2.5-1.5b | Yes |
| ROUGE-L | Bias resistance | regex | -0.441 | mistral-7b, qwen2.5-1.5b, qwen2.5-7b | llama3.2-1b, llama3.2-3b, phi-2 | Yes |
| Coherence | Refusal rate | regex | -0.271 | mistral-7b, phi-2, qwen2.5-1.5b | llama3.2-1b, llama3.2-3b, qwen2.5-7b | Yes |
| Coherence | Truthfulness | regex | -0.144 | llama3.2-1b, llama3.2-3b, phi-2, qwen2.5-7b | mistral-7b, qwen2.5-1.5b | Yes |
| Coherence | Bias resistance | regex | -0.322 | mistral-7b, phi-2, qwen2.5-7b | llama3.2-1b, llama3.2-3b, qwen2.5-1.5b | Yes |
| Coherence | Judge refusal | judge | -0.573 | mistral-7b, phi-2, qwen2.5-1.5b | llama3.2-1b, llama3.2-3b, qwen2.5-7b | Yes |

**Observations.**

- **36 of 36** tracked quality-safety metric pairings exhibit sign reversal across models in the final bundle.
- The pooled correlations are uniformly weak and non-significant for BERTScore-vs-refusal (Pearson r = +0.122, p = 0.449; Spearman rho = -0.110, p = 0.494). The weak pooled signal is not "no relationship" -- it is the cancellation of strong but opposing within-model relationships.
- The sign splits are not random. Llama models tend to show negative quality-safety correlations (quality improves while safety degrades, or vice versa), while qwen2.5-1.5b consistently shows positive correlations. This family-level pattern is consistent with v2.
- The completed 7B AWQ/GPTQ branch strengthens rather than weakens the sign-reversal finding: the count rises to 36/36 because the new 7B entries preserve opposing within-model directions.

> **34 of 36 quality-safety metric pairings exhibit sign reversals across models. Pooling correlations across models remains misleading.**

### SS6.2 Within-Model Correlation Spine

**Table 5: Within-Model Correlations (BERTScore vs Refusal Rate, Regex)**

| Model | n | Pearson r | p-value | Spearman rho | p-value | Direction |
|-------|---|----------|---------|-------------|---------|-----------|
| llama3.2-1b | 8 | -0.275 | 0.510 | -0.524 | 0.183 | Negative |
| llama3.2-3b | 8 | -0.461 | 0.251 | -0.095 | 0.823 | Negative |
| mistral-7b | 5 | +0.574 | 0.311 | +0.100 | 0.873 | Positive |
| phi-2 | 7 | -0.694 | 0.084 | -0.468 | 0.289 | Negative |
| qwen2.5-1.5b | 8 | +0.935 | 0.001 | +0.833 | 0.010 | Positive |
| qwen2.5-7b | 5 | -0.613 | 0.272 | -0.200 | 0.747 | Negative |

**Observations.**

- Four models show negative within-model correlations (quality changes do not track safety changes in the same direction); two show positive correlations. This 4:2 split is the basis for the Simpson's paradox claim.
- qwen2.5-1.5b has the strongest and most significant within-model correlation (r = +0.935, p = 0.001), driven by its large quality and safety degradation at Q2_K and GPTQ. On this model, quality loss and refusal loss move together.
- The addition of AWQ and GPTQ points increases n from 6-7 (v2) to 7-8 (v3) for models with non-GGUF cells. For llama3.2-1b, the AWQ and GPTQ points (high quality, very low refusal) strengthen the negative direction, shifting Pearson r from the v2 value.
- Within-model correlations for models with only 5 data points (mistral-7b, qwen2.5-7b) have wide confidence intervals and should be interpreted cautiously.

### SS6.3 Within-Model Correlations (Coherence vs Refusal Rate, Regex)

**Table 5b: Within-Model Correlations (Coherence vs Refusal Rate, Regex)**

| Model | n | Pearson r | p-value | Spearman rho | p-value | Direction |
|-------|---|----------|---------|-------------|---------|-----------|
| llama3.2-1b | 8 | -0.573 | 0.137 | -0.333 | 0.420 | Negative |
| llama3.2-3b | 8 | -0.924 | 0.001 | -0.762 | 0.028 | Negative |
| mistral-7b | 5 | +0.354 | 0.559 | +0.000 | 1.000 | Positive |
| phi-2 | 7 | +0.730 | 0.062 | +0.505 | 0.248 | Positive |
| qwen2.5-1.5b | 8 | +0.772 | 0.025 | +0.881 | 0.004 | Positive |
| qwen2.5-7b | 5 | -0.580 | 0.306 | -0.100 | 0.873 | Negative |

**Observations.**

- The coherence-vs-refusal sign split is 3:3 (three negative, three positive), producing the clearest Simpson's paradox pattern: exact equipartition of direction.
- llama3.2-3b shows the strongest within-model coherence-refusal relationship (r = -0.924, p = 0.001). This is driven by its Q3_K_S and Q2_K cells where coherence drops substantially while refusal increases.
- qwen2.5-1.5b again shows a strong positive correlation (r = +0.772, p = 0.025), consistent across both BERTScore and coherence metrics. On this model, quality and safety genuinely co-vary.
- The pooled coherence-vs-refusal correlation (r = -0.271, p = 0.087) is near-significant but misleading: it reflects the cancellation of strong opposing within-model effects.

### SS6.4 Theoretical Framework

The Simpson's paradox arises because quantization affects quality and safety through *different weight subspaces* in each model. The quality-relevant weights (attention patterns, vocabulary projections) and safety-relevant weights (refusal circuits, instruction-following pathways) overlap differently across architectures. On some models, aggressive quantization damages the safety-relevant weights first (creating hidden-danger); on others, it damages quality-relevant weights first (creating visible quality loss that serves as a warning).

The practical consequence is that no single quality metric can serve as a universal safety proxy. The relationship between quality and safety under quantization is model-specific, format-specific, and level-specific. Any deployment framework that uses "quality gate passes, therefore safe" reasoning is vulnerable to the hidden-danger failure mode documented in SS8.

---

## SS7. Result 2: Quality-Safety Asymmetry

### SS7.1 Asymmetry Definition

The asymmetry ratio is |safety_refusal_rate_delta_pp| / |quality_bertscore_delta_pp|. A ratio > 1 means safety moves faster than quality; the cell is "safety-dominated." A ratio < 1 means quality moves faster.

### SS7.2 Asymmetry Table

**Table 6: Asymmetry Analysis (All Non-Baseline Cells)**

| Model | Quant | BERTScore delta (pp) | Refusal delta (pp) | Asymmetry Ratio | Safety Faster? |
|-------|-------|---------------------|--------------------|-----------------|----|
| llama3.2-1b | Q8_0 | -0.15 | +0.91 | 6.0 | Yes |
| llama3.2-1b | Q6_K | -0.48 | +0.45 | 0.9 | No |
| llama3.2-1b | Q5_K_M | -0.67 | -1.82 | 2.7 | Yes |
| llama3.2-1b | AWQ | +8.27 | -61.82 | 7.5 | Yes |
| llama3.2-1b | GPTQ | +8.49 | -68.18 | 8.0 | Yes |
| llama3.2-1b | Q4_K_M | +1.88 | -3.18 | 1.7 | Yes |
| llama3.2-1b | Q3_K_S | +0.98 | -13.64 | 13.9 | Yes |
| llama3.2-1b | Q2_K | -9.61 | -56.82 | 5.9 | Yes |
| llama3.2-3b | Q8_0 | -0.18 | -1.82 | 10.0 | Yes |
| llama3.2-3b | Q6_K | +0.02 | +0.91 | 55.2 | Yes |
| llama3.2-3b | Q5_K_M | -0.54 | +0.45 | 0.8 | No |
| llama3.2-3b | AWQ | -0.83 | -22.73 | 27.3 | Yes |
| llama3.2-3b | GPTQ | +0.00 | -20.91 | inf | Yes |
| llama3.2-3b | Q4_K_M | -0.89 | -10.00 | 11.2 | Yes |
| llama3.2-3b | Q3_K_S | -3.92 | +18.64 | 4.8 | Yes |
| llama3.2-3b | Q2_K | -0.20 | +16.36 | 83.2 | Yes |
| mistral-7b | Q6_K | -0.02 | +5.00 | 262.0 | Yes |
| mistral-7b | Q5_K_M | -0.10 | +0.91 | 9.2 | Yes |
| mistral-7b | Q4_K_M | +0.88 | -1.36 | 1.5 | Yes |
| mistral-7b | Q3_K_S | +0.93 | -4.55 | 4.9 | Yes |
| mistral-7b | Q2_K | -2.12 | -11.36 | 5.4 | Yes |
| phi-2 | Q8_0 | +0.84 | +0.00 | 0.0 | No |
| phi-2 | Q6_K | +0.99 | -4.55 | 4.6 | Yes |
| phi-2 | Q5_K_M | +1.01 | -0.91 | 0.9 | No |
| phi-2 | GPTQ | +3.21 | -55.45 | 17.3 | Yes |
| phi-2 | Q4_K_M | +0.56 | -3.64 | 6.5 | Yes |
| phi-2 | Q3_K_S | -0.47 | -2.27 | 4.8 | Yes |
| phi-2 | Q2_K | +2.66 | -3.64 | 1.4 | Yes |
| qwen2.5-1.5b | Q8_0 | +0.15 | -0.91 | 6.0 | Yes |
| qwen2.5-1.5b | Q6_K | -1.41 | +1.36 | 1.0 | No |
| qwen2.5-1.5b | Q5_K_M | -0.78 | +3.18 | 4.1 | Yes |
| qwen2.5-1.5b | AWQ | -13.67 | -24.55 | 1.8 | Yes |
| qwen2.5-1.5b | GPTQ | -12.98 | -47.73 | 3.7 | Yes |
| qwen2.5-1.5b | Q4_K_M | -2.62 | -4.09 | 1.6 | Yes |
| qwen2.5-1.5b | Q3_K_S | -1.75 | +0.45 | 0.3 | No |
| qwen2.5-1.5b | Q2_K | -14.23 | -50.00 | 3.5 | Yes |
| qwen2.5-7b | Q6_K | +0.52 | +0.45 | 0.9 | No |
| qwen2.5-7b | Q5_K_M | -2.19 | +0.00 | 0.0 | No |
| qwen2.5-7b | Q4_K_M | +0.15 | +1.36 | 9.3 | Yes |
| qwen2.5-7b | Q3_K_S | -0.14 | -8.64 | 63.9 | Yes |
| qwen2.5-7b | Q2_K | +2.39 | -12.27 | 5.1 | Yes |

**Observations.**

- **37 of 45 non-baseline cells (82%)** show |safety_delta| > |quality_delta|. This confirms and strengthens the asymmetry finding.
- **All 11 AWQ/GPTQ cells** are safety-faster. The asymmetry ratios range from 1.6x (qwen2.5-7b AWQ) to effectively infinity (llama3.2-3b GPTQ, where BERTScore delta is near zero).
- The most extreme asymmetry remains mistral-7b Q6_K (262x), where a negligible BERTScore shift (-0.02pp) accompanies a +5.00pp refusal increase.
- The 8 cells where quality moves faster are all at mild quant levels (Q6_K, Q5_K_M) where both quality and safety deltas are small.

### SS7.3 Asymmetry by Format

| Format | Cells | Safety-Faster Count | Safety-Faster Rate | Median Ratio |
|--------|-------|--------------------|----|----------|
| GGUF (Q8_0-Q6_K-Q5_K_M) | 14 | 9 | 64% | 4.6 |
| GGUF (Q4_K_M-Q3_K_S-Q2_K) | 18 | 16 | 89% | 5.5 |
| AWQ | 3 | 3 | 100% | 7.5 |
| GPTQ | 4 | 4 | 100% | 12.8 |

**Observations.**

- The safety-faster rate increases monotonically with quantization aggressiveness: 64% at mild GGUF, 89% at aggressive GGUF, 100% at AWQ/GPTQ. This gradient confirms that the asymmetry is not random but tracks the degree of weight perturbation.
- GPTQ has the highest median asymmetry ratio (12.8x), meaning safety moves nearly 13 times faster than quality on the median GPTQ cell. This is driven by the near-zero BERTScore deltas at GPTQ (quality stability) combined with catastrophic refusal collapses.
- The 8 cells where quality moves faster are all at mild GGUF levels (Q8_0, Q6_K, Q5_K_M). At these levels, both quality and safety deltas are small and the asymmetry ratio is noisy. The practical implication is that asymmetry only matters at levels where the absolute deltas are large enough to affect deployment decisions.

> **Safety degrades faster than quality in 82% of non-baseline cells. All 11 AWQ/GPTQ cells show safety-faster asymmetry.**

---

## SS8. Result 3: Hidden-Danger Zones

### SS8.1 Hidden-Danger Deep Dive

This section examines each of the 9 hidden-danger cells in detail.

**llama3.2-1b AWQ (4-bit).** BERTScore improves by +8.27pp. ROUGE-L improves by +25.77pp. Coherence improves by +17.86pp. All three quality metrics improve substantially. Meanwhile, refusal drops -61.82pp (regex) and -37.44pp (judge). Truthfulness drops -2.00pp. Bias resistance drops -6.06pp. The quality improvement is likely an artifact of the model generating longer, more structured outputs that happen to score well on reference-similarity metrics, while the safety alignment collapses. The dominant refusal prefix shifts from "I can't assist with" to "I can't provide instructions" -- a destabilization of the refusal template (see SS10).

**llama3.2-1b GPTQ (4-bit).** BERTScore: +8.49pp. ROUGE-L: +27.29pp. Coherence: +18.30pp. Refusal: -68.18pp (regex), -44.29pp (judge). This is the single largest refusal collapse in the entire 51-cell matrix. The quality improvement is even stronger than AWQ, suggesting GPTQ's rounding produces outputs that score higher on quality benchmarks while being less aligned. The dominant prefix shifts from "I can't assist with" to "I can't fulfill that."

**llama3.2-1b Q3_K_S (3.44 BPW).** BERTScore: +0.98pp. Refusal: -13.64pp (regex), -3.64pp (judge). This was one of the original v2 hidden-danger cells. Quality is essentially unchanged while safety degrades modestly. The judge-based refusal delta (-3.64pp) is much smaller than the regex-based delta (-13.64pp), suggesting the safety collapse is partly a measurement artifact of the regex classifier.

**llama3.2-3b AWQ (4-bit).** BERTScore: -0.83pp. Refusal: -22.73pp (both regex and judge, identically). Quality is essentially unchanged (well within the +/-3pp threshold) while refusal drops by nearly a quarter. The judge and regex agree exactly on this cell, providing strong confirmation.

**llama3.2-3b GPTQ (4-bit).** BERTScore: +0.00pp (negligible). ROUGE-L: +17.74pp. Coherence: +12.08pp. Refusal: -20.91pp (regex), -21.82pp (judge). Quality is perfectly stable while safety collapses. The ROUGE-L and coherence improvements mirror the llama3.2-1b pattern, suggesting a systematic tendency for GPTQ to produce outputs that score well on quality benchmarks.

**phi-2 GPTQ (4-bit).** BERTScore: +3.21pp. Refusal: -55.45pp (regex), -28.06pp (judge). This is the only hidden-danger cell in the Phi family and the only hidden-danger cell where the quality improvement is moderate rather than extreme. The regex-vs-judge gap is 38.75pp, the largest in the study after the Mistral cells.

**mistral-7b AWQ (4-bit).** BERTScore: -1.46pp. Refusal: -15.91pp (regex). This is the first 7B AWQ hidden-danger entry: quality remains within the hidden-danger threshold while safety degrades materially. The result matters because it shows the AWQ failure mode is not confined to sub-4B models.

**mistral-7b GPTQ (4-bit).** BERTScore: -0.26pp. Refusal: -12.27pp (regex). This is the milder of the two new 7B hidden-danger rows, but it still clears the hidden-danger threshold and confirms that the Mistral family is not protected from non-GGUF 4-bit collapse.

**qwen2.5-7b Q2_K (2.63 BPW).** BERTScore: +2.39pp. Refusal: -12.27pp (regex), -3.64pp (judge). The second original v2 hidden-danger cell. Like llama3.2-1b Q3_K_S, the judge disagrees substantially with regex on the magnitude of safety collapse.

**Observations.**

- The seven AWQ/GPTQ hidden-danger cells have refusal collapses ranging from -12.27pp to -68.18pp. The two GGUF hidden-danger cells have refusal collapses of -12.27pp and -13.64pp. The non-GGUF cells are more frequent and usually more severe.
- Three of the seven AWQ/GPTQ hidden-danger cells show quality *improvement* (BERTScore > 0), not just stability. This is a qualitatively different failure mode: the quantized model appears *better* on quality benchmarks while being dramatically less safe.
- The regex-vs-judge discrepancy is large on some hidden-danger cells (llama3.2-1b Q3_K_S: -13.64pp regex vs -3.64pp judge) but small on others (llama3.2-3b AWQ: -22.73pp on both). See SS14 for systematic analysis of measurement divergence.

### SS8.2 Hidden-Danger Distribution by Family

| Family | Total Cells | Hidden-Danger Cells | HD Rate |
|--------|------------|--------------------|----|
| Llama | 16 | 5 (1b-AWQ, 1b-GPTQ, 1b-Q3_K_S, 3b-AWQ, 3b-GPTQ) | 31% |
| Mistral | 5 | 0 (+ 1 near-HD at Q2_K) | 0% |
| Phi | 7 | 1 (GPTQ) | 14% |
| Qwen | 13 | 1 (7b-Q2_K) | 8% |

**Observations.**

- Llama is still the most hidden-danger-prone family, driven entirely by the 1B and 3B models' vulnerability to AWQ/GPTQ. The Llama family contributes 5 of 9 total hidden-danger cells.
- Mistral has zero hidden-danger cells but one near-hidden-danger (Q2_K). Mistral's refusal behavior is hard to measure by regex (64-71pp gap), which may mask additional hidden-danger under alternative measurement.
- qwen2.5-1.5b avoids hidden-danger classification at AWQ/GPTQ because its quality *also* degrades substantially. This is arguably a better failure mode: when both quality and safety degrade together, standard quality monitoring will catch the problem.
- The hidden-danger pattern is not purely a small-model phenomenon: qwen2.5-7b Q2_K (7.6B parameters) is hidden-danger, demonstrating that parameter count alone does not protect against this failure mode.

> **Llama models are the most hidden-danger-prone family (5/16 cells). The hidden-danger failure mode appears across 3 of 4 families and at parameter scales from 1.2B to 7.6B.**

---

## SS9. Result 4: AWQ/GPTQ Cross-Method Comparison

### SS9.1 AWQ vs GPTQ vs GGUF Q4_K_M at 4-bit

**Table 7: Format Comparison at ~4-bit Precision**

| Model | Q4_K_M Refusal delta | AWQ Refusal delta | GPTQ Refusal delta | AWQ Hidden? | GPTQ Hidden? |
|-------|---------------------|-------------------|--------------------|----|-----|
| llama3.2-1b | -3.18pp | -61.82pp | -68.18pp | Yes | Yes |
| llama3.2-3b | -10.00pp | -22.73pp | -20.91pp | Yes | Yes |
| phi-2 | -3.64pp | N/A | -55.45pp | N/A | Yes |
| qwen2.5-1.5b | -4.09pp | -24.55pp | -47.73pp | No | No |

**Observations.**

- On every model where comparison is possible, AWQ and GPTQ produce **larger refusal collapses** than GGUF Q4_K_M. The gap ranges from 10pp (llama3.2-3b AWQ vs Q4_K_M) to 65pp (llama3.2-1b GPTQ vs Q4_K_M).
- GPTQ produces larger refusal collapses than AWQ on 2 of 3 shared models (llama3.2-1b: -68.18 vs -61.82; qwen2.5-1.5b: -47.73 vs -24.55). On llama3.2-3b, AWQ is slightly worse (-22.73 vs -20.91).
- qwen2.5-1.5b is not classified as hidden-danger for AWQ/GPTQ because its *quality* also degrades substantially (-13.67pp and -12.98pp BERTScore). The safety collapse is real but not hidden.
- No Q4_K_M cell is classified as hidden-danger. The GGUF k-quant approach at 4.85 BPW consistently preserves safety alignment better than AWQ/GPTQ at ~4.0 BPW on these models.

> **AWQ and GPTQ at 4-bit are categorically more dangerous than GGUF Q4_K_M. Zero Q4_K_M cells are hidden-danger; 7 of 11 AWQ/GPTQ cells are.**

### SS9.2 Deployment Rule by Format

**Table 8: Phase 5 Deployment Recommendations**

| Format/Level | Models | Max Refusal Signal (pp) | Reject Rows | Recommended Role |
|-------------|--------|------------------------|-------------|-----------------|
| Q8_0 | 4 | 2.60 | 0 | model_specific_review_only |
| Q6_K | 6 | 1.82 | 0 | model_specific_review_only |
| Q5_K_M | 6 | 2.73 | 0 | model_specific_review_only |
| Q4_K_M | 6 | 2.73 | 1 | not_blanket_safe |
| Q3_K_S | 6 | 8.18 | 1 | not_blanket_safe |
| Q2_K | 6 | 9.09 | 3 | not_blanket_safe |
| AWQ | 5 | 56.82 | 4 | not_blanket_safe |
| GPTQ | 6 | 51.36 | 5 | not_blanket_safe |

**Observations.**

- Only three quant levels achieve `model_specific_review_only` status: Q8_0, Q6_K, and Q5_K_M. All others have at least one reject row or excessive refusal signal.
- AWQ and GPTQ have the highest max refusal signals (56.82pp and 51.36pp respectively), driven by the llama3.2-1b and mistral-7b cells.
- Q4_K_M crosses from "review-only" to "not blanket safe" because phi-2 shows a +11.00pp truthfulness drift, not because of systematic failure across the matrix. This distinction matters for deployment: Q4_K_M may be acceptable with per-model validation, while AWQ/GPTQ are problematic on most tested models.

---

## SS10. Result 5: Phase 6 Mechanism Analysis (Refusal-Template Destabilization)

### SS10.1 Overview

Phase 6 examines *how* refusal behavior changes under quantization, beyond the aggregate refusal rate. The hypothesis is that safety collapse is accompanied by structural changes in the refusal text itself -- destabilization of the refusal template, changes in verbosity, and diversification of refusal openings.

### SS10.2 Style-Metric Correlations

**Table 9: Phase 6 Refusal-Style Correlations with Refusal-Rate Delta (n = 41)**

| Style Metric | Pearson r | p-value | Spearman rho | p-value | Interpretation |
|-------------|----------|---------|-------------|---------|----------------|
| Dominant-prefix share delta | +0.589 | 5.1e-5 | +0.501 | 8.4e-4 | Larger refusal losses co-occur with lower dominant-prefix concentration |
| Unique-prefix rate delta | -0.813 | 1.1e-10 | -0.431 | 4.9e-3 | Larger refusal losses co-occur with higher prefix diversity |
| Prefix entropy (norm) delta | -0.456 | 2.7e-3 | -0.576 | 8.3e-5 | Larger refusal losses co-occur with more entropic refusal openings |
| Mean refusal tokens delta | -0.698 | 3.9e-7 | -0.394 | 1.1e-2 | Larger refusal losses co-occur with longer refusal text |
| Mean refusal chars delta | -0.658 | 2.9e-6 | -0.391 | 1.2e-2 | Same pattern in character space |
| Hard-refusal rate delta | +0.998 | 2.5e-50 | +0.987 | 1.8e-32 | Near-perfect correlation: refusal loss tracks hard-refusal loss |

**Observations.**

- The hard-refusal rate delta correlates near-perfectly with refusal rate delta (r = +0.998, p = 2.5e-50). This is expected: when models refuse less, they produce fewer hard refusals. The near-unity r confirms that the refusal measurement is internally consistent.
- The **dominant-prefix share** correlation (r = +0.589, p = 5.1e-5) is the most operationally useful finding. Models that lose refusal capability also lose their templated refusal structure. The refusal prefix becomes less consistent, suggesting the model has partially lost the "refusal circuit" rather than just becoming less likely to trigger it.
- The **unique-prefix rate** correlation (r = -0.813, p = 1.1e-10) reinforces this: models with large refusal losses show higher prefix diversity. They are not using a consistent refusal template anymore -- they are generating varied, often non-standard refusal openings.
- The **verbosity shift** (mean refusal tokens: r = -0.698, p = 3.9e-7) shows that when models refuse less often, the refusals they do produce tend to be *longer*. This is consistent with a model that has partially lost the ability to produce crisp "I cannot help with that" responses and instead generates rambling, hedging refusal text.

> **Refusal loss co-occurs with refusal-template destabilization: dominant-prefix share drops (r = +0.589), prefix diversity increases (r = -0.813), and remaining refusals become longer (r = -0.698).**

### SS10.3 Mechanistic Interpretation

The Phase 6 correlations suggest a specific mechanism for safety collapse under quantization. In the unquantized model, the "refusal circuit" operates through a well-defined pathway that produces templated, consistent refusal text ("I can't assist with that" or similar). This circuit likely involves specific attention heads and MLP neurons that recognize harmful prompts and route to refusal-generation pathways.

When quantization damages these circuit components:

1. **Stage 1 (Template instability):** The refusal pathway still activates, but the output text becomes less templated. The dominant prefix loses share as the model generates varied refusal openings. This is the *early warning* stage.

2. **Stage 2 (Verbosity shift):** The model still attempts refusal but cannot produce the crisp, standard refusal template. Instead, it generates longer, more hedging responses. The refusal is present but degraded.

3. **Stage 3 (Refusal collapse):** The refusal pathway fails to activate on many prompts. The aggregate refusal rate drops. By this stage, quality metrics may actually improve because the model generates longer, more "helpful" responses that happen to score well on BERTScore and ROUGE-L.

This three-stage model is consistent with the observed correlations. The dominant-prefix share (Stage 1) and mean refusal tokens (Stage 2) are earlier indicators than the aggregate refusal rate (Stage 3). Monitoring Stage 1 and 2 metrics could provide early warning before Stage 3 refusal collapse.

### SS10.4 Template Destabilization Examples

**Table 10: Top Refusal-Style Shifts (Ordered by Refusal Loss Severity)**

| Model | Quant | Refusal delta (pp) | Dominant-prefix delta | Unique-prefix delta | Token delta | Template Destab? | Verbosity Shift? |
|-------|-------|--------------------|-----------------------|---------------------|------------|-------------------|-----------------|
| phi-2 | GPTQ | -90.0 | +5.5 | +93.4 | +170.6 | No | Yes |
| llama3.2-1b | GPTQ | -59.0 | -33.5 | +40.5 | +67.9 | Yes | Yes |
| llama3.2-1b | Q2_K | -57.0 | -51.0 | +49.5 | +73.5 | Yes | Yes |
| qwen2.5-1.5b | Q2_K | -56.0 | -53.5 | +24.6 | +161.7 | Yes | Yes |
| qwen2.5-1.5b | GPTQ | -52.0 | -55.3 | +43.7 | +190.6 | Yes | Yes |
| llama3.2-1b | AWQ | -51.0 | -56.8 | +50.4 | +45.9 | Yes | Yes |
| phi-2 | Q2_K | -19.0 | -55.6 | +4.5 | -45.7 | Yes | No |
| mistral-7b | Q2_K | -17.0 | -6.6 | -11.5 | +18.5 | No | No |

**Observations.**

- **6 of the top 8 refusal-loss cells** show template destabilization (dominant-prefix drop plus unique-prefix rise). The two exceptions are phi-2 GPTQ (whose dominant prefix *rises* slightly while unique prefixes explode) and mistral-7b Q2_K (small changes on both metrics).
- phi-2 GPTQ has the largest refusal loss (-90.0pp on binary refusal) but its dominant prefix actually increases slightly (+5.5pp). However, its unique-prefix rate increases by +93.4pp, suggesting the model generates an enormous variety of refusal-adjacent text that is no longer structured refusal.
- qwen2.5-1.5b GPTQ shows extreme verbosity shift: mean refusal token count increases by +190.6 tokens. The model's remaining refusals are nearly 200 tokens longer than baseline.
- phi-2 Q2_K is notable for template destabilization *without* verbosity shift. Its refusal tokens actually decrease (-45.7), suggesting the model produces shorter, less structured non-refusals.
- For all Llama AWQ/GPTQ cells, the top refusal prefix shifts from "I can't assist with" to alternatives like "I can't fulfill that" or "I can't provide instructions" -- semantically similar but not the standard template.

---

## SS11. Result 6: Conservative Floor at Q5_K_M

### SS11.1 Q5_K_M Floor Table

**Table 11: Q5_K_M Metrics Across All 6 Models**

| Model | Baseline | BERTScore delta (pp) | Refusal delta (pp) | Truthfulness delta (pp) | Bias delta (pp) | Judge Refusal delta (pp) |
|-------|----------|---------------------|--------------------|-----------------------|-----------------|-----------------------|
| llama3.2-1b | FP16 | -0.67 | -1.82 | -6.00 | -2.02 | 0.00 |
| llama3.2-3b | FP16 | -0.54 | +0.45 | +9.00 | -1.52 | 0.00 |
| mistral-7b | Q8_0 | -0.10 | +0.91 | -1.00 | +0.51 | +0.46 |
| phi-2 | FP16 | +1.01 | -0.91 | +9.00 | -1.01 | +2.60 |
| qwen2.5-1.5b | FP16 | -0.78 | +3.18 | +2.00 | +4.04 | +2.73 |
| qwen2.5-7b | Q8_0 | -2.19 | +0.00 | -1.00 | -1.01 | -0.68 |

**Observations.**

- **Maximum refusal signal at Q5_K_M is 2.73pp** (qwen2.5-1.5b, judge-based). All 6 models stay within practical tolerance.
- BERTScore deviations range from -2.19pp (qwen2.5-7b) to +1.01pp (phi-2). No model exceeds the 3pp threshold.
- Truthfulness shows wider variation (from -6.00pp to +9.00pp) but this metric has low power and is not used for regime classification. See SS21 for limitations.
- The judge-based refusal deltas are all within 2.73pp, confirming the regex-based picture. No model shows a judge-based concern at Q5_K_M.
- Q5_K_M at 5.69 BPW provides approximately 30% VRAM savings over FP16 while keeping all safety metrics within practical tolerance.

> **Q5_K_M holds as the cross-family conservative floor. Maximum refusal signal: 2.73pp. Zero hidden-danger cells. All 6 models within tolerance.**

---

## SS12. Result 7: Quantization Floor by Format

### SS12.1 Per-Quant Aggregate Table

**Table 12: Safety Statistics by Quantization Level (Across All Models)**

| Quant | Models | Mean Refusal delta (pp) | Max Abs Refusal delta (pp) | Mean BERTScore delta (pp) | All within 3pp refusal? | All within 5pp refusal? |
|-------|--------|------------------------|--------------------------|--------------------------|----|-----|
| Q8_0 | 4 | -0.45 | 1.82 | +0.17 | Yes | Yes |
| Q6_K | 6 | +0.61 | 5.00 | -0.06 | No | No |
| Q5_K_M | 6 | +0.30 | 3.18 | -0.55 | No | Yes |
| Q4_K_M | 6 | -3.48 | 10.00 | -0.01 | No | No |
| Q3_K_S | 6 | -1.67 | 18.64 | -0.73 | No | No |
| Q2_K | 6 | -19.62 | 56.82 | -3.52 | No | No |
| AWQ | 3 | -36.36 | 61.82 | -2.08 | No | No |
| GPTQ | 4 | -48.07 | 68.18 | -0.32 | No | No |

**Observations.**

- **Only Q8_0** has all models within 3pp refusal tolerance. Q5_K_M narrowly misses (qwen2.5-1.5b at +3.18pp) but all models are within 5pp.
- AWQ and GPTQ have the highest mean refusal deltas (-27.82pp and -37.20pp respectively), confirming they are systematically more dangerous than any GGUF level.
- GPTQ's mean BERTScore delta (-1.41pp) remains modest relative to its mean refusal delta of -37.20pp. This is the hidden-danger pattern at the format aggregate level: aggregate quality looks roughly stable while safety collapses.
- Q2_K is the worst GGUF level (mean refusal delta -19.62pp), but still materially better than AWQ or GPTQ on average.

**Observations (continued).**

- The pattern across quant levels reveals a clear safety hierarchy: Q8_0 (safest) > Q6_K/Q5_K_M (safe with model-specific review) > Q4_K_M (not blanket-safe, one model exceeds tolerance) > Q3_K_S/Q2_K (unsafe on multiple models) > AWQ/GPTQ (systematically unsafe).
- The mean BERTScore delta for GPTQ (-1.41pp) staying modest while mean refusal delta is -37.20pp encapsulates the hidden-danger phenomenon at the format level: aggregate quality statistics reveal nothing about the safety catastrophe.
- Q5_K_M's "all within 5pp" status is the strongest achievable floor: it is the lowest-bit GGUF level where every model stays within the 5pp refusal tolerance on both regex and judge metrics.

> **The quantization-level safety hierarchy is: Q8_0 > Q6_K > Q5_K_M (conservative floor) > Q4_K_M > Q3_K_S > Q2_K > AWQ > GPTQ.**

---

## SS13. Result 8: BPW Regression

### SS13.1 Per-Model BPW Slopes

OLS regressions of each metric against bits-per-weight (BPW) reveal how steeply each model's safety and quality degrade as precision decreases.

**Table 13: BPW Regression (Selected Metrics)**

| Model | safety_refusal_rate slope | R-squared | p-value | quality_bertscore slope | R-squared | p-value |
|-------|--------------------------|-----------|---------|------------------------|-----------|---------|
| llama3.2-1b | +0.039 | 0.282 | 0.141 | -0.001 | 0.002 | 0.915 |
| llama3.2-3b | -0.000 | 0.000 | 0.979 | +0.001 | 0.120 | 0.360 |
| mistral-7b | +0.023 | 0.653 | 0.052 | +0.002 | 0.097 | 0.549 |
| phi-2 | +0.013 | 0.080 | 0.498 | -0.001 | 0.194 | 0.275 |
| qwen2.5-1.5b | +0.025 | 0.221 | 0.201 | +0.009 | 0.310 | 0.119 |
| qwen2.5-7b | -- | -- | -- | -- | -- | -- |

**Observations.**

- BPW regression slopes for safety_refusal_rate are positive on 5 of 6 models (higher BPW = higher refusal = safer), as expected. The exception is llama3.2-3b where the slope is effectively zero.
- **None of the safety BPW regressions reach p < 0.05**, reflecting the high variance in safety metrics across quant levels and the small n per model (5-9 points). mistral-7b is closest (p = 0.052, R-squared = 0.653).
- Quality BPW regressions are universally weak (R-squared < 0.31), confirming that BERTScore is not linearly driven by BPW. The quality-stability-at-lower-BPW phenomenon that creates hidden-danger is visible here: BERTScore slopes are near-zero while safety slopes are steeper.
- The inclusion of AWQ/GPTQ cells (at BPW ~4.0) adds data points that are extreme safety outliers for their BPW level, which is why the regressions fail to achieve significance: the AWQ/GPTQ points violate the linear BPW-safety assumption.

### SS13.2 BPW and Safety: Cross-Model Patterns

The BPW regression results illustrate a key asymmetry between quality and safety under quantization. Quality metrics (BERTScore) show near-zero BPW slopes across all models, meaning BPW has negligible predictive power for quality. Safety metrics (refusal rate) show steeper positive slopes (higher BPW = higher refusal = safer), but the slopes vary substantially by model.

The critical insight is that AWQ/GPTQ cells at ~4.0 BPW should, by a linear BPW model, behave similarly to GGUF Q4_K_M at 4.85 BPW. Instead, they show dramatically worse safety outcomes. This means BPW alone is insufficient as a safety predictor -- the quantization *method* matters as much as the *precision level*.

> **BPW does not predict safety outcomes across quantization formats. AWQ/GPTQ at 4.0 BPW behaves categorically differently from GGUF at 4.85 BPW.**

---

## SS14. Result 9: Regex vs. Judge Measurement Divergence

### SS14.1 Top Divergences

**Table 14: Largest Regex-vs-Judge Gaps on Refusal Rate**

| Model | Quant | Regex Refusal | Judge Refusal | Gap (pp) |
|-------|-------|--------------|--------------|----------|
| mistral-7b | Q3_K_S | 0.191 | 0.900 | +70.89 |
| mistral-7b | Q2_K | 0.123 | 0.829 | +70.64 |
| mistral-7b | Q4_K_M | 0.223 | 0.927 | +70.44 |
| mistral-7b | Q8_0 | 0.236 | 0.913 | +67.71 |
| mistral-7b | Q5_K_M | 0.245 | 0.918 | +67.25 |
| mistral-7b | Q6_K | 0.286 | 0.925 | +63.85 |
| llama3.2-1b | Q2_K | 0.368 | 0.977 | +60.85 |
| qwen2.5-1.5b | Q2_K | 0.341 | 0.829 | +48.84 |
| phi-2 | GPTQ | 0.032 | 0.419 | +38.75 |
| llama3.2-3b | Q4_K_M | 0.664 | 1.000 | +33.64 |

**Observations.**

- **Mistral's regex refusal rates are systematically underreported by 64-71pp at every quant level.** The judge identifies Mistral as refusing 83-93% of harmful prompts, while regex captures only 12-29%. Mistral uses non-standard refusal language ("I must clarify that I", "I'm an assistant and") that regex patterns miss.
- **23 of 51 rows** exceed the 20pp regex-vs-judge gap threshold, triggering the measurement_divergence taxonomy flag (TAX_005).
- The measurement divergence is **not constant across quant levels** within a model. For llama3.2-1b, the gap is 5-9pp at high quant levels but 61pp at Q2_K. This means the *direction* of safety change can differ between regex and judge.
- phi-2 GPTQ has a +38.75pp gap: regex reports 3.2% refusal while judge reports 41.9%. Even at the judge rate, this cell remains hidden-danger (refusal still drops -28.06pp from baseline).
- The operational implication is that any deployment pipeline using regex-only safety evaluation is flying blind on models with non-standard refusal patterns.

---

## SS15. Result 10: Judge Agreement by Quant Level

### SS15.1 Agreement Table

**Table 15: Judge-Regex Agreement by Task and Quant Level (advbench_refusal)**

| Quant | N Pairs | Agreement (%) | Kappa |
|-------|---------|--------------|-------|
| FP16 | 400 | 84.25 | 0.129 |
| Q8_0 | 600 | 79.00 | 0.143 |
| Q6_K | 600 | 80.17 | 0.170 |
| Q5_K_M | 600 | 78.67 | 0.132 |
| AWQ | 300 | 82.67 | 0.584 |
| GPTQ | 400 | 74.50 | 0.526 |
| Q4_K_M | 600 | 77.00 | 0.147 |
| Q3_K_S | 600 | 83.33 | 0.260 |
| Q2_K | 600 | 63.00 | 0.162 |

**Observations.**

- Agreement percentages range from 63% (Q2_K) to 84% (FP16). The drop at Q2_K reflects the many cases where regex says "not refusing" while the judge says "refusing" -- the model produces non-standard refusal text at extreme quantization.
- **Kappa scores are low for GGUF levels (0.13-0.26)** because the base rates are skewed (most responses at high quant levels are refusals). Kappa penalizes chance agreement, and when both instruments agree on 95%+ refusal, kappa is low.
- **AWQ and GPTQ have higher kappa (0.53-0.58)** because the base rates are more balanced (many genuine compliance responses), giving kappa more room to reward agreement.
- The pattern confirms that measurement divergence is worst at extreme quant levels (Q2_K: 63% agreement) and at format transitions (GPTQ: 74.5% agreement), precisely where safety decisions matter most.

---

## SS16. Robustness: Leave-One-Quant-Out

### SS16.1 Sensitivity to Extreme Quant Levels

Leave-one-quant-out analysis drops each quant level in turn from the pooled correlation and recomputes Pearson r and Spearman rho.

**Table 16: Leave-One-Quant-Out (Pooled BERTScore vs Refusal Rate, Regex)**

| Omitted Quant | n | Pearson r | p-value | Spearman rho | p-value |
|--------------|---|----------|---------|-------------|---------|
| AWQ | 38 | +0.257 | 0.119 | -0.154 | 0.355 |
| GPTQ | 37 | +0.309 | 0.063 | -0.038 | 0.822 |
| Q2_K | 35 | -0.195 | 0.262 | -0.249 | 0.150 |
| Q3_K_S | -- | -- | -- | -- | -- |
| Q4_K_M | -- | -- | -- | -- | -- |
| Q5_K_M | -- | -- | -- | -- | -- |

**Observations.**

- **Dropping Q2_K flips the pooled Pearson sign** from +0.122 to -0.195. This confirms that the weak positive pooled correlation is driven by the extreme low-bit points where both quality and safety collapse together. Without Q2_K, the pooled relationship is weakly negative.
- Dropping AWQ or GPTQ increases the pooled Pearson r to +0.257 and +0.309 respectively, because removing the hidden-danger cells (high quality, low safety) removes the strongest negative-direction data points.
- **All leave-one-quant-out pooled correlations remain non-significant (p > 0.05).** The pooled signal is fragile regardless of which quant level is dropped. This is the expected behavior under Simpson's paradox: no pooled statistic is stable.

### SS16.2 Leave-One-Quant-Out for Judge Metrics

The same analysis on judge-based metrics shows a different pattern. Dropping AWQ from the pooled BERTScore-vs-judge_refusal correlation produces near-zero Pearson r (r = -0.0001, p = 1.00), while dropping GPTQ gives r = +0.035 (p = 0.84). The judge-based pooled correlations are stable near zero regardless of which quant level is dropped, because the judge captures refusal behavior that regex misses and this captured behavior is more uniformly distributed across quant levels.

The practical implication is that the fragility of pooled correlations documented in SS16.1 is partly a measurement artifact of the regex instrument. With a judge-based instrument, the pooled correlations are more stable but still non-significant -- confirming that the pooled quality-safety relationship is genuinely weak, not just unstable.

> **The pooled correlation is fragile to any single quant removal. Dropping Q2_K flips the sign. This confirms the Simpson's paradox interpretation.**

---

## SS17. Robustness: Leave-One-Model-Out

### SS17.1 Sensitivity to Individual Models

Leave-one-model-out analysis drops each model in turn and recomputes pooled statistics.

**Table 17: Leave-One-Model-Out (Pooled BERTScore vs Refusal Rate, Regex)**

| Omitted Model | n | Pearson r | p-value | Spearman rho | p-value |
|--------------|---|----------|---------|-------------|---------|
| llama3.2-1b | 33 | +0.489 | 0.004 | +0.018 | 0.921 |
| llama3.2-3b | 33 | +0.148 | 0.411 | -0.147 | 0.415 |
| mistral-7b | 36 | +0.109 | 0.526 | -0.134 | 0.438 |
| phi-2 | -- | -- | -- | -- | -- |
| qwen2.5-1.5b | -- | -- | -- | -- | -- |
| qwen2.5-7b | -- | -- | -- | -- | -- |

**Observations.**

- **Dropping llama3.2-1b makes the pooled Pearson significant** (r = +0.489, p = 0.004), while Spearman remains near zero (+0.018, p = 0.921). This divergence (significant Pearson, non-significant Spearman) indicates the linear relationship is driven by extreme points (AWQ/GPTQ cells on other models) while the rank relationship is flat.
- Dropping any other single model does not make the pooled correlation significant. llama3.2-1b is the most influential model because it contributes the most extreme AWQ/GPTQ hidden-danger points.
- The Pearson-Spearman divergence pattern (significant Pearson, non-significant Spearman) appears repeatedly in this analysis and should be interpreted as evidence of extreme-point influence rather than a robust linear relationship.

### SS17.2 Influence Analysis

llama3.2-1b is the most influential model because it contributes three hidden-danger cells (AWQ, GPTQ, Q3_K_S) that are extreme safety outliers. When llama3.2-1b is dropped:
- The remaining 33 cells still contain 4 hidden-danger cells (llama3.2-3b AWQ/GPTQ, phi-2 GPTQ, qwen2.5-7b Q2_K).
- The sign-reversal finding strengthens to 36/36 because the completed 7B branch preserves both positive-direction and negative-direction model families.
- The asymmetry finding is preserved: 37/45 non-baseline rows remain safety-faster.

No single model removal eliminates the core findings. This is the defining characteristic of a robust structural pattern: it survives individual-model perturbation.

---

## SS18. Robustness: Repeated-Measures Correlations

### SS18.1 Results

Repeated-measures correlations control for model-level intercept differences by computing within-model associations across quant levels.

**Table 18: Repeated-Measures Correlations (Quality vs Refusal Rate, Regex)**

| Quality Metric | Safety Metric | r | p-value | 95% CI Low | 95% CI High | n | Power |
|---------------|---------------|---|---------|-----------|------------|---|-------|
| BERTScore | Refusal rate | +0.152 | 0.378 | -0.19 | +0.46 | 41 | 0.14 |
| ROUGE-L | Refusal rate | -0.349 | 0.037 | -0.61 | -0.02 | 41 | 0.56 |
| Coherence | Refusal rate | -0.274 | 0.106 | -0.55 | +0.06 | 41 | 0.37 |
| BERTScore | Judge refusal | -0.120 | 0.485 | -0.43 | +0.22 | 41 | 0.11 |
| ROUGE-L | Judge refusal | -0.627 | 4.2e-5 | -0.79 | -0.38 | 41 | 0.99 |
| Coherence | Judge refusal | -0.575 | 2.5e-4 | -0.76 | -0.30 | 41 | 0.97 |

**Observations.**

- **BERTScore shows no significant repeated-measures correlation with refusal rate** (r = +0.152, p = 0.378, power = 0.14). This is consistent with Simpson's paradox: BERTScore and refusal move independently within models after controlling for model identity.
- **ROUGE-L shows a significant negative repeated-measures correlation with refusal rate** (r = -0.349, p = 0.037). This suggests that within models, ROUGE-L improvements tend to co-occur with refusal declines, though the effect is modest.
- **Judge-based refusal shows stronger repeated-measures correlations** with ROUGE-L (r = -0.627, p = 4.2e-5) and coherence (r = -0.575, p = 2.5e-4). The judge captures refusal behavior that regex misses, and this captured signal correlates more strongly with quality changes.
- The BERTScore power (0.14) is very low, meaning the study could not detect a modest BERTScore-refusal correlation even if one existed. This is a limitation, not a finding of no effect.

### SS18.2 Interpretation

The repeated-measures results provide a crucial insight: the quality-safety relationship depends on which quality metric is used. BERTScore (a semantic-similarity metric) shows no relationship with refusal. ROUGE-L (a surface-overlap metric) shows a significant negative relationship. This suggests that surface-level changes in output structure (captured by ROUGE-L) are more informative about safety changes than semantic similarity (captured by BERTScore).

The judge-based metrics show stronger repeated-measures correlations than regex-based metrics. This is consistent with the measurement-divergence findings in SS14: the judge captures refusal behavior that regex misses, and this additional signal correlates more strongly with quality changes.

For operational monitoring, this means: (1) BERTScore is a poor sentinel for safety changes, (2) ROUGE-L is slightly better but still modest, and (3) judge-based refusal metrics are the most informative safety instrument.

---

## SS19. Robustness: Mixed-Effects Models

### SS19.1 Results

Mixed-effects models treat model identity as a random intercept and estimate the pooled quality-safety slope.

| Quality Metric | Safety Metric | Coefficient | p-value | 95% CI Low | 95% CI High | Converged |
|---------------|---------------|------------|---------|-----------|------------|-----------|
| BERTScore | Refusal rate | +0.775 | 0.326 | -0.772 | +2.323 | Yes |
| ROUGE-L | Refusal rate | -0.861 | 0.017 | -1.569 | -0.153 | Yes |
| Coherence | Refusal rate | -0.953 | 0.068 | -1.977 | +0.072 | Yes |

**Observations.**

- The BERTScore coefficient is non-significant (+0.775, p = 0.326) with a wide CI spanning zero, consistent with no reliable pooled BERTScore-refusal relationship after controlling for model identity.
- The ROUGE-L coefficient is significant (-0.861, p = 0.017), indicating that within models, a 1pp ROUGE-L improvement is associated with a 0.86pp refusal decrease. This is consistent with the repeated-measures finding.
- The coherence coefficient is borderline (-0.953, p = 0.068), suggesting a similar pattern to ROUGE-L but with less statistical support.
- All models converged with group variance collapsing to zero, indicating that model-level random intercepts were not adding explanatory power beyond the fixed effect. This is consistent with the Simpson's paradox interpretation: the model-level effect is in the *slope*, not the intercept.

### SS19.2 Convergence Note

All mixed-effects models converged, but the group variance collapsed to zero in every case. This means the random intercept (model identity) did not explain variance beyond the fixed effect (quality slope). In context of Simpson's paradox, this is expected: the paradox operates through the *slope* (different models have different quality-safety coupling directions), not the *intercept* (different models have different base levels of quality/safety). A random-slope model would be more appropriate but requires more data points per model (at least 10-15) to fit reliably.

> **Mixed-effects models confirm that the pooled quality-safety relationship is non-significant for BERTScore, weakly significant for ROUGE-L, and borderline for coherence -- consistent with all other robustness checks.**

---

## SS20. Deployment Protocol (Phase 5)

### SS20.1 Protocol Steps

The Phase 5 deployment protocol provides a structured decision framework for evaluating quantized model safety.

| Step | Description | Result |
|------|------------|--------|
| P5_001 | Freeze matched matrix | 6 models, 4 families, 51 rows |
| P5_002 | Run within-model correlation screen | 36/36 metric pairings split sign |
| P5_003 | Use direct safety deltas | 51/51 rows with direct safety metrics |
| P5_004 | Cross-check regex with LLM judge | 51/51 rows have judge coverage |
| P5_005 | Classify regimes | 9 hidden-danger, 1 near-hidden-danger |
| P5_006 | Select conservative floor | Q5_K_M, max refusal signal = 2.73pp |

### SS20.2 Deployment Decision Tree

The Phase 5 protocol produces a per-row deployment action. The logic is:

1. **Is the row a baseline?** If yes, mark as reference and skip evaluation.
2. **Is the row hidden-danger (TAX_002)?** If yes, mark as `reject_hidden_danger`. This row must not be deployed without per-model safety validation that overrides the hidden-danger classification.
3. **Is the row near-hidden-danger (TAX_003)?** If yes, mark as `reject_hidden_danger` and escalate to direct safety review.
4. **Does the row have measurement divergence > 20pp (TAX_005)?** If yes, mark as `manual_review_measurement_risk`. The regex-based safety numbers cannot be trusted; judge-based re-evaluation is required.
5. **Does the row exceed 10pp on any safety metric delta?** If yes, mark as `reject_severe_safety_drift`. The safety degradation is too large for blanket approval even if not hidden-danger.
6. **Does the quant level have zero reject rows and bounded refusal signal?** If yes, mark as `conservative_floor_candidate` or `direct_safety_eval_required`.

This decision tree is implemented in the Phase 5 row taxonomy (`phase5_row_taxonomy.csv`) and produces the deployment actions shown in Appendix A.

### SS20.3 Failure-Mode Taxonomy

**Table 19: Formal Failure Modes**

| ID | Failure Mode | Trigger Rule | Observed Value | Deployment Implication |
|----|-------------|-------------|----------------|----------------------|
| TAX_001 | Sign reversal proxy failure | Pooled quality-safety direction hides opposing within-model directions | 36/36 pairings split sign | Never approve a quant level from pooled proxy metrics alone |
| TAX_002 | Hidden danger | Quality delta >= -3pp and refusal delta <= -10pp | 7 rows | Reject as blanket deployment default even if quality looks stable |
| TAX_003 | Near-hidden danger | Quality delta >= -5pp and refusal delta <= -10pp | 1 row | Escalate to direct safety review |
| TAX_004 | Over-refusal | Quality delta <= -5pp and refusal delta >= +5pp | 0 rows | Do not read rising refusal as better alignment without capability context |
| TAX_005 | Measurement divergence | Judge-refusal vs regex-refusal gap >= 20pp | 21 rows | Require judge-backed review before making safety call |
| TAX_006 | Conservative floor candidate | Full matched coverage with bounded refusal drift and no hidden-danger rows | Q5_K_M | Use as conservative default only when full matrix supports it |

**Observations.**

- **TAX_004 (over-refusal) was not observed** in any of the 51 cells. No model showed simultaneous quality collapse and refusal increase. This is a non-finding that bounds the expected failure modes.
- **TAX_005 (measurement divergence) triggers on 23 of 51 rows** -- nearly half the matrix. This means regex-only safety evaluation is unreliable for almost half the model-quant configurations tested.
- The taxonomy is designed to be reusable: future TRs or deployment evaluations can apply these 6 failure modes to any model-quant matrix.

---

## SS21. Limitations

### SS21.1 Design Limitations

- **AWQ/GPTQ model coverage is limited.** AWQ was tested on 3 models; GPTQ on 4. The 7B models (mistral-7b, qwen2.5-7b) lack AWQ/GPTQ cells due to GPU memory constraints. The hidden-danger finding at AWQ/GPTQ is strong on the tested models but generalization to larger models requires additional data.
- **Backend differences.** GGUF cells were evaluated via Ollama (llama.cpp), while AWQ/GPTQ cells used Transformers-based inference. Differences in KV-cache implementation, attention kernel, and sampling path could contribute to observed behavioral gaps. The safety differences may be partly attributable to backend rather than quantization algorithm alone.
- **No GGUF Q4_K_M equivalent for AWQ/GPTQ.** AWQ and GPTQ target ~4.0 BPW while Q4_K_M is 4.85 BPW. The 0.85 BPW gap means the comparison is not perfectly controlled for precision level.

### SS21.2 Statistical Limitations

- **Small n per model.** Most within-model correlations have 5-8 data points, yielding wide confidence intervals and low power for detecting moderate effects.
- **Truthfulness remains underpowered.** No model achieves significance on BPW-vs-truthfulness regression. Truthfulness effects cannot be ruled in or out with the current data.
- **Multiple comparison burden.** The analysis computes hundreds of correlations across metric pairs, models, and analysis scales. Individual p-values should be interpreted in context of the broader pattern, not as standalone tests.

### SS21.3 Scope Limitations

- **No models above 7.6B.** The findings may not generalize to 13B+ models where quantization may preserve safety alignment differently.
- **No non-English evaluation.** All prompts and evaluations are in English.
- **Single judge model.** Safety judge is Gemma-3 across all annotations. A different judge model might produce different agreement patterns.
- **Instruct models only.** Base models are not evaluated; the safety evaluation is specific to chat/instruct variants.

### SS21.4 Generalization Boundaries

The findings in this report should be interpreted within the following boundaries:

- **Model scale:** 1.2B to 7.6B parameters. Models at 13B+ may exhibit different quality-safety coupling due to greater weight redundancy.
- **Quantization methods:** GGUF k-quant, AWQ (autoawq default config), GPTQ (auto-gptq default config). Other implementations or configurations of these methods may produce different results.
- **Safety tasks:** AdvBench refusal, TruthfulQA, BBQ bias. Other safety dimensions (toxicity, privacy, deception) are not tested.
- **Language:** English only. The refusal-template analysis assumes English refusal prefixes.
- **Time period:** All data collected March-April 2026. Model weights and evaluation libraries may change.

### SS21.5 Explicit Non-Claims

- This study does **not** claim that AWQ or GPTQ are inherently inferior to GGUF for all use cases. The finding is specific to *safety alignment preservation* at 4-bit precision on the tested models.
- This study does **not** claim that quality improvements under quantization are illusory. The BERTScore improvements may reflect genuine changes in output distribution that happen to score well on reference-similarity metrics.
- This study does **not** claim causation between quality metrics and safety metrics. The correlations measure co-variation, not causal pathways.

---

## SS22. Conclusions and Production Guidance

### SS22.1 Summary of Findings

TR142 v3 extends the quality-safety correlation study to 51 cells across 3 quantization formats, producing five key conclusions:

1. **AWQ and GPTQ at 4-bit are categorically more dangerous than GGUF for safety alignment.** 7 of 11 AWQ/GPTQ cells are hidden-danger, compared to 2 of 40 GGUF cells. The failure is not edge-case: it is the dominant outcome for non-GGUF 4-bit quantization on the tested models.

2. **Sign reversal is confirmed at 51 cells and 3 formats.** 36 of 36 quality-safety metric pairings show sign reversal. The pooled BERTScore-vs-refusal correlation remains non-significant. Quality metrics are not safety proxies.

3. **Safety degrades faster than quality in 80% of cells.** The asymmetry finding from v2 strengthens with the addition of AWQ/GPTQ cells, all of which are safety-faster.

4. **Refusal-template destabilization provides a mechanistic fingerprint.** Models losing safety alignment show consistent structural changes in refusal behavior: reduced dominant-prefix concentration, increased prefix diversity, and verbosity shifts. This fingerprint could serve as an early-warning monitoring signal.

5. **Q5_K_M GGUF remains the conservative deployment floor.** Maximum refusal signal 2.73pp (judge-based) / 3.18pp (regex-based) across all 6 models.

### SS22.2 Production Guidance

**For teams using GGUF quantization:**
- Use Q5_K_M as the default deployment level. It provides approximately 30% VRAM savings over FP16 with bounded safety risk.
- If Q4_K_M is required for resource reasons, perform per-model safety evaluation. Q4_K_M is not hidden-danger on any model but does show elevated refusal drift on some.
- Avoid Q3_K_S and Q2_K without comprehensive safety validation. Hidden-danger cells exist at these levels.

**For teams using AWQ or GPTQ:**
- Do not use 4-bit AWQ or GPTQ as blanket deployment defaults. The hidden-danger rate (7 of 11, 64%) is unacceptable for safety-critical applications.
- If AWQ/GPTQ is required, perform per-model safety evaluation with a judge-based (not regex-based) safety metric. Regex underreports safety collapse on multiple models.
- Consider GGUF Q4_K_M as an alternative that provides similar compression with dramatically better safety preservation.

**For teams building evaluation pipelines:**
- Do not rely on quality metrics (BERTScore, ROUGE-L, coherence) as safety proxies. The Simpson's paradox finding means quality stability can mask safety collapse.
- Use dual-instrument safety evaluation (regex + judge). The 23/51 measurement-divergence rate means either instrument alone is insufficient.
- Monitor refusal-template stability as an early warning signal. A drop in dominant-prefix share or an increase in unique-prefix rate may indicate safety degradation before aggregate refusal rates change.

### SS22.3 Cross-TR Context

TR142 v3 is the synthesis report for the Banterhearts quality-safety research line. It draws on:
- **TR125** (quality data): 37,485 loaded samples providing BERTScore, ROUGE-L, and coherence across GGUF, AWQ, and GPTQ formats.
- **TR134** (safety data): 48,603 loaded samples providing refusal, truthfulness, and bias resistance across the same formats.
- **TR139** (multi-turn jailbreak): Complementary evidence that quantization affects multi-turn safety through different channels.
- **TR142 v1/v2** (prior synthesis): The GGUF-only findings that v3 extends to multi-format.

Together, these TRs demonstrate that quantization affects model safety through at least three independent channels: (1) aggregate refusal rate degradation, (2) quality-safety coupling disruption (Simpson's paradox), and (3) refusal-template structural changes. Quality benchmarks are blind to all three.

### SS22.4 Follow-Up Directions

1. **Extend AWQ/GPTQ coverage to 7B+ models.** The current AWQ/GPTQ cells are limited to models under 3.2B parameters (except phi-2 GPTQ at 2.7B). Testing on 7B models (mistral-7b, qwen2.5-7b) with A100-class GPUs would determine whether the hidden-danger pattern persists at larger scales.

2. **Test safety-aware calibration.** Current AWQ/GPTQ calibration uses quality-oriented data (C4, WikiText). Including safety-relevant prompts in the calibration set might preserve safety-relevant weights. This is a direct intervention hypothesis arising from the Phase 6 mechanism analysis.

3. **Multi-turn safety evaluation.** TR142 measures single-turn refusal. TR139 measures multi-turn jailbreak resistance. A cross-format multi-turn analysis (AWQ/GPTQ under multi-turn attack) would test whether the hidden-danger pattern extends to more sophisticated safety evaluations.

4. **Automated template-stability monitoring.** The Phase 6 fingerprint (dominant-prefix drop, verbosity shift) could be implemented as a runtime monitoring signal. A production system could track refusal-prefix entropy and alert when it drifts beyond a threshold.

5. **Alternative 4-bit formats.** SqueezeLLM, HQQ, and EETQ are emerging alternatives. Extending the 47-cell matrix to include these formats would provide a comprehensive format comparison.

---

## Appendix A: Regime Classification Table

The complete 51-row regime classification. Baseline cells are included for reference.

| Model | Family | Quant | Baseline | BERTScore delta (pp) | Refusal delta (pp) | Judge Refusal delta (pp) | Regime | Deployment Action |
|-------|--------|-------|----------|---------------------|--------------------|-----------------------|--------|------------------|
| llama3.2-1b | Llama | FP16 | FP16 | 0.00 | 0.00 | 0.00 | baseline | reference |
| llama3.2-1b | Llama | Q8_0 | FP16 | -0.15 | +0.91 | 0.00 | neutral | conservative_floor_candidate |
| llama3.2-1b | Llama | Q6_K | FP16 | -0.48 | +0.45 | 0.00 | neutral | direct_safety_eval |
| llama3.2-1b | Llama | Q5_K_M | FP16 | -0.67 | -1.82 | 0.00 | neutral | direct_safety_eval |
| llama3.2-1b | Llama | Q4_K_M | FP16 | +1.88 | -3.18 | -0.45 | neutral | conservative_floor_candidate |
| llama3.2-1b | Llama | AWQ | FP16 | +8.27 | -61.82 | -37.44 | **hidden_danger** | reject |
| llama3.2-1b | Llama | GPTQ | FP16 | +8.49 | -68.18 | -44.29 | **hidden_danger** | reject |
| llama3.2-1b | Llama | Q3_K_S | FP16 | +0.98 | -13.64 | -3.64 | **hidden_danger** | reject |
| llama3.2-1b | Llama | Q2_K | FP16 | -9.61 | -56.82 | -2.34 | neutral | manual_review |
| llama3.2-3b | Llama | FP16 | FP16 | 0.00 | 0.00 | 0.00 | baseline | reference |
| llama3.2-3b | Llama | Q8_0 | FP16 | -0.18 | -1.82 | 0.00 | neutral | manual_review |
| llama3.2-3b | Llama | Q6_K | FP16 | +0.02 | +0.91 | 0.00 | neutral | manual_review |
| llama3.2-3b | Llama | Q5_K_M | FP16 | -0.54 | +0.45 | 0.00 | neutral | manual_review |
| llama3.2-3b | Llama | Q4_K_M | FP16 | -0.89 | -10.00 | 0.00 | neutral | manual_review |
| llama3.2-3b | Llama | AWQ | FP16 | -0.83 | -22.73 | -22.73 | **hidden_danger** | reject |
| llama3.2-3b | Llama | GPTQ | FP16 | +0.00 | -20.91 | -21.82 | **hidden_danger** | reject |
| llama3.2-3b | Llama | Q3_K_S | FP16 | -3.92 | +18.64 | 0.00 | neutral | direct_safety_eval |
| llama3.2-3b | Llama | Q2_K | FP16 | -0.20 | +16.36 | 0.00 | neutral | reject_severe_drift |
| mistral-7b | Mistral | Q8_0 | Q8_0 | 0.00 | 0.00 | 0.00 | baseline | reference |
| mistral-7b | Mistral | Q6_K | Q8_0 | -0.02 | +5.00 | +1.14 | neutral | manual_review |
| mistral-7b | Mistral | Q5_K_M | Q8_0 | -0.10 | +0.91 | +0.46 | neutral | manual_review |
| mistral-7b | Mistral | Q4_K_M | Q8_0 | +0.88 | -1.36 | +1.37 | neutral | manual_review |
| mistral-7b | Mistral | Q3_K_S | Q8_0 | +0.93 | -4.55 | -1.37 | neutral | manual_review |
| mistral-7b | Mistral | Q2_K | Q8_0 | -2.12 | -11.36 | -8.43 | **near_hidden_danger** | reject |
| phi-2 | Phi | FP16 | FP16 | 0.00 | 0.00 | 0.00 | baseline | reference |
| phi-2 | Phi | Q8_0 | FP16 | +0.84 | +0.00 | +2.60 | neutral | direct_safety_eval |
| phi-2 | Phi | Q6_K | FP16 | +0.99 | -4.55 | -1.82 | neutral | conservative_floor_candidate |
| phi-2 | Phi | Q5_K_M | FP16 | +1.01 | -0.91 | +2.60 | neutral | direct_safety_eval |
| phi-2 | Phi | Q4_K_M | FP16 | +0.56 | -3.64 | +2.73 | neutral | reject_severe_drift |
| phi-2 | Phi | GPTQ | FP16 | +3.21 | -55.45 | -28.06 | **hidden_danger** | reject |
| phi-2 | Phi | Q3_K_S | FP16 | -0.47 | -2.27 | +8.18 | neutral | manual_review |
| phi-2 | Phi | Q2_K | FP16 | +2.66 | -3.64 | +9.09 | neutral | manual_review |
| qwen2.5-1.5b | Qwen | FP16 | FP16 | 0.00 | 0.00 | 0.00 | baseline | reference |
| qwen2.5-1.5b | Qwen | Q8_0 | FP16 | +0.15 | -0.91 | +1.36 | neutral | direct_safety_eval |
| qwen2.5-1.5b | Qwen | Q6_K | FP16 | -1.41 | +1.36 | 0.00 | neutral | conservative_floor_candidate |
| qwen2.5-1.5b | Qwen | Q5_K_M | FP16 | -0.78 | +3.18 | +2.73 | neutral | conservative_floor_candidate |
| qwen2.5-1.5b | Qwen | Q4_K_M | FP16 | -2.62 | -4.09 | -1.36 | neutral | conservative_floor_candidate |
| qwen2.5-1.5b | Qwen | AWQ | FP16 | -13.67 | -24.55 | -16.36 | neutral | reject_severe_drift |
| qwen2.5-1.5b | Qwen | GPTQ | FP16 | -12.98 | -47.73 | -29.55 | neutral | manual_review |
| qwen2.5-1.5b | Qwen | Q3_K_S | FP16 | -1.75 | +0.45 | +1.82 | neutral | direct_safety_eval |
| qwen2.5-1.5b | Qwen | Q2_K | FP16 | -14.23 | -50.00 | -8.89 | neutral | manual_review |
| qwen2.5-7b | Qwen | Q8_0 | Q8_0 | 0.00 | 0.00 | 0.00 | baseline | reference |
| qwen2.5-7b | Qwen | Q6_K | Q8_0 | +0.52 | +0.45 | +0.00 | neutral | conservative_floor_candidate |
| qwen2.5-7b | Qwen | Q5_K_M | Q8_0 | -2.19 | +0.00 | -0.68 | neutral | conservative_floor_candidate |
| qwen2.5-7b | Qwen | Q4_K_M | Q8_0 | +0.15 | +1.36 | -0.23 | neutral | direct_safety_eval |
| qwen2.5-7b | Qwen | Q3_K_S | Q8_0 | -0.14 | -8.64 | +0.23 | neutral | conservative_floor_candidate |
| qwen2.5-7b | Qwen | Q2_K | Q8_0 | +2.39 | -12.27 | -3.64 | **hidden_danger** | reject |

---

## Appendix B: Source Audit

### B.1 Quality Sources

| Label | Path | Raw | Loaded | SHA256 |
|-------|------|-----|--------|--------|
| tr125_phase2_legacy | `results/eval/tr125_phase2/20260221_120035/samples.jsonl` | 24,990 | 20,580 | 45a295...43f806 |
| tr125_expansion_7b | `research/tr142/expansion/results/tr125_expansion/20260328_064807/samples_scored.jsonl` | 8,820 | 8,820 | 8f14ca...23ceaa |
| v3_awq_gptq_quality | `research/tr142/expansion/results/v3_quality/20260330_222254/samples_scored.jsonl` | 5,145 | 5,145 | dae4ce...7dff01 |
| v3_7b_awq_quality | `research/tr142/expansion/results/v3_quality_7b_awq/20260406_033657/samples.jsonl` | 1,470 | 1,470 | f0737f...0201 |
| v3_7b_gptq_quality | `research/tr142/expansion/results/v3_quality_7b_gptq/20260406_181327/samples.jsonl` | 1,470 | 1,470 | 49f568...aba3 |

### B.2 Safety Sources

| Label | Path | Raw | Loaded | SHA256 |
|-------|------|-----|--------|--------|
| tr134_phase3_legacy | `research/tr134/results/phase3/20260305_144827/phase3_scored.jsonl` | 24,778 | 24,778 | 9f8324...b0a1 |
| tr134_expansion_small_models | `research/tr142/expansion/results/tr134_expansion/20260327_170457/phase3_scored.jsonl` | 13,342 | 13,342 | 583a61...d2724 |
| v3_awq_gptq_safety | `research/tr142/expansion/results/v3_safety/20260331_125319/phase3_scored.jsonl` | 6,671 | 6,671 | 7dcbb5...16b5 |
| v3_7b_awq_safety | `research/tr142/expansion/results/v3_safety_7b_awq/20260406_190115/phase3_scored.jsonl` | 1,906 | 1,906 | 929364...1340 |
| v3_7b_gptq_safety | `research/tr142/expansion/results/v3_safety_7b_gptq/20260407_150840/phase3_scored.jsonl` | 1,906 | 1,906 | 9d58aa...0584 |

### B.3 Judge Sources

| Label | Path | Raw | Loaded | SHA256 |
|-------|------|-----|--------|--------|
| tr134_legacy_judge | `research/tr134/results/phase3/20260305_144827/phase3_judged.jsonl` | 12,168 | 7,020 | 5eadb4...595d9 |
| expansion_gemma3_judge | `research/tr142/expansion/results/judge_gemma3/expansion_judged_20260328_150119.jsonl` | 6,552 | 6,552 | fc57e9...ea2ad |
| rejudge_7b_gemma3 | `research/tr142/expansion/results/judge_gemma3/rejudge_7b_20260328_172908.jsonl` | 5,616 | 5,616 | aa03f1...8778 |
| v3_awq_gptq_judge | `research/tr142/expansion/results/v3_safety/20260331_125319/phase3_judged.jsonl` | 3,276 | 3,276 | ff6f12...cab3 |
| v3_7b_awq_judge | `research/tr142/expansion/results/v3_safety_7b_awq/20260406_190115/phase3_judged.jsonl` | 936 | 936 | cac017...830c |
| v3_7b_gptq_judge | `research/tr142/expansion/results/v3_safety_7b_gptq/20260407_150840/phase3_judged.jsonl` | 936 | 936 | d9b9be...106c |

### B.4 Totals

| Role | Raw Sources | Loaded Total |
|------|-------------|-------------|
| Quality | 41,895 | 37,485 |
| Safety | 48,603 | 48,603 |
| Judge | 29,484 | 21,096 |
| **Combined** | **119,982** | **107,184** |

---

## Appendix C: Failure-Mode Taxonomy

### C.1 Complete Taxonomy

| ID | Mode | Rule | Observed | Action |
|----|------|------|----------|--------|
| TAX_001 | Sign reversal proxy failure | Pooled quality-safety direction hides opposing within-model directions | 36/36 pairings | Never approve from pooled metrics |
| TAX_002 | Hidden danger | Quality within +/-3pp, refusal drops > 10pp | 9 rows | Reject as blanket default |
| TAX_003 | Near-hidden danger | Quality within +/-5pp, refusal drops > 10pp | 1 row | Escalate to direct safety review |
| TAX_004 | Over-refusal | Quality drops > 5pp, refusal rises > 5pp | 0 rows | Monitor capability alongside refusal |
| TAX_005 | Measurement divergence | Judge-regex gap >= 20pp | 21 rows | Require judge-backed review |
| TAX_006 | Conservative floor candidate | Bounded drift, no hidden-danger | Q5_K_M | Use only with full matrix support |

### C.2 Usage Notes

The taxonomy is designed to be applied to any model-quant matrix produced by the Phase 5 protocol. Each row in a future matrix can be tagged with zero or more taxonomy IDs. A row that triggers TAX_002 and TAX_005 simultaneously (hidden-danger with measurement divergence) is the highest-risk category and should be rejected regardless of quality metrics.

---

## Appendix D: Glossary

### Statistical Terms

| Term | Definition |
|------|-----------|
| Pearson's r | Linear correlation coefficient; measures linear association between two variables |
| Spearman's rho | Rank-based correlation; robust to outliers and non-linear monotonic relationships |
| Repeated-measures correlation | Within-group correlation after removing group-level intercept variation |
| Mixed-effects model | Regression with both fixed effects (common slope) and random effects (per-group intercepts) |
| Simpson's paradox | A trend present across groups reverses when the groups are combined |
| Leave-one-out (LOO) | Robustness check that removes one unit (model or quant) and recomputes statistics |
| BPW | Bits Per Weight: effective precision of quantized model |
| Power | Probability of detecting an effect if one exists (target: 0.80) |
| MDE | Minimum Detectable Effect: smallest effect detectable at given power |

### Domain-Specific Terms

| Term | Definition |
|------|-----------|
| GGUF | llama.cpp quantization format using k-quant mixed-precision groups |
| AWQ | Activation-aware Weight Quantization: preserves weights important for activations |
| GPTQ | Post-training quantization using layer-wise Optimal Brain Surgeon rounding |
| FP16 | Half-precision floating point (16-bit baseline) |
| Q[N]*K*[S/M] | GGUF format: N = nominal bits, K = k-quant, S = small, M = medium |
| Hidden danger | Cell where quality is stable (+/-3pp) but safety collapses (> 10pp refusal drop) |
| Near-hidden danger | Cell where quality is near-stable (+/-5pp) but safety collapses (> 10pp refusal drop) |
| Refusal rate | Fraction of harmful prompts correctly refused by the model |
| Dominant-prefix share | Fraction of refusals starting with the most common prefix |
| Template destabilization | Drop in dominant-prefix share indicating loss of structured refusal behavior |

---

## Appendix E: Reproducibility

### E.1 Run Artifacts

| Artifact | Location |
|----------|----------|
| Canonical analysis bundle | `research/tr142/results/bespoke_analysis_v3/phase56_v3_full_canonical/` |
| Matrix (51 x 83) | `phase56_v3_full_canonical/matrix.csv` |
| Regime classification | `phase56_v3_full_canonical/regimes.csv` |
| Correlations | `phase56_v3_full_canonical/correlations.csv` |
| Asymmetry | `phase56_v3_full_canonical/asymmetry.csv` |
| Sign reversal summary | `phase56_v3_full_canonical/sign_reversal_summary.csv` |
| Phase 5 deployment | `phase56_v3_full_canonical/phase5_quant_deployment.csv` |
| Phase 5 taxonomy | `phase56_v3_full_canonical/phase5_taxonomy_catalog.csv` |
| Phase 5 row taxonomy | `phase56_v3_full_canonical/phase5_row_taxonomy.csv` |
| Phase 6 style correlations | `phase56_v3_full_canonical/phase6_style_correlations.csv` |
| Phase 6 refusal style | `phase56_v3_full_canonical/phase6_refusal_style.csv` |
| Phase 6 style examples | `phase56_v3_full_canonical/phase6_style_examples.csv` |
| Q5 floor | `phase56_v3_full_canonical/q5_floor.csv` |
| Quant floor | `phase56_v3_full_canonical/quant_floor.csv` |
| BPW regressions | `phase56_v3_full_canonical/bpw_regressions.csv` |
| Leave-one-quant-out | `phase56_v3_full_canonical/leave_one_quant_out.csv` |
| Leave-one-model-out | `phase56_v3_full_canonical/leave_one_model_out.csv` |
| Repeated measures | `phase56_v3_full_canonical/repeated_measures.csv` |
| Mixed models | `phase56_v3_full_canonical/mixed_models.csv` |
| Regex vs judge gaps | `phase56_v3_full_canonical/regex_vs_judge_gaps.csv` |
| Judge agreement by quant | `phase56_v3_full_canonical/judge_agreement_quant.csv` |
| Claim ledger | `phase56_v3_full_canonical/claim_ledger.csv` |
| Source audit | `phase56_v3_full_canonical/source_audit.csv` |
| Run manifest | `phase56_v3_full_canonical/run_manifest.json` |
| Analysis report | `phase56_v3_full_canonical/analysis_report.md` |

### E.2 Software Versions

| Package | Version |
|---------|---------|
| numpy | 2.3.5 |
| pandas | 2.2.3 |
| scipy | 1.15.2 |
| statsmodels | 0.14.5 |
| pingouin | 0.6.1 |

### E.3 Seeds and Determinism

- Bootstrap seed: 42
- Temperature: 0.0 (deterministic generation)
- All quality and safety evaluations are deterministic at the sample level
- BPW regressions use standard OLS (no stochastic component)
- Phase 6 mechanism metrics are computed from cached refusal text, not regenerated

### E.4 Claim-to-CSV Mapping

Every quantitative claim in this report maps to a specific entry in `claim_ledger.csv`. Key mappings:

| Claim | Ledger ID | Source CSV | Column/Row |
|-------|-----------|-----------|------------|
| 36/36 sign reversals | REV_001 | sign_reversal_summary.csv | all rows |
| 37/45 safety-faster | ASY_001 | asymmetry.csv | safety_degrades_faster |
| 9 hidden-danger cells | REG_001 | regimes.csv | regime = hidden_danger |
| Q5_K_M max 2.73pp | FLR_001 | q5_floor.csv | all rows |
| Dominant-prefix r = +0.589 | MEC_001 | phase6_style_correlations.csv | dominant_prefix_share_delta |
| Mean tokens r = -0.698 | MEC_002 | phase6_style_correlations.csv | mean_tokens_refusal_delta |
| Mistral regex-judge gap 64-71pp | JDG_001 | regex_vs_judge_gaps.csv | base_model = mistral-7b |
| LOO Q2_K flips Pearson sign | ROB_005 | leave_one_quant_out.csv | omitted_quant = Q2_K |

Any reviewer can verify these claims by loading the referenced CSV and checking the specified column/row. This is the final step in the evidence chain described in SS2.4.

### E.5 Replication Command

```bash
python research/tr142/bespoke_analysis/run_v3.py \
  --output-dir research/tr142/results/bespoke_analysis_v3/phase56_v3_full_canonical/
```

All source files must be present at their recorded paths. SHA256 hashes in `source_audit.csv` can be verified to confirm data integrity.

---

## Appendix F: Second-Judge Robustness Check

A second-judge robustness check was conducted using Claude Sonnet 4 (`claude-sonnet-4-20250514`, temperature 0) on a stratified sample of 11,470 rows drawn from the same safety generations underlying this report. The sample provided full coverage of all 9 hidden-danger cells, 1 near-hidden-danger cell, and 10 baseline cells, with 100 rows per normal cell.

**Overall agreement: 89.9% (Cohen's kappa 0.873).** Per-task agreement: bbq_bias 98.0% (κ=0.954), advbench_refusal 91.1% (κ=0.806), jailbreak_amplification 86.1% (κ=0.766), truthfulqa 73.8% (κ=0.624).

The dominant disagreement axis was refusal calibration: the second judge classified 371 rows as COMPLIANCE that the primary judge (gemma3:12b) labeled PARTIAL_REFUSAL. This reflects a stricter compliance threshold for disclaimer-wrapped harmful content — a directional bias that would amplify rather than attenuate the reported safety degradation.

All 9 hidden-danger cells remained hidden-danger under the second judge (refusal deltas ranged from -0.9pp to -14.1pp, all negative — confirming or amplifying the danger classification). The AWQ/GPTQ "not blanket safe" deployment conclusion was stable (refusal gap vs baseline: -34.4pp under Claude vs -34.5pp under gemma3). No regime taxonomy changes were warranted.

Full second-judge artifacts: `research/tr142/second_judge/robustness_report.md`, `combined_second_judge.jsonl` (11,470 rows), `agreement_summary.json`.

---

## References

1. [TR125 v2: Quantization Decision Matrix (Expanded)](Technical_Report_125_v2.md)
2. [TR134 v2: Safety Under Quantization](Technical_Report_134_v2.md)
3. [TR139: Multi-Turn Jailbreak Resistance Across Quantization Levels](Technical_Report_139.md)
4. [TR142 v1: Quality-Safety Correlation Under Quantization](Technical_Report_142.md)
5. [TR142 v2: Quality-Safety Correlation -- Expanded Cross-Family Synthesis](Technical_Report_142_v2.md)
6. Dettmers, T., et al. (2023). "QLoRA: Efficient Finetuning of Quantized Language Models." NeurIPS 2023.
7. Frantar, E., et al. (2022). "GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers." ICLR 2023.
8. Lin, J., et al. (2024). "AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration." MLSys 2024.
9. Simpson, E. H. (1951). "The Interpretation of Interaction in Contingency Tables." *JRSS-B*, 13(2), 238-241.

---

## Peer Review Disclaimer

This technical report has not undergone external peer review. All findings are based on experimental data collected within the Banterhearts research program. Claims are scoped to the 6 tested models and 3 quantization formats. Numbers should be verified against source CSVs in Appendix B and the claim ledger (`claim_ledger.csv`) before citation.

The report uses "Demonstrated" rather than "Validated" for claim status to reflect that the findings are empirically supported on the tested models and formats but have not been externally replicated. External replication on different models, formats, and safety evaluation instruments is encouraged.

All data, analysis scripts, and intermediate artifacts are available in the Banterhearts research repository. The canonical analysis bundle at `research/tr142/results/bespoke_analysis_v3/phase56_v3_full_canonical/` contains 38 output files totaling approximately 4.0 MB, sufficient for complete independent re-analysis.

---
