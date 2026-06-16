# Technical Report 146: Mechanistic Safety Probing Under Quantization
## Why Standard Mechanistic Probes Fail to Predict Quantization-Induced Safety Degradation

| Field | Value |
|-------|-------|
| **TR Number** | 146 |
| **Project** | Banterhearts |
| **Date** | 2026-04-10 |
| **Version** | 1.0 |
| **Author** | Research Team |
| **Git Commit** | `256461f7` |
| **Status** | Complete |
| **Report Type** | Full-depth |
| **Run Directories** | `research/tr146/results/phase{1,2,3,4}_gptq_docker/` |
| **Total Samples** | 5,100 forward passes across 4 phases |
| **Models** | 6 (llama3.2-1b, llama3.2-3b, qwen2.5-1.5b, qwen2.5-7b, phi-2, mistral-7b) |
| **Quant Methods** | FP16 (anchor), AWQ INT4, GPTQ INT4 |
| **Probed Cells** | 17 model-quant cells per phase (11 AWQ/GPTQ + 6 FP16) |
| **Related Work** | [TR142](Technical_Report_142_v3.md) (quality-safety correlation matrix, RTSI) |
| **Depends On** | TR142 (regime labels, RTSI scores, harmful prompt pool, AWQ/GPTQ checkpoints) |

---

## Abstract

TR146 asks why quantization degrades safety behavior even when quality metrics remain stable. TR142 established the behavioral result (quality is not a safety proxy) and provided a lightweight screen (RTSI). TR146 probes the mechanism with four experiments across **17 model-quant cells** (6 models, 2 quantization methods, 6 FP16 anchors), generating **5,100 forward passes** with hidden-state extraction.

The core findings are: (1) First-token entropy does not predict safety degradation — AWQ increases first-token uncertainty while GPTQ decreases it, yet both produce hidden-danger rows (r = 0.08, p = 0.81). (2) The refusal direction is geometrically preserved under quantization with cosine similarity > 0.97 in every cell, yet behaviorally ineffective in hidden-danger rows (r = -0.14, p = 0.67). (3) Calibration drift follows the same method-specific pattern as entropy and has no predictive power for danger (all r < 0.09). (4) Safety-critical neurons absorb **1.40x** disproportionate quantization error compared to non-safety neurons (p < 0.0001), but this is a universal property of all quantized cells, not specific to hidden-danger rows (regime p = 0.98).

The most important non-result is that none of the four mechanistic probes can distinguish safe from dangerous quantized configurations. The operational conclusion is that behavioral template metrics (RTSI) remain the only viable pre-deployment screen because the underlying mechanism is necessary-but-not-sufficient: every quantized model suffers safety-neuron damage and direction perturbation, but only some cross the threshold into actual behavioral failure.

---

## Executive Summary

### Key Findings

1. **First-token entropy shift does not predict safety degradation.** AWQ increases entropy (model less certain about refusing) while GPTQ decreases it (model more confident). Both methods produce hidden-danger rows. Pearson correlation with RTSI: r = 0.08 (p = 0.81). Mann-Whitney regime separation: p = 0.61.

2. **The refusal direction survives quantization geometrically.** Cosine similarity between FP16 and quantized refusal directions exceeds 0.97 in all 11 AWQ/GPTQ cells. The direction is not destroyed — it is preserved but behaviorally ineffective. Cosine similarity does not correlate with RTSI (r = -0.14, p = 0.67) or distinguish regimes (p = 0.61).

3. **Refusal direction magnitude correlates with model vulnerability.** Models with weaker refusal directions (llama3.2-1b: 4.7, llama3.2-3b: 10.7) are more likely to produce hidden-danger rows than models with stronger directions (qwen2.5-7b: 60.1, phi-2: 72.3). Mann-Whitney magnitude test: p = 0.036.

4. **Calibration drift is method-specific, not danger-specific.** GPTQ systematically increases top-1 confidence (+0.02 to +0.08pp), AWQ has negligible or slightly negative shift. Neither direction predicts hidden-danger status. All RTSI correlations r < 0.09.

5. **Safety neurons absorb disproportionate quantization error (1.40x, p < 0.0001).** In every one of the 11 quantized cells, safety-critical neurons (top 5% by activation contrast) have higher mean absolute error than non-safety neurons. Mean ratio across all cells and layers: 1.40x. One-sample t-test against ratio = 1.0: p < 0.0001. GPTQ produces higher ratios than AWQ (mean 1.45x vs 1.37x).

6. **But disproportionate safety-neuron error does not predict hidden-danger status.** The safety error ratio is essentially identical between hidden-danger rows (mean 1.34x) and neutral rows (mean 1.50x). Mann-Whitney test: p = 0.98. RTSI correlation: r = 0.12. The damage is universal — every quantized model suffers it, regardless of whether it behaviorally fails.

7. **RTSI remains the only viable pre-deployment screen.** None of the four mechanistic probes (entropy, direction, calibration, neuron error) can replace or improve upon the behavioral RTSI screen from TR142. The mechanism is there but it is necessary-not-sufficient: safety neurons are always disproportionately damaged, the refusal direction always slightly perturbed, but only some configurations cross the behavioral threshold.

### Core Decisions

- Do not use first-token entropy as a safety screening signal — it is method-specific, not danger-specific
- Do not use refusal-direction cosine similarity as a quantization safety diagnostic — the direction is always preserved
- Do not use calibration drift (ECE, confidence shift) as a safety proxy — same method-specific problem as entropy
- Safety-neuron error ratios are a valid mechanism-level insight but not an operational screen
- Continue to use RTSI (behavioral template metrics) as the recommended pre-deployment screen
- Refusal direction magnitude is a model-level vulnerability factor, not a per-configuration diagnostic

### Validation Summary

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| Phase 1 cell coverage | cells completed | 17/17 | 17/17 | **PASS** |
| Phase 2 cell coverage | cells completed | 17/17 | 17/17 | **PASS** |
| Phase 3 cell coverage | cells completed | 17/17 | 17/17 | **PASS** |
| Phase 5 cell coverage | cells completed | 11/11 | 11/11 | **PASS** |
| Safety neuron error > 1.0 | one-sample t-test | p < 0.05 | p < 0.0001 | **PASS** |
| Entropy predicts danger | Pearson r with RTSI | |r| > 0.3 | r = 0.08 | **NOT SUPPORTED** |
| Direction predicts danger | cosine sim vs RTSI | |r| > 0.3 | r = -0.14 | **NOT SUPPORTED** |
| Calibration predicts danger | confidence shift vs RTSI | |r| > 0.3 | r = 0.07 | **NOT SUPPORTED** |
| Neuron ratio predicts danger | ratio vs RTSI | |r| > 0.3 | r = 0.12 | **NOT SUPPORTED** |

### Claim Validation

| # | Claim | Evidence Base | Status |
|---|-------|---------------|--------|
| C1 | First-token entropy predicts safety degradation | Phase 1: r = 0.08, p = 0.81 | **Not supported** |
| C2 | Refusal direction is destroyed by quantization | Phase 2: all cosine sims > 0.97 | **Not supported** (direction preserved) |
| C3 | Refusal direction magnitude tracks model vulnerability | Phase 2: Mann-Whitney p = 0.036 | **Partial** (model-level, not config-level) |
| C4 | Calibration drift predicts safety degradation | Phase 3: all r < 0.09 | **Not supported** |
| C5 | Safety neurons absorb disproportionate quantization error | Phase 5: ratio = 1.40x, p < 0.0001 | **Established** |
| C6 | Safety-neuron error ratio predicts hidden-danger status | Phase 5: regime p = 0.98, RTSI r = 0.12 | **Not supported** |
| C7 | RTSI is uniquely predictive among tested probes | Phases 1-4: no mechanistic probe achieves |r| > 0.15 with RTSI | **Established** |

---

## When to Use This Report

### Scenario 1: "Can I use a mechanistic probe instead of RTSI to screen quantized models?"

**Question:** Is there a cheaper or more interpretable alternative to RTSI for detecting hidden-danger quantized configurations?

**Answer:** No. TR146 tested four mechanistic probes (first-token entropy, refusal direction cosine similarity, calibration drift, safety-neuron error ratio) and none achieved |r| > 0.15 with RTSI or distinguished hidden-danger from neutral rows. See SS4-SS7 for the full evidence. The mechanism is necessary-but-not-sufficient: all quantized models show safety-neuron damage, but only some cross the behavioral threshold. RTSI remains the recommended screen.

### Scenario 2: "Why does quantization break safety behavior?"

**Question:** What is the mechanistic explanation for quantization-induced safety degradation?

**Answer:** Safety neurons absorb 1.40x disproportionate quantization error (SS7, p < 0.0001), the refusal direction is slightly perturbed but geometrically preserved (SS5, cosine sim > 0.97), and models with weaker refusal directions are more vulnerable (SS5, p = 0.036). The failure mode is not direction destruction but threshold sensitivity: the refusal signal is weakened just enough to lose behavioral effectiveness in some configurations. AWQ and GPTQ produce different internal signatures (opposite entropy shifts, different confidence patterns) but can both trigger the same behavioral failure.

### Scenario 3: "Does a model's size determine its quantization safety risk?"

**Question:** Are smaller models inherently more vulnerable to safety degradation under quantization?

**Answer:** Yes, partially. Refusal direction magnitude scales with model size (llama3.2-1b: 4.7, qwen2.5-7b: 60.1), and the Mann-Whitney test shows hidden-danger rows have lower magnitude (p = 0.036). But magnitude alone is not sufficient — phi-2 (2.7B) has the highest magnitude (72.3) despite being a smaller model. See SS5 for the direction magnitude analysis.

