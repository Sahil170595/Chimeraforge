# TR134-TR137 Decision Whitepaper
## Executive guidance for safety-critical LLM deployment

Project: Banterhearts LLM Performance Research
Date: 2026-03-08
Version: 1.0
Audience: Decision makers, product leaders, ML ops leaders
Scope: TR134 (Alignment Under Quantization), TR135 (Concurrency x Safety), TR136 (Cross-Backend Safety), TR137 (Safety Tax Synthesis)
Primary source: `PublishReady/reports/Technical_Report_Conclusive_134-137.md`

---

## Abstract

This whitepaper distills four technical reports (TR134-TR137) and 74,254 evaluated samples into deployment policy for safety-critical LLM inference. The central question: when optimizing a small LLM for production (quantization, concurrency, backend), which optimization degrades safety alignment, by how much, and for which models? Outcome: six shippable decisions that cover the full safety-optimization space, backed by bootstrap confidence intervals, effect sizes, and per-model profiling across 5 models, 7 quantization levels, 4 concurrency levels, and 4 serving backends.

---

## Boundary conditions (do not skip)

This guidance is valid only under the measured boundary:

- Models at or below 7.6B parameters (Llama 3.2 1B/3B, Mistral 7B Instruct v0.3, Qwen 2.5 7B Instruct, Qwen 2.5 3B/1.5B)
- Fixed hardware class: NVIDIA RTX consumer GPU, single-GPU inference
- Quantization via Ollama GGUF (Q2_K through FP16, 7 levels)
- Serving backends: Ollama, vLLM, TGI, HuggingFace Transformers
- Safety scored by automated classifiers (RefusalDetector, BiasDetector, TruthfulnessScorer) — not human annotation
- Temperature 0 (deterministic sampling) throughout
- Safety tasks: AdvBench refusal (100 samples), TruthfulQA (50), BBQ bias (200), jailbreak amplification (120)
- Capability tasks: MMLU (285 samples), ARC-Challenge (200)

If any of these change, re-run the safety evaluation matrix and re-validate before applying these decisions.

---

## Six decisions you can ship now

1. **Quantization floor for safety-critical applications: Q4_K_M.** At Q4_K_M, all tested models retain >= 93% of baseline safety. The marginal safety cost at this level is 1.3-4.6pp — well within acceptable bounds. Q8_0 or FP16 are safer but offer marginal improvement (98-101% retention). Below Q4_K_M, safety degrades model-specifically and unpredictably.

2. **Concurrency scaling is safety-neutral: scale freely.** Maximum observed safety effect across all models, tasks, and concurrency levels (N=1 to N=8) is 0.4pp. All jailbreak compliance slopes under concurrency are exactly zero. No safety testing is required for concurrency changes.

3. **Backend migrations are safety-critical changes: re-validate.** Switching from Ollama GGUF to vLLM/TGI FP16 can cost 4-25pp of safety depending on the model. No backend pair achieves TOST equivalence at +/-3pp (0/18 tests pass). Treat every backend change as requiring full safety re-evaluation.

4. **Per-model safety profiling is mandatory.** I-squared heterogeneity = 99.9% on the quantization axis. Models do not agree on the direction of safety degradation, let alone the magnitude. Llama 1B loses 35pp at Q2_K; Llama 3B gains 6pp. No generic "safe quantization level" guideline is reliable across models.

5. **Ban Q2_K for Llama-class 1B models.** All Q2_K configurations for Llama 3.2 1B are rated CRITICAL risk (57.5% safety retention). This is the only model-quant combination that falls below the 80% safety threshold. The ban is model-specific — other models do not show this catastrophic pattern at Q2_K.

6. **Monitor jailbreak susceptibility under quantization.** All four jailbreak techniques (prefix injection, direct, DAN-style, roleplay) become more effective at lower quantization levels (all BPW slopes negative). Prefix injection is the most dangerous (-0.036 compliance/BPW). Jailbreak vulnerability is invariant to concurrency.

---

## Decision matrix (one-glance policy)

| Condition | Quantization | Concurrency | Backend | Safety Action |
|-----------|-------------|-------------|---------|---------------|
| Safety-critical, any model | Q4_K_M or higher | Any (N=1-8) | Current (no change) | Standard monitoring |
| Safety-critical, Llama 1B | Q4_K_M or higher | Any | Current | Enhanced monitoring |
| Safety-critical, new model | Profile first | Any | Current | Full safety evaluation before deployment |
| Cost-optimized, non-critical | Q3_K_S (model-dependent) | Any | Any | Spot-check safety |
| Backend migration | Keep current quant | Any | Re-validate safety | Full safety evaluation |
| Scaling concurrency | Keep current quant | Scale freely | Keep current backend | No action needed |
| Maximum risk tolerance | Q2_K (not for Llama 1B) | Any | Any | Accept CRITICAL risk |

---

## Key findings (decision-grade)