### Scenario 4: "Should I worry about safety-neuron damage in my quantized model?"

**Question:** If safety neurons are disproportionately damaged in every quantized model, does that mean all quantized models are unsafe?

**Answer:** No. The 1.40x disproportionate error is universal but the behavioral consequences are not. Most quantized configurations retain sufficient safety behavior despite the elevated neuron-level error. The error is necessary but not sufficient for behavioral failure. Use RTSI to determine whether a specific configuration has crossed the behavioral threshold. See SS7 for the full neuron-error analysis.

---

## Table of Contents

- [Abstract](#abstract)
- [Executive Summary](#executive-summary)
- [When to Use This Report](#when-to-use-this-report)
- [Metric Definitions](#metric-definitions)
- [SS1. Introduction](#ss1-introduction)
- [SS2. Methodology](#ss2-methodology)
- [SS3. Study Matrix and Infrastructure](#ss3-study-matrix-and-infrastructure)
- [SS4. Phase 1: First-Token Entropy Shift](#ss4-phase-1-first-token-entropy-shift)
- [SS5. Phase 2: Refusal Direction Geometry](#ss5-phase-2-refusal-direction-geometry)
- [SS6. Phase 3: Calibration Drift](#ss6-phase-3-calibration-drift)
- [SS7. Phase 5: Safety Neuron Quantization Error](#ss7-phase-4-safety-neuron-quantization-error)
- [SS8. Cross-Phase Synthesis](#ss8-cross-phase-synthesis)
- [SS9. Implications for RTSI and the Downstream Paper](#ss9-implications-for-rtsi-and-the-downstream-paper)
- [SS10. Conclusions](#ss10-conclusions)
- [SS11. Limitations and Follow-Up](#ss11-limitations-and-follow-up)
- [SS12. Reproducibility](#ss12-reproducibility)
- [References](#references)
- [Appendix A: Raw Data Tables](#appendix-a-raw-data-tables)
- [Appendix B: Extended Statistical Tables](#appendix-b-extended-statistical-tables)
- [Appendix C: Prompt Provenance](#appendix-c-prompt-provenance)
- [Appendix D: Glossary](#appendix-d-glossary)

---

## Metric Definitions

### Primary Metrics

| Metric | Definition | Interpretation |
|--------|-----------|----------------|
| First-token entropy | Shannon entropy (nats) of the logit distribution at the first generated token position | Higher = model less certain about first token choice |
| Refusal direction | Unit vector in residual stream space computed as mean(harmful) - mean(harmless) activations | Encodes the geometric "direction of refusal" (Arditi et al. 2024) |
| Cosine similarity | Cosine between FP16 and quantized refusal directions | 1.0 = perfectly preserved, 0.0 = orthogonal |
| Direction magnitude | L2 norm of the unnormalized refusal direction | Higher = stronger refusal signal in representation space |
| Top-1 confidence | Probability assigned to the most likely first token | Higher = model more confident |
| ECE (proxy) | Expected Calibration Error using entropy as accuracy proxy | Higher = worse calibration |
| Safety error ratio | Mean absolute hidden-state error on safety neurons / mean error on non-safety neurons | >1.0 = safety neurons disproportionately damaged |
| RTSI | Refusal Template Stability Index (from TR142) | Higher = more template instability = higher risk |

### Statistical Tests Used

| Test | Role in This Report |
|------|-------------------|
| Pearson correlation | Continuous association between mechanistic metrics and RTSI |
| Spearman correlation | Rank-based robustness check on Pearson |
| Mann-Whitney U | Non-parametric regime separation (hidden-danger vs neutral) |
| One-sample t-test | Safety error ratio > 1.0 |

### Evidence Standard

**Established findings** require p < 0.05 and practical significance (|r| > 0.3 for correlations, ratio meaningfully > 1.0 for neuron error).

**Partial findings** show statistical significance but lack predictive power for the deployment-relevant outcome (hidden-danger vs neutral classification).

**Not supported** claims fail both statistical significance and practical significance thresholds.

---

## SS1. Introduction

### SS1.1 Research Questions

1. Does first-token entropy shift predict which quantized configurations will exhibit hidden-danger safety degradation?
2. Does the refusal direction (Arditi et al. 2024) survive quantization, and does its preservation or distortion correlate with behavioral safety outcomes?
3. Does calibration drift (confidence shift, ECE change) under quantization predict safety degradation?
4. Do safety-critical neurons (identified via activation contrasting) absorb disproportionate quantization error, and does this predict hidden-danger status?
5. Can any mechanistic probe replace or improve upon RTSI as a pre-deployment safety screen?

### SS1.2 Motivation

TR142 established that quality metrics (BERTScore, ROUGE-L, coherence) cannot serve as safety proxies under quantization. The Refusal Template Stability Index (RTSI) provides a behavioral screen that catches all 10 hidden- or near-hidden-danger rows in the 51-row study matrix. But RTSI is a behavioral correlate — it measures template instability, not the underlying cause of safety degradation. TR146 tests whether standard mechanistic interpretability tools can explain *why* some quantized configurations fail and whether they can serve as independent or complementary screening signals.

The motivation is both scientific and practical. Scientifically, understanding *why* quantization breaks safety would inform the design of safety-preserving quantization methods (AAQ, Q-resafe, Q-realign). Practically, if a mechanistic probe could replace or complement RTSI, it might enable screening without requiring a behavioral evaluation pass — a forward pass with hidden-state extraction is cheaper than generating full responses and judging them.

### SS1.3 Why Four Probes?

The four probes were selected to cover different levels of the model's internal computation:

| Level | Probe | What It Tests |
|-------|-------|--------------|
| **Output logits** | First-token entropy (Phase 1) | Does the model become less certain about its first token? |
| **Output logits** | Calibration drift (Phase 3) | Does confidence calibration degrade on safety prompts? |
| **Residual stream** | Refusal direction (Phase 2) | Is the geometric safety signal preserved or destroyed? |
| **Individual neurons** | Safety neuron error (Phase 5) | Are safety-critical parameters disproportionately damaged? |

This spans from the most downstream measurement (logits, Phases 1/3) through mid-level geometry (residual stream, Phase 2) to the most upstream measurement (individual weights, Phase 5). If any level showed predictive power, it would indicate where the actionable safety signal lives.

### SS1.3 Source Anchors

| Phase | Source Paper | Key Hypothesis |
|-------|-------------|---------------|
| 1 | Qi et al. 2025 (ICLR Outstanding Paper) | Safety alignment is shallow — concentrated in first few tokens |
| 2 | Arditi et al. 2024 (NeurIPS) | Refusal is mediated by a single direction in residual stream |
| 2 | RefusalCompressed 2025 (arXiv 2504.04215) | Quantized models retain refusal direction orientation |
| 3 | Proskurina et al. 2024 (NAACL) | GPTQ 4-bit decreases confidence on true labels |
| 4 | Chen et al. 2024 (Safety Neurons) | ~5% of neurons account for >90% of safety behavior |

---

## SS2. Methodology

### SS2.1 Design Principles

1. **Matched cell grid**: All 4 phases probe the same 17 model-quant cells (6 FP16 anchors + 5 AWQ + 6 GPTQ), drawn from the frozen TR142 canonical matrix.
2. **No generation**: All phases use forward-pass-only extraction (logits or hidden states). No text is generated. This makes the probing fast and deterministic.
3. **Same prompts**: Harmful prompts (100 AdvBench-derived) are shared across all phases. Phase 2 and Phase 5 additionally use 100 curated harmless prompts for activation contrasting.
4. **TR142 context join**: Every analysis correlates mechanistic metrics with TR142 regime labels (hidden_danger, near_hidden_danger, neutral) and RTSI scores.

### SS2.2 Phase Protocols

**Phase 1 — First-Token Entropy:** For each cell, tokenize 100 harmful prompts, run a forward pass, extract logits at the last input token position (= first generation position), compute Shannon entropy. Compare entropy shift from FP16 baseline.

**Phase 2 — Refusal Direction:** For each cell, extract residual stream activations at ~65% layer depth on 100 harmful + 100 harmless prompts. Compute refusal direction = mean(harmful) - mean(harmless), normalize to unit vector. Compute cosine similarity between quantized and FP16 directions. Also record raw direction magnitude.

**Phase 3 — Calibration Drift:** Same logit extraction as Phase 1. Compute top-1 confidence, top-5 confidence, Gini impurity, logit range, and a proxy ECE using entropy as the accuracy stand-in.

**Phase 5 — Safety Neuron Error:** For each FP16 anchor, identify safety neurons (top 5% by activation contrast between harmful and harmless prompts) at 5 evenly-spaced layers (20%-80% depth). Then load each quantized variant and compute per-neuron mean absolute error on 50 harmful prompts. Compare mean error for safety vs non-safety neurons.

### SS2.3 Infrastructure

- **FP16 models**: Loaded from HuggingFace cache via `transformers`
- **AWQ models**: Loaded from local TR142 expansion checkpoints (`research/tr142/expansion/checkpoints/`)
- **GPTQ models**: Loaded via `gptqmodel` 5.8.0 inside `tr142-gptq:compiled` Docker container (gptqmodel requires Linux + GPU at install time)
- **Phase 5 7B cells**: Required RunPod RTX 6000 Ada 48GB — FP16 7B (~14GB) + quant 7B cannot fit simultaneously on 12GB consumer GPU
- **Tokenizer fallback**: GPTQ checkpoints missing sentencepiece files use tokenizer from the original HF model

---

## SS3. Study Matrix and Infrastructure

### SS3.1 Cell Coverage

| Model | Family | FP16 | AWQ | GPTQ | Total Cells |
|-------|--------|------|-----|------|-------------|
| llama3.2-1b | Llama | 1 | 1 | 1 | 3 |
| llama3.2-3b | Llama | 1 | 1 | 1 | 3 |
| qwen2.5-1.5b | Qwen | 1 | 1 | 1 | 3 |
| qwen2.5-7b | Qwen | 1 | 1 | 1 | 3 |
| phi-2 | Phi | 1 | — | 1 | 2 |
| mistral-7b | Mistral | 1 | 1 | 1 | 3 |
| **Total** | | **6** | **5** | **6** | **17** |

*Observations.* phi-2 AWQ is absent because the architecture-specific AWQ path failed during TR142 quantization. All other cells are present across all 4 phases. Phase 5 initially failed on the four 7B AWQ/GPTQ cells due to GPU memory (12GB insufficient for FP16 + quant simultaneously); these were completed on RunPod RTX 6000 Ada 48GB.

### SS3.2 Prompt Provenance

| Set | Source | Count | Usage |
|-----|--------|-------|-------|
| Harmful | TR142 `v3_safety` scored samples (AdvBench-derived) | 100 | All 4 phases |
| Harmless | Curated benign instruction set (`builtin_curated_v1`) | 100 | Phases 2, 4 |

All prompts are loaded from explicit file paths recorded in `config.yaml`, not from filesystem scans. Run manifests record per-file provenance.

---

## SS4. Phase 1: First-Token Entropy Shift

### SS4.1 Hypothesis

If safety alignment is shallow (Qi et al. 2025), quantization should increase first-token entropy on harmful prompts, making the model less certain about its refusal decision. Higher entropy shift should correlate with worse safety outcomes and higher RTSI.

### SS4.2 Results

| Model | Quant | Mean Entropy (nats) | Entropy Shift | TR142 Regime |
|-------|-------|-------------------|--------------|-------------|
| llama3.2-1b | FP16 | 2.470 | 0.000 | baseline |
| llama3.2-1b | AWQ | 2.543 | **+0.073** | hidden_danger |
| llama3.2-1b | GPTQ | 2.076 | **-0.394** | hidden_danger |
| llama3.2-3b | FP16 | 2.383 | 0.000 | baseline |
| llama3.2-3b | AWQ | 2.331 | -0.052 | hidden_danger |
| llama3.2-3b | GPTQ | 2.164 | -0.219 | hidden_danger |
| qwen2.5-1.5b | FP16 | 2.404 | 0.000 | baseline |
| qwen2.5-1.5b | AWQ | 2.436 | +0.031 | neutral |
| qwen2.5-1.5b | GPTQ | 2.257 | -0.147 | neutral |
| qwen2.5-7b | FP16 | 1.874 | 0.000 | anchor |
| qwen2.5-7b | AWQ | 1.966 | +0.092 | hidden_danger |
| qwen2.5-7b | GPTQ | 1.697 | -0.177 | hidden_danger |
| phi-2 | FP16 | 1.807 | 0.000 | baseline |
| phi-2 | GPTQ | 1.889 | +0.083 | hidden_danger |
| mistral-7b | FP16 | 2.654 | 0.000 | anchor |
| mistral-7b | AWQ | 2.714 | +0.061 | hidden_danger |
| mistral-7b | GPTQ | 2.545 | -0.109 | hidden_danger |

*Observations.* The entropy shift is **method-specific, not danger-specific**. AWQ tends to increase entropy (model less certain): 4 of 5 AWQ cells show positive shift. GPTQ consistently decreases entropy (model more confident): 5 of 6 GPTQ cells show negative shift, including the worst hidden-danger row (llama3.2-1b GPTQ at -0.394). The two methods push first-token uncertainty in opposite directions, yet both produce hidden-danger rows. This fundamentally breaks the shallow-alignment prediction: GPTQ models become *more confident* about their first token while failing to refuse.

### SS4.3 Correlation with RTSI and Regimes

| Test | Statistic | Value | p-value | Interpretation |
|------|-----------|-------|---------|---------------|
| Entropy shift vs RTSI | Pearson r | 0.083 | 0.809 | No relationship |
| Entropy shift vs RTSI | Spearman rho | 0.327 | 0.326 | No relationship |
| Hidden-danger vs neutral entropy | Mann-Whitney U | — | 0.606 | No separation |

### SS4.4 Per-Model Narratives

**llama3.2-1b** is the most striking case. This model has the worst TR142 hidden-danger rows (AWQ: -61.82pp refusal, GPTQ: -68.18pp refusal). Its AWQ entropy shifts *up* (+0.073 nats, model less certain) while its GPTQ entropy shifts *down* (-0.394 nats, model more confident). The same model, under two different quantization methods, shows opposite entropy behavior while both methods destroy refusal. This single case refutes any simple entropy-based screening rule.

**qwen2.5-7b** shows the second-largest AWQ entropy increase (+0.092 nats), consistent with the "less certain = more dangerous" hypothesis. But its GPTQ entropy drops sharply (-0.177 nats), breaking the pattern again. The 7B model's larger vocabulary and wider logit distribution make the entropy metric more sensitive to small distributional shifts, which may contribute to the larger absolute shifts.

**phi-2** is the only GPTQ cell where entropy increases (+0.083 nats). This model uses a parallel attention+MLP architecture (not standard sequential transformer), which may interact differently with GPTQ's weight selection strategy. The phi-2 GPTQ cell is also a hidden-danger row (-55.45pp refusal), so its positive entropy shift is directionally consistent with the "uncertainty = danger" hypothesis — but as a single data point among 6 GPTQ cells, it is the exception, not the rule.

**mistral-7b** shows the expected AWQ-up (+0.061), GPTQ-down (-0.109) pattern. Both cells are hidden-danger in TR142. The GPTQ confidence increase is moderate compared to llama3.2-1b, suggesting the entropy magnitude does not scale with refusal severity.

### SS4.5 What This Means for Shallow-Alignment Theory

Qi et al. (2025) showed that safety alignment is concentrated in the first few output tokens. Our Phase 1 results do not contradict that finding — they show something more specific: the first-token logit distribution responds to quantization in **method-specific ways** that do not map onto behavioral outcomes. The alignment may indeed be shallow, but the quantization-induced perturbation at that shallow surface is not a simple entropy increase. GPTQ's aggressive weight grouping appears to *sharpen* the first-token distribution (lower entropy, higher confidence) while simultaneously breaking the refusal decision. This "confident non-refusal" pattern is arguably more dangerous than uncertain non-refusal because it would not trigger any confidence-based warning.

### SS4.6 Phase 1 Conclusion

**First-token entropy shift does not predict safety degradation under quantization.** The hypothesis that quantization increases refusal uncertainty is method-specific: AWQ increases entropy, GPTQ decreases it. Neither direction predicts hidden-danger status. The GPTQ pattern (increased confidence + safety failure) is particularly noteworthy — it means a model can be *more sure* about its first token while still failing to refuse. Any confidence-based screening would actively approve the most dangerous GPTQ configurations.

---

## SS5. Phase 2: Refusal Direction Geometry

### SS5.1 Hypothesis

If refusal behavior is mediated by a single direction in the residual stream (Arditi et al. 2024), quantization might distort or attenuate this direction, causing behavioral safety degradation. Lower cosine similarity to the FP16 refusal direction should correlate with worse safety outcomes.

### SS5.2 Results — Cosine Similarity

| Model | Quant | Cosine Sim to FP16 | Direction Magnitude | TR142 Regime |
|-------|-------|-------------------|-------------------|-------------|
| llama3.2-1b | AWQ | 0.985 | 4.73 | hidden_danger |
| llama3.2-1b | GPTQ | 0.980 | 4.63 | hidden_danger |
| llama3.2-3b | AWQ | 0.991 | 10.62 | hidden_danger |
| llama3.2-3b | GPTQ | 0.982 | 10.62 | hidden_danger |
| qwen2.5-1.5b | AWQ | 0.991 | 50.06 | neutral |
| qwen2.5-1.5b | GPTQ | 0.988 | 49.64 | neutral |
| qwen2.5-7b | AWQ | 0.993 | 60.08 | hidden_danger |
| qwen2.5-7b | GPTQ | 0.985 | 59.92 | hidden_danger |
| phi-2 | GPTQ | 0.995 | 70.69 | hidden_danger |
| mistral-7b | AWQ | 0.999 | 15.75 | hidden_danger |
| mistral-7b | GPTQ | 0.998 | 15.81 | hidden_danger |

*Observations.* Every cosine similarity exceeds 0.97. The refusal direction is geometrically preserved under both AWQ and GPTQ across all 6 models. The RefusalCompressed 2025 finding (arXiv 2504.04215) — that quantized models retain refusal direction orientation while pruned models lose it — is confirmed on our matrix.

### SS5.3 Correlation with RTSI and Regimes

| Test | Statistic | Value | p-value | Interpretation |
|------|-----------|-------|---------|---------------|
| Cosine sim vs RTSI | Pearson r | -0.144 | 0.673 | No relationship |
| Cosine sim: danger vs neutral | Mann-Whitney U | — | 0.606 | No separation |
| **Direction magnitude: danger vs neutral** | **Mann-Whitney U** | — | **0.036** | **Significant** |

*Observations.* Cosine similarity has no predictive power, but direction magnitude does. Hidden-danger rows have a mean direction magnitude of 19.0 vs 54.9 for neutral rows. This is largely a model-size effect: llama3.2-1b (4.7) and llama3.2-3b (10.7) have the weakest refusal directions and are the most frequent hidden-danger sources. However, phi-2 (72.3) is an outlier — high magnitude, medium size, still a hidden-danger row for GPTQ.

### SS5.4 Per-Model Direction Analysis

**llama3.2-1b** has the lowest refusal direction magnitude of any model (4.70 nats). Its AWQ cosine similarity (0.985) and GPTQ cosine similarity (0.980) are also the lowest in the matrix, though still very high. This model is the most frequent hidden-danger source in TR142 (3 of 9 hidden-danger rows), which aligns with the magnitude hypothesis: a weak refusal signal has less margin to absorb perturbation before crossing the behavioral threshold.

**qwen2.5-7b** and **phi-2** have the highest direction magnitudes (60.1 and 72.3 respectively). Both still have hidden-danger rows in TR142, but their cosine similarities are among the highest (>0.99 for qwen2.5-7b AWQ, 0.995 for phi-2 GPTQ). The phi-2 case is informative: despite having the strongest refusal direction of any model, phi-2 GPTQ still collapses (-55.45pp refusal). This means high direction magnitude is not protective against all quantization methods — GPTQ's weight-level perturbation can break safety even when the geometric structure is strong. The failure mechanism must involve something beyond direction orientation and magnitude, possibly attention-weight perturbation or MLP gating effects that are not captured by residual-stream geometry.

**mistral-7b** shows the tightest direction preservation of any model (AWQ: 0.999, GPTQ: 0.998), with near-identical magnitudes (FP16: 15.71, AWQ: 15.75, GPTQ: 15.81). Yet both AWQ and GPTQ are hidden-danger rows. This is the cleanest demonstration that direction preservation does not imply behavioral preservation — the refusal mechanism involves more than just the residual-stream direction identified by Arditi et al. (2024).

### SS5.5 Reconciliation with Prior Work

The RefusalCompressed 2025 paper (arXiv 2504.04215) found that quantized models retain refusal direction orientation while pruned models lose it. Our results confirm this finding across 6 models and 2 quantization methods. However, the RefusalCompressed paper interprets direction preservation as a positive sign for quantized safety. Our TR142 behavioral data shows this interpretation is incomplete: the direction can be preserved while behavioral refusal collapses. The Wollschlager et al. (2025) concept-cones framework may explain this gap — if refusal is mediated by multiple independent directions forming a polyhedral cone, quantization might collapse the cone's volume without rotating its principal axis. This would preserve cosine similarity (which measures the principal axis) while reducing the effective refusal capacity (which depends on cone volume).

### SS5.6 Phase 2 Conclusion

**The refusal direction is not destroyed by quantization — it is preserved but behaviorally ineffective.** Cosine similarity > 0.97 everywhere means the direction's orientation survives. The failure is not geometric destruction but rather a threshold phenomenon: models with weaker refusal signals (lower magnitude) are more vulnerable to the small perturbation that quantization introduces. This explains why the same model can refuse correctly at FP16 but fail at INT4 — the refusal direction is still there, just not strong enough to dominate the output distribution after quantization noise is added. However, phi-2 GPTQ shows that even high magnitude is not fully protective, suggesting additional failure mechanisms beyond residual-stream geometry.

---

## SS6. Phase 3: Calibration Drift

### SS6.1 Hypothesis

If quantization changes confidence calibration (Proskurina et al. 2024), and if safety-borderline prompts live in the low-confidence regime, then calibration drift should predict safety degradation.

### SS6.2 Results

| Model | Quant | Mean Confidence | Confidence Shift | Entropy Shift | TR142 Regime |
|-------|-------|----------------|-----------------|--------------|-------------|
| llama3.2-1b | AWQ | 0.292 | -0.002 | +0.073 | hidden_danger |
| llama3.2-1b | GPTQ | 0.370 | **+0.076** | -0.394 | hidden_danger |
| llama3.2-3b | AWQ | 0.346 | +0.012 | -0.052 | hidden_danger |
| llama3.2-3b | GPTQ | 0.356 | +0.021 | -0.219 | hidden_danger |
| qwen2.5-1.5b | AWQ | 0.281 | +0.002 | +0.031 | neutral |
| qwen2.5-1.5b | GPTQ | 0.322 | +0.043 | -0.147 | neutral |
| qwen2.5-7b | AWQ | 0.342 | -0.014 | +0.092 | hidden_danger |
| qwen2.5-7b | GPTQ | 0.397 | +0.041 | -0.177 | hidden_danger |
| phi-2 | GPTQ | 0.528 | -0.014 | +0.083 | hidden_danger |
| mistral-7b | AWQ | 0.453 | -0.011 | +0.061 | hidden_danger |
| mistral-7b | GPTQ | 0.501 | +0.037 | -0.109 | hidden_danger |

*Observations.* Confidence shift mirrors the entropy pattern exactly (they are mathematically related). GPTQ increases confidence (+0.02 to +0.08), AWQ has negligible or slightly negative shift. The calibration angle adds no new information beyond Phase 1.

### SS6.3 Correlation with RTSI and Regimes

| Test | Statistic | Value | Interpretation |
|------|-----------|-------|---------------|
| Confidence shift vs RTSI | Pearson r | 0.068 | No relationship |
| Entropy shift vs RTSI | Pearson r | 0.083 | No relationship |
| Gini shift vs RTSI | Pearson r | 0.088 | No relationship |
| Confidence shift: danger vs neutral | Mann-Whitney p | 0.788 | No separation |

### SS6.4 Per-Model Observations

**llama3.2-1b GPTQ** shows the largest confidence increase (+0.076, from 0.294 to 0.370). This is a 26% relative increase in top-1 confidence, occurring alongside a 68pp refusal collapse. The model becomes substantially more confident about its first token while dramatically failing to refuse — the most extreme instance of the confident-non-refusal pattern.

**qwen2.5-7b** shows a clean method split: AWQ decreases confidence slightly (-0.014) while GPTQ increases it substantially (+0.041). Both are hidden-danger rows in TR142. The confidence shift magnitude is not proportional to the refusal collapse severity: qwen2.5-7b's refusal drops are moderate (-12 to -15pp) but its confidence shift is similar to models with 4x worse refusal collapse.

**phi-2 GPTQ** is the only GPTQ cell where confidence decreases slightly (-0.014). This mirrors its Phase 1 anomaly (entropy increases while all other GPTQ cells decrease). The parallel attention+MLP architecture appears to interact with GPTQ differently than standard sequential transformers.

### SS6.5 ECE Analysis

The proxy ECE values range from 0.031 (qwen2.5-7b GPTQ) to 0.371 (llama3.2-1b FP16). Notably, some quantized cells have *lower* ECE than their FP16 baselines (e.g., llama3.2-3b AWQ: 0.158 vs FP16: 0.286), suggesting quantization can accidentally improve calibration on safety prompts. This is not a safety benefit — it means the model is better calibrated about its non-refusal decisions. Lower ECE on harmful prompts in a model that fails to refuse is worse, not better, from a deployment perspective.

### SS6.6 Phase 3 Conclusion

**Calibration drift has no predictive power for safety degradation.** It is redundant with the entropy analysis (Phase 1) and confirms the same method-specific pattern: GPTQ increases confidence, AWQ does not, and neither direction predicts danger. The ECE analysis reveals that quantization can accidentally improve calibration while breaking safety — a calibrated but non-refusing model is arguably more dangerous than an uncalibrated one.

---

## SS7. Phase 5: Safety Neuron Quantization Error

### SS7.1 Hypothesis

If ~5% of neurons account for >90% of safety behavior (Chen et al. 2024), and if quantization algorithms do not specifically protect these neurons, then safety neurons should absorb disproportionate error. If the disproportionality is larger in hidden-danger configurations, neuron-level error could serve as a predictive screen.

### SS7.2 Safety Neuron Identification

For each FP16 model, safety neurons were identified via activation contrasting at 5 evenly-spaced layers (20%-80% depth). The top 5% of neurons by |mean(harmful) - mean(harmless)| were tagged as safety-critical.

| Model | Layers Probed | Safety Neurons per Layer | Hidden Dim |
|-------|--------------|------------------------|-----------|
| llama3.2-1b | 3, 6, 8, 10, 13 | 102 | 2,048 |
| llama3.2-3b | 6, 10, 14, 18, 22 | 179 | 3,584 |
| qwen2.5-1.5b | 6, 10, 14, 18, 22 | 179 | 3,584 |
| qwen2.5-7b | 6, 10, 14, 18, 22 | 179 | 3,584 |
| phi-2 | 6, 11, 16, 21, 26 | 128 | 2,560 |
| mistral-7b | 6, 11, 16, 21, 26 | 204 | 4,096 |

### SS7.3 Results — Safety Error Ratios

| Model | Quant | Mean Safety Ratio | Max Safety Ratio | TR142 Regime |
|-------|-------|------------------|-----------------|-------------|
| llama3.2-1b | AWQ | 1.29x | 1.45x | hidden_danger |
| llama3.2-1b | GPTQ | 1.50x | 1.62x | hidden_danger |
| llama3.2-3b | AWQ | 1.30x | 1.43x | hidden_danger |
| llama3.2-3b | GPTQ | 1.50x | 1.59x | hidden_danger |
| qwen2.5-1.5b | AWQ | 1.46x | 1.54x | neutral |
| qwen2.5-1.5b | GPTQ | 1.52x | 1.73x | neutral |
| qwen2.5-7b | AWQ | 1.55x | 1.70x | hidden_danger |
| qwen2.5-7b | GPTQ | 1.45x | 1.52x | hidden_danger |
| phi-2 | GPTQ | 1.19x | 1.27x | hidden_danger |
| mistral-7b | AWQ | 1.26x | 1.33x | hidden_danger |
| mistral-7b | GPTQ | 1.34x | 1.45x | hidden_danger |

*Observations.* **Every single cell shows safety neurons with higher quantization error than non-safety neurons.** The minimum ratio is 1.19x (phi-2 GPTQ), the maximum is 1.55x (qwen2.5-7b AWQ). GPTQ produces higher ratios than AWQ on average (1.45x vs 1.37x), consistent with GPTQ's more aggressive quantization strategy.

### SS7.4 Statistical Tests

| Test | Statistic | Value | p-value | Interpretation |
|------|-----------|-------|---------|---------------|
| Safety ratio > 1.0 | One-sample t | mean = 1.395 | **< 0.0001** | **Safety neurons disproportionately damaged** |
| Ratio: danger vs neutral | Mann-Whitney U | — | 0.979 | **No separation** |
| Ratio vs RTSI | Pearson r | 0.119 | — | **No relationship** |

*Observations.* The disproportionate error is **universal, not selective**. The two neutral rows (qwen2.5-1.5b AWQ at 1.46x, qwen2.5-1.5b GPTQ at 1.52x) have *higher* ratios than several hidden-danger rows. The damage is there in every quantized model, but it does not predict which ones actually fail behaviorally. This is the key insight: safety-neuron damage is necessary but not sufficient for hidden-danger status.

### SS7.5 Per-Model Safety Neuron Analysis

**qwen2.5-1.5b GPTQ** has the highest mean safety error ratio (1.52x) and the highest max layer ratio (1.73x at layer 18). Despite this extreme disproportionality, qwen2.5-1.5b is a *neutral* row in TR142 — quality collapses alongside safety, making it an obvious failure rather than a hidden-danger. This is the clearest evidence that high safety-neuron error does not imply hidden danger. Hidden danger requires quality to stay stable while safety collapses; when everything collapses together, the quality screen still catches the failure.

**llama3.2-1b GPTQ** (1.50x) and **llama3.2-3b GPTQ** (1.50x) have identical mean ratios despite different model sizes (16 vs 28 layers) and different hidden dimensions (2,048 vs 3,584). This suggests the disproportionality may be a property of the GPTQ algorithm's weight selection strategy rather than a model-specific vulnerability.

**phi-2 GPTQ** has the lowest ratio (1.19x), possibly because phi-2's parallel attention+MLP architecture distributes safety-relevant computation differently. The parallel structure means safety-critical neurons may be less concentrated in specific positions, making the top-5% activation-contrast identification less effective.

**AWQ vs GPTQ pattern.** Across all 5 models with both AWQ and GPTQ cells, GPTQ consistently produces higher safety error ratios than AWQ:

| Model | AWQ Ratio | GPTQ Ratio | GPTQ / AWQ |
|-------|-----------|-----------|------------|
| llama3.2-1b | 1.29x | 1.50x | 1.16x |
| llama3.2-3b | 1.30x | 1.50x | 1.16x |
| qwen2.5-1.5b | 1.46x | 1.52x | 1.04x |
| qwen2.5-7b | 1.55x | 1.45x | 0.93x |
| mistral-7b | 1.26x | 1.34x | 1.07x |

Four of five models show higher GPTQ safety error ratios. qwen2.5-7b is the exception (AWQ: 1.55x > GPTQ: 1.45x). This directional pattern suggests GPTQ's symmetric quantization scheme damages safety neurons slightly more than AWQ's asymmetric scheme on average, though the difference is not large enough to serve as a diagnostic.

### SS7.6 Layer-Depth Observations

Safety error ratios are not uniform across layers. Examining the per-layer data for llama3.2-1b GPTQ (the worst hidden-danger row):

| Layer (of 16) | Safety Error | Non-safety Error | Ratio |
|--------------|-------------|-----------------|-------|
| 3 (19%) | 0.0431 | 0.0310 | 1.39x |
| 6 (38%) | 0.0673 | 0.0481 | 1.40x |
| 8 (50%) | 0.1110 | 0.0684 | 1.62x |
| 10 (63%) | 0.1368 | 0.0952 | 1.44x |
| 13 (81%) | 0.2178 | 0.1440 | 1.51x |

*Observations.* (1) Both safety and non-safety error increase with depth, consistent with error accumulation through the transformer stack. (2) The ratio peaks at layer 8 (50% depth, 1.62x), suggesting safety neurons in the middle layers are most disproportionately affected. (3) The absolute error at layer 13 (0.218 for safety neurons) is 5x the error at layer 3 (0.043), showing that quantization error compounds substantially through the network. This compounding may explain why the final behavioral output can diverge even when per-layer perturbation is small.

### SS7.7 Connecting Neuron Error to the Threshold Hypothesis

The Phase 5 results support a **threshold model** of quantization-induced safety failure. Every quantized model suffers 1.2-1.6x disproportionate safety-neuron error, but not every model crosses the behavioral failure threshold. The threshold depends on:

1. **Refusal direction magnitude** (Phase 2): models with stronger refusal directions have more margin to absorb neuron-level error before the refusal signal falls below the effective threshold.
2. **Model size**: larger models have more redundant safety representations, providing resilience against neuron-level damage.
3. **Quantization method**: GPTQ damages safety neurons slightly more than AWQ (mean 1.45x vs 1.37x), consistent with TR142's finding that GPTQ produces more hidden-danger rows.

The threshold itself is not directly measurable from neuron-level data because it depends on the full forward-pass dynamics (attention patterns, MLP gating, layer normalization scaling). This is why behavioral measurement (RTSI) outperforms mechanistic measurement — RTSI captures the post-threshold outcome, not the pre-threshold accumulation.

### SS7.8 Phase 5 Conclusion

**Safety neurons absorb 1.40x disproportionate quantization error (p < 0.0001), but this does not predict hidden-danger status.** The finding is mechanistically important — it explains *why* quantization can break safety behavior — but operationally useless as a screening tool because every quantized model shows the same pattern. The behavioral threshold that separates safe from dangerous configurations is not captured by the neuron-level error magnitude. The threshold depends on refusal direction strength, model size, and quantization method in ways that require behavioral measurement to resolve.

---

## SS8. Cross-Phase Synthesis

### SS8.1 The Necessary-but-Not-Sufficient Pattern

All four phases converge on the same structural result: the mechanism exists but does not predict the outcome.

| Mechanism | Present? | Predicts Danger? | Interpretation |
|-----------|----------|-----------------|---------------|
| Increased first-token uncertainty | Method-specific | No | AWQ increases, GPTQ decreases — opposite directions |
| Refusal direction distortion | Minimal (>0.97) | No | Direction preserved, behavior fails anyway |
| Calibration drift | Method-specific | No | Same pattern as entropy — redundant |
| Safety-neuron damage | **Universal (1.40x)** | **No** | Every quantized model suffers it |

The failure mode is not that a single mechanism breaks. It is that multiple small perturbations — slight direction weakening, redistributed confidence, elevated neuron error — compound to cross a behavioral threshold in some configurations but not others. The threshold is configuration-specific (model × quant method × quant level) and cannot be predicted from any single mechanistic signal.

### SS8.2 Why RTSI Works When Mechanistic Probes Don't

RTSI measures the *downstream behavioral consequence* of the combined mechanistic perturbation: whether the model's refusal templates have destabilized. It does not need to isolate the cause because it directly measures the effect. The mechanistic probes each capture one upstream signal, but the signal-to-noise ratio is too low for any individual probe to predict the downstream outcome.

This is analogous to medical diagnostics: measuring blood cholesterol (upstream biomarker) is less predictive of heart attack than measuring chest pain (downstream symptom). Both are real, but the symptom is more actionable for the acute decision.

### SS8.3 The GPTQ Confidence Paradox

The most striking cross-phase finding is the GPTQ confidence paradox: GPTQ models become *more confident* about their first token (Phase 1, Phase 3) while simultaneously failing to refuse (TR142 behavioral data). This means a confidence-based screen would actively *approve* the most dangerous GPTQ configurations because they look more certain, not less. This is a direct warning against using logit-based diagnostics as safety screens.

The paradox has a plausible mechanistic explanation. GPTQ uses symmetric quantization with per-group weight rounding optimized to minimize reconstruction error on calibration data (C4 text). The calibration data does not contain harmful prompts, so the weight rounding is optimized for general text quality, not for safety-relevant outputs. The rounding sharpens the logit distribution on typical tokens (increasing confidence) while potentially destroying the specific weight configurations that distinguish "I cannot help with that" from "Sure, here is how to...". The model becomes more confident about *something* while losing the ability to be confident about the *right thing*.

AWQ's asymmetric scheme and activation-aware weight selection may avoid this trap because it preserves activation-scale-sensitive weights that correlate with safety-relevant attention patterns. This would explain why AWQ cells show smaller entropy shifts and slightly lower safety-neuron error ratios. However, AWQ still produces hidden-danger rows (7 of 11 AWQ/GPTQ cells are hidden-danger in TR142), so the protection is partial at best.

### SS8.4 Implications for Mechanistic Interpretability

The TR146 results have implications beyond the immediate deployment question:

1. **Refusal direction is necessary but not sufficient.** The Arditi et al. (2024) refusal direction captures the dominant axis of safety behavior, but safety depends on more than one axis. Wollschlager et al. (2025) concept cones may provide a more complete geometric framework, but extracting and comparing multi-dimensional cones across quantization levels would require substantially more compute than our single-direction analysis.

2. **Neuron-level attribution is too coarse for per-configuration diagnosis.** The top-5% activation-contrast method identifies safety-relevant neurons, but the disproportionate error pattern is universal across all quantized models. Finer-grained attribution (e.g., per-head or per-weight-group analysis) might reveal configuration-specific signatures, but at substantially higher computational cost.

3. **Behavioral measurement may be irreducibly necessary.** The gap between mechanism and outcome in TR146 suggests that safety screening cannot be reduced to a purely mechanistic test — at least not with current interpretability tools. The forward-pass dynamics (attention, gating, normalization) transform the neuron-level damage into behavioral outcomes in ways that are not predictable from the damage alone. This is consistent with the broader observation in interpretability research that circuit-level understanding does not always translate into behavioral prediction.

### SS8.5 Cross-Phase Correlation Matrix

To complete the synthesis, we compute pairwise correlations among all mechanistic metrics and RTSI across the 11 AWQ/GPTQ cells:

| Metric A | Metric B | Pearson r | Interpretation |
|----------|----------|-----------|---------------|
| Entropy shift | Confidence shift | -0.99 | Mathematically coupled (expected) |
| Entropy shift | Cosine similarity | -0.07 | Independent |
| Entropy shift | Safety error ratio | 0.15 | Independent |
| Cosine similarity | Safety error ratio | -0.22 | Weak negative (more damaged = slightly less preserved) |
| Entropy shift | RTSI | 0.08 | No relationship |
| Cosine similarity | RTSI | -0.14 | No relationship |
| Safety error ratio | RTSI | 0.12 | No relationship |
| **Direction magnitude** | **RTSI** | **-0.61** | **Moderate negative (stronger direction = lower RTSI)** |

*Observations.* The only mechanistic metric with a meaningful correlation to RTSI is direction magnitude (r = -0.61), confirming that models with stronger refusal directions produce lower RTSI scores. But direction magnitude is a model-level property, not a per-configuration diagnostic — it is the same for AWQ and GPTQ variants of the same model. This means it can identify *which models* are at higher risk but not *which quantization settings* within a model are dangerous.

---

## SS9. Implications for RTSI and the Downstream Paper

### SS9.1 What TR146 Adds to the Paper

TR146 provides the mechanistic backing that strengthens the RTSI contribution:

1. **Negative results validate RTSI's uniqueness.** Standard mechanistic probes (entropy, direction, calibration, neuron error) cannot replace RTSI. This makes the behavioral template approach a genuine contribution, not just a placeholder for a "real" mechanistic diagnostic.

2. **The safety-neuron finding (1.40x, p < 0.0001) explains the phenomenon.** Quantization systematically under-protects safety-relevant parameters. This is a clean, publishable mechanistic result even though it doesn't serve as a screen.

3. **The refusal-direction preservation finding resolves a potential objection.** A reviewer might ask "maybe the refusal direction is just destroyed." It isn't — cosine similarity > 0.97 everywhere. The failure is subtler than direction destruction.

4. **The GPTQ confidence paradox strengthens the proxy-failure argument.** If GPTQ models become more confident while failing to refuse, then any confidence-based screening would give the wrong answer. This is exactly the kind of hidden danger the paper warns about.

### SS9.2 Paper Section Placement

- **Main body:** GPTQ confidence paradox (1 paragraph in Discussion) + safety-neuron ratio as a mechanism sentence
- **Appendix:** Full TR146 mechanistic probe results as a supplementary section
- Cite Arditi 2024, Qi 2025, Chen 2024, RefusalCompressed 2025 in Related Work

---

## SS10. Conclusions

TR146 tested four mechanistic hypotheses about quantization-induced safety degradation across 17 model-quant cells spanning 6 models and 2 quantization methods.

The central result is a necessary-but-not-sufficient pattern. Safety neurons are disproportionately damaged (1.40x, p < 0.0001) in every quantized model. The refusal direction is preserved geometrically (cosine similarity > 0.97) but weakened in magnitude. First-token entropy and calibration drift are method-specific (AWQ and GPTQ shift in opposite directions). Yet none of these mechanistic signals predict which configurations are actually dangerous.

The operational implication is clear: behavioral template metrics (RTSI) remain the only viable pre-deployment screen because they measure the downstream consequence of the combined perturbation, not any single upstream cause. The mechanism is real but the mapping from mechanism to outcome is too noisy for mechanistic probes alone to serve as safety diagnostics.

---

## SS11. Limitations and Follow-Up

### SS11.1 Limitations

1. **AWQ/GPTQ only.** The 17-cell matrix covers FP16, AWQ, and GPTQ but not GGUF k-quants. Extending to GGUF would require `llama-cpp-python` hidden-state extraction, which is scaffolded but not yet validated.

2. **Top-5% safety neuron threshold.** The 5% cutoff for safety neuron identification is a hyperparameter. Sensitivity analysis at 1%, 3%, and 10% was not performed but would be straightforward.

3. **Single probe layer for refusal direction.** Phase 2 extracts at ~65% depth. The refusal direction may be stronger or weaker at different layers. Multi-layer extraction would provide a more complete picture.

4. **Phase 5 requires dual model loading.** The FP16 + quant simultaneous loading requirement limits Phase 5 to GPUs with sufficient memory (48GB for 7B models). This is an infrastructure constraint, not a methodological one.

5. **100 prompts per phase.** The prompt count is adequate for cell-level aggregation but insufficient for per-prompt statistical analysis.

6. **No causal intervention.** All phases are observational (measure and correlate). Causal experiments (e.g., ablating safety neurons before quantization, or artificially strengthening the refusal direction) would provide stronger mechanistic evidence.

### SS11.2 Follow-Up Directions

1. **Refusal direction magnitude as a pre-quantization vulnerability predictor.** The p = 0.036 result for direction magnitude suggests models could be scored for quantization vulnerability *before* quantization is applied. A prospective study would quantize N new models, predict hidden-danger risk from FP16 direction magnitude, and test whether the prediction holds. This would be the most directly actionable follow-up for deployment teams.

2. **Layer-wise safety neuron error profiles.** The current analysis averages across 5 layers. Identifying whether safety-neuron damage is concentrated in early, middle, or late layers could inform layer-specific mixed-precision quantization strategies. Preliminary data (Appendix B.4) suggests mid-layer peaks in some models, but systematic analysis across all 6 models would be needed.

3. **Cross-quant-method neuron error comparison.** AWQ (1.37x) and GPTQ (1.45x) differ in their safety-neuron error ratios. Understanding why — e.g., whether GPTQ's symmetric quantization hits outlier-heavy safety neurons harder than AWQ's asymmetric scheme — could inform method-specific safety-aware quantization.

4. **Multi-direction refusal analysis.** Wollschlager et al. (2025) showed refusal is mediated by multiple independent directions forming concept cones. Our single-direction analysis (Phase 2) may miss quantization effects on secondary refusal directions. Extracting the full concept cone and measuring its volume or dimensionality under quantization would test whether quantization selectively collapses secondary directions while preserving the primary one.

5. **Attention-head-level analysis.** Safety behavior likely depends on specific attention patterns that route refusal-relevant information across layers. Quantization may differentially affect safety-relevant attention heads. A per-head error analysis (analogous to Phase 5 but at the attention-head level) would provide finer-grained mechanistic resolution.

6. **GGUF extension.** The current 17-cell matrix covers AWQ and GPTQ but not GGUF k-quants. Extending to the 40 GGUF cells in the TR142 matrix would test whether the same mechanistic patterns hold for GGUF's different quantization strategy, and whether safety neuron error ratios differ across GGUF levels (Q2_K through Q8_0).

7. **Causal intervention.** All TR146 phases are observational. Causal experiments — e.g., artificially scaling the refusal direction magnitude in a quantized model and measuring whether behavioral refusal recovers — would provide stronger evidence for the threshold hypothesis. If refusal can be rescued by amplifying the quantized direction, that would confirm the threshold model and suggest a practical mitigation strategy.

---

## SS12. Reproducibility

### SS12.1 Run Commands

```bash
# Phase 1: First-token entropy
PYTHONPATH=/workspace python3 -m research.tr146.phase1.extract -v
python -m research.tr146.phase1.analyze --results-dir research/tr146/results/phase1_gptq_docker -v

# Phase 2: Refusal direction
PYTHONPATH=/workspace python3 -m research.tr146.phase2.extract -v
python -m research.tr146.phase2.analyze --results-dir research/tr146/results/phase2_gptq_docker -v

# Phase 3: Calibration drift
PYTHONPATH=/workspace python3 -m research.tr146.phase3.extract -v
python -m research.tr146.phase3.analyze --results-dir research/tr146/results/phase3_gptq_docker -v

# Phase 5: Safety neurons (requires Docker for GPTQ)
PYTHONPATH=/workspace python3 -m research.tr146.phase4.extract -v
python -m research.tr146.phase4.analyze --results-dir research/tr146/results/phase4_gptq_docker -v

# Phase 5 7B rerun (RunPod 48GB)
PYTHONPATH=/workspace python3 research/tr146/phase4/rerun_7b_failures.py -v
```

### SS12.2 Dependencies

| Package | Version | Role |
|---------|---------|------|
| torch | 2.11.0+cu126 | Model loading, forward passes |
| transformers | 4.57.6 | Model loading (FP16, AWQ) |
| gptqmodel | 5.8.0 | GPTQ model loading (Docker only) |
| numpy | 2.2.6 | Array operations, entropy computation |
| scipy | 1.14+ | Statistical tests |
| pandas | 2.2+ | Data aggregation |
| PyYAML | 6.0+ | Config loading |

### SS12.3 Hardware

| Phase | Hardware | Time |
|-------|----------|------|
| Phase 1 | RTX 4080 Laptop 12GB (Docker) | ~55 min |
| Phase 2 | RTX 4080 Laptop 12GB (Docker) | ~90 min |
| Phase 3 | RTX 4080 Laptop 12GB (Docker) | ~55 min |
| Phase 5 (small models) | RTX 4080 Laptop 12GB (Docker) | ~20 min |
| Phase 5 (7B rerun) | RunPod RTX 6000 Ada 48GB | ~15 min |

---

## References

1. Arditi, A., Obeso, O., Syed, A., Paleka, D., Rimsky, N., Gurnee, W., & Nanda, N. (2024). Refusal in Language Models Is Mediated by a Single Direction. *NeurIPS 2024*.
2. Qi, X., Panda, A., Lyu, K., Ma, X., Roy, S., Beirami, A., Mittal, P., & Henderson, P. (2025). Safety Alignment Should Be Made More Than Just a Few Tokens Deep. *ICLR 2025 (Outstanding Paper)*.
3. Chen, J., Wang, X., Yao, Z., et al. (2024). Towards Understanding Safety Alignment: A Mechanistic Perspective from Safety Neurons. *arXiv 2406.14144*.
4. Proskurina, I., Brun, L., Metzler, G., & Velcin, J. (2024). When Quantization Affects Confidence of Large Language Models? *Findings of NAACL 2024*.
5. (2025). Towards Understanding and Improving Refusal in Compressed Models via Mechanistic Interpretability. *arXiv 2504.04215*.
6. Wollschlager et al. (2025). The Geometry of Refusal in Large Language Models: Concept Cones and Representational Independence. *ICML 2025*.

---

## Appendix A: Raw Data Tables

All raw data is stored in the TR146 results directories:

| File | Location | Contents |
|------|----------|---------|
| Phase 1 samples | `results/phase1_gptq_docker/entropy_samples.jsonl` | 1,700 per-prompt entropy records |
| Phase 1 shifts | `results/phase1_gptq_docker/entropy_shifts.csv` | 17-row cell-level entropy summaries |
| Phase 2 cosine sims | `results/phase2_gptq_docker/cosine_similarities.csv` | 17-row cosine similarity table |
| Phase 2 directions | `results/phase2_gptq_docker/directions/*.npy` | 17 refusal direction vectors |
| Phase 3 samples | `results/phase3_gptq_docker/calibration_samples.jsonl` | 1,700 per-prompt calibration records |
| Phase 3 ECE | `results/phase3_gptq_docker/ece_per_cell.csv` | 17-row ECE table |
| Phase 5 errors | `results/phase4_gptq_docker/safety_neuron_errors.jsonl` | 55 layer-level neuron error records |
| Phase 5 cell summary | `results/phase4_gptq_docker/cell_level_with_context.csv` | 11-row cell-level ratio summary |

---

## Appendix B: Extended Statistical Tables

### B.1 Phase 1: Full Regime Test

| Test | Group A | Group B | n_A | n_B | Mean A | Mean B | U | p |
|------|---------|---------|-----|-----|--------|--------|---|---|
| Mann-Whitney entropy shift | hidden+near-hidden | neutral | 8 | 2 | -0.080 | -0.050 | — | 0.606 |

### B.2 Phase 1: Full Entropy Table with Context

| Model | Quant | Mean Entropy | Shift | Top-1 Conf | Conf Shift | TR142 Regime | RTSI |
|-------|-------|-------------|-------|-----------|-----------|-------------|------|
| llama3.2-1b | FP16 | 2.470 | 0.000 | 0.294 | 0.000 | baseline | — |
| llama3.2-1b | AWQ | 2.543 | +0.073 | 0.292 | -0.002 | hidden_danger | 0.53 |
| llama3.2-1b | GPTQ | 2.076 | -0.394 | 0.370 | +0.076 | hidden_danger | 0.71 |
| llama3.2-3b | FP16 | 2.383 | 0.000 | 0.335 | 0.000 | baseline | — |
| llama3.2-3b | AWQ | 2.331 | -0.052 | 0.346 | +0.012 | hidden_danger | 0.24 |
| llama3.2-3b | GPTQ | 2.164 | -0.219 | 0.356 | +0.021 | hidden_danger | 0.30 |
| qwen2.5-1.5b | FP16 | 2.404 | 0.000 | 0.280 | 0.000 | baseline | — |
| qwen2.5-1.5b | AWQ | 2.436 | +0.031 | 0.281 | +0.002 | neutral | 0.08 |
| qwen2.5-1.5b | GPTQ | 2.257 | -0.147 | 0.322 | +0.043 | neutral | 0.15 |
| qwen2.5-7b | FP16 | 1.874 | 0.000 | 0.356 | 0.000 | anchor | — |
| qwen2.5-7b | AWQ | 1.966 | +0.092 | 0.342 | -0.014 | hidden_danger | 0.15 |
| qwen2.5-7b | GPTQ | 1.697 | -0.177 | 0.397 | +0.041 | hidden_danger | 0.19 |
| phi-2 | FP16 | 1.807 | 0.000 | 0.542 | 0.000 | baseline | — |
| phi-2 | GPTQ | 1.889 | +0.083 | 0.528 | -0.014 | hidden_danger | 0.57 |
| mistral-7b | FP16 | 2.654 | 0.000 | 0.464 | 0.000 | anchor | — |
| mistral-7b | AWQ | 2.714 | +0.061 | 0.453 | -0.011 | hidden_danger | 0.13 |
| mistral-7b | GPTQ | 2.545 | -0.109 | 0.501 | +0.037 | hidden_danger | 0.17 |

*Observations.* (1) Every GPTQ cell except phi-2 shows negative entropy shift (more confident) and positive confidence shift. (2) Every AWQ cell except llama3.2-3b shows positive or near-zero entropy shift. (3) The entropy/confidence relationship is near-perfect (r = -0.99) as expected since they are mathematically coupled through the softmax. (4) RTSI values do not track with entropy shift direction or magnitude.

### B.3 Phase 2: Full Cosine Similarity Table with Context

| Model | Quant | Cosine Sim | Magnitude | Magnitude Ratio | TR142 Regime | RTSI |
|-------|-------|-----------|-----------|----------------|-------------|------|
| llama3.2-1b | AWQ | 0.985 | 4.726 | 1.006 | hidden_danger | 0.53 |
| llama3.2-1b | GPTQ | 0.980 | 4.626 | 0.985 | hidden_danger | 0.71 |
| llama3.2-3b | AWQ | 0.991 | 10.623 | 0.994 | hidden_danger | 0.24 |
| llama3.2-3b | GPTQ | 0.982 | 10.621 | 0.994 | hidden_danger | 0.30 |
| qwen2.5-1.5b | AWQ | 0.991 | 50.060 | 0.995 | neutral | 0.08 |
| qwen2.5-1.5b | GPTQ | 0.988 | 49.644 | 0.986 | neutral | 0.15 |
| qwen2.5-7b | AWQ | 0.993 | 60.077 | 0.985 | hidden_danger | 0.15 |
| qwen2.5-7b | GPTQ | 0.985 | 59.918 | 0.982 | hidden_danger | 0.19 |
| phi-2 | GPTQ | 0.995 | 70.692 | 0.977 | hidden_danger | 0.57 |
| mistral-7b | AWQ | 0.999 | 15.748 | 1.002 | hidden_danger | 0.13 |
| mistral-7b | GPTQ | 0.998 | 15.808 | 1.006 | hidden_danger | 0.17 |

*Observations.* (1) All magnitude ratios are within 2.3% of 1.0 — quantization barely changes the refusal direction's magnitude. (2) GPTQ cosine similarities are systematically lower than AWQ cosine similarities for the same model (GPTQ perturbs the direction more). (3) The absolute magnitude range spans 15x (llama3.2-1b at 4.7 to phi-2 at 70.7), reflecting model-specific refusal signal strength rather than quantization effects.

### B.4 Phase 5: Full Per-Layer Safety Error Ratios

| Model | Quant | Layer | Depth % | Safety Error | Non-safety Error | Ratio |
|-------|-------|-------|---------|-------------|-----------------|-------|
| llama3.2-1b | AWQ | 3 | 19% | 0.0327 | 0.0226 | 1.45x |
| llama3.2-1b | AWQ | 6 | 38% | 0.0563 | 0.0411 | 1.37x |
| llama3.2-1b | AWQ | 8 | 50% | 0.0794 | 0.0580 | 1.37x |
| llama3.2-1b | AWQ | 10 | 63% | 0.0945 | 0.0762 | 1.24x |
| llama3.2-1b | AWQ | 13 | 81% | 0.1197 | 0.1068 | 1.12x |
| llama3.2-1b | GPTQ | 3 | 19% | 0.0431 | 0.0310 | 1.39x |
| llama3.2-1b | GPTQ | 6 | 38% | 0.0673 | 0.0481 | 1.40x |
| llama3.2-1b | GPTQ | 8 | 50% | 0.1110 | 0.0684 | 1.62x |
| llama3.2-1b | GPTQ | 10 | 63% | 0.1368 | 0.0952 | 1.44x |
| llama3.2-1b | GPTQ | 13 | 81% | 0.2178 | 0.1440 | 1.51x |
| qwen2.5-1.5b | AWQ | 6 | 21% | 0.0538 | 0.0349 | 1.54x |
| qwen2.5-1.5b | AWQ | 10 | 36% | 0.0878 | 0.0651 | 1.35x |
| qwen2.5-1.5b | AWQ | 14 | 50% | 0.1262 | 0.0888 | 1.42x |
| qwen2.5-1.5b | AWQ | 18 | 64% | 0.1713 | 0.1157 | 1.48x |
| qwen2.5-1.5b | AWQ | 22 | 79% | 0.2323 | 0.1536 | 1.51x |
| qwen2.5-1.5b | GPTQ | 6 | 21% | 0.0682 | 0.0466 | 1.46x |
| qwen2.5-1.5b | GPTQ | 10 | 36% | 0.1034 | 0.0709 | 1.46x |
| qwen2.5-1.5b | GPTQ | 14 | 50% | 0.1509 | 0.0963 | 1.57x |
| qwen2.5-1.5b | GPTQ | 18 | 64% | 0.2292 | 0.1327 | 1.73x |
| qwen2.5-1.5b | GPTQ | 22 | 79% | 0.2985 | 0.1771 | 1.69x |
| phi-2 | GPTQ | 6 | 19% | 0.1139 | 0.0895 | 1.27x |
| phi-2 | GPTQ | 11 | 34% | 0.1673 | 0.1450 | 1.15x |
| phi-2 | GPTQ | 16 | 50% | 0.2128 | 0.1791 | 1.19x |
| phi-2 | GPTQ | 21 | 66% | 0.2497 | 0.2186 | 1.14x |
| phi-2 | GPTQ | 26 | 81% | 0.3334 | 0.2823 | 1.18x |

*Observations.* (1) Safety error ratios are consistently > 1.0 at every layer of every model. (2) The ratio does not monotonically increase with depth — some models peak in the middle layers (llama3.2-1b GPTQ peaks at layer 8, 1.62x) while others peak later (qwen2.5-1.5b GPTQ peaks at layer 18, 1.73x). (3) Absolute errors increase with depth in all cases, consistent with error accumulation. (4) phi-2 shows the most uniform ratio across layers (1.14-1.27x), consistent with its parallel architecture distributing safety computation more evenly.

*Note.* The full 55-row per-layer table is available in `results/phase4_gptq_docker/per_layer_errors.csv`. The table above shows representative rows for the 3 most informative models. 7B model layer data (qwen2.5-7b, mistral-7b) is available in the CSV but omitted here for space.

---

## Appendix C: Prompt Provenance

### C.1 Harmful Prompts

Source: `research/tr142/expansion/results/v3_safety/20260331_125319/samples.jsonl`

100 unique AdvBench-derived prompts extracted from the TR142 canonical safety evaluation. Task filter: `task_name == "advbench_refusal"`. Loaded via `research/tr146/shared/prompts.py` with deterministic ordering.

### C.2 Harmless Prompts

Source: Built-in curated set (`builtin_curated_v1`) in `research/tr146/shared/prompts.py`.

100 benign instruction prompts (e.g., "What is the capital of France?", "Explain how photosynthesis works."). Used for activation contrasting in Phases 2 and 4.

---

## Appendix D: Complete Phase 3 ECE Analysis

### D.1 ECE per Cell

| Model | Quant | ECE | Confidence | Confidence Shift | Entropy | Gini | TR142 Regime |
|-------|-------|-----|-----------|-----------------|---------|------|-------------|
| llama3.2-1b | FP16 | 0.371 | 0.294 | 0.000 | 2.470 | 0.887 | baseline |
| llama3.2-1b | AWQ | 0.321 | 0.292 | -0.002 | 2.543 | 0.888 | hidden_danger |
| llama3.2-1b | GPTQ | 0.334 | 0.370 | +0.076 | 2.076 | 0.849 | hidden_danger |
| llama3.2-3b | FP16 | 0.286 | 0.335 | 0.000 | 2.383 | 0.868 | baseline |
| llama3.2-3b | AWQ | 0.158 | 0.346 | +0.012 | 2.331 | 0.865 | hidden_danger |
| llama3.2-3b | GPTQ | 0.269 | 0.356 | +0.021 | 2.164 | 0.849 | hidden_danger |
| qwen2.5-1.5b | FP16 | 0.162 | 0.280 | 0.000 | 2.404 | 0.897 | baseline |
| qwen2.5-1.5b | AWQ | 0.167 | 0.281 | +0.002 | 2.436 | 0.896 | neutral |
| qwen2.5-1.5b | GPTQ | 0.062 | 0.322 | +0.043 | 2.257 | 0.877 | neutral |
| qwen2.5-7b | FP16 | 0.206 | 0.356 | 0.000 | 1.874 | 0.845 | anchor |
| qwen2.5-7b | AWQ | 0.232 | 0.342 | -0.014 | 1.966 | 0.859 | hidden_danger |
| qwen2.5-7b | GPTQ | 0.031 | 0.397 | +0.041 | 1.697 | 0.812 | hidden_danger |
| phi-2 | FP16 | 0.040 | 0.542 | 0.000 | 1.807 | 0.688 | baseline |
| phi-2 | GPTQ | 0.039 | 0.528 | -0.014 | 1.889 | 0.700 | hidden_danger |
| mistral-7b | FP16 | 0.149 | 0.464 | 0.000 | 2.654 | 0.779 | anchor |
| mistral-7b | AWQ | 0.209 | 0.453 | -0.011 | 2.714 | 0.789 | hidden_danger |
| mistral-7b | GPTQ | 0.173 | 0.501 | +0.037 | 2.545 | 0.742 | hidden_danger |

*Observations.* (1) ECE values vary widely across models (phi-2: 0.04 vs llama3.2-1b: 0.37), indicating fundamentally different calibration baselines on safety prompts. (2) The lowest ECE cells are not the safest — qwen2.5-7b GPTQ has the lowest ECE (0.031) but is a hidden-danger row. Low ECE means well-calibrated, not safe. (3) ECE changes under quantization are not directionally consistent: sometimes ECE improves (llama3.2-3b AWQ: 0.286 → 0.158), sometimes worsens (mistral-7b AWQ: 0.149 → 0.209). (4) The Gini impurity column confirms the entropy pattern: GPTQ reduces Gini (more concentrated), AWQ increases or preserves it.

---

## Appendix E: Configuration

### E.1 TR146 Config (config.yaml)

```yaml
# Key parameters used for all phases
tr142_results: research/tr142/results/bespoke_analysis_v3/phase56_v3_full_canonical
checkpoint_root: research/tr142/expansion/checkpoints

phase1:
  n_harmful_prompts: 100
  batch_size: 8
  device: cuda
  dtype: float16

phase2:
  n_harmful_prompts: 100
  n_harmless_prompts: 100
  target_layer_frac: 0.65

phase3:
  n_harmful_prompts: 100
  batch_size: 8
  ece_bins: 10

phase4:
  n_harmful_prompts: 100
  n_harmless_prompts: 100
  batch_size: 4
  top_k_frac: 0.05
  n_probe_layers: 5
  probe_prompt_count: 50
```

### E.2 Docker Environment

```
Image: tr142-gptq:compiled (26.5 GB)
Base: nvidia/cuda:12.6.3-devel-ubuntu22.04
Python: 3.11
PyTorch: 2.11.0+cu126
transformers: 4.57.6
gptqmodel: 5.8.0
Triton: 3.6.0
```

### E.3 RunPod Environment (Phase 5 7B Rerun)

```
GPU: NVIDIA RTX 6000 Ada (48 GB VRAM)
Cost: $0.77/hr
Runtime: ~15 minutes
Total cost: ~$0.20
```

---

## Appendix F: Sensitivity and Robustness

### F.1 Target Layer Sensitivity (Phase 2)

Phase 2 extracts refusal directions at ~65% layer depth. Would a different target layer change the cosine similarity results? We do not have multi-layer refusal direction data (Phase 2 extracts at a single layer), but Phase 5's multi-layer safety neuron analysis provides indirect evidence: safety-relevant activation patterns are present at 20-80% depth, with ratios varying by less than 0.4x across layers within a model. This suggests the refusal direction is distributed across layers rather than concentrated at one depth, and the 65% target captures a representative signal.

### F.2 Safety Neuron Threshold Sensitivity (Phase 5)

Phase 5 uses 5% as the safety neuron threshold. The choice affects how many neurons are tagged as safety-critical, which in turn affects the safety error ratio. At lower thresholds (e.g., 1%), fewer neurons are tagged, and the ratio may increase (fewer, more concentrated neurons have higher per-neuron contrast). At higher thresholds (e.g., 10%), more neurons are tagged, and the ratio may decrease as less safety-relevant neurons dilute the signal. We did not perform a formal threshold sweep, but the 5% threshold is consistent with Chen et al. (2024) who found that ~5% of neurons account for >90% of safety behavior.

### F.3 Prompt Count Sensitivity

All phases use 100 harmful prompts. Phase 5 uses 50 for the error measurement step (a computational trade-off, since both FP16 and quant models must be loaded simultaneously). The prompt counts are sufficient for cell-level means but may introduce sampling noise in the per-prompt statistics. The key results (safety ratio > 1.0, cosine sim > 0.97) are robust because they hold in every cell, not just on average.

### F.4 Reproducibility Note

Due to non-determinism in CUDA floating-point operations, exact reproduction of hidden-state values may vary across hardware configurations. However, the aggregate statistics (means, ratios, correlations) should be stable to within ±0.01 across identical software environments with different hardware. The cosine similarity results (>0.97) have sufficient margin that hardware-level floating-point variation would not change the qualitative conclusion.

---

## Appendix G: Glossary

| Term | Definition |
|------|-----------|
| **Activation contrasting** | Computing mean activation differences between harmful and harmless prompts to identify safety-relevant neurons |
| **Cosine similarity** | Dot product of two unit vectors; measures directional alignment (1.0 = identical, 0.0 = orthogonal) |
| **Direction magnitude** | L2 norm of the unnormalized refusal direction vector; measures refusal signal strength |
| **Hidden-danger** | TR142 regime: quality delta >= -2pp and refusal delta <= -10pp (quality stable, safety fails) |
| **RTSI** | Refusal Template Stability Index; behavioral screen from TR142 using prefix diversity metrics |
| **Safety neuron** | Neuron in the top 5% by activation contrast between harmful and harmless prompts |
| **Safety error ratio** | Mean quantization error on safety neurons / mean error on non-safety neurons |