- **Quantization accounts for 57% of total safety cost.** Mean absolute delta: 20.6pp across 2 anchor models. Cohen's d = 1.93 for Llama 1B (large effect). However, the 95% bootstrap CI spans [-6.0, 35.2]pp because one model improves under quantization while the other degrades severely. This extreme variance is itself the finding.

- **Backend choice accounts for 41% of total safety cost.** Mean delta: 14.8pp (CI: [4.4, 25.1]pp). The mechanism is chat template divergence between GGUF-embedded and HuggingFace tokenizer templates, not the serving framework itself (vLLM and TGI are functionally identical: d < 0.03). This is a weight format issue, not a software issue.

- **Concurrency accounts for 2% of total safety cost.** Mean delta: 0.1pp (CI: [-0.3, 0.4]pp). This is the only axis where all models agree (I-squared = 0.0%). Deterministic sampling produces identical outputs regardless of concurrent load.

- **The safety veneer hypothesis is not universally supported.** Only 3 of 10 model-axis combinations show safety degrading faster than capability. RLHF alignment is not a uniquely fragile "thin layer" for most models — safety and capability degrade comparably.

- **Nationality is the most vulnerable bias category under quantization.** BBQ per-category slopes show Nationality at -0.010/BPW (worsening) and Race/Ethnicity at +0.015/BPW (improving). Race-related bias mitigation is more robust to quantization, likely due to heavier emphasis in RLHF training data.

- **Automated classifiers disagree more at low quantization.** Cohen's kappa between regex and LLM judge drops from 0.000 (baseline, but 72% raw agreement) to 0.007 (Q2_K, 58% agreement) on AdvBench. Safety scores at extreme quant levels carry higher measurement uncertainty.

---

## Operational recommendations (policy statements)

### Quantization policy

- **Policy:** Q4_K_M is the safety-validated default for all tested models at or below 7.6B parameters.
- **Policy gate:** Use Q8_0 or FP16 when safety retention >= 98% is required.
- **Policy ban:** Never deploy Q2_K for Llama 3.2 1B in any safety-sensitive context (57.5% retention = CRITICAL).
- **Policy:** Always run per-model safety profiling before deploying a new model at any quantization level. Do not extrapolate from other models.

### Concurrency policy

- **Policy:** Scale concurrency (N=1 to N=8+) without safety constraints.
- **Rationale:** Zero jailbreak slope, zero bias slope, max 0.4pp overall safety delta across all tested models and tasks.

### Backend policy

- **Policy:** Treat any backend migration as a safety-critical change requiring full re-evaluation.
- **Policy gate:** If migrating from Ollama to vLLM/TGI, expect 4-25pp safety impact (model-dependent). Budget for safety testing before production cutover.
- **Policy:** Do not assume vLLM and TGI are safety-equivalent to Ollama merely because they serve the same weights. Chat template handling differs by weight format (GGUF vs HuggingFace FP16).

### Jailbreak monitoring

- **Policy:** Test all deployed quantized models against prefix injection and direct prompt jailbreaks.
- **Policy:** Models at Q3_K_S or below require jailbreak testing at deployment and after any weight format change.
- **Policy:** Concurrency scaling does not require jailbreak re-testing.

### Bias monitoring

- **Policy:** Monitor Nationality-related bias under quantization — most vulnerable category.
- **Policy:** Race/Ethnicity bias is the most robust category, but this should not be assumed for untested models.

---

## Risk impact

### Safety cost by optimization axis (ranked)

1. **Quantization:** 57% of total safety cost. Range: -6pp to +35pp depending on model. The dominant lever and the most dangerous because of extreme model disagreement (I-squared = 99.9%).
2. **Backend:** 41% of total safety cost. Range: 4pp to 25pp. Driven by weight format and chat template, not serving framework.
3. **Concurrency:** 2% of total safety cost. Range: 0pp to 0.4pp. Negligible and consistent across models.

### Worst-case deployment

- Model: Llama 3.2 1B at Q2_K, N=1, Ollama
- Safety retention: **57.5%** (CRITICAL)
- Additional backend variance: 25.1pp (if backend changes)
- Theoretical floor (Q2_K + TGI): below 30% retention (not directly measured)

### Risk distribution across 24 assessed configurations

| Risk Level | Count | Percentage |
|-----------|-------|------------|
| Critical (< 80% retention) | 3 | 12.5% |
| High (80-90%) | 0 | 0.0% |
| Moderate (90-95%) | 3 | 12.5% |
| Low (>= 95%) | 18 | 75.0% |

Avoiding Q2_K for Llama 1B eliminates all critical risk. Using Q4_K_M or higher reduces risk to moderate or low for all configurations.

---

## Implementation plan (30-day view)

**Days 1-7: establish safety baseline**

- Run per-model safety profiling at your deployed quantization level using the 4-task safety battery (advbench, jailbreak, bbq, truthfulqa).
- Compute safety retention against FP16/Q8_0 baseline for each model.
- Flag any model-quant combination below 90% retention for immediate review.

**Days 8-14: enforce quantization policy**

- Set Q4_K_M as default quantization for all safety-sensitive deployments.
- Ban Q2_K for Llama-class 1B models. Require explicit risk acceptance for Q2_K on other models.
- Document model-specific safety profiles and store alongside deployment configs.

**Days 15-21: backend migration protocol**

- If backend migration is planned (Ollama <-> vLLM/TGI), run full safety evaluation on the target backend before cutover.
- Compare safety scores across backends. If delta exceeds 3pp, investigate chat template handling before proceeding.
- Create a backend migration safety checklist.

**Days 22-30: ongoing monitoring**

- Add jailbreak resistance (prefix injection + direct) to CI/CD safety gates for quantized models.
- Monitor Nationality-bias scores under quantization in production if applicable.
- Schedule quarterly re-evaluation when models, quant levels, or backends change.

---

## Risks, limitations, invalidation triggers

### Limitations

- **Two-model anchor set.** All cross-axis conclusions rest on Llama 3.2 1B and 3B. Adding models to the cross-axis analysis would improve confidence.
- **No factorial design.** Each TR varied one axis. Interaction effects (e.g., quantization x concurrency synergy) are not measured. The deployment matrix uses an additive model.
- **Automated scoring only.** Safety scores come from regex classifiers with poor LLM judge agreement (kappa = 0.147). Human annotation would improve confidence.
- **Temperature 0 only.** Stochastic sampling may interact differently with optimization axes.
- **Consumer hardware only.** Datacenter GPUs (A100, H100) may behave differently, especially for vLLM/TGI.
- **Small models only (<= 7.6B).** Larger models may show different quantization resilience.

### What invalidates this guidance

- Model family not in the tested set (Llama 3.2, Mistral 7B, Qwen 2.5) — re-profile
- Quantization method other than GGUF (e.g., GPTQ, AWQ) — different degradation profile
- Temperature > 0 — unknown interaction with safety under quantization
- Multi-GPU tensor parallelism — untested serving configuration
- Model size > 7.6B parameters — different redundancy characteristics
- Safety classifier change — scores are not absolute, they depend on the classifier

---

## Evidence anchors (audit-ready)

| Decision | Artifact | Validation |
|----------|----------|------------|
| Q4_K_M preserves >= 93% safety | `research/tr134/results/phase3/20260305_144827/phase3_analysis.json` | Per-model retention at Q4_K_M: 98.4% (Llama 1B), 93.8% (Llama 3B) |
| Concurrency is safety-neutral | `research/tr135/results/20260307_162151/tr135_analysis.json` | Max delta 0.4pp, all jailbreak slopes = 0.000 |
| No backend pair equivalent at +/-3pp | `research/tr136/results/20260308_015147/tr136_analysis.json` | 0/18 TOST tests pass |
| Q2_K is CRITICAL for Llama 1B | `research/tr137/results/20260308_180727/tr137_deployment_matrix.csv` | 57.5% retention, 3/3 Q2_K configs critical |
| I-squared = 99.9% on quant axis | `research/tr137/results/20260308_180727/tr137_analysis.json` | Heterogeneity pass, N=2 models |
| Prefix injection most effective jailbreak | `research/tr134/results/phase3/20260305_144827/phase3_analysis.json` | Slope = -0.036/BPW, steepest of 4 techniques |
| Nationality most vulnerable bias category | `research/tr134/results/phase3/20260305_144827/phase3_analysis.json` | Avg slope = -0.010/BPW across 4 models |
| Backend effect is chat template, not framework | `research/tr136/results/20260308_015147/tr136_analysis.json` | vLLM vs TGI d < 0.03; Ollama vs vLLM d = 0.60 |

---

## References

- Conclusive report: `PublishReady/reports/Technical_Report_Conclusive_134-137.md`
- TR134: `PublishReady/reports/Technical_Report_134.md` (Alignment Under Quantization)
- TR135: `PublishReady/reports/Technical_Report_135.md` (Concurrency x Safety)
- TR136: `PublishReady/reports/Technical_Report_136.md` (Cross-Backend Safety)
- TR137: `PublishReady/reports/Technical_Report_137.md` (Safety Tax Synthesis)
- Prior phase whitepaper: `PublishReady/reports/Technical_Report_Conclusive_123-133_Whitepaper.md`

---

## Optional upgrades (board-ready polish)

- Add a 1-page Safety Decision Card: the six-row matrix + boundary conditions + three invalidation triggers.
- Add a safety degradation heatmap (model x quant x task) as a visual summary.
- Add a Cost-Safety Pareto chart: plot $/token savings vs safety retention for each quant level.
- Add a Change Control clause: any model, backend, or quantization change triggers re-run of the safety profiling battery.
- Commission human annotation study (500 samples at FP16, Q4_K_M, Q2_K) to calibrate automated classifiers.
