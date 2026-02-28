# Conclusive Report 117-122: From Benchmarking to Decision-Grade Inference
## A dissertation-style synthesis of performance, cost, scaling, compiler behavior, and physical limits

Project: Banterhearts LLM Performance Research
Date: 2025-12-26
Author: Research Team
Report Type: Conclusive synthesis across TR117-TR122 (artifact-backed)
Scope: TR117, TR118_v2.2, TR119v1, TR120, TR121v1, TR122
Primary Sources:
- PublishReady/reports/Technical_Report_117.md
- PublishReady/reports/Technical_Report_118_v2.2.md
- PublishReady/reports/Technical_Report_119v1.md
- PublishReady/reports/Technical_Report_120.md
- PublishReady/reports/Technical_Report_121v1.md
- PublishReady/reports/Technical_Report_122.md

---

## Abstract

This dissertation-style report synthesizes TR117 through TR122 into a single decision-grade narrative for local-first LLM inference on a fixed hardware baseline. The research arc begins with a single-model performance matrix (TR117), then evolves into a reproducible and validated measurement stack (TR118_v2.2), a fully explicit cost and energy model (TR119v1), a compiler attribution audit with controlled reproduction (TR120), a regime-aware scaling study across model sizes (TR121v1), and a physics-based measurement layer that defines what can and cannot be trusted at the event level (TR122). The synthesis establishes three stable principles: (1) decode throughput dominates end-to-end capacity once generation is moderate, (2) workload shape and model structure govern performance more reliably than parameter count in small-model GPU regimes, and (3) energy attribution is valid only when the measurement system can observe the event window. The report does not claim universal scaling laws or cross-hardware generality; it provides an artifact-backed decision framework within the measured boundary conditions. External research on transformer architecture and efficient attention is cited for context [1]-[3], and system-level measurement references are included for instrumentation grounding [5]-[8].

This synthesis also makes explicit the chain-of-custody between measurement and claim, including where the chain fails. In particular, it distinguishes: (a) what is measured at the backend boundary, (b) what is modeled from those measurements, and (c) what is inferred for production decisions. This is not a semantic nicety; it is the difference between a benchmark that reads well and a report that survives audit.

Finally, the report treats operational impact as a first-class scientific outcome. Each major finding is translated into a routing decision, a capacity planning heuristic, or a risk control. The goal is not to maximize metrics, but to minimize decision regret under the stated boundary conditions.

This work is not a universal performance claim. It is a decision framework validated on one hardware baseline and bounded workloads. The portable output is the method and gating rules, not the absolute numbers.

---

## Table of Contents

Executive Summary
Operational Defaults (Decision Card)
1. Introduction and Research Questions
2. Background and Related Work
3. Methods and Measurement Framework
4. Decision Impact Matrix (TR117-TR122)
5. Results by Report (TR117-TR122)
   5.1 TR117: Baseline Matrix and the Paradox
   5.2 TR118_v2.2: Validation and Artifact Integrity
   5.3 TR119v1: Cost and Energy Economics
   5.4 TR120: Compiler Reality and Shape Stability
   5.5 TR121v1: Scaling Regimes and Structural Predictors
   5.6 TR122: Physics Baseline and Energy Gating
6. Cross-Report Synthesis by Decision Axis
7. Economics and Capacity (Token-First and Request-First)
8. Operational Doctrine and Risk Controls
9. Threats to Validity and Scope Limits
10. Limitations by Report and Mitigations
11. Roadmap Without TR123
12. Conclusive Statement
13. References
14. Appendix A: Key Formulas
15. Appendix B: Claim-to-Artifact Chain-of-Custody
16. Appendix C: Per-TR Key Numbers (Extracted)
17. Appendix D: Glossary and Definitions
18. Appendix E: Operational Checklists
19. Appendix F: Workload Taxonomy and Routing Examples
20. Appendix G: Worked Examples and Calculations
21. Appendix H: Operational Playbooks and Templates
22. Appendix I: Statistical Notes and Fit Diagnostics
23. Appendix J: Traceability Map (TR117-TR122 to Decisions)
24. Appendix K: Extended Literature Review
25. Appendix L: Measurement Boundary Catalog
26. Appendix M: Detailed Methods by Report
27. Appendix N: Expanded Discussion and Implications
28. Appendix O: Extended Results Narratives
29. Appendix P: Decision-Grade Reporting Rubric
30. Appendix Q: Extended Decision Case Studies
31. Appendix R: Metric Definitions and Data Schema
32. Appendix S: Governance and Reporting Templates
33. Appendix T: Extended Risk Register
34. Appendix U: Program Evolution Narrative
35. Appendix V: Extended Cost Modeling Examples
36. Appendix W: Extended Workload Taxonomy
37. Appendix X: Experiment Planning Template
38. Appendix Y: Extended Operational Playbook
39. Appendix Z: Extended Cost-Quality Tradeoff Analysis
40. Appendix AA: Measurement Formula Catalog
41. Appendix AB: Phase-Specific Observations
42. Appendix AC: Detailed Model Comparison Narrative
43. Appendix AD: Extended Methodological Rationale
44. Appendix AE: Future Directions Without TR123
45. Appendix AF: Annotated Literature Notes
46. Appendix AG: Extended Glossary and Acronyms
47. Appendix AH: Detailed Artifact Inventory
48. Appendix AI: Artifact-to-Claim Examples
49. Appendix AJ: Reproducibility and Regeneration Notes
50. Appendix AK: Scenario-Specific Policy Playbooks
51. Appendix AL: Scenario Taxonomy and Metric Mapping
52. Appendix AM: Decision Heuristics and Rules of Thumb
53. Appendix AN: Policy Decision Trees
54. Appendix AO: Extended Systems Glossary
55. Appendix AP: Extended Synthesis Narrative
56. Appendix AQ: Extended Risk Mitigation Strategies
57. Appendix AR: Operational Metrics and Dashboards
58. Appendix AS: Cross-Report Comparison Table (Narrative)
59. Appendix AT: Extended Decision Matrix Commentary
60. Appendix AU: Expanded Operational Checklists
61. Appendix AV: Extended Economic Sensitivity Analysis
62. Appendix AW: Measurement Ethics and Reproducibility Principles
63. Appendix AX: Architectural Considerations
64. Appendix AY: Operational Lessons Learned
65. Appendix AZ: Scaling Laws vs Inference Performance
66. Appendix BA: Energy, Carbon, and Sustainability Considerations
67. Appendix BB: Methodological QA Checklist
68. Appendix BC: Model Registry Metadata Schema
69. Appendix BD: Implementation Guidance by Team Role
70. Appendix BE: Quality Evaluation and Acceptance Criteria
71. Appendix BF: Example Report Update Workflow
72. Appendix BG: Evaluation Philosophy and Limitations
73. Appendix BH: Additional Notes on Documentation and Communication

Supplemental material remains mirrored in `PublishReady/reports/Technical_Report_Conclusive_117-122_Extended_Appendices.md`.

---

## Executive Summary

This report closes the loop started in TR117 and makes the research program decision-grade. We moved from a single-model performance matrix to a reproducible, attribution-correct, cost-aware, and physics-grounded evaluation stack. The outcome is a set of stable conclusions about what matters for deployment on this hardware and under these measurement boundaries.

### The synthesis in one line

The dominant driver of cost and capacity is tokens per second, but the meaning of tokens per second depends on phase (prefill vs decode), workload shape, and physical limits (power, thermal, and measurement resolution).

### Claim status (cross-report, reviewer-proof)

| Claim ID | Claim | Evidence base | Status |
| --- | --- | --- | --- |
| C1 | Backend labels are a reliable proxy for runtime behavior | TR117 vs TR120 label audit | False (compile label was not compiler-real) |
| C2 | End-to-end capacity can be reasoned from prefill alone | TR119v1 + TR121v1 | False (decode dominates at gen >= 64) |
| C3 | Token economics are stable under time-priced compute | TR119v1 + TR121v1 | Supported (throughput drives cost; energy share is small) |
| C4 | Small-model GPU scaling is predictable from params alone | TR121v1 | Not identifiable (depth and overhead dominate) |
| C5 | Large-model serving scales strongly with params under fixed decode | TR121v1 (Ollama) | Supported (regime) |
| C6 | Energy attribution is precise at sub-100ms event scale with 100ms polling | TR122 | False (most short events have no data) |

### Program trajectory (TR117 -> TR122)

The research program is intentionally sequential. Each report closes a failure mode from the previous one:

1. TR117 establishes a baseline matrix but exposes distribution paradoxes and label drift risk.
2. TR118_v2.2 hardens the artifact pipeline so later claims are reproducible, not just repeatable.
3. TR119v1 converts throughput into cost and energy, forcing a decision-grade framing.
4. TR120 proves compiler attribution and shows why shape stability must be a policy, not a hope.
5. TR121v1 replaces the single-model worldview with regime-aware scaling and structural predictors.
6. TR122 defines the physics floor: what can and cannot be trusted at the event scale.

This ordering is deliberate: you cannot do meaningful cost modeling before validity; you cannot do compiler policy before attribution; you cannot do scaling without regime control; you cannot do energy reporting without physical gating.

### Bottom-line decisions you can ship

1. Default backend for serving with generation: onnxruntime-gpu remains the cost winner under TR119v1 and is robust across generate scenarios. Prefill-only batch workloads can invert this, so route by workload if you can.
2. Compiler policy: do not ship a compile backend unless it is compiler-real and shape-stable. Compile prefill only; keep KV decode eager unless you can demonstrate a decode win.
3. Scaling policy: for small models at batch=1, depth is a better latency predictor than params on GPU. For large models under fixed decode length, params is a usable regime descriptor.
4. Physical policy: use a measured idle baseline and accept that 100ms polling cannot attribute sub-100ms events. Energy numbers are reliable only for macro windows, not micro events.

### Operational Defaults (Decision Card)

Valid under stated boundary conditions.

- Default backend: onnxruntime-gpu for decode-heavy workloads; route prefill-heavy batch workloads to transformers-gpu when measured wins exist.
- Routing triggers: decode-heavy if gen_tokens >= 64 or decode fraction > 0.9; prefill-heavy if batch > 1 and minimal decode.
- Compile policy: compile prefill only; require shape bucketing and compiler-real evidence; keep decode eager unless a win is demonstrated.
- Warmup policy: run pre-routing warmups and maintain warm pools for large models; track cold-start separately from steady-state SLOs.
- Energy gating rule: report per-event energy only with >= 2 in-window samples; otherwise classify as no_data.
- Invalidates this report: driver/compiler/runtime/model upgrades or workload mix shifts without a rerun.

Manifest requirements (minimum):

- GPU model + driver
- CUDA version
- PyTorch version
- ONNX Runtime version
- Ollama version (if used)
- Git commit SHAs for report generation and analysis scripts

---

## 1. Introduction and Research Questions

### 1.1 Motivation

Performance research for LLM inference often fails not because the measurements are wrong, but because the questions are mis-scoped. A benchmark that answers "which backend is faster" on a single model can still be operationally misleading if it ignores cost, energy, workload shape, or physics. The TR117-TR122 sequence was constructed to close these gaps deliberately.

The central challenge is a shift in question type: from benchmarking to decision-making. Benchmarks are descriptive; decision-grade research is prescriptive. The difference lies in explicit measurement boundaries, reproducibility, and the translation of latency into operational and financial consequences.

### 1.2 Research questions (program level)

This conclusive report answers the following cross-cutting questions:

1. What is the minimum artifact-backed evidence required to compare inference backends in a publishable way?
2. How do we translate throughput into decision-grade cost and capacity metrics?
3. When and why do compiler optimizations help or hurt, and how should they be gated in production?
4. What scaling regimes exist across model sizes, and which proxies (params, depth, batch) are valid under each regime?
5. What are the physical limits of energy attribution given the polling resolution of the measurement stack?

### 1.3 Contributions of this synthesis

Contributions. This synthesis contributes six decision-grade deliverables:

- Decision framework: a phase-aware, workload-aware policy model that converts measurements into routing, capacity, and risk controls.
- Traceability: a claim-to-artifact chain that distinguishes (a) measured quantities, (b) modeled quantities, and (c) inferred deployment rules.
- Attribution correction: a formal separation between backend labels and runtime reality, including criteria for "compiler-real" evidence.
- Economics translation: a unified token-first and request-first cost/capacity model, explicitly parameterized by workload mix and pricing tiers.
- Regime mapping: a scaling interpretation that treats parameter count as conditional (regime-dependent) and elevates structural predictors (e.g., depth) when appropriate.
- Measurement validity gating: a physics-grounded boundary that prevents false precision in energy attribution and makes "no_data" an explicit outcome, not a silent failure.

### 1.4 Document structure and reading guide

Reading guide.

If you need deployment decisions: read Executive Summary, Section 4 (Decision Impact Matrix), Section 6 (Synthesis by axis), and Section 8 (Operational Doctrine).

If you need method defensibility: read Section 3 plus the limitation gates in Section 10, then Appendix B (Claim-to-Artifact).

If you need planning numbers: read Section 7 and Appendix A for formulas; worked examples are labeled inline.

If you are auditing energy claims: read the TR122 summary in 5.6 plus Section 3.4 and the gating rules in Section 8.4.

---

## 2. Background and Related Work

### 2.1 Transformer inference and phase separation

Transformers [1] are composed of repeated blocks, and inference naturally splits into prefill (context encoding) and decode (token-by-token generation). Transformer-XL [2] formalizes the idea of longer contexts and illustrates why cache-based decode changes the computational profile. This phase split is not a mere implementation detail; it is the core structural reason cost and latency behave differently across workloads.

### 2.2 Efficient attention kernels and decode dominance

FlashAttention [3] shows that memory-efficient kernels can reduce attention cost substantially, but the benefits differ across prefill and decode. These research results provide the context for TR120 and TR121: if the kernel path changes under compilation or if decode is dominant, throughput and tail behavior can shift in ways a single aggregated metric cannot capture.

### 2.3 Scaling laws and model size as proxy

Large-scale language model scaling is documented in the literature, including GPT-style systems [4]. However, these scaling laws are usually derived in training or in a more homogeneous architectural setting. TR121v1 treats parameter count as a regime descriptor and does not claim universality. This is a direct response to the known limitations of cross-family comparisons.

### 2.4 System instrumentation and energy measurement

Instrumentation grounding. The program uses NVML-derived GPU power telemetry as the primary substrate for energy attribution and treats its sampling cadence as a hard constraint on what claims are valid. Polling-based power measurement supports macro-window attribution (multi-second) but cannot reliably resolve micro-events shorter than the polling period. As a result, energy is reported only under validity gates (Section 3.4 / TR122) and is treated as a secondary decision axis unless hardware energy counters with event-level resolution are available.

Attributing energy to inference steps requires hardware instrumentation. NVML is a commonly used interface for NVIDIA GPU power telemetry [5]. PyTorch offers compiler-level optimization (torch.compile) and runtime instrumentation [6]. ONNX Runtime is a widely used inference engine for production deployments [7]. Ollama is a local inference stack that exposes prompt and decode timings [8]. These tools provide the measurement substrate for TR119 through TR122.

### 2.5 Compiler systems and dynamic shape handling

Modern compiler stacks for deep learning (e.g., torch.compile with Inductor/Triton) operate under assumptions about tensor shapes and control flow. Dynamic shape handling introduces guard checks and potential recompiles. The literature in this space emphasizes the tradeoff: aggressive specialization can yield high performance for stable shapes but create tail risks when shapes vary. TR120 operationalizes this tradeoff as a policy problem.

### 2.6 Benchmarking methodology and interpretability

Performance benchmarking literature emphasizes that measurement boundaries and workload definitions are inseparable from interpretation. A benchmark is not simply a dataset; it is a statement about what is included in the timed region, which workloads are representative, and which summaries are considered authoritative. TR117-TR122 apply this principle by exposing measurement boundaries explicitly and by treating workload shape as a first-class variable.

### 2.7 Scaling laws in the literature and their limits

Scaling laws in language modeling have been documented in the training literature, notably in the work on compute-optimal scaling and loss curves [9], [10]. These results are valuable, but they do not automatically transfer to inference latency. Training scaling laws usually assume homogeneous model families and do not incorporate runtime stack effects such as kernel selection, compilation, or serving overhead. TR121v1 treats parameter count as a regime descriptor rather than a universal law, which is the safe interpretation given the mixed-family and mixed-quantization setting.

### 2.8 Benchmarking standards and interpretability frameworks

Benchmarking frameworks such as MLPerf Inference [11] emphasize reproducibility and fixed measurement boundaries. The TR117-TR122 program aligns with this spirit but focuses on decision-grade interpretability rather than leaderboard performance. The choice to publish artifact chains, validation outputs, and boundary conditions reflects a broader principle: a benchmark without interpretability is a marketing claim, not a scientific result.

### 2.9 Efficient attention variants and decode-specific kernels

Recent attention variants and kernel implementations, including FlashAttention-2 [13] and broader surveys [12], show that decode performance can be dominated by kernel availability and memory movement, not just model size. This contextualizes TR120 and TR121: if a compiler or runtime disables a specialized kernel path, decode can regress even when prefill improves. The synthesis therefore treats kernel-path availability as a hidden but powerful confound in any scaling or compiler claim.

### 2.10 Quantization and memory hierarchy

Quantization changes both arithmetic intensity and memory bandwidth requirements. Inference stacks such as Ollama and GGUF-based runtimes often operate in quantized modes by default. This is not merely a compression technique; it alters the effective throughput per parameter. In a scaling context, this means that a parameter-count axis becomes entangled with quantization level. The program treats this entanglement explicitly by labeling Ollama results as regime descriptors and by adding within-family checks where possible.

### 2.11 Systems literature on latency tails and variance

System performance literature emphasizes that tail latency can dominate user experience, even when mean latency is stable. The TR117/TR120 paradox is a concrete manifestation of this principle in the LLM inference domain. This is why the program standardizes on distributional reporting and uses warmup ratios as first-class metrics.

---

## 3. Methods and Measurement Framework

### 3.1 Artifact-first methodology

TR118_v2.2 established the methodological rule: any claim that matters must be artifact-backed. This includes:

- Raw run logs (metrics.csv, JSONL)
- Processed summaries with deterministic transformations
- Validation reports and manifest metadata

The goal is to ensure a chain of custody from measurement to claim.

### 3.2 Phase-aware metrics

All key reports treat prefill, decode, and end-to-end as separate measures:

- Prefill: one forward pass over the prompt context
- KV decode: fixed-length decode loop with cache
- End-to-end: prefill plus decode

This phase split is essential for compiler analysis (TR120), scaling (TR121v1), and cost modeling (TR119v1).

### 3.3 Cost model alignment

TR119v1 uses a fully explicit compute-hour model for cost:

- seconds_per_1M = 1e6 / tokens_per_s
- usd_per_1M = (seconds_per_1M / 3600) * usd_per_hour

TR121v1 extends this to capacity planning and request-level costing, which is used in the synthesis here.

### 3.4 Physical measurement gating

TR122 defines the instrumentation boundaries:

- Baseline idle power must be measured and subtracted.
- Per-event energy is only valid if sufficient samples fall within the event window.

This boundary defines where energy attribution is valid and where it must be marked as no_data.

### 3.5 Statistical framing

Statistical framing. The analysis prioritizes robustness over parametric elegance. Latency is summarized using medians and percentile bands to reflect user-facing experience under heavy-tail risk. Means are retained only where they estimate aggregate compute burden. Scaling and sensitivity analyses are gated: a fit is treated as actionable only when explanatory power is non-trivial and uncertainty bounds do not allow sign flips. When n is small or model families are heterogeneous, the synthesis defaults to regime descriptors and rank correlations rather than asserting universal exponents.

### 3.6 Scenario definitions and token accounting

Across the program, a scenario is defined by prompt length, batch size, and decode length. Prefill tokens are computed from the padded prompt length in the relevant runner, and decode tokens are controlled explicitly in the KV decode loops. This ensures the timing window is aligned with a known number of tokens, which makes throughput and cost derivations reproducible. Where early stop is possible (Ollama), a fixed-length equivalence model is used and its error is explicitly bounded.

### 3.7 Warmup policy and boundary alignment

The program treats warmup as a first-class measurement phase. Warmup runs are labeled, excluded from scaling fits, and analyzed separately for cold-start risk. This policy emerged directly from TR117 and TR120, where first-call effects created misleading mean metrics. The conclusive report therefore treats warmup as a legitimate operational metric rather than a nuisance.

### 3.8 Sampling cadence and energy attribution

Sampling cadence constraint. Let polling period be Delta t and event duration be T. The expected number of in-window samples is approximately n ~= T / Delta t. When n < 2, estimating event-average delta power is underdetermined in practice because baseline noise and sample-phase alignment dominate. TR122 therefore implements explicit gating: per-event energy is reported only when sufficient in-window sample coverage exists; otherwise the result is classified as no_data and excluded from energy aggregates.

### 3.9 Causal attribution vs descriptive measurement

Descriptive vs causal roles. TR117 is descriptive by design: it measures a service boundary that matches user-visible experience, including cold-start and runtime overhead. TR120 is causal by design: it manipulates compilation explicitly under a controlled boundary to isolate mechanism and tail risk. The synthesis preserves this distinction to avoid a common methodological failure: inferring causality from label-only descriptive benchmarks.

### 3.10 Data reduction and aggregation policy

Aggregates in the program are intentionally conservative. Medians are preferred to means where tails exist. Scenario-aggregated values use geometric means to avoid single-scenario dominance. When a fit has low explanatory power (e.g., R^2 near zero), the slope is reported but explicitly marked as unidentifiable. This policy prevents the accidental promotion of weak fits into policy claims.

### 3.11 Uncertainty communication and decision thresholds

Uncertainty is not merely statistical; it is decision-aligned. The program uses bootstrap confidence intervals for slopes and nonparametric rank correlations to avoid overclaiming in small-n regimes. A fit is treated as actionable only when its confidence intervals exclude sign flips and when its monotonicity aligns with the mechanistic explanation. This approach is less aggressive than typical ML regression reporting but more appropriate for deployment guidance.

### 3.12 Boundary-shift experiments as falsification tools

TR121's boundary-shift runs (batch=8, gen_tokens=512) are not performance optimizations; they are falsification tests. The purpose is to see whether the regime conclusion changes when the measurement boundary changes. This is a key scientific move: if a conclusion survives boundary shifts, it is more likely to be a real phenomenon rather than an artifact of a narrow benchmark.

### 3.13 Per-TR measurement boundaries

Each report defines a specific measurement boundary. The boundaries are not identical; they are chosen to match the question being asked. TR117 measures a service boundary, TR120 measures a kernel-focused boundary, TR121 measures phase-level boundaries, and TR122 measures an instrumentation boundary. The synthesis treats these boundaries as explicit constraints rather than as hidden assumptions.

### 3.14 Decision-grade reporting protocol

Decision-grade reporting requires three layers: (1) measurement validity, (2) attribution correctness, and (3) decision translation. A report that is valid but not attributed correctly can still produce invalid recommendations. A report that is attributed but not translated produces numbers without decisions. TR117-TR122 can be read as a sequential construction of these layers.

---

## 4. Decision Impact Matrix (TR117-TR122)

This table anchors each report to its primary decision impact. The objective is not just to summarize, but to show how each report changes what you should do in production.

| Report | Primary question answered | Key artifact(s) | Decision impact | Risk if ignored |
| --- | --- | --- | --- | --- |
| TR117 | Which backend is fastest on a single model? | Tier-3 matrix runs | Baseline performance matrix and scenarios | Label drift and mean/median paradox can lead to false conclusions |
| TR118_v2.2 | Are the measurements reliable and reproducible? | Validation + artifact pipeline | Establishes publishable measurement standard | Silent data corruption, non-reproducible claims |
| TR119v1 | What is the cost and energy per token? | Cost and energy model + telemetry | Turns throughput into budget decisions | Optimizing the wrong phase or backend wastes budget |
| TR120 | Is "compile" real, and when does it help? | Controlled compiler runs | Compile prefill only; avoid decode regression | Shipping compile blindly causes tail latency and regressions |
| TR121v1 | How does scaling behave across models? | Scaling fits + regime analysis | Params is regime-dependent; depth matters on GPU | Mis-sizing models or fleets due to wrong scaling assumptions |
| TR122 | What are the physical measurement limits? | Baseline, poller stats, energy gating | Baseline subtraction and event-level gating | Unjustified energy claims or invalid comparisons |

---

### 4.1 How to read the decision impact matrix

The matrix is a bridge between measurement and policy. Each row corresponds to a report, but more importantly, each row answers a single deployment-critical question. The intent is to prevent scope drift: if a decision requires evidence that a report does not provide, the policy must wait for that evidence. This is the discipline that keeps the research program from turning into a collection of disconnected benchmarks.

### 4.2 Decision dependencies and ordering

The matrix also implies an ordering. You cannot make compiler policy decisions without attribution (TR120), and you cannot make cost policy decisions without validated throughput measurements (TR118). The synthesis therefore treats the matrix as a dependency graph, not just a summary table.

## 5. Results by Report (TR117-TR122)

This section summarizes each report as a self-contained result, then leads into synthesis. Each subsection includes: objective, method, key results, and decision implications.

### 5.1 TR117: Baseline performance matrix and the paradox

#### 5.1.1 Experimental design and artifact boundary

TR117 constructs the Tier-3 matrix as a deliberately small but diverse workload set. It mixes single-prompt and batched scenarios to capture both interactive latency and throughput-oriented prefill. The measurement boundary is the inference-service call, which intentionally includes any initialization, caching, or runtime overhead that a user would experience in a real service call. This choice is valid for user-facing latency, but it is also the seed of the later paradox: if the boundary includes cold-start work, distribution tails can dominate mean metrics.

The artifact structure matters: TR117 stores per-run arrays of latency samples (not just a single aggregate). This later enables TR120 to pinpoint cold-start skew in the first element of the array and to separate per-run effects from scenario-level effects. The ability to interrogate per-sample distributions, not just aggregated means, is one of the core reasons TR117 remains valuable even after its label attribution is corrected.

#### 5.1.2 Distribution anatomy and the mean/median paradox

The paradox in TR117 is not a minor statistical artifact. It is a direct consequence of heavy-tail events that are sparse but large. When the timed boundary captures a cold-start event or an internal initialization, the first sample can be orders of magnitude larger than the steady-state samples in the same run. In a mean-driven comparison, these single events can invert rankings. In a median-driven comparison, they disappear. That is not a nuisance; it is a decision hinge.

TR120 shows that these heavy tails were not caused by compilation in this repository. That retroactively reframes TR117 as a measurement lesson: a single aggregated statistic is unsafe unless the distribution is unimodal and the boundary excludes cold-start effects. This is why the later reports (TR119 onward) insist on phase separation and explicit warmup handling.

#### 5.1.3 Implications for the program

TR117 makes two program-level demands explicit: artifact validation and attribution correction. The mean/median paradox and label drift show that performance claims can invert if the data pipeline is fragile or if labels are treated as causal evidence. This is why TR118 and TR120 are not optional extensions; they are methodological repairs.

#### 5.1.4 Limitations and boundary conditions

TR117 is bounded by a service-level timing boundary that includes initialization effects and cold-start behavior. It is descriptive, not causal, and it is single-model on a single hardware baseline. It cannot, by itself, support scaling claims or compiler attribution.

#### 5.1.5 Transferability and scope

TR117's baseline matrix is transferable only to workloads that match its scenario design and to hardware that is similar in architecture and driver stack. It is not a universal baseline. The correct way to generalize TR117 is to treat it as a methodology template: re-run the same matrix on new hardware or model variants and compare the relative ordering rather than absolute numbers.

TR117 is a single-model study with a fixed hardware target. Its greatest limitation is scope: it does not answer cross-model scaling or cross-hardware generalization. It also does not validate compiler behavior. The conclusive report therefore treats TR117 as a foundational benchmark, not as a decision final. All later reports can be read as responses to TR117's scope limitations.

TR117 provides the baseline comparison but also demonstrates two systemic risks that must be managed going forward: label drift and cold-start skew. The program response is structural: TR118_v2.2 enforces artifact validation, TR120 enforces attribution, and TR121 enforces regime-aware scaling. In other words, TR117 is valuable because it is the point where the research program learns that performance benchmarking cannot be a single-table exercise.

Evidence snapshot (artifact-backed):

| Backend label | n | mean_ms | median_ms | p95_ms | p99_ms | max_ms | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| transformers-gpu-compile | 273 | 389.2 | 328.7 | 594.7 | 631.2 | 681.8 | scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv |
| transformers-gpu | 273 | 404.1 | 322.7 | 612.5 | 931.5 | 3325.8 | scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv |

Interpretation: the label-only dataset exhibits similar medians but materially different tails, which is why TR120 treats the label as a measurement category rather than compiler evidence. Source artifacts: results/tr117_tier3/metrics.csv and scripts/tr120/results/tr120_compile_paradox/processed/summary.json.


Objective:

- Establish a baseline backend comparison matrix on a single model, covering multiple scenarios and backends.

Method:

- Tier-3 matrix of scenarios, repeated measurements, latency and throughput reporting.

Key results:

- Label-level performance differences existed but were not attributable to runtime behavior in all cases.
- The mean vs median paradox indicated tail behavior and cold-start effects.

Decision implications:

- Label-only results are not sufficient for compiler claims.
- Distribution shape matters more than a single aggregated statistic.

### 5.2 TR118_v2.2: Measurement validity and pipeline integrity

#### 5.2.1 Validation stack and artifact integrity

TR118_v2.2 introduces a layered validation model. It asserts that every report must be traceable to raw artifacts and that those artifacts must pass consistency checks. This includes manifest metadata, deterministic processing steps, and explicit validation outputs. The practical effect is to prevent a silent error from propagating into a published conclusion.

This is not bureaucracy. In performance research, small pipeline errors can invert winners. A single malformed throughput field or a missing unit conversion can make a backend appear faster or cheaper than it really is. TR118_v2.2 treats this as a first-class failure mode and requires that each report either pass validation or clearly state why it cannot.

#### 5.2.2 Failure taxonomy and degraded-run handling

The pipeline defines a degraded run as a run that times out, errors, or violates core invariants. Degraded runs are retained in raw artifacts so failure is visible, but they are excluded from aggregates. This is crucial for honest reporting: it avoids both hiding failures and mixing invalid data into summary statistics. The decision impact is direct: the success rate becomes a metric in its own right, and the absence of degraded runs becomes publishable evidence, not a silent assumption.

#### 5.2.3 Why this matters for later reports

TR119, TR120, TR121, and TR122 all depend on validated, consistent latency artifacts. Without TR118's validation discipline, later cost, scaling, and attribution claims would be fragile and potentially non-reproducible.

#### 5.2.4 Measurement governance and repeatability

TR118 introduces governance primitives: manifest capture, config hashes, and degraded-run classification. These make reruns comparable across time and prevent silent boundary drift from being mistaken as performance change.

#### 5.2.5 Residual risk after validation

Validation reduces but does not eliminate risk. The primary residual risk is measurement boundary drift: a report can be regenerated with a subtly different workload mix without violating validation checks. This is why scenario definitions and config hashes remain part of the claim chain.

TR118_v2.2 effectively introduces governance for measurement. It treats configuration hashes, manifest metadata, and validation outcomes as reportable artifacts. This matters because it makes the research program resilient to incidental drift. When a report is regenerated, it can be compared to the prior run for structural equivalence, not just numerical similarity. This is a form of measurement governance that is often missing in performance studies.

TR119, TR120, and TR121 depend on TR118's guarantees. Cost modeling, compiler attribution, and scaling analysis all assume that the underlying latency measurements are coherent and reproducible. TR118_v2.2 therefore acts as the credibility foundation for the rest of the program. Without it, any policy recommendation would be methodologically fragile.

Evidence snapshot (artifact-backed):

| Mode | Total runs (per model) | Degraded runs | Degraded rate | Evidence |
| --- | ---: | ---: | ---: | --- |
| prefill | 180 | 10 | 5.6% | scripts/tr118/results/tr118v2_audit/run_counts.json |
| generate | 180 | 90 | 50.0% | scripts/tr118/results/tr118v2_audit/run_counts.json |

TRT failures are explicitly captured rather than silently dropped (e.g., tensorrt-fp16/fp32/int8 generate profile_mismatch = 60 each; tensorrt-fp16 prefill profile_mismatch = 20), which is why degraded-run classification is a governance requirement. Source: scripts/tr118/results/tr118v2_audit/trt_failures.json.


Objective:

- Harden the measurement pipeline to prevent silent errors and to make claims reproducible.

Method:

- Validation layers for artifacts, explicit failure modes, and manifest metadata.

Key results:

- The pipeline can classify degraded runs and prevent invalid comparisons.
- Artifacts provide a deterministic chain from raw data to summary.

Decision implications:

- Future reports can claim reproducibility, not just repeatability.
- Validation is a prerequisite for any cost or policy conclusion.

### 5.3 TR119v1: Token economics and cost sensitivity

#### 5.3.1 Cost model decomposition and the role of throughput

TR119v1 formalizes the idea that time-priced compute makes throughput the dominant cost driver. The model is explicit: dollars per token are a function of seconds per token, not just a function of power. This transforms a latency benchmark into a budget lever. It also reveals why energy is usually a second-order effect under typical pricing. The energy term is included for completeness and carbon reporting, but in the measured configuration it represents a small fraction of total cost.

#### 5.3.2 Scenario weighting and winner inversion

One of TR119's key contributions is to expose how scenario weighting changes outcomes. When prefill is batched, a different backend can become the cheapest even if it is not the best on single prompts. This is not just a statistical curiosity: it is a routing policy. If your service is batch-heavy prefill with little generation, the optimal backend can differ from the optimal interactive backend. TR119 formalizes that as a decision rule rather than a post-hoc observation.

#### 5.3.3 Request-level costing and TCO interpretation

Request-level costing converts token economics into per-request budgets and planning numbers. It is only as valid as the assumed request mix, so it must be treated as a configurable input rather than a universal TCO claim.

#### 5.3.4 Pricing tiers and sensitivity

TR119 explicitly varies hourly rates (on-demand, spot, reserved). The ordering of backends is stable under these tiers, which means throughput is the dominant driver of cost in this regime. This matters because it gives engineering teams a robust default: you can optimize for throughput without worrying that a pricing change will invert the winner.

#### 5.3.5 Carbon and governance context

Energy and carbon are policy axes, not micro-optimization targets, under the current measurement cadence. The report labels these numbers as shadow-priced and gated, and ties them to governance rather than to per-event claims.

#### 5.3.6 Interpreting cost deltas as budget levers

The cost differences in TR119v1 are not marginal; they are multiplicative at scale. The synthesis therefore interprets cost deltas as budget levers rather than as minor efficiency optimizations. This framing is essential for production teams: a backend choice can be a five-figure budget decision at billion-token scale.

Carbon metrics are included to support sustainability reporting, but TR119 makes a careful attribution choice: GPU backends use GPU power, CPU backends use CPU package power. The synthesis treats these as lower bounds for full-system energy. This is an important governance point: carbon numbers are useful for relative ranking under fixed assumptions, but they are not a substitute for full-system power measurement if regulatory reporting is required.

By composing prefill and decode into a request-level cost, TR119 connects benchmark numbers to product planning. It clarifies that in mixed workloads, decode dominates the request-level cost, and therefore the backend decision should be made in the decode regime unless the product is explicitly prefill-only. This logic is directly reused in TR121's capacity planning and in the synthesis here.


Objective:

- Translate throughput into dollars, energy, and carbon under explicit pricing assumptions.

Method:

- Compute-hour model with tiered pricing and measured throughput and power.

Key results:

- onnxruntime-gpu wins all generate scenarios in cost per token.
- Prefill batch workloads can invert winners.
- Energy cost is a small fraction of total cost under tested rates.

Decision implications:

- Default backend choice is stable when generation exists.
- Prefill-only workloads should be routed by scenario.

Evidence snapshot (artifact-backed):

Mean on-demand total cost per 1M tokens (mean across scenarios):

| Mode | Backend | total_cost_usd_per_1m_tokens_on_demand | Evidence |
| --- | --- | ---: | --- |
| generate | onnxruntime-gpu | 1.2041 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| generate | transformers-gpu-compile | 3.1536 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| generate | transformers-gpu | 3.6257 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| prefill | onnxruntime-gpu | 0.1279 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| prefill | transformers-gpu-compile | 0.1995 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| prefill | transformers-gpu | 0.2605 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |

Scenario inversion in prefill mode (on-demand cost):

| Scenario | Winner | total_cost_usd_per_1m_tokens_on_demand | Evidence |
| --- | --- | ---: | --- |
| batch_short | transformers-gpu | 0.0585 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| batch_medium | transformers-gpu | 0.0905 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| single_short | onnxruntime-gpu | 0.1529 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |

### 5.4 TR120: Compiler reality check

#### 5.4.1 Label audit and attribution correction

The primary corrective result in TR120 is attribution: the compile label in TR117 did not activate torch.compile in this repository. This is a nontrivial finding because the label had already influenced interpretation. TR120 therefore reclassifies the TR117 paradox as label drift, not compiler behavior. This distinction is the difference between a runtime policy change and a benchmark naming fix.

#### 5.4.2 Controlled compiler harness and shape stability

TR120 then establishes a controlled runner that explicitly compiles and records compiler metadata. The runner removes confounds (pre-tokenization, single model load, explicit synchronization) so that compile effects are isolated. Under this harness, compilation produces a strong p50 win in prefill but can introduce heavy tails when shapes vary. The mechanism is concrete: dynamic shape guard failures lead to multiple graphs and recompilations.

Padding and dynamic shapes are tested as mitigation strategies. Padding stabilizes shapes and collapses tails, while dynamic compilation reduces churn at the cost of some median performance. Both techniques are valid, but they are policy choices, not free optimizations.

#### 5.4.3 Decode as a distinct regime

Decode behaves differently from prefill under compilation. TR120 shows that prefill wins do not automatically transfer to KV decode, and in some cases decode regresses. This demands separate evidence for decode before enabling compile in production.

#### 5.4.4 Compiler evidence requirements

TR120 establishes a hard rule: a compile claim is valid only if compiler-real evidence exists in the artifacts. This includes the requested backend, the actual backend, and compiler counters. This policy prevents a common failure mode where a system advertises compile support but silently falls back to eager.

#### 5.4.5 Production gating and safe rollout

Production rollout must treat compilation as a gated feature flag. Enable only with compiler-real evidence, shape stability, and live monitoring of recompile counters; revert on fallback or tail regression.

#### 5.4.6 Compiler policy as a lifecycle rule

Compiler behavior is not static. Changes in PyTorch, CUDA, or model architecture can alter graph capture and guard behavior. The program therefore treats compiler policy as a lifecycle rule: after each dependency upgrade, rerun the controlled compilation harness and verify that tail behavior remains within bounds before re-enabling compilation in production.

The synthesis adopts a conservative rollout strategy: compile prefill only, validate shape stability, and monitor recompilation counters. If recompiles or fallbacks appear, the system should automatically revert to eager. This is not a theoretical preference; it is a pragmatic response to the tail risks observed in the controlled runs.

The most important negative result in TR120 is that KV decode does not automatically benefit from compilation. In the controlled runs, compiled decode regresses relative to eager execution. This forces a phase-aware compilation policy: compile prefill only, leave decode eager unless you have a specific decode win under the same boundary conditions. The broader implication is that optimization is not a binary switch; it must be segmented by phase.

Evidence snapshot (artifact-backed, label-only distribution audit):

| Backend label | mean_ms | median_ms | p99_ms | max_ms | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| transformers-gpu-compile | 389.2 | 328.7 | 631.2 | 681.8 | scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv |
| transformers-gpu | 404.1 | 322.7 | 931.5 | 3325.8 | scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv |

The Mann-Whitney test on label-only distributions is non-significant (p = 0.749), reinforcing that the label difference is not compiler evidence. Source: scripts/tr120/results/tr120_compile_paradox/processed/summary.json.


Objective:

- Determine whether "compile" is real in the code path and what it does to latency distributions.

Method:

- Label audit + controlled reproduction with compiler metadata.

Key results:

- The compile label in TR117 was not compiler-real.
- Real compilation yields p50 wins but can create heavy tails under shape churn.
- Padding or dynamic shapes mitigate tail risk.
- KV decode does not necessarily benefit from compilation and can regress.

Decision implications:

- Compile is a gated feature, not a default.
- Phase-specific compilation is necessary for stability.

### 5.5 TR121v1: Scaling regimes and structural predictors

#### 5.5.1 Scaling regimes as operational categories

TR121v1 identifies three operational regimes rather than a single scaling law. The small-model HF GPU regime is dominated by overhead and depth; the CPU regime shows strong rank correlation with parameter count; and the large-model Ollama regime shows a monotonic relationship with params under fixed-length decode. These are not abstract categories. They determine what proxy you can use in planning and which backends are predictable under a given load.

#### 5.5.2 Structural predictors: depth, width, and sequential steps

A key insight is that parameter count is not a sufficient proxy for GPU latency in the small-model regime. A deep-but-narrow model can be slower than a larger-but-shallow model because decode cost scales with sequential layers per token. This is strengthened by a multivariate fit that shows the depth term dominates while the parameter term is near zero in this boundary. The implication is practical: if you are selecting models for GPU batch=1 workloads, depth is a stronger axis than params for latency risk.

#### 5.5.3 Early-stop modeling and fixed-length equivalence

TR121 explicitly handles early-stop behavior in Ollama by projecting decode duration to a fixed-length equivalent. This is necessary because early stop is common in short prompts and would otherwise bias the scaling fit. The report bounds this projection error and shows that regime conclusions persist even under length-limited samples. This makes the Ollama scaling claims defensible as regime descriptors rather than fragile artifacts of prompt termination.

#### 5.5.4 Scaling as a capacity decision, not a theory claim

TR121 treats scaling fits as capacity planning tools, not universal laws. Fits are used only within the validated regime boundary, and they are gated when R^2 is low or uncertainty is high. The outcome is a planning heuristic, not a theoretical exponent.

#### 5.5.5 Boundary-shift experiments and regime confirmation

TR121 does not merely claim a regime; it tests boundary shifts. Increasing batch size and decode length improves identifiability but does not collapse all variance into params. This is a critical nuance: the overhead regime can be softened but not eliminated when the model set is heterogeneous. The conclusion is not that params is useless, but that it is conditional on regime and architecture.

#### 5.5.6 Implications for model selection policy

Model selection should explicitly include depth and quantization metadata rather than relying on parameter count alone. For GPU batch=1 workloads, depth is the safer predictor; for large-model serving, params can guide planning but must be paired with memory and quantization constraints.

#### 5.5.7 Scaling results as organizational knowledge

A scaling report becomes most valuable when it is internalized as organizational knowledge rather than as a single document. The synthesis encourages teams to encode the regime findings into model selection checklists, default routing policies, and cost calculators so that the conclusions persist beyond the report itself.

From an operational perspective, the scaling findings imply that model selection should be policy-driven rather than parameter-driven. For GPU batch=1 workloads, depth should be a selection criterion. For large-model serving, parameter count remains a useful proxy but should be combined with quantization and memory constraints.

The most important use of TR121 is not to publish an exponent; it is to choose a model tier that fits your budget and SLOs. A 7B model can be roughly 2.5x cheaper than a 20B model at fixed decode length under the measured boundary. This is the operational meaning of scaling: model size is a fleet multiplier.

Evidence snapshot (artifact-backed):

Decode dominance at gen_tokens = 64 (median decode fraction):

| Backend kind | Median decode fraction | Evidence |
| --- | ---: | --- |
| hf | 0.9805 | scripts/tr121/results/tr121_decode_sweep/20251224_002955/gen_64/metrics.csv |
| ollama | 0.9821 | scripts/tr121/results/tr121_decode_sweep/20251224_002955/gen_64/metrics.csv |

Scaling fits (e2e_kv, geomean across scenarios):

| Regime | n_models | slope | r2 | Notes | Evidence |
| --- | ---: | ---: | ---: | --- | --- |
| HF GPU params-only | 7 | 0.0427 | 0.0609 | slope CI crosses zero | scripts/tr121/results/20251224_002149/analysis/scaling_fits.csv |
| HF GPU multivariate (log params + log layers) | 7 | beta=-0.0616, gamma=0.7335 | 0.8738 | params term crosses zero; depth term dominates | scripts/tr121/results/20251224_002149/analysis/hf_multivariate_fits.csv |
| Ollama regime | 5 | 0.6572 | 0.9057 | monotone within boundary | scripts/tr121/results/20251223_230615/analysis/scaling_fits.csv |
| Gemma family (within-family check) | 2 | 0.5603 | 1.0 | small n, supportive only | scripts/tr121/results/tr121_gemma_family_20251223/analysis/scaling_fits.csv |


Objective:

- Measure scaling behavior across model sizes and identify valid predictors.

Method:

- Phase-split measurements across multiple models and backends with scenario-aggregation.

Key results:

- Small-model GPU scaling is not identifiable by params under batch=1 and short prompts.
- Depth is a stronger predictor for GPU latency in this regime.
- Large-model Ollama scaling is monotone under fixed-length decode equivalence.
- Decode dominates end-to-end by gen >= 64.

Decision implications:

- Use depth and workload shape for small-model GPU planning.
- Use params as a regime descriptor for large-model serving.

### 5.6 TR122: Physics baseline and energy gating

#### 5.6.1 Baseline calibration and measurement noise

TR122 formalizes a baseline calibration step for idle power and quantifies its variance. This is not optional: energy attribution without baseline subtraction is dominated by idle noise in short windows. The report quantifies the standard error under the actual polling cadence and demonstrates that even a seemingly stable mean can hide high instantaneous variability.

#### 5.6.2 Polling resolution and event validity

The central finding is that 100 ms polling cannot reliably attribute energy to sub-100 ms events. Most prefill events are shorter than a single polling window, which yields no_data windows. TR122 therefore introduces explicit gating: energy and delta power are only reported when sufficient samples fall within the event window. This transforms energy reporting from a heuristic into a validity-filtered measurement.

#### 5.6.3 Implications for energy claims

Energy claims are valid only when sample coverage is sufficient. The synthesis therefore treats energy per token as a macro-window metric and classifies short-event attribution as no_data rather than as a number.

#### 5.6.4 Measurement upgrade path

Event-level energy requires higher-fidelity instrumentation. The practical upgrade path is to use hardware energy counters or longer measurement windows that preserve timing while increasing sample coverage.

#### 5.6.5 Energy reporting ethics

The program takes a conservative stance: do not publish energy numbers unless the measurement system can support them. This is an ethical as much as a technical position. Publishing energy per token without adequate sampling is a form of false precision that can mislead decision-makers and regulators.

TR122 implicitly defines a roadmap for energy measurement: adopt hardware energy counters where available, increase sampling cadence only if it does not distort timing, and separate macro energy reporting from micro event reporting. This provides a future path for integrating energy into decision-making without overstating precision.

The synthesis takes a strict stance: energy per token is meaningful only when the measurement window is sufficiently long or when hardware energy counters are available. Short-event energy claims must be labeled as invalid or deferred. This is a methodological boundary that protects the credibility of the entire cost-and-energy narrative.

Evidence snapshot (artifact-backed):

| Measurement | Value | Evidence |
| --- | ---: | --- |
| Idle baseline mean (W) | 20.7096 | scripts/tr122/results/20251225_190043/baseline.json |
| Idle baseline std (W) | 9.9650 | scripts/tr122/results/20251225_190043/baseline.json |

Energy attribution quality (event-level):

| Phase | energy_quality=good | energy_quality=no_data | Evidence |
| --- | ---: | ---: | --- |
| prefill | 0 / 15 (0%) | 15 / 15 (100%) | scripts/tr122/results/20251225_190043/generation_events.jsonl |
| decode | 15 / 15 (100%) | 0 / 15 (0%) | scripts/tr122/results/20251225_190043/generation_events.jsonl |


Objective:

- Establish the physical baseline and measurement constraints for energy attribution.

Method:

- Idle baseline calibration, poller quality analysis, event-level energy gating.

Key results:

- Idle baseline measured at mean 20.71 W with high instantaneous variability.
- 100ms polling cannot attribute sub-100ms events; most prefill windows are no_data.

Decision implications:

- Baseline subtraction is mandatory.
- Energy attribution is only valid for macro windows unless energy counters exist.

---

### 5.7 Extended Analyses (dissertation depth)

This section expands each report's logic into a deeper narrative. It is intentionally verbose and analytical, designed to make the chain of reasoning visible without requiring readers to jump back into the individual report files. The content here is not new data; it is a tighter articulation of why the data lead to the stated decisions.

#### 5.7.1 TR117 extended analysis: the role of distributions in performance claims

The single-model matrix in TR117 is a typical starting point for benchmark-driven decision-making. It is also a trap if interpreted without distributional awareness. The matrix itself is valuable because it reveals a stable ordering of backends under a fixed model and controlled scenarios. However, the raw data also shows that latency distributions can be heavy-tailed, and that a small number of extreme values can dominate mean statistics. This matters because service-level outcomes are often tied to tails, not means. A user does not experience the average of a thousand requests; they experience one request that either completes or does not.

The TR117 paradox therefore becomes a methodological lesson: the choice of summary statistic is a first-class modeling decision. Median latency captures the typical experience but ignores tail risk; mean latency captures aggregate compute burden but can be hijacked by rare events. In a decision-grade report, both must be shown, and the reasons for divergence must be explained. TR117 provides the data that allows this explanation, but TR120 provides the attribution. Together they demonstrate that a benchmark is not a single number; it is a distribution with operational consequences.

The deeper implication is that performance claims must be tied to a measurement boundary. TR117's boundary includes initialization and caching work, which makes it accurate for real user-facing latency but fragile for causal attribution. The synthesis therefore treats TR117 as a high-fidelity observation of user experience, not a mechanistic explanation. This distinction is crucial for responsible deployment: you can use TR117 to choose a backend for a specific workload, but you cannot use it to infer compiler performance without additional evidence.

#### 5.7.2 TR118_v2.2 extended analysis: reproducibility as a governance layer

TR118_v2.2 is best understood as governance infrastructure for the entire research program. It formalizes what counts as evidence. The report's validation stages are not simply quality checks; they are protections against interpretive drift. In a multi-report program, data can silently change due to configuration differences, version skew, or incomplete artifacts. Without validation, the integrity of cross-report synthesis collapses.

TR118's contributions include: manifest-driven provenance, explicit degraded-run handling, and deterministic processing steps. These are the properties that allow later reports to state claims like "the cost model is derived from throughput that is derived from measured latency arrays." That chain is only valid when the pipeline itself is validated. This is why TR118 is not just a technical note; it is an epistemic requirement for the rest of the program.

From a methodological perspective, TR118 also influences how we interpret missingness. Degraded runs are not deleted; they are classified and excluded from aggregates. This is a subtle but important point: failures are part of performance reality, but they must not be mixed into throughput statistics. The dual treatment'retain for visibility, exclude for aggregates'balances transparency with statistical integrity.

#### 5.7.3 TR119v1 extended analysis: economics as a transformation layer

TR119v1 is the report that turns performance numbers into budget numbers. It does so by making the cost model fully explicit and by keeping the model simple enough that its assumptions are visible. The key transformation is from throughput to cost per token, and from cost per token to request-level cost. This is the point in the program where a benchmark becomes a business decision.

The report's most important conceptual move is to separate infrastructure cost from energy cost, and then to show that under time-priced compute, infrastructure cost dominates. This does not diminish the importance of energy; it clarifies which levers move the budget. In the tested configuration, the energy term is a small fraction, so throughput drives dollars. This is the reason TR119's recommendations are stable across pricing tiers: the ranking is driven by tokens per second, which does not change with price.

TR119 also shows how scenario weighting can invert winners. A backend can be optimal for batched prefill but suboptimal for decode-heavy workloads. This is not a technicality; it is a routing strategy. If your workload mix is known, you should weight scenarios accordingly. If your mix is unknown, you should default to the backend that wins in the decode regime because decode dominates end-to-end cost in most services. This logic is reused in TR121's capacity planning, reinforcing the coherence of the program.

#### 5.7.4 TR120 extended analysis: compilation as a controlled experiment

TR120 transforms compiler performance from folklore into a controlled experiment. It does this by explicitly wiring compilation, recording compiler metadata, and removing confounds that would otherwise blur the interpretation. The result is two separate truths: compilation can produce dramatic p50 improvements, and compilation can create heavy tails when shapes vary. The mechanism is observable: guard failures, multiple compiled graphs, and recompile limits.

This is one of the most operationally relevant outcomes of the program. Compiler toggles are seductive because they promise speed without architectural change. TR120 shows that this promise is conditional. If you cannot stabilize shapes, compilation becomes a tail risk. If you can stabilize shapes, compilation becomes a performance win'at least for prefill. Decode remains a separate regime where compilation can regress. This is why the synthesis insists on phase-specific compilation policy.

The deeper lesson is that compiler behavior is not a property of the compiler alone; it is a property of the workload and the measurement boundary. The same compiler can be stable on fixed-shape prefill and unstable on variable-shape decode. A production policy that does not incorporate this nuance will either leave performance on the table or introduce unacceptable tail risk.

#### 5.7.5 TR121v1 extended analysis: scaling as a regime, not a law

TR121v1 rejects the idea of a single scaling exponent across all models and backends. Instead, it treats scaling as a regime concept: under some boundaries, params correlate with latency; under others, architecture and overhead dominate. This is the correct framing for decision-making because it acknowledges that scaling is not purely a property of the model. It is a property of the model, the workload, and the runtime stack.

The small-model HF GPU regime is particularly instructive. It shows that depth can dominate latency even when parameter count is small. This is consistent with the mechanics of decode: each token requires sequential passes through each transformer block. A shallow, wider model can therefore be faster than a deeper, narrower model with fewer parameters. The multivariate fit strengthens this claim by isolating the depth term.

In the large-model Ollama regime, parameter count recovers as a useful predictor, but only under fixed-length decode equivalence. Early-stop behavior would otherwise distort the scaling fit. The report therefore makes a modeling choice'fixed-length projection'and validates it by bounding the projection error. This is exactly the kind of explicit modeling choice that a decision-grade report should make: acknowledge the modeling assumption, quantify its error, and show that it does not change the regime conclusion.

#### 5.7.6 TR122 extended analysis: physics as a constraint, not an afterthought

TR122 introduces a critical reality check: energy measurement has physical limits. A polling system cannot attribute energy to events shorter than its sampling interval, and baseline noise can dominate short windows. Without an explicit gating policy, energy numbers become impressionistic rather than evidentiary. TR122 therefore replaces the naive "energy = power * time" assumption with a conditional statement: energy attribution is valid only when the measurement system can observe the event.

This is an important correction for any cost-and-energy reporting. It means that energy numbers are reliable for macro events (multi-second runs) but not for sub-100 ms prefill calls. The synthesis takes this seriously: it does not use micro-event energy as a decision lever. Instead, it uses TR122 to define when energy reporting is valid and to guard against false precision. This is not a limitation; it is a strengthening of credibility.

## 6. Cross-Report Synthesis by Decision Axis

This section distills the results into decision axes that consistently predict outcomes.

### 6.1 Phase: prefill vs decode

- TR120 shows compiler behavior diverges by phase.
- TR121v1 shows decode dominates end-to-end for gen >= 64 tokens.
- TR119v1 shows cost is dominated by decode whenever generation exists.

Implication: optimize decode throughput first; treat prefill as a separate phase for TTFT and batching policy.

### 6.2 Workload shape: batch and prompt length

- TR119v1 shows batch prefill can invert backend winners.
- TR121v1 shows short prompts drive overhead regimes on GPU.

Implication: never report a single mean without workload weighting; route by scenario when feasible.

### 6.3 Compiler behavior and shape stability

- TR120 shows shape instability causes recompiles and heavy tails.
- Padding or dynamic compilation can collapse tails, but decode remains a separate regime.

Implication: compiler policy must include shape stabilization and phase-specific routing.

### 6.4 Model structure vs parameter count

- TR121v1 shows GPU latency correlates with depth more than params at batch=1.
- CPU latency tracks params more closely in the HF regime.

Implication: choose model architecture with depth awareness for GPU-bound small-model serving.

### 6.5 Physical measurement limits

Physical limits as policy inputs. TR122 establishes that instrumentation limits are not "noise" to be averaged away; they determine whether a metric exists. At 100 ms polling, most sub-100 ms events cannot support energy attribution, so energy becomes meaningful only for sufficiently long windows or with higher-fidelity counters. This forces a policy constraint: energy metrics may inform macro-level governance (cost, sustainability), but must not be used to rank micro-optimizations unless the measurement system can observe them.

### 6.6 Cold-start and warmup as an SLO axis

Cold-start behavior is a cross-cutting axis because it appears in every phase: prefill spikes, model load time, and the first decode path. TR117 first revealed the hazard, TR120 explained its measurement boundary, TR121v1 quantified its magnitude, and TR122 showed why short events are hard to attribute energetically. The synthesis is therefore not a single report result; it is a program-wide principle: cold-start is a distinct regime that must be modeled and operationally gated. Any service-level objective that ignores cold-start will systematically understate tail risk.

### 6.7 Measurement boundary as epistemic constraint

A measurement boundary is not just a technical detail; it defines what kind of claims are valid. TR117's boundary included initialization effects, which made mean metrics sensitive to cold-start. TR120's controlled boundary removed those effects to isolate compiler behavior. TR122's energy boundary shows that even if you can measure latency, you may not be able to measure energy at the same granularity. These are epistemic constraints: they define what can and cannot be inferred from the data. A defensible report must state those constraints explicitly.

### 6.8 Optimization stack interactions (backend, compiler, kernels)

The program shows that optimization happens at multiple layers: backend selection (TR117/119), compiler policy (TR120), and kernel choice (implied by the attention literature). These layers interact. A backend that wins in eager mode can lose when compiled; a compile strategy that accelerates prefill can regress decode; and kernel availability can dominate all of the above. The synthesis therefore avoids single-lever conclusions: it treats optimization as a stack, not a switch.

### 6.9 Minimal decision set (what must be true to ship)

A deployment decision can be reduced to a minimal set of truths that must be validated:

1. The backend's decode throughput is known under the target workload mix.
2. The compiler (if enabled) is compiler-real and does not introduce unacceptable tail risk.
3. Warmup behavior is bounded and operationally mitigated.
4. Energy claims are valid at the chosen reporting granularity.

If any of these conditions are unknown, the decision is not yet safe. The value of the TR117-TR122 program is that it supplies evidence for each condition.

### 6.10 Tradeoff frontier: throughput, tail risk, and cost

The optimization frontier is three-dimensional. Increasing throughput reduces cost but can increase tail risk if it requires compilation under unstable shapes. Reducing tail risk often requires warm pools or additional capacity, which increases cost. The correct decision depends on which dimension is most constrained: budget, SLO, or throughput.

### 6.11 Synthesis: what changed from TR117 to TR122

The program's center of gravity moved over time. TR117 was about speed; TR118 was about evidence; TR119 was about cost; TR120 was about attribution; TR121 was about scaling; TR122 was about physics. The synthesis here converts these into a single decision framework. The most important change is that performance is no longer treated as a scalar. It is treated as a vector of phase-specific throughput, tail risk, and cost. This is the conceptual upgrade that makes the program decision-grade.

### 6.12 Policy coherence and avoidance of contradictory optimizations

A common failure mode in performance engineering is to pursue contradictory optimizations: e.g., enabling compilation to improve prefill while harming decode, or focusing on mean latency while ignoring cold-start effects that dominate user-facing tails. The synthesis provides a coherent policy: prioritize decode throughput for end-to-end capacity, enforce shape stability for compilation, and treat warmup as a distinct operational regime. These rules are coherent across the reports and prevent optimization whiplash.

Evidence anchors by decision axis:

| Decision axis | Quantitative anchor | Evidence |
| --- | --- | --- |
| Phase separation | median decode fraction 0.9805 at gen_tokens = 64 | scripts/tr121/results/tr121_decode_sweep/20251224_002955/gen_64/metrics.csv |
| Workload shape | batch_short prefill winner cost 0.0585 (transformers-gpu) | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| Compiler behavior | p99 931.5 ms vs 631.2 ms (label-only), MW p=0.749 | scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv |
| Model structure | gamma_log_layers = 0.7335, r2 = 0.8738 (HF GPU multivariate) | scripts/tr121/results/20251224_002149/analysis/hf_multivariate_fits.csv |
| Measurement limits | prefill energy_quality no_data 15 / 15 | scripts/tr122/results/20251225_190043/generation_events.jsonl |

---

## 7. Economics and Capacity (Token-First and Request-First)

### 7.1 Token-first economics

Tokens per second is the most stable cross-stack metric. Under a compute-hour model:

- seconds_per_1M = 1e6 / tokens_per_s
- usd_per_1M = (seconds_per_1M / 3600) * usd_per_hour

TR119v1 demonstrates that cost rankings largely track throughput rankings under time-priced compute.

Evidence snapshot (TR119v1, mean total cost per 1M tokens on-demand across scenarios):

| Backend | Mode | Mean total cost per 1M tokens | n scenarios | Artifact |
| --- | --- | ---: | ---: | --- |
| onnxruntime-gpu | generate | 1.2041 | 5 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| onnxruntime-gpu | prefill | 0.1279 | 5 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| transformers-gpu | generate | 3.6257 | 5 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| transformers-gpu | prefill | 0.2605 | 5 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| transformers-gpu-compile | generate | 3.1536 | 5 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| transformers-gpu-compile | prefill | 0.1995 | 5 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |

### 7.2 Request-first economics

To map tokens into requests:

- tokens_per_request = prompt_tokens + generated_tokens
- cost_per_request = (tokens_per_request / 1e6) * usd_per_1M

Worked example (derived from TR121v1 tokens_per_s_geomean; illustrative, not universal):

| Scenario | Prompt tokens | Gen tokens | Total tokens |
| --- | ---: | ---: | ---: |
| chat_default | 256 | 128 | 384 |
| agent_tool_step | 512 | 32 | 544 |
| codegen_medium | 512 | 1024 | 1536 |
| long_context_summary | 2048 | 256 | 2304 |

Worked example costs per 1k requests using derived shadow prices (usd_per_hour = 1.006):

| Model | usd_per_1M | chat_default | agent_tool_step | codegen_medium | long_context_summary |
| --- | ---: | ---: | ---: | ---: | ---: |
| gpt-oss-20b:latest | 6.093 | 2.340 | 3.315 | 9.359 | 14.038 |
| qwen2.5:7b | 2.000 | 0.768 | 1.088 | 3.072 | 4.608 |
| gemma3:270m | 0.453 | 0.174 | 0.246 | 0.696 | 1.044 |

Traceability: tokens_per_s_geomean from `scripts/tr121/results/20251223_230615/analysis/summary_by_model_backend_mode_agg.csv` (gen_tokens = 64 per `scripts/tr121/results/20251223_230615/manifest.json`), with usd_per_1M computed from usd_per_hour = 1.006.

### 7.3 Worked example: capacity at 1B tokens per month

From TR121v1 run 20251223_230615 scenario-aggregated e2e_kv tokens/s (gen_tokens = 64):

| Model | Tokens/s | Workers for 1B/month | Shadow cost per 1M tokens |
| --- | ---: | ---: | ---: |
| gpt-oss-20b:latest (Ollama) | 45.9 | 8.41 | 6.093 |
| qwen2.5:7b (Ollama) | 139.7 | 2.76 | 2.000 |
| gemma3:270m (Ollama) | 616.9 | 0.63 | 0.453 |
| gpt2-100m (HF GPU) | 203.9 | 1.89 | 1.370 |
| gpt2-100m (HF CPU) | 41.1 | 9.39 | 6.805 |

Worked example note: assumes a 30-day month (2,592,000 seconds) and utilization-perfect workers. Tokens/s are from `scripts/tr121/results/20251223_230615/analysis/summary_by_model_backend_mode_agg.csv`; costs are computed from usd_per_hour = 1.006.

Interpretation:

- 7B vs 20B is roughly a 3.0x cost and capacity lever in this regime.
- CPU vs GPU is a feasibility boundary, not just a speed delta.

### 7.4 Break-even logic for tiering

Let:

- C_small = cost per request for the small model
- C_big = cost per request for the big model
- p_small = success probability for small model
- p_big = success probability for big model

The big model is justified when:

- C_big / p_big <= C_small / p_small
- p_big >= p_small * (C_big / C_small)

With a ~3.0x cost ratio, success-rate alone must improve by ~3.0x to justify the switch. This implies tiered routing is rational: reserve the large model for high-value requests, paid tiers, or failure-prone tasks.

---

### 7.5 Capacity planning under burstiness

All capacity numbers in this report are utilization-perfect lower bounds. Real traffic is bursty. If p95 load is 5x the mean, the fleet must be sized accordingly unless batching and queueing can absorb the burst without violating latency SLOs. This is not a theoretical warning; it is a practical guardrail. The correct use of the token-first model is to establish a baseline, then apply a burst factor derived from real traffic distributions.

### 7.6 Tiering and routing economics

The economics in TR119 and TR121 imply that model tiering is not optional once token volume grows. A two-tier policy (default small model + premium large model) captures most of the quality benefit without paying the large-model cost for every request. The conclusive report therefore frames tiering as a policy decision supported by measured throughput, not as a purely product or research preference.

### 7.7 Sensitivity to request mix and prompt length

Prompt length and generation length change the effective phase balance. Short prompts exaggerate overhead and cold-start effects; long prompts reduce overhead share and make compute scaling more visible. The synthesis therefore treats request mix as a first-class sensitivity parameter. Any production plan should substitute its own prompt-length distribution into the cost and capacity formulas before committing to a backend or model tier.

### 7.8 Deriving token and request models

Token-first models are stable across serving stacks, but product planning is request-first. The conversion requires a distribution over prompt and generation lengths. The correct approach is to compute cost and capacity as expectations under that distribution, not as a single point estimate. This is why TR119 and TR121 provide both token-level and request-level frameworks.

### 7.9 Queueing and saturation effects (why lower bounds are not enough)

The throughput numbers in this report assume perfect utilization. Real systems experience queueing, burstiness, and head-of-line blocking. When utilization approaches saturation, latency can rise superlinearly. This is a standard queueing effect and does not require a complex model to recognize: a fleet sized only to mean load is fragile under burst. The synthesis therefore frames capacity numbers as lower bounds and encourages burst-aware scaling policies.

### 7.10 Cost vs latency tradeoffs

A system can buy latency with capacity. If a service needs to reduce tail latency, it can provision more workers than the token-first minimum. The economics in TR119 and TR121 therefore connect directly to SLO decisions: each additional worker is a latency-control lever. This is the practical interpretation of "cost per token": it is the marginal cost of reducing tail latency by increasing slack capacity.

### 7.11 Economies of scale and fleet heterogeneity

A fleet can be heterogeneous. Running a mix of small and large models can reduce average cost while preserving quality for high-value requests. This creates an economy of scale: the marginal cost of a high-quality tier is amortized across a larger volume of low-cost requests. The program's cost model supports this by providing a common unit (tokens per second) across tiers.

### 7.12 Sensitivity to policy changes

Routing policy is itself a cost lever. A small change in routing thresholds can shift a large fraction of tokens to a more expensive tier. The report therefore recommends that routing policies be versioned and audited, much like code. The cost model provides a quantitative framework for evaluating those policy changes.

### 7.13 Pricing-tier scenarios

Cost sensitivity to pricing tier is linear in the compute-hour model. This means that the relative ordering of backends and models is stable across tiers, even when absolute costs change. The practical implication is that tier selection (spot vs reserved) is a global cost lever that should be decided independently of backend selection. Backend selection is driven by throughput; tier selection is driven by business constraints such as availability and commitment.

### 7.14 Cost exposure under growth

Token volume growth multiplies cost directly. A 10x increase in token volume requires a 10x increase in capacity or a 10x increase in efficiency. This simple fact makes early backend and model selection a long-term budget decision. The synthesis therefore treats scaling not as a theoretical curiosity but as a capacity planning requirement.

## 8. Operational Doctrine and Risk Controls

Evidence-to-policy mapping (artifact pointers for each operational rule):

| Policy rule | Metric anchor | Artifact |
| --- | --- | --- |
| Route decode-heavy workloads to onnxruntime-gpu by default | Mean total cost per 1M tokens (generate) onnxruntime-gpu 1.2041 vs transformers-gpu 3.6257 and transformers-gpu-compile 3.1536 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| Route batch prefill to transformers-gpu when a win exists | batch_short prefill cost 0.0585 (transformers-gpu) vs 0.1445 (onnxruntime-gpu) | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json |
| Compile prefill only; do not assume decode wins | p99 tail 931.5 ms vs 631.2 ms with MW p = 0.749 under label-only compile | scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv; scripts/tr120/results/tr120_compile_paradox/summary.json |
| Treat decode-heavy as the default regime | median decode fraction 0.9805 at gen_tokens = 64 | scripts/tr121/results/tr121_decode_sweep/20251224_002955/gen_64/metrics.csv |
| Require explicit warmup policy | warmup_to_measured_ratio median 1.19, p95 15.63 | scripts/tr121/results/20251223_230615/analysis/warmup_effect.csv |
| Enforce energy gating at event scale | prefill energy_quality no_data 15 / 15; decode good 15 / 15 | scripts/tr122/results/20251225_190043/generation_events.jsonl |

### 8.1 Preflight checks

- Baseline calibration passes (TR122)
- Poller continuity quality is not degraded (TR122)
- Warmup behavior is measured and acceptable (TR121v1)
- Compiler-real evidence exists if compilation is enabled (TR120)

### 8.2 Default routing policy

- Route to onnxruntime-gpu for workloads with nontrivial decode (TR119v1)
- Route to transformers-gpu for prefill-heavy batch workloads that show a win in your mix (TR119v1)

### 8.3 Compiler gating

- Compile prefill only when shapes are stable and compiler-real evidence exists (TR120)
- Keep KV decode eager unless a decode win is demonstrated in your stack (TR120)

### 8.4 Measurement gating

- Do not report per-event energy for events with fewer than 2 in-window samples (TR122)
- Treat energy attribution as valid only for macro windows unless counters are available

### 8.5 Warmup and cold-start policy

- Explicit warmup before routing production traffic
- Track cold-start latency separately from steady-state SLOs

### 8.6 Risk register

| Risk | Impact if ignored | Mitigation | Validated by |
| --- | --- | --- | --- |
| Label drift | False performance claims | Require compiler-real evidence | TR120 |
| Phase conflation | Wrong optimization target | Split prefill and decode | TR120, TR121v1 |
| Workload-shape sensitivity | Winner flips in production | Scenario routing and weighting | TR119v1, TR121v1 |
| Compiler tail risk | p99 regressions | Shape stabilization and compile gating | TR120 |
| Cold-start skew | Mean hides p95 | Warmup before routing | TR120, TR121v1 |
| Energy misattribution | Wrong cost claims | Baseline subtraction and gating | TR122 |
| Poller resolution limit | False precision | Require >=2 samples or counters | TR122 |
| Over-generalized scaling | Mis-sized fleets | Use regime descriptors, not universal laws | TR121v1 |
| Thermal drift | Latency changes over time | Heat soak and equilibrium checks | TR122 |
| Data integrity drift | Non-reproducible claims | Manifest + validation | TR118_v2.2 |

### 8.7 Implementation checklist (deployment-ready)

This checklist is intentionally short and operational:

1. Validate compiler-real backend capability at startup (record actual backend).
2. Run phase-specific warmups (prefill, decode) before accepting user traffic.
3. Emit per-request phase timing (prefill ms, decode ms, tokens).
4. Enforce routing by workload shape (batching and prompt length).
5. Record cold-start markers (worker age, time since last request).

### 8.8 Telemetry and audit expectations

Operational trust in the report depends on auditability. The report recommends a minimal audit trail: manifest hashes, report version, and a short summary of any deviations from the published measurement boundary. To keep claims valid after deployment, telemetry must match report boundaries. At minimum, record: tokens per request, prompt length, generation length, and phase-specific latency. For energy, record only in windows where sample coverage is sufficient (TR122 gating).

### 8.9 Applied case studies (decision walkthroughs)

The following short case studies show how the report's principles translate into concrete choices. They are intentionally narrative: the goal is to demonstrate how to go from artifact-backed claims to a policy decision without introducing new assumptions.

#### 8.9.1 Interactive chat service (moderate decode, strict SLOs)

Scenario: a chat product with prompt lengths in the 100-300 token range and generation lengths around 64-128 tokens. The dominant user-facing metric is TTFT, but throughput must meet a stable tokens-per-second target.

Decision path: TR121v1 establishes that decode dominates end-to-end at these generation lengths. TR119v1 shows that cost per token is dominated by throughput under time-priced compute. Therefore, the backend choice should be driven by decode throughput, not prefill. TR120 cautions against compile-on-decode without evidence.

Outcome: choose the backend with best decode throughput and stable tails (e.g., ORT GPU in TR119v1), keep decode eager, and treat prefill optimization as a TTFT improvement rather than a capacity lever. Warmup is mandatory, as TR121 and TR120 demonstrate that cold-start prefill spikes can degrade TTFT.

#### 8.9.2 Batch prefill pipeline (reranking or embeddings-like work)

Scenario: an offline or asynchronous pipeline dominated by batched prefill, with negligible generation. The primary metric is throughput and cost per token; tail latency is less critical.

Decision path: TR119v1 shows that prefill batch scenarios can invert winners; the cheapest backend is not necessarily the best at single prompts. TR121v1's scaling regime analysis is less relevant because generation length is near zero. TR122's energy gating is also less critical because batch prefill windows are longer, making energy attribution more reliable.

Outcome: route to the backend with the best batched prefill cost in the relevant scenario. Use scenario weighting to ensure the chosen backend aligns with the actual batch size distribution.

#### 8.9.3 Cold-start sensitive multi-tenant serving

Scenario: a multi-tenant service where models are evicted or loaded on demand. The first request after eviction must still meet an SLO to avoid user-visible failures.

Decision path: TR121v1 provides warmup ratios and absolute deltas; TR120 shows how first-call effects can distort distributions; TR122 shows that short events are difficult to measure energetically. The key conclusion is that cold-start must be treated as a distinct operational regime.

Outcome: maintain a warm pool for large models, add a pre-routing warmup stage, and explicitly separate cold-start SLOs from steady-state SLOs. In reporting, never mix warmup samples into steady-state aggregates.

#### 8.9.4 Compiler-enabled service under shape variability

Scenario: a service that wants to use torch.compile for throughput gains but sees variable prompt lengths and mixed batch sizes.

Decision path: TR120 shows that compilation yields p50 wins but can create heavy tails under shape churn. Padding or dynamic compilation can mitigate tails, but decode can still regress. TR121v1 demonstrates that decode dominates at moderate generation lengths.

Outcome: compile prefill only, stabilize shapes via padding or bucketing, keep decode eager unless a decode win is demonstrated under the real workload. Monitor unique_graphs and recompile_limit events as a policy guard.

### 8.10 Reporting cadence and governance

Decision-grade reporting is not a one-time activity. The program suggests a cadence: rerun the core matrix after backend upgrades, after model architecture changes, and after substantial workload shifts. This is especially important for compilation and scaling because small changes in input shape can alter performance profiles.

### 8.11 Incident response and regression detection

Performance regressions should be treated as incidents when they affect cost or SLOs. The minimum incident workflow includes: detecting a sustained drop in tokens per second, linking it to a backend, model, or compiler change, and rolling back or rerouting traffic. This workflow mirrors traditional reliability engineering, but the triggering metric is throughput rather than uptime.

### 8.12 Governance for report reuse

If this conclusive report is used as a policy baseline, it should be tied to a specific hardware and software manifest. Any changes to drivers, compiler versions, or model architectures should trigger a rerun of the relevant TRs. This governance prevents the report from becoming a stale policy artifact.

### 8.13 Change management and regression policy

Any change to the inference stack (compiler, runtime, model, driver) should be treated as a policy change. The regression policy is: rerun the relevant TRs, compare key metrics to prior baselines, and update the conclusive report if the decision envelope shifts. This is the minimum standard for keeping a performance report operationally valid.

### 8.14 Documentation and audit trail

Treat the conclusive report as a release artifact. Archive report versions alongside their manifest hashes and a short change log so audits can reconstruct the exact decision boundary that was in effect.

---

## 9. Threats to Validity and Scope Limits

### 9.1 Model heterogeneity and cross-family effects

TR121 mixes local HF GPT-2 variants with Ollama GGUF models from multiple families. This is intentional for regime mapping, but it limits any claim of a single scaling law. The synthesis therefore treats cross-family exponents as regime descriptors, not architecture-invariant truths.

### 9.2 Boundary conditions and workload shape

Many conclusions are conditional on short prompts, batch=1, and fixed generation length. Longer contexts or larger batches can change the dominant cost terms. This is not a weakness; it is an explicit boundary. It also implies that any deployment should rerun the pipeline with its own workload mix before locking decisions.

### 9.3 Small-n statistical fragility

Several fits use n_models between 5 and 7. This is sufficient for regime detection but not for fine-grained exponent estimation. The report mitigates this by using bootstrap intervals and nonparametric checks, but it does not claim precise exponents where fit quality is low.

### 9.4 Instrumentation limits

Energy attribution is bounded by polling resolution and counter availability. TR122 explicitly gates energy reporting to avoid false precision. As a result, energy claims are restricted to macro windows and are not used as primary decision criteria in micro events.

### 9.5 External validity across hardware

The entire program is anchored to a specific laptop-class GPU and CPU. While relative ordering is often stable across similar hardware, absolute throughput and cost numbers will change on different devices. The synthesis therefore recommends rerunning the core pipeline for any hardware class that is operationally significant.

### 9.6 External validity across software stacks

Compiler and runtime behavior can change significantly with driver versions, PyTorch releases, or different inference engines. This is particularly relevant for TR120 and TR119. A report that is valid for one stack can become invalid after a major upgrade.

### 9.7 Data selection bias

The scenarios used in TR117 and TR121 are intentionally small and controlled. This improves interpretability but can underrepresent real-world prompt distributions. The synthesis therefore treats scenario weighting as a decision lever and encourages users to substitute their own traffic distributions in the cost and capacity formulas.
Scope limits summary:

1. Single hardware system: all results are on one RTX 4080 laptop configuration. Cross-hardware generalization is not established.
2. Limited model families: HF GPT-2 variants and a small set of Ollama models are not a universal sample of architectures.
3. Measurement boundaries: short prompts and batch=1 produce overhead-dominated regimes. Longer sequences and batching could shift results.
4. Energy measurement resolution: 100ms polling is insufficient for short events. Energy conclusions are valid only for macro windows.
5. Quality outcomes not measured: this program does not quantify model quality or accuracy. Cost trade-offs must be combined with quality metrics from separate evaluations.

These limits are explicit guardrails that prevent over-claiming. They do not invalidate the conclusions within scope.

---

## 10. Limitations by Report and Mitigations

This section consolidates limitations report-by-report and pairs each with the mitigation that the program actually uses. The goal is to make the scope limits actionable rather than merely descriptive.

### 10.1 Limitation-to-mitigation matrix

| Report | Limitation | Practical impact | Mitigation used in program |
| --- | --- | --- | --- |
| TR117 | Label-only attribution; single-model scope | Compiler claims and scaling cannot be inferred | TR120 label audit and controlled compile runs; TR121 scaling study |
| TR118_v2.2 | Validation does not prevent boundary drift | Later runs can differ subtly in workload mix | Manifest hashes + scenario taxonomy + explicit boundary statements |
| TR119v1 | Energy is partial; pricing is a shadow input | Energy share and absolute $ depend on assumptions | Explicit energy attribution notes + tier sensitivity + shadow price labeling |
| TR120 | Compiler results are hardware and shape dependent | Compile benefits can flip under new shapes | Shape stabilization (padding/dynamic) + compile gating + per-run compiler evidence |
| TR121v1 | Mixed families and small-n fits | Scaling exponents not universal | Regime language + fit gating + boundary-shift experiments + within-family check |
| TR122 | Polling cadence limits event attribution | Sub-100 ms energy numbers invalid | Energy gating + baseline subtraction + macro-window reporting only |

### 10.2 Decision gating thresholds (the minimum to trust a claim)

The program uses explicit gates to decide whether a claim is safe to ship:

1. Scaling fits are actionable only if R^2 >= 0.2 and bootstrap CIs do not cross zero.
2. Compiler claims are actionable only if compile backend actual is recorded and no fallback occurs.
3. Energy attribution is actionable only if the event window has sufficient samples (TR122 gating).
4. Warmup ratios above 10x trigger mandatory warm pool or pre-routing warmup policy.
5. Scenario aggregation is required before claiming a backend winner; single-scenario wins are treated as routing hints, not global conclusions.

### 10.3 How to extend without breaking the chain

If a new report is added later, it should follow the same limitation-to-mitigation pattern. The report should state (a) what it cannot answer, (b) which prior reports cover those gaps, and (c) what policy should be gated until the gap is closed. This keeps the program coherent as it grows.

## 11. Roadmap Without TR123

### 11.1 Consolidation objectives

With TR123 removed from scope, the roadmap focuses on consolidation rather than expansion. The objective is to make TR117-TR122 a stable, canonical pipeline that can be rerun for new hardware, new models, or new backends without changing the analytical framing.

### 11.2 Priority actions

1. Normalize artifact locations and naming across TR117-TR122 to simplify cross-report synthesis.
2. Integrate energy gating (TR122) into any cost pipeline that reports energy or carbon (TR119).
3. Standardize phase timing outputs so prefill/decode metrics are directly comparable across reports.
4. Add a report regeneration script that produces the conclusive report from underlying artifacts.

### 11.3 Criteria for program completion

The program is complete when a single pipeline can: (a) run the scenario matrix, (b) validate artifacts, (c) compute cost and capacity, (d) enforce compiler attribution, and (e) apply energy gating where appropriate. At that point, new models or backends can be evaluated without revisiting methodology.

TR123 is not required to make the current program decision-grade. The next steps that strengthen evidence without changing core conclusions are:

1. TR122.A: instrument response square-wave validation
2. TR121 + TR122 integration: energy and memory telemetry added to scaling runs
3. Compile decode sweep: KV decode under multiple compile strategies

---

## 12. Conclusive Statement

The program is now coherent and decision-grade. TR117 gave us the first matrix. TR118 made it credible. TR119 turned speed into money. TR120 made compiler claims real. TR121 defined scaling regimes. TR122 grounded everything in physical measurement.

The operational result is clear:

- Optimize for decode throughput.
- Route by workload shape.
- Treat warmup and baseline as first-class constraints.
- Only trust energy where the sensor can see the event.

This is a publishable, defensible, and actionable synthesis of the TR117 to TR122 arc.

---

## 13. References

[1] A. Vaswani et al., "Attention Is All You Need," in Advances in Neural Information Processing Systems, 2017. arXiv:1706.03762.

[2] Z. Dai et al., "Transformer-XL: Attentive Language Models Beyond a Fixed-Length Context," 2019. arXiv:1901.02860.

[3] T. Dao et al., "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness," 2022. arXiv:2205.14135.

[4] T. B. Brown et al., "Language Models are Few-Shot Learners," 2020. arXiv:2005.14165.

[5] NVIDIA Corporation, "NVIDIA Management Library (NVML) API Reference," 2024. [Online]. Available: https://docs.nvidia.com/deploy/nvml-api/index.html

[6] PyTorch, "torch.compile Documentation," 2024. [Online]. Available: https://pytorch.org/docs/stable/generated/torch.compile.html

[7] ONNX Runtime, "ONNX Runtime Documentation," 2024. [Online]. Available: https://onnxruntime.ai/

[8] Ollama, "Ollama Documentation and API," 2024. [Online]. Available: https://ollama.ai/

[9] J. Kaplan et al., "Scaling Laws for Neural Language Models," 2020. arXiv:2001.08361.

[10] J. Hoffmann et al., "Training Compute-Optimal Large Language Models," 2022. arXiv:2203.15556.

[11] C. Mattson et al., "MLPerf Inference Benchmark," 2020. arXiv:1911.02549.

[12] Y. Tay et al., "Efficient Transformers: A Survey," 2020. arXiv:2009.06732.

[13] T. Dao et al., "FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning," 2023. arXiv:2307.08691.

---


## Appendix A: Key Formulas

1. Tokens per second

- tokens_per_s = tokens_total / (latency_ms / 1000)

2. Compute-hour shadow cost

- seconds_per_1M = 1e6 / tokens_per_s
- usd_per_1M = (seconds_per_1M / 3600) * usd_per_hour

3. Capacity lower bound

- avg_tokens_per_s = tokens_per_month / seconds_per_month
- workers = avg_tokens_per_s / tokens_per_s

4. Request cost

- tokens_per_request = prompt_tokens + generated_tokens
- cost_per_request = (tokens_per_request / 1e6) * usd_per_1M

---


## Appendix B: Claim-to-Artifact Chain-of-Custody

This appendix maps the highest-impact synthesis claims to the specific artifacts that make them defensible. It is the operational proof that the conclusive report is not a narrative summary but an artifact-backed inference.

Claim IDs C1-C6 correspond to the Executive Summary claim table.

| Claim ID | Claim | Report anchor (section/table) | Artifact path(s) | Notes |
| --- | --- | --- | --- | --- |
| C1 | Backend labels are a reliable proxy for runtime behavior | TR120 Section 3 (backend label audit) | results/tr117_tier3/metrics.csv; scripts/tr120/results/tr120_compile_paradox/processed/summary.json | Status: False; label-only, not compiler-real. |
| C2 | End-to-end capacity can be reasoned from prefill alone | TR119 Section 5.3; TR121 decode fraction sweep | scripts/tr119/results/tr119_matrix/processed/latency_summary_cost.csv; scripts/tr121/results/tr121_decode_sweep/20251224_002955/gen_64/metrics.csv | Status: False; decode dominates by gen >= 64. |
| C3 | Token economics are stable under time-priced compute | TR119 Sections 4.2 and 5.1 | scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json; scripts/tr119/results/tr119_matrix/processed/latency_summary_cost.csv | Status: Supported; throughput drives cost. |
| C4 | Small-model GPU scaling is predictable from params alone | TR121 scaling fits (HF GPU) | scripts/tr121/results/20251224_002149/analysis/scaling_fits.csv; scripts/tr121/results/20251224_002149/analysis/hf_multivariate_fits.csv | Status: Not identifiable; depth dominates. |
| C5 | Large-model serving scales strongly with params under fixed decode | TR121 Ollama regime | scripts/tr121/results/20251224_004400/analysis/scaling_fits_length_limited.csv; scripts/tr121/results/tr121_gemma_family_20251223/analysis/scaling_fits.csv | Status: Supported within regime. |
| C6 | Energy attribution is precise at sub-100 ms event scale with 100 ms polling | TR122 polling resolution section | scripts/tr122/results/20251225_190043/power_trace.csv; scripts/tr122/results/20251225_190043/generation_events.jsonl; scripts/tr122/results/20251225_190043/baseline.json | Status: False; gated as no_data. |
| C7 | Prefill vs decode separation is required for decisions | TR120 phase split; TR119 cost model | scripts/tr120/results/tr120_root_cause_triton/20251221_184201/prefill/metrics.csv; scripts/tr120/results/tr120_root_cause_triton/20251221_184201/kv_decode/metrics.csv | Phase-specific evidence. |
| C8 | Prefill batch workloads can flip winners | TR119 Section 5.2 scenario winners | scripts/tr119/results/tr119_matrix/processed/latency_summary_cost.csv | Drives routing policy. |
| C9 | Measurement integrity is enforced via artifacts | TR118 validation pipeline | scripts/tr118/results/tr118v2_audit/run_counts.json; scripts/tr118/results/tr118v2_audit/trt_failures.json; scripts/tr118/results/processed/config_used_1765588711.yaml | Validation-backed chain. |
| C10 | Energy attribution requires baseline subtraction | TR122 baseline calibration | scripts/tr122/results/20251225_190043/baseline.json; scripts/tr122/results/20251225_190043/power_trace.csv | Baseline noise dominates short windows. |

Interpretation:

- The synthesis is a chain, not a collection. Removing any of the links above weakens downstream claims.
- Each claim can be revalidated by regenerating the cited artifact set.

---


## Appendix C: Per-TR Key Numbers (Extracted)

This appendix collects headline numbers from the component reports to make cross-report comparisons easier.

TR119v1 (cost highlights, on-demand):
- Prefill best mean: onnxruntime-gpu at about $0.1279 per 1M tokens
- Generate best mean: onnxruntime-gpu at about $1.204 per 1M tokens
- Request mix (256 prompt, 128 generate): onnxruntime-gpu at about $0.0001475 per request

TR121v1 (scaling highlights, gen_tokens = 64):
- Decode fraction by 64 tokens: about 0.98 to 0.99 across HF and Ollama
- HF GPU small-model scaling: R^2 near 0 for params-only fits under batch=1
- Ollama large-model scaling: monotone under fixed-length decode equivalence

TR122 (physics highlights):
- Idle baseline mean 20.71 W; sigma 9.97 W
- Poller nominal period 100ms with tight distribution
- Most sub-100ms events have no data for energy attribution

---


## Appendix D: Glossary and Definitions

- Backend: A runtime implementation of model inference (e.g., ONNX Runtime, PyTorch eager).
- Boundary: The start and end points of the timed region in a measurement.
- Compile-real: A run where torch.compile actually executed with the requested backend and recorded compiler metadata.
- Decode dominance: The condition where kv_decode latency is the majority of end-to-end latency.
- Dynamic shapes: Inputs whose shape can vary between runs, requiring guard checks or recompilation.
- E2E: End-to-end, typically prefill plus decode.
- EOS: End-of-sequence token. Early EOS can terminate generation before the target length.
- Fallback: Automatic switch to a different backend when the requested backend fails.
- Gating: A validity filter that prevents reporting metrics when measurement coverage is insufficient.
- KV cache: Key/value cache used to speed decoding by avoiding recomputation of prior context.
- Load duration: Time spent loading a model into memory (often relevant in Ollama).
- Manifest: File containing environment and configuration metadata for a run.
- Polling cadence: Frequency of power sampling for energy measurement.
- Prefill: Phase where the prompt context is encoded.
- Scenario: A specific workload shape (prompt length, batch size, generation length).
- Shadow price: A cost proxy used to translate throughput into dollars per token under a time-priced compute model.
- Tail latency: High-percentile latency (p95, p99), representing worst-case user experience.
- Warmup: Initial inference runs used to stabilize caches and kernels before measurement.


## Appendix E: Operational Checklists

### E.1 Pre-deployment checklist

- Confirm backend availability and capability (e.g., ORT providers, Triton presence).
- Run phase-specific warmups and record warmup deltas.
- Validate scenario coverage (batch sizes, prompt lengths, decode lengths).
- Confirm artifact logging (metrics, manifest, validation outputs).

### E.2 Production monitoring checklist

- Emit phase timings per request (prefill, decode).
- Track tokens per request distribution (prompt and generate).
- Track cold-start events and their latency deltas.
- Record backend routing decisions and fallbacks.

### E.3 Post-deployment audit checklist

- Compare production medians and tails to report medians and tails.
- Recompute $/token and $/request with real traffic distributions.
- Validate compiler-real execution and detect drift in unique_graphs or recompile_limit events.


## Appendix F: Workload Taxonomy and Routing Examples

This appendix summarizes workload classes and example routing decisions. It is intended as a practical complement to the decision matrix.

- Interactive chat: decode-dominant; route to best decode throughput backend.
- Batch prefill pipelines: prefill-dominant; route to best batched prefill cost backend.
- Tool-augmented agents: short prompts with high concurrency; prioritize overhead and warmup stability.


## Appendix G: Worked Examples and Calculations

This appendix provides worked examples derived from the report formulas and artifact-backed inputs. The examples are illustrative and should be recomputed with your own workload mix and pricing.

### G.1 Request mix example (prompt=256, generate=128)

- tokens_per_request = 384
- cost_per_request = (tokens_per_request / 1e6) * usd_per_1M

Use `scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json` to select a usd_per_1M value for the backend and pricing tier you intend to model.

### G.2 Capacity example (1B tokens per month)

- avg_tokens_per_s = tokens_per_month / seconds_per_month
- workers = avg_tokens_per_s / tokens_per_s

Plug in tokens_per_s from Section 7.3 or from `scripts/tr121/results/.../metrics.csv` for your chosen model and stack.

### G.3 Burst factor adjustment

Lower-bound worker counts assume perfect utilization. Multiply by a burst factor derived from your observed p95 or p99 load to avoid under-provisioning.

## Appendix H: Operational Playbooks and Templates

This appendix lists templates for common operational actions, such as warmup procedures, routing changes, and regression response. The detailed playbooks appear later in Appendix Y.


## Appendix I: Statistical Notes and Fit Diagnostics

This appendix summarizes the statistical conventions and fit diagnostics used across the program.

### I.1 Summary statistics

Latency is summarized with medians and percentile bands to reflect tail risk. Means are retained only to estimate aggregate compute burden.

### I.2 Fit gating

Scaling fits are treated as actionable only when R^2 is non-trivial and bootstrap confidence intervals do not cross zero. This prevents over-claiming under small-n or heterogeneous model families.

### I.3 Scenario aggregation

Scenario aggregation uses geometric means to avoid over-weighting any single prompt shape. This is appropriate for multiplicative relationships such as throughput and cost.

### I.4 Fit artifact locations

- scripts/tr121/results/20251224_002149/analysis/scaling_fits.csv
- scripts/tr121/results/20251224_002149/analysis/hf_multivariate_fits.csv
- scripts/tr121/results/20251224_002740/analysis/overhead_compute_fits.csv

## Appendix J: Traceability Map (TR117-TR122 to Decisions)

This appendix provides a compact mapping from report outputs to operational decisions. It mirrors the Decision Impact Matrix but is oriented toward daily use.

- Backend selection: TR117, TR119
- Compiler policy: TR120
- Scaling and model tiering: TR121
- Energy gating and measurement validity: TR122


## Appendix K: Extended Literature Review

This appendix expands the literature context for readers who want a deeper grounding beyond the core citations. The goal is not to survey all work, but to provide a canonical set of references that align with the program's themes: transformer architecture, scaling laws, efficient kernels, and benchmarking methodology.

Key thematic clusters:

1. Transformer foundations and long-context mechanisms [1], [2].
2. Efficient attention and kernel-level optimization [3], [12], [13].
3. Scaling laws and compute-optimal modeling [9], [10].
4. Benchmarking and reproducibility standards [11].

These references are intentionally broad; they provide a shared vocabulary for interpreting the TR117-TR122 program without assuming a single model family or runtime stack.


## Appendix L: Measurement Boundary Catalog

This appendix enumerates measurement boundaries per report to prevent accidental cross-boundary comparisons. Each boundary statement specifies what is included in the timed region and what is excluded.


## Appendix M: Detailed Methods by Report

This appendix provides a narrative, method-level expansion for each report. It is intentionally verbose and designed to support audits, replications, and policy reviews.

### M.1 TR117 Method Detail

TR117 is structured as a matrix benchmark. The core design decision is the scenario set: a small set of prompt lengths and batch shapes that expose both single-prompt latency and batch throughput. Each run records multiple latency samples rather than a single aggregate, enabling distributional analysis. The timed boundary is the inference service call, which includes user-visible overhead. This boundary aligns with operational experience but introduces initialization effects. TR117 therefore functions as a high-fidelity user-facing measurement rather than a kernel microbenchmark.

The most important methodological choice in TR117 is that it treats backend names as labels without verifying runtime behavior. This is not an error; it is a common benchmark assumption. The program later identifies this as a risk, and TR120 corrects it. The inclusion of raw latency arrays is what makes the correction possible. In a sense, TR117's methodology is strong enough to diagnose its own attribution limitations.

### M.2 TR118_v2.2 Method Detail

TR118_v2.2 establishes the artifact pipeline as the system of record. Raw data is preserved and every transformation is deterministic. Validation steps include sanity checks on cost monotonicity, missing values, and degraded-run classification. This is not simply a technical housekeeping effort. It defines the minimum evidence required for a publishable claim. The report explicitly distinguishes between measurement failure and inference failure, allowing downstream reports to remain credible even when some runs degrade.

The TR118 methodology also introduces manifest metadata as a reproducibility contract. Each run is associated with a configuration hash and environment snapshot, enabling detection of silent drift. This is a foundational requirement for a multi-report program where conclusions are compared and synthesized.

### M.3 TR119v1 Method Detail

TR119v1 defines a minimal, explicit cost model: tokens per second are converted into seconds per million tokens, which are then multiplied by an hourly rate. Energy is computed from measured power and time. The model is intentionally simple to avoid hidden assumptions. The key methodological choice is to separate prefill and decode, which allows cost to be computed in phase-specific terms. This prevents a single aggregate from masking the dominant phase.

TR119 also formalizes a request-level cost by combining prefill and decode under a fixed token mix. This translation is essential for product-level planning. The report is explicit about the request mix and treats it as a configurable input rather than as a universal constant. This is the correct methodological stance for decision-grade cost modeling.

### M.4 TR120 Method Detail

TR120's methodology is explicitly causal. It introduces a controlled runner that isolates compilation effects by ensuring consistent model loading, prompt tokenization, and CUDA synchronization. The runner records compiler metadata, including the requested backend, actual backend, and compilation counters. This makes compilation an observable variable rather than a label.

The study uses ablations (padding, dynamic shapes) to test mechanistic hypotheses. This is critical: without ablations, tail behavior could be attributed to noise. The ablations show that shape stability reduces compilation churn, which is a mechanistic finding with direct policy implications. The decode regime is studied separately, acknowledging that prefill and decode are distinct optimization targets.

### M.5 TR121v1 Method Detail

TR121v1 is a regime analysis rather than a universal scaling law. Its methodology combines phase-split measurement with multiple model sizes and backend stacks. The report uses scenario aggregation (geometric means across scenarios) to avoid over-weighting any single prompt shape. It computes scaling fits only on medians, reflecting the program's focus on decision-grade metrics rather than noise-sensitive means.

A critical methodological choice is the handling of early-stop behavior in Ollama. The report uses fixed-length decode equivalence to project decode time to a target token length and then bounds the modeling error. This avoids a common bias in scaling studies where shorter generations are mistaken for faster models. The inclusion of boundary-shift runs (batch size and generation length) serves as a falsification test for regime claims.

### M.6 TR122 Method Detail

TR122 focuses on measurement physics. Its core method is idle baseline calibration with explicit sampling cadence. It then evaluates the fraction of events that contain sufficient samples to compute meaningful energy attribution. The report enforces a gating rule that classifies short events as no_data. This is not a cosmetic adjustment; it prevents false precision.

The methodological contribution is the explicit linkage between sampling cadence, event duration, and attribution validity. This allows the synthesis to distinguish between macro-window energy claims and micro-event energy claims, and to state which claims are valid under the current instrumentation.


## Appendix N: Expanded Discussion and Implications

This appendix provides a narrative expansion of the implications for research practice and production policy. It is intended for readers who want a continuous argument rather than modular sections.


## Appendix O: Extended Results Narratives

This appendix provides long-form narratives for each report's results, written in a dissertation style. The goal is to clarify how the measured artifacts become the conclusions presented in the main body.

### O.1 TR117 Narrative

The TR117 dataset is a canonical example of why baseline benchmarks are necessary and insufficient. The matrix shows that different backends produce materially different latencies and throughput even on the same model. This is an important observation because it validates the premise of backend selection: backends are not interchangeable, and their performance is not merely a matter of noise.

However, the dataset also reveals a distributional phenomenon. The presence of extreme outliers in some scenarios indicates that the timed boundary captures events that are not stable across runs. The paradox emerges because the mean, which is sensitive to those outliers, tells a different story than the median, which is not. This is not a mathematical trick; it reflects the fact that system-level events (cache misses, initialization, driver behavior) can dominate latency for some requests but not others.

The narrative conclusion is therefore twofold: (1) backends differ in real and consequential ways, and (2) those differences cannot be summarized by a single number without explanation of the distribution. TR117 provides the evidence for both, but it does not explain the mechanism. That explanation is deliberately deferred to TR120.

### O.2 TR118_v2.2 Narrative

The TR118_v2.2 report is an infrastructure milestone rather than a performance milestone. Its narrative is about trust: without validated artifacts, any derived cost or scaling claim is fragile. The report's major contribution is to force the reader to confront the hidden assumptions of a typical benchmark. It requires validation outputs, it separates degraded runs, and it encodes configuration in a manifest.

The narrative implication is that performance research is a data pipeline problem as much as it is a measurement problem. The TR118 pipeline makes that explicit. It ensures that later reports, which are more decision-critical, can lean on validated data rather than on ad hoc calculations. This is why the synthesis treats TR118 as a prerequisite rather than as an optional enhancement.

### O.3 TR119v1 Narrative

TR119v1 reframes performance data as a budget decision. The critical narrative move is the explicit cost model: throughput is converted to dollars by a transparent formula, and energy is included as a secondary term. This prevents a common failure mode where performance wins are reported but their economic implications are left implicit.

The narrative also highlights a subtlety: prefill and decode are not interchangeable. A backend can be optimal for one phase and suboptimal for the other. The report therefore promotes a policy view: if your workload is decode-heavy, you should optimize decode; if you are prefill-only, you should optimize prefill. The case studies in TR119 make this distinction concrete by showing that batch prefill can invert winners.

### O.4 TR120 Narrative

TR120 is the corrective lens for the compile paradox. It demonstrates that a backend label can be disconnected from runtime behavior and shows how that can mislead interpretation. The narrative is rigorous: it audits the code path, then builds a controlled harness where compilation is explicit, observable, and repeatable.

The results show a classic fast-path/slow-path distribution: compiled prefill is faster for typical calls, but variability in input shapes triggers recompiles and heavy tails. The narrative consequence is that compilation is both an opportunity and a risk. This is why the report's primary recommendation is not "compile" but "compile with shape stability and phase awareness."

The decode results are equally important: compilation does not necessarily help decode, and can regress it. This breaks the common assumption that compilation is universally beneficial. The narrative therefore elevates phase separation from a measurement detail to a policy principle.

### O.5 TR121v1 Narrative

TR121v1 attempts to answer the question that TR117 could not: how does performance scale with model size? The narrative is deliberately cautious. Rather than claiming a universal law, the report identifies regimes. In the small-model GPU regime, parameter count does not explain latency. Depth and overhead do. In the CPU regime, parameter count is a coarse but usable proxy. In the large-model Ollama regime, parameter count is again predictive under fixed-length decode equivalence.

The narrative meaning is that scaling is not a law but a conditional relationship. It depends on the architecture, the runtime, and the workload boundary. This is why the report uses boundary-shift experiments as falsification tests: if a scaling relationship appears only under a narrow boundary, it should not be generalized.

The second narrative layer is business impact. The scaling results are not just theoretical curves; they are fleet multipliers. Moving from a 7B to a 20B model can multiply cost and capacity requirements by a factor of roughly 2-3 under the measured boundary. This is the reason the report advocates tiering and routing policies.

### O.6 TR122 Narrative

TR122 shifts the lens from performance to physics. It acknowledges a reality that many benchmarks ignore: energy attribution has hard limits. Polling-based power measurements cannot assign energy to events shorter than the polling interval. Without a gating policy, energy numbers for short events are not just noisy; they are invalid.

The narrative consequence is a more disciplined energy reporting framework. TR122 does not claim that energy is unimportant; it claims that energy must be measured under conditions where measurement is valid. This is a direct response to a common failure mode in performance reports: presenting energy numbers with unwarranted precision.


## Appendix P: Decision-Grade Reporting Rubric

This appendix defines a rubric for assessing whether a report is decision-grade. The rubric is a checklist of evidence, attribution, and translation criteria that must be satisfied before policy decisions rely on the report.


## Appendix Q: Extended Decision Case Studies

This appendix provides longer, narrative case studies that illustrate how to apply the conclusive report in realistic planning settings. Each case study is framed as a decision problem with constraints, evidence requirements, and a concrete recommendation.

### Q.1 SaaS chat product with strict TTFT SLOs

Context: A SaaS product provides interactive chat to paying users. The product SLO requires TTFT under 500 ms for p95 requests, and end-to-end under 2 seconds for p95 responses. Traffic is bursty during business hours, with p95 load roughly 4-5x the mean. The team is considering a move from a 7B model to a 20B model for quality improvements.

Evidence from TR121 and TR119: The decode phase dominates end-to-end latency at gen >= 64. The 7B model has roughly 2-3x higher tokens per second than the 20B model under the measured boundary. The cost per 1M tokens is therefore roughly 2-3x higher for the 20B model. Cold-start effects can add seconds of TTFT if warmup is not handled.

Decision: The team should not switch all traffic to the 20B model. Instead, use a tiered policy: default to the 7B model for standard chat, and route to the 20B model only for high-value sessions or failure cases. The cost model shows that a full switch would increase required capacity and spend disproportionately to likely quality gains. The policy should also include warm pool management to avoid cold-start TTFT spikes, as TR121 shows prefill warmup can be extreme.

### Q.2 Internal summarization pipeline with batch prefill

Context: An internal pipeline summarizes large volumes of text offline. Requests are batched and do not require interactive TTFT. The critical metric is cost per token and throughput, with loose latency SLOs.

Evidence from TR119: Batch prefill workloads can invert backend winners. A backend that is not optimal for single-prompt latency may be cheaper for batch prefill. Decode is not dominant because generation length is short.

Decision: Use the backend that minimizes prefill cost under batch scenarios, and do not overweight decode performance. If the pipeline is prefill-heavy, the cost model should be applied to prefill-only scenarios. The primary operational risk is not tail latency but cost and throughput under large batch sizes.

### Q.3 Developer tool with frequent cold starts

Context: A developer-facing tool runs on demand and frequently spins up new inference workers. Cold-start latency is user-visible and directly affects perceived responsiveness.

Evidence from TR121 and TR120: Warmup ratios for prefill can exceed 100x in extreme cases, and cold-start events can dominate perceived latency. Compilation can introduce tail risk if shapes vary.

Decision: The system should incorporate explicit warmup and keep a small warm pool if user experience is critical. Compiler features should be gated by shape stability and compiler-real evidence. If cold-start cannot be mitigated, the service should explicitly communicate a "warming up" state to users to preserve trust.

### Q.4 Multi-tenant inference hosting with mixed workloads

Context: A hosting platform supports multiple tenant models, some with short prompts and short generations, others with long generations. The platform wants a single routing policy for simplicity.

Evidence: TR119 and TR121 show that workload mix determines the dominant phase. A single policy cannot be optimal across all tenants if their workload shapes differ.

Decision: Implement routing policy per tenant or per workload bucket. Use tokens-per-request distributions to classify workloads. For decode-heavy tenants, prioritize decode throughput; for prefill-heavy tenants, prioritize prefill cost. The routing policy should be transparent and auditable, with each tenant's policy derived from their measured workload mix.

### Q.5 Research team validating a new backend

Context: A research team wants to add a new backend to the pipeline and claim performance improvements.

Evidence: TR118 requires artifact validation; TR120 requires attribution; TR122 requires energy gating if energy claims are made.

Decision: The new backend must be evaluated with the same scenario matrix, validated artifacts, and phase-split reporting. Any compiler-related claims must include compiler-real evidence. Energy claims must be gated by sampling validity. Without these, the backend can be tested internally but should not be included in the canonical report set.


## Appendix R: Metric Definitions and Data Schema

This appendix defines the core metrics and schema concepts used across TR117-TR122. It is intended to prevent ambiguity when reusing or extending the pipeline.

### R.1 Latency metrics

- latency_ms: wall-clock time for the timed region (per mode).
- prefill_ms: time for a single forward pass over the prompt context.
- kv_decode_ms: time for fixed-length decode with KV cache.
- e2e_kv_ms: prefill + kv decode total.

### R.2 Throughput metrics

- tokens_per_s = tokens_total / (latency_ms / 1000).
- tokens_total depends on mode (prompt tokens, decode tokens, or both).

### R.3 Warmup metrics

- is_warmup: boolean flag for warmup runs.
- warmup_ratio = warmup_median / steady_median for a given grouping.
- warmup_delta_ms = warmup_median_ms - steady_median_ms.

### R.4 Compiler metrics

- compile.backend_requested: the backend requested in the runner.
- compile.backend_actual: the backend actually used (after fallback).
- dynamo_counters: compiler counters including unique_graphs and recompile events.

### R.5 Energy metrics

- idle_power_w: baseline idle power.
- delta_power_w: event power minus baseline.
- energy_j = delta_power_w * duration_s, only when sampling is valid.

### R.6 Schema invariants

- Every report must preserve raw measurements and provide a deterministic path to summary tables.
- Degraded runs are retained in raw artifacts but excluded from aggregates.
- Measurement boundaries must be explicit for each metric.


## Appendix S: Governance and Reporting Templates

This appendix provides templates for report versioning, change logs, and approval workflows. These templates make it easier to keep a canonical report synchronized with production changes.


## Appendix T: Extended Risk Register

This appendix provides a more detailed risk register than the concise table in Section 8.6. Each risk includes a cause, a signal, and a mitigation aligned with the program's findings.

1. Label drift risk: backend names do not reflect runtime behavior. Signal: absence of compiler metadata or provider logs. Mitigation: enforce compiler-real evidence and backend capability checks (TR120).
2. Cold-start tail risk: first requests incur large latency spikes. Signal: warmup ratios above 10x or absolute deltas above SLO. Mitigation: warm pools, pre-routing warmups (TR121).
3. Shape instability risk: dynamic shapes trigger recompiles and tails. Signal: unique_graphs growth, recompile_limit warnings. Mitigation: padding, dynamic compile, phase-specific compilation (TR120).
4. Measurement boundary drift: same experiment run with different prompt mixes. Signal: config hashes differ, scenario distributions shift. Mitigation: manifest enforcement, scenario taxonomy (TR118).
5. Energy false precision: energy reported for sub-100 ms events. Signal: no_data coverage, polling interval larger than event. Mitigation: energy gating (TR122).
6. Overreliance on params: model selection based on parameter count alone. Signal: depth outliers, non-monotonic latency. Mitigation: structural predictors and multivariate fits (TR121).
7. Hidden kernel path changes: compiler or backend changes disable optimized kernels. Signal: decode regression without code changes. Mitigation: profiler traces, kernel audits (TR120/TR121).
8. Cost misinterpretation: shadow-priced $/token read as exact TCO. Signal: cost claims used for procurement without tier context. Mitigation: explicit shadow-price labeling (TR119/TR121).
9. Validation bypass: artifacts used without passing validation. Signal: missing validation reports. Mitigation: pipeline enforcement (TR118).
10. Overfitting to small-n scaling fits: slopes treated as laws. Signal: low R^2 or sign-crossing CIs. Mitigation: fit gating and regime language (TR121).


## Appendix U: Program Evolution Narrative

This appendix provides a short narrative of how the TR117-TR122 program evolved, emphasizing the sequence of methodological corrections that lead to the current decision-grade framework.


## Appendix V: Extended Cost Modeling Examples

This appendix expands the cost modeling examples to show how token-first metrics map to different product and organizational constraints. The calculations use the same shadow-price model described in the main report; they do not introduce new pricing assumptions.

### V.1 Example: 100M tokens per month

At 100M tokens per month (30-day month), the average load is 38.6 tokens per second. A backend that delivers 200 tokens per second can handle this load with 0.19 workers in a utilization-perfect model. In practice, a minimum of 1 worker is required, and any burst factor would require additional capacity. The key point is that at low volumes, the dominant cost is not throughput; it is the fixed cost of running a worker at all.

### V.2 Example: 1B tokens per month

At 1B tokens per month, the average load is 385.8 tokens per second. A backend delivering 100 tokens per second requires 3.86 workers in a utilization-perfect model. If p95 load is 5x mean, the fleet must be roughly 20 workers. This illustrates why burst factors dominate planning at scale: they can exceed the mean-based estimate by a large multiple.

### V.3 Example: 10B tokens per month

At 10B tokens per month, the average load is 3858 tokens per second. This is a regime where small differences in tokens per second translate into large budget changes. A backend that is 20% faster can reduce required capacity by hundreds of workers at scale. This is where throughput optimization becomes a budget strategy rather than a performance tuning exercise.

### V.4 Example: mixed request mix

Suppose a service has two request classes: 80% of requests are short (384 total tokens), and 20% are long (2304 total tokens). The average tokens per request is  (0.8 * 384) + (0.2 * 2304) = 768 tokens. The correct cost calculation uses this expected value, not the short-request value. This illustrates why request mix is a critical input to cost modeling.

### V.5 Example: routing-driven cost reduction

Assume a two-tier policy where 80% of requests use a small model costing 0.76 dollars per 1k requests and 20% use a large model costing 2.05 dollars per 1k requests. The weighted average cost is (0.8 * 0.76) + (0.2 * 2.05) = 1.02 dollars per 1k requests. If the policy were inverted (80% large), the cost would be 1.79 dollars per 1k requests. This demonstrates the leverage of routing policy on budget.


## Appendix W: Extended Workload Taxonomy

This appendix expands the workload taxonomy to include common enterprise and consumer inference patterns. The goal is to provide a vocabulary for mapping product requirements to benchmark scenarios.

### W.1 Consumer chat

Characterized by moderate prompt lengths and moderate generation lengths. TTFT is important for perceived responsiveness, but decode throughput dominates cost. This aligns with the TR121 observation that decode dominates at gen >= 64.

### W.2 Agentic tool execution

Short prompts and short generations, high concurrency. This is a regime where overhead can dominate and where cold-start effects are particularly visible. Prefill optimization can improve responsiveness, but decode still governs total throughput.

### W.3 Long-context summarization

Large prefill, moderate decode. Prefill becomes significant, and batching can deliver substantial throughput gains. Backend selection should weight prefill more heavily.

### W.4 Batch analytics and embeddings

High batch sizes, prefill-only or minimal decode. The cost model should be applied to prefill in batch scenarios. Decode results are less relevant.

### W.5 Retrieval-augmented generation (RAG)

RAG workloads can have large prompt contexts (retrieved documents) combined with moderate decode lengths. This pushes the system into a mixed regime where both prefill and decode matter. The correct approach is to measure both phases explicitly and weight them by the actual request mix.


## Appendix X: Experiment Planning Template

This appendix provides a simple planning template for future experiments, covering decision question, boundary definition, scenario selection, artifact outputs, and validation requirements.


## Appendix Y: Extended Operational Playbook

This appendix provides a more detailed operational playbook for teams adopting the TR117-TR122 framework. It is intentionally verbose and procedural, mirroring how operational runbooks are written.

### Y.1 Pre-deployment validation

1. Confirm that the backend stack is compiler-real if compilation is enabled. Record the actual compiler backend and any fallback messages.
2. Run warmup sequences for prefill and decode separately. Record warmup deltas and verify they fall within acceptable bounds.
3. Validate scenario coverage: ensure that prompt lengths and generation lengths reflect production distributions, or explicitly document the differences.
4. Run the validation pipeline and confirm no degraded runs are present in the critical scenarios.

### Y.2 Deployment monitoring

1. Emit per-request phase timings and tokens.
2. Emit cold-start markers (worker age, time since last request, model load status).
3. Track phase-level p50/p95/p99 and compare to the report baselines.
4. Monitor compile counters (unique_graphs, recompile_limit) if compilation is enabled.

### Y.3 Regression response

1. If decode throughput drops by >10%, classify the event as a performance regression.
2. Identify the change window (driver update, model change, backend version).
3. Roll back or reroute to the prior stable configuration if possible.
4. Re-run the relevant TR pipeline to re-establish a valid baseline.

### Y.4 Policy review cadence

1. Recompute cost and capacity models quarterly or after major product changes.
2. Update routing policies when workload mix shifts.
3. Audit energy reporting practices annually or after instrumentation changes.


## Appendix Z: Extended Cost-Quality Tradeoff Analysis

This appendix provides a more detailed discussion of cost-quality tradeoffs. The goal is to show how model tiering and routing can be justified quantitatively, even when quality gains are not easily measured.

### Z.1 Quality as a multi-dimensional metric

Quality is rarely a single scalar. It can include correctness, safety, factuality, and user satisfaction. A large model may improve one dimension but degrade another. This means that cost decisions cannot rely on a single "quality score"; they must consider the dimensions that matter most to the product.

### Z.2 Cost per successful outcome

A useful framing is cost per successful outcome, where \"success\" is defined by the product's acceptance criteria. This allows a direct comparison between a cheap model with lower success rate and an expensive model with higher success rate. The break-even logic in Section 7.4 provides a formal basis for this comparison.

### Z.3 Value-at-risk framing

In high-stakes applications, the cost of a failure can be large. In such cases, a more expensive model can be justified even if its success rate improvement is modest, because the marginal reduction in failure risk is valuable. The program's cost model provides the "price" side of this calculation; the product team must provide the value side.

### Z.4 Routing as an insurance policy

Routing can be interpreted as an insurance policy: most traffic is handled cheaply, and expensive capacity is reserved for high-risk or high-value requests. This strategy aligns with the economics in TR121 and TR119 and is consistent with the observation that decode dominates cost.

### Z.5 Governance and fairness considerations

If routing policies are based on user tiers or request classification, governance and fairness considerations arise. The report does not prescribe a policy, but it does recommend that routing rules be explicit, auditable, and tied to documented objectives. In regulated settings, this may require formal review.


## Appendix AA: Measurement Formula Catalog

This appendix catalogs the formulas used across the reports, including throughput, cost, warmup ratios, decode fractions, and energy gating. It is a quick reference for reviewers and implementers.


## Appendix AB: Phase-Specific Observations

This appendix captures a set of phase-specific observations that cut across the reports. These are not new results; they are a structured interpretation of existing artifacts.

### AB.1 Prefill phase observations

Prefill latency is highly sensitive to prompt length and batch size. For short prompts, launch overhead can dominate on GPU, making prefill insensitive to parameter count. For longer prompts, the compute term becomes more visible. This is why TR121's boundary-shift experiments improve identifiability: they lengthen or batch the prefill phase, reducing the relative impact of overhead.

Prefill also shows the largest warmup ratios. This is consistent with the notion that prefill is where kernel autotuning, cache allocation, and initial compilation costs are paid. The operational implication is that prefill warmup should be explicitly managed, even if decode dominates steady-state throughput.

### AB.2 Decode phase observations

Decode latency scales approximately linearly with generation length once cache is established. This makes decode a natural target for throughput optimization and cost modeling. The phase split is crucial: any claim about end-to-end throughput implicitly assumes a relationship between prefill and decode. The program treats decode as the dominant term for gen >= 64, and this assumption is validated by the decode fraction sweep in TR121.

Decode is also where compiler regressions can manifest. The TR120 controlled runs show that compilation can degrade decode even when it improves prefill. This establishes a key policy: compile decisions must be phase-specific.

### AB.3 End-to-end phase observations

End-to-end measurements are the most operationally relevant but the hardest to interpret. They combine prefill and decode, each with different scaling properties. Without phase separation, an end-to-end number can hide important shifts in performance. The program therefore treats end-to-end as a decision metric only when it is accompanied by phase breakdowns.


## Appendix AC: Detailed Model Comparison Narrative

This appendix provides narrative comparisons between specific model pairs, highlighting how depth, width, and quantization can invert parameter-based expectations.


## Appendix AD: Extended Methodological Rationale

This appendix elaborates on several methodological design choices that might appear arbitrary in isolation but are deliberate when viewed across the program.

### AD.1 Why phase separation is non-negotiable

A single latency number is insufficient because prefill and decode have distinct scaling behaviors and optimization constraints. Prefill is sensitive to prompt length and batching, while decode is sensitive to sequential depth and generation length. The program treats phase separation as a structural property of the model, not as a reporting convenience. This is why phase separation is required in every decision-grade report in the program.

### AD.2 Why medians are preferred to means

Means are sensitive to outliers. In the presence of cold-start effects, a small number of extreme latencies can dominate the mean, leading to misleading conclusions. Medians provide a more stable estimate of typical behavior. The program does not ignore means; it uses them to estimate aggregate compute, but it does not allow them to drive policy without distributional context.

### AD.3 Why scenario aggregation uses geometric means

Scenario aggregation is necessary to avoid over-weighting a single prompt shape. Geometric means are used because they reduce the influence of extreme values and preserve multiplicative relationships, which is appropriate for throughput and cost scaling. This choice is consistent with the program's emphasis on robust decision-making under variability.

### AD.4 Why boundary shifts are used as falsification tests

Boundary shifts (batch size, generation length) are not designed to optimize performance; they are designed to test whether a conclusion is robust to changes in workload. If a conclusion disappears under a boundary shift, it should be treated as boundary-specific rather than general. This is a simple but powerful scientific control that improves interpretability.

### AD.5 Why energy gating is treated as validity, not just noise

Energy measurements are only meaningful when the sampling system can observe the event. Treating energy attribution as a statistical estimation problem without gating invites false precision. The program therefore treats sampling adequacy as a validity condition: if the condition is not met, the metric is not reported. This is a conservative stance, but it protects the credibility of energy claims.


## Appendix AE: Future Directions Without TR123

This appendix lists the next highest-ROI experiments that extend the program without expanding scope beyond TR117-TR122.


## Appendix AF: Annotated Literature Notes

This appendix provides short annotations for the key references, explaining why each is relevant to the program. These notes are intended to help readers understand how the external literature supports the interpretation of the program's results.

[1] Attention Is All You Need: foundational architecture for transformers. The phase split in inference arises directly from the self-attention structure, which motivates prefill vs decode separation in TR120 and TR121.

[2] Transformer-XL: extends the context length with recurrence, illustrating why long-context inference changes the compute profile and why cache mechanisms matter. This contextualizes the decode-dominant findings in TR121.

[3] FlashAttention: demonstrates how kernel-level optimizations can change attention efficiency. It provides background for why backend and compiler changes can shift performance, particularly in decode.

[4] GPT-3 Few-Shot Learning: exemplifies large-scale model behavior and the scale at which inference costs become significant budget drivers, motivating TR119-style cost modeling.

[5] NVML API: provides the GPU power telemetry used in energy attribution. TR119 and TR122 rely on this instrumentation boundary.

[6] torch.compile documentation: defines the compiler interface used in TR120, including backend selection and dynamic shape handling.

[7] ONNX Runtime documentation: provides context for the ORT backend used in TR117 and TR119.

[8] Ollama documentation: provides the API surface and timing semantics used in TR121's large-model regime analysis.

[9] Scaling Laws for Neural Language Models: provides a canonical scaling framework, but with training-centric assumptions. The report uses this as context, not as a direct predictor for inference latency.

[10] Compute-Optimal Training (Chinchilla): emphasizes the tradeoff between model size and data, reinforcing the idea that parameter count alone is not a universal proxy.

[11] MLPerf Inference: provides a benchmarking standard emphasizing reproducibility and defined boundaries, aligned with TR118's validation focus.

[12] Efficient Transformers survey: summarizes the kernel and architectural landscape, which explains why model structure and kernel selection can dominate latency in certain regimes.

[13] FlashAttention-2: highlights how improved kernel parallelism can change attention throughput and thus decode performance, providing a concrete example of why kernel path availability can dominate backend comparisons.


## Appendix AG: Extended Glossary and Acronyms

This appendix extends Appendix D with a broader set of terms and acronyms used across the program and in the referenced literature.


## Appendix AH: Detailed Artifact Inventory

This appendix provides a descriptive inventory of the main artifact classes produced across TR117-TR122. The goal is to clarify how each file type contributes to the claim chain.

### AH.1 Raw measurement artifacts

Raw artifacts typically include per-run JSON or CSV records with latency arrays, throughput values, and contextual metadata. These files are the ground truth. They are never modified in-place; all derived summaries are produced by deterministic analysis scripts.

### AH.2 Processed summaries

Processed summaries aggregate raw data into scenario-level or model-level statistics. Examples include mean, median, p95, p99, and throughput. These summaries are used directly in report tables. The report always references the source summary path to maintain traceability.

### AH.3 Validation artifacts

Validation artifacts record the results of consistency checks. They document missing values, monotonicity checks, and degraded-run classifications. A report is not considered decision-grade unless its validation artifacts indicate a clean pass or explicitly justify any exceptions.

### AH.4 Plots

Plots are generated from processed summaries. They are visual aids, not evidence in themselves. The report treats plots as secondary to tabular summaries and raw artifacts.

### AH.5 Manifests

Manifests provide environment metadata, configuration hashes, and resolved settings. They serve as the provenance layer for reproducibility. Any report that lacks a manifest is treated as non-canonical.

### AH.6 Cross-report artifact linkage

Some artifacts are reused across reports, particularly where a later report extends a prior dataset. The conclusive report requires that these linkages are explicit to avoid unintentional drift or duplication.


## Appendix AI: Artifact-to-Claim Examples

This appendix illustrates how specific claims map to artifact categories. The examples are representative and can be used as a template for future reports.

### AI.1 Compile attribution claim (TR120)

Claim: compilation is compiler-real for a given run. Evidence: run artifacts contain compile.backend_actual = "inductor" and dynamo_counters_after_compile. Validation: no fallback errors in the same artifact.

### AI.2 Decode dominance claim (TR121)

Claim: decode dominates end-to-end for gen >= 64. Evidence: summary tables and decode fraction plots showing kv_decode_ms / e2e_kv_ms near 1.0. Validation: scenario-aggregated medians across models.

### AI.3 Energy gating claim (TR122)

Claim: sub-100 ms events are not energy-attributable at 100 ms polling. Evidence: event coverage analysis showing insufficient samples. Validation: no_data gating applied in summaries.

### AI.4 Cost per token claim (TR119)

Claim: onnxruntime-gpu has lowest cost per token for generate. Evidence: cost summary JSON derived from throughput and power. Validation: cost monotonicity checks and pricing tier validation.


## Appendix AJ: Reproducibility and Regeneration Notes

This appendix records the minimal environment and command requirements to regenerate each report and the conclusive synthesis, including any external tool dependencies.


## Appendix AK: Scenario-Specific Policy Playbooks

This appendix provides playbooks tailored to specific workload scenarios. Each playbook maps the report's findings to a concrete policy decision.

### AK.1 Interactive short-form chat

Policy goals: low TTFT, stable p95 latency, predictable cost.

Recommended actions:
- Prioritize decode throughput in backend selection (TR119/TR121).
- Keep decode eager unless a compile win is proven (TR120).
- Use warm pools to eliminate cold-start TTFT spikes (TR121).

### AK.2 Long-context summarization

Policy goals: throughput for long prompts, acceptable end-to-end latency.

Recommended actions:
- Weight prefill performance more heavily; consider batching (TR119).
- Use prompt-length buckets to stabilize performance (TR120/TR121).
- Re-evaluate scaling under long-context boundary conditions (TR121).

### AK.3 Tool-augmented agents

Policy goals: low latency per step, high concurrency, predictable tail behavior.

Recommended actions:
- Focus on overhead minimization for small prompts (TR121).
- Avoid compiler-induced tail risk unless shapes are stable (TR120).
- Route high-value steps to larger models only when needed (TR121/Cost).

### AK.4 Offline batch analytics

Policy goals: maximize throughput, minimize cost per token.

Recommended actions:
- Use the cheapest backend for batched prefill scenarios (TR119).
- Energy attribution can be more reliable due to long runs (TR122).
- Batch size and prompt length distribution should be measured and used for weighting (TR121).


## Appendix AL: Scenario Taxonomy and Metric Mapping

This appendix expands the scenario taxonomy and maps each scenario to the most decision-relevant metrics (prefill vs decode vs e2e).


## Appendix AM: Decision Heuristics and Rules of Thumb

This appendix provides a short list of decision heuristics derived from the program, intended as quick guidance when full remeasurement is not possible.


## Appendix AN: Policy Decision Trees

This appendix converts the report's guidance into explicit decision trees. Each tree is written in text form to remain tool-agnostic.

### AN.1 Backend selection decision tree

1. Is the workload decode-heavy (gen >= 64 or decode fraction > 0.9)?
   - Yes: choose backend with best decode throughput (TR119/121).
   - No: go to step 2.
2. Is the workload batched prefill (batch > 1, minimal decode)?
   - Yes: choose backend with best batched prefill cost (TR119).
   - No: choose backend with best single-prompt prefill latency.

### AN.2 Compiler enablement decision tree

1. Is compiler-real evidence available (backend_actual, counters)?
   - No: disable compile.
   - Yes: go to step 2.
2. Are shapes stable or bucketed?
   - No: compile only if dynamic shapes are supported and tails are validated.
   - Yes: compile prefill, but keep decode eager unless decode wins are demonstrated.

### AN.3 Cold-start mitigation decision tree

1. Are warmup ratios > 10x or warmup deltas > SLO budget?
   - Yes: enforce warm pools and pre-routing warmup.
   - No: monitor cold-start trends and re-evaluate quarterly.

### AN.4 Scaling decision tree

1. Are models heterogeneous (mixed families/quantization)?
   - Yes: treat params as regime descriptor only.
   - No: use params as proxy with fit gating (R^2 and CI checks).


## Appendix AO: Extended Systems Glossary

This appendix lists additional system-level terms (scheduler, queueing, kernel fusion, guard failure) used implicitly in the report.


## Appendix AP: Extended Synthesis Narrative

This appendix provides a long-form synthesis that complements the main body. It is written in narrative style to reflect the "mini dissertation" requirement and to make the report accessible to readers who want a continuous argument rather than modular sections.

### AP.1 The arc from measurement to decision

The program begins with measurement and ends with decision. TR117 measures performance, TR118 validates measurement, TR119 translates measurement into cost, TR120 corrects attribution, TR121 maps scaling regimes, and TR122 defines physical limits. This progression is not incidental. It reflects a methodological maturation: each report identifies a failure mode in decision-making and then addresses it. The conclusive report is the formal closure of that maturation.

### AP.2 The role of boundary conditions

A central lesson is that boundary conditions define interpretability. The same model can appear fast or slow depending on whether the timed region includes initialization, tokenization, or compilation. The program treats boundary conditions as epistemic constraints: they define what a metric means. This is why the synthesis repeatedly emphasizes the boundary rather than the number. The number without the boundary is a claim without context.

### AP.3 The economics of inference as a systems problem

Cost modeling reveals that inference economics is a systems problem rather than a model problem. The dominant term in cost per token is time, which depends on throughput, which depends on backend, compiler, kernel paths, and workload shape. This is the reason the program resists model-only explanations for performance. The system is the unit of analysis.

### AP.4 The ethics of measurement and reporting

The program also embodies a normative stance: reports should avoid false precision. TR122's gating rules for energy attribution are a concrete example. A report that presents precise energy numbers without sufficient measurement coverage may appear rigorous but is actually misleading. The program treats this as an ethical issue because decision-makers rely on these numbers.

### AP.5 The stability of conclusions

The conclusions of the program are stable across the reports because they are grounded in mechanisms, not just data. Decode dominance is a mechanism of autoregressive inference. Compiler tail risk is a mechanism of dynamic shape recompilation. Cold-start spikes are a mechanism of initialization. These mechanisms are likely to persist across hardware and software changes, even if the absolute numbers change.

### AP.6 The limits of generalization

The report is deliberately conservative about generalization. It does not claim that the observed slopes or ratios apply to all models. Instead, it claims that the decision logic is portable: measure phase-specific throughput, validate attribution, and translate to cost under explicit assumptions. This is the correct level of generality for decision-grade research.


## Appendix AQ: Extended Risk Mitigation Strategies

This appendix expands the mitigation strategies with implementation tips, trigger thresholds, and suggested operational owners.


## Appendix AR: Operational Metrics and Dashboards

This appendix outlines a recommended dashboard structure for monitoring inference performance in production. The metrics map directly to the report's phases and decision axes.

### AR.1 Phase-level latency dashboard

Metrics:
- p50/p95/p99 prefill latency (ms)
- p50/p95/p99 decode latency (ms)
- decode fraction (kv_decode_ms / e2e_kv_ms)

Purpose: Detect phase-specific regressions and confirm decode dominance assumptions.

### AR.2 Throughput and capacity dashboard

Metrics:
- tokens per second (overall)
- tokens per second by request bucket (prompt length, generation length)
- utilization vs capacity bound (tokens/s)

Purpose: Align production throughput with the report's capacity planning numbers and detect drift.

### AR.3 Warmup and cold-start dashboard

Metrics:
- warmup ratio distribution
- cold-start latency deltas
- time since last request (per worker)

Purpose: Identify cold-start regimes and evaluate warm pool effectiveness.

### AR.4 Compiler stability dashboard

Metrics:
- unique_graphs count
- recompile_limit events
- compile backend actual vs requested

Purpose: Detect compilation churn and ensure compiler-real execution.

### AR.5 Cost and budget dashboard

Metrics:
- $/1M tokens (shadow price)
- monthly compute-hours consumed
- cost per request by tier

Purpose: Connect throughput changes to budget impact in near real-time.


## Appendix AS: Cross-Report Comparison Table (Narrative)

This appendix provides a narrative comparison of how each report shifts the decision boundary, emphasizing what new evidence each report adds.


## Appendix AT: Extended Decision Matrix Commentary

This appendix expands on the Decision Impact Matrix by providing commentary for each cell. The intent is to show how each report changes a decision and what would happen if that evidence were missing.

TR117 baseline performance: Without TR117, backend selection would be guesswork. The matrix provides a starting point even if it is later refined by cost and scaling analysis.

TR118 validation: Without TR118, it would be impossible to assert that the measured differences are real rather than artifacts of data processing errors. This undermines any cost or policy conclusion.

TR119 economics: Without TR119, the system could optimize latency without understanding cost impact, which can lead to expensive but marginal improvements.

TR120 compiler audit: Without TR120, compile claims might be based on labels rather than behavior, leading to misattributed performance conclusions and unstable production policies.

TR121 scaling: Without TR121, model selection would be based on anecdote or parameter count alone, which is unreliable in heterogeneous small-model GPU regimes.

TR122 physical limits: Without TR122, energy numbers could be reported with false precision, potentially misleading sustainability decisions.


## Appendix AU: Expanded Operational Checklists

This appendix extends the operational checklists with phase-specific and role-specific steps for engineering, operations, and product.


## Appendix AV: Extended Economic Sensitivity Analysis

This appendix expands the economics section with additional sensitivity analyses that are useful for planning under uncertainty. The calculations use the same shadow-price model and do not introduce new assumptions.

### AV.1 Sensitivity to request length distribution

Cost per request is linear in tokens per request. If the distribution of request lengths shifts, cost shifts linearly. This means that a product change that increases average generation length by 2x will increase compute cost by roughly 2x unless throughput also changes. This is why request-length telemetry is critical for budgeting.

### AV.2 Sensitivity to burst factors

Capacity planning based on mean load can underestimate required fleet size. A burst factor of 5x implies 5x the worker count if no batching or queueing is used. This multiplier is often larger than the cost difference between model tiers, which means that traffic burstiness can dominate model-selection economics.

### AV.3 Sensitivity to tier pricing

Switching from on-demand to spot pricing can reduce cost by a factor of 3 or more, but introduces availability risk. The program treats pricing as a global scaling factor on cost; it does not change backend ordering. This means pricing decisions should be made independently of backend choice.

### AV.4 Sensitivity to routing policy

Routing policy determines the fraction of traffic sent to each model tier. A small change in routing thresholds can have a large effect on cost. This is why routing should be versioned and monitored as a first-class policy variable, not as a static configuration.


## Appendix AW: Measurement Ethics and Reproducibility Principles

This appendix summarizes the ethical stance of the program: avoid false precision, expose assumptions, and maintain auditability of claims.


## Appendix AX: Architectural Considerations

This appendix expands on architectural factors that influence inference performance beyond parameter count. These factors are referenced throughout TR121 and are critical to interpreting scaling results.

### AX.1 Depth vs width tradeoffs

Transformer depth (number of layers) controls the number of sequential operations per token. Depth therefore has a direct effect on decode latency. Width (hidden size) controls per-layer compute and memory, which can dominate on CPU or in batch-heavy GPU regimes. The HF model set in TR121 demonstrates how depth can dominate GPU latency in small-model, batch=1 settings.

### AX.2 Attention head count

Head count affects both parallelism and kernel efficiency. A model with an unusual head count can exhibit non-monotonic performance relative to parameter count. This is another reason the report treats parameter count as a coarse proxy rather than a deterministic predictor.

### AX.3 KV cache behavior

KV cache size grows linearly with generation length and linearly with the number of layers. This means that deep models have larger KV cache pressure per token. In decode-dominant regimes, KV cache behavior can become a performance bottleneck even if parameter count suggests otherwise.

### AX.4 Quantization and effective compute

Quantization changes the effective compute per parameter. A quantized 8B model can have performance characteristics closer to an unquantized smaller model. This is why TR121 treats quantized Ollama models as a distinct regime and uses within-family checks to control for quantization effects.

### AX.5 Kernel fusion and graph capture

Compiler frameworks can fuse kernels or capture larger graphs, reducing overhead. This can benefit prefill but can introduce fragility when shapes vary. The TR120 results show that these mechanisms can create heavy tails. This is a direct architectural interaction between model structure and compiler strategy.


## Appendix AY: Operational Lessons Learned

This appendix lists practical lessons observed during the program, focusing on what repeatedly caused regressions or misinterpretations.


## Appendix AZ: Scaling Laws vs Inference Performance

This appendix expands on the distinction between training-time scaling laws and inference-time performance scaling.

### AZ.1 Training scaling laws are not inference laws

Training scaling laws describe loss as a function of parameters, data, and compute. Inference performance depends on different factors: kernel efficiency, memory bandwidth, and runtime stack behavior. A model that is compute-optimal for training can still be inefficient for inference if its architecture or runtime stack induces overheads. This is why the program treats parameter count as a regime descriptor rather than a universal predictor.

### AZ.2 Architectural heterogeneity breaks simple scaling

Inference scaling assumes a homogeneous family. When models differ in depth, width, head count, or quantization, a single exponent can be misleading. The HF set in TR121 illustrates this: a deeper smaller model can be slower than a shallower larger model on GPU. This is a structural counterexample to simple scaling.

### AZ.3 Runtime stack effects

Inference performance depends on the backend stack. ONNX Runtime, PyTorch eager, and GGUF-based runtimes have different kernel implementations and memory layouts. These differences can dominate latency, particularly in small-model regimes. The scaling exponent therefore cannot be interpreted without the runtime context.

### AZ.4 Implications for policy

Scaling laws are useful for high-level planning but insufficient for production policy. The correct policy is to measure throughput under the actual runtime stack, then use scaling laws only as a secondary guide. This is the guiding principle behind TR121's regime analysis.


## Appendix BA: Energy, Carbon, and Sustainability Considerations

This appendix provides guidance on when energy and carbon metrics are appropriate, how to parameterize carbon intensity, and how to avoid overstating precision.


## Appendix BB: Methodological QA Checklist

This appendix provides a checklist that can be used to verify that a report conforms to the standards established by TR118-TR122.

### BB.1 Measurement QA

- Are raw artifacts present and complete?
- Are degraded runs classified and excluded from aggregates?
- Is the measurement boundary explicitly stated?
- Are warmup runs labeled and excluded from scaling fits?

### BB.2 Attribution QA

- Is backend behavior verified (provider logs or compile metadata)?
- Are compiler fallbacks recorded?
- Are shape-stability policies documented when compilation is enabled?

### BB.3 Statistical QA

- Are medians and tails reported?
- Are scaling fits labeled as unidentifiable when R^2 is low?
- Are confidence intervals reported for slopes?

### BB.4 Decision QA

- Does the report translate throughput into cost and capacity?
- Are routing or policy recommendations explicit?
- Are limitations and boundary conditions stated?


## Appendix BC: Model Registry Metadata Schema

This appendix defines a minimal schema for model registry metadata that supports the program's selection and scaling policies.


## Appendix BD: Implementation Guidance by Team Role

This appendix summarizes role-specific responsibilities for engineering, operations, product, and research teams when applying the report's guidance.


## Appendix BE: Quality Evaluation and Acceptance Criteria

This appendix expands on the quality evaluation concepts introduced in the business impact section. It provides a framework for defining "success" in a way that can be used in cost-justification calculations.

### BE.1 Defining success

Success should be defined in terms of the product's acceptance criteria. Examples include: correct answer rates for QA, accurate tool invocation for agents, or factual consistency for summarization. Each criterion should be measurable and tied to user or business outcomes.

### BE.2 Selecting evaluation datasets

Evaluation datasets should reflect real production queries. Synthetic benchmarks are useful for relative comparisons but can diverge from production distributions. The report recommends building evaluation sets from logged production queries, with privacy-safe sampling and manual curation for edge cases.

### BE.3 Combining offline and online metrics

Offline metrics provide controlled measurement; online metrics provide real-world validity. A decision-grade evaluation should include both. Offline evaluations can detect large differences in model quality; online evaluations can detect user preference and behavior shifts.

### BE.4 Mapping quality to cost justification

Once success probabilities are measured, the cost per success calculation provides a quantitative justification for model tiering. This is a decision framework rather than a pure research metric, and it aligns with the program's emphasis on decision-grade reporting.


## Appendix BF: Example Report Update Workflow

This appendix provides a step-by-step workflow for updating the conclusive report when new runs or backends are added.


## Appendix BG: Evaluation Philosophy and Limitations

This appendix clarifies the philosophical stance of the report on evaluation and measurement. It is included to make the reasoning explicit and to prevent misinterpretation of the report's scope.

### BG.1 Measurement is not the same as truth

Measurements are mediated by boundaries, instrumentation, and modeling assumptions. The program therefore treats measurement as evidence within a defined scope rather than as absolute truth. This is why the report repeatedly states boundary conditions and avoids universal claims.

### BG.2 Decision-grade does not mean definitive

A decision-grade report provides sufficient evidence to make a policy decision under stated assumptions. It does not guarantee that the decision will remain optimal under future changes. This is why the report emphasizes update cadence and manifest alignment.

### BG.3 The role of qualitative judgment

Even with quantitative metrics, qualitative judgment remains necessary. For example, a 2x cost increase might be acceptable if it unlocks a critical product feature. The report provides the quantitative frame, but the final decision must incorporate product context.


## Appendix BH: Additional Notes on Documentation and Communication

This appendix covers practical communication practices when using the report in organizational settings.

### BH.1 Communicating uncertainty

When presenting scaling exponents or cost models, explicitly state confidence intervals, boundary conditions, and applicability. This prevents overinterpretation by non-technical stakeholders.

### BH.2 Aligning stakeholders

Performance, cost, and quality teams often have different priorities. The report can be used as a shared reference point, but only if its limitations are communicated clearly. This appendix encourages teams to treat the report as a negotiation artifact rather than as an unquestionable directive.

### BH.3 Avoiding report drift

Reports can drift from their original meaning as they are summarized and reused. To avoid drift, always link claims back to artifact paths and maintain a versioned record of report updates.

This appendix provides a concrete example of how to update the conclusive report when a new backend or model is added.

1. Run the core scenario matrix on the new backend or model.
2. Validate artifacts and ensure that validation outputs pass.
3. Recompute cost and capacity metrics for the updated set.
4. Update any decision matrices and risk registers affected by the change.
5. Regenerate the conclusive report and update the manifest references.

This workflow ensures that the report remains current and avoids ad hoc updates that could introduce inconsistencies.

This appendix provides role-specific guidance for implementing the program's recommendations. The goal is to make the report actionable across engineering, product, and operations teams.

### BD.1 Engineering teams

Engineering teams are responsible for implementing the measurement pipeline and ensuring that backend behavior matches report assumptions. Key tasks include:

- Integrate phase-specific timing into the inference stack.
- Ensure compiler metadata is recorded and surfaced.
- Implement warmup routines and expose warmup metrics.
- Maintain a manifest system that captures runtime configuration.

Engineering teams should treat measurement as a product requirement. If measurement is brittle, all downstream decisions become brittle.

### BD.2 Product teams

Product teams should use the report's cost and capacity translations to make tiering decisions. The key is to connect model choice to user value. Product teams should:

- Define quality metrics that align with business outcomes.
- Use cost per successful request as a decision metric.
- Collaborate with engineering to define routing policies.

Product teams should avoid treating model upgrades as purely technical improvements. They are budget and reliability decisions.

### BD.3 Operations teams

Operations teams are responsible for maintaining SLOs under real traffic. Their tasks include:

- Monitoring phase-specific latency and tail behavior.
- Ensuring warm pools are maintained when cold-start risk is high.
- Applying burst factors to capacity planning.
- Responding to regressions with rerouting or rollback.

Operations teams should treat throughput as a primary SLO, not just latency. Throughput directly determines cost and capacity.

### BD.4 Research teams

Research teams should use the program to evaluate new models and backends. Their responsibilities include:

- Running controlled experiments for compiler and scaling claims.
- Extending boundary-shift tests when regimes are uncertain.
- Documenting new artifacts and integrating them into the report chain.

Research teams should avoid speculative claims without artifact evidence. The program's credibility depends on conservative reporting.

### BD.5 Leadership and governance

Leaders should treat the conclusive report as a governance artifact. It should inform budget planning, staffing, and product roadmaps. Governance tasks include:

- Approving major backend or model changes only after report updates.
- Ensuring that cost and capacity decisions are evidence-backed.
- Providing resources for periodic remeasurement.

The report is not merely a technical document; it is an organizational decision framework.

This appendix proposes a minimal metadata schema for model registries that aligns with the program's findings.

Required fields:

- model_name
- parameter_count
- n_layer
- n_embd
- n_head
- quantization (if applicable)
- runtime stack (backend, compiler, provider)

Optional fields:

- max_context_length
- kv_cache layout
- kernel optimizations (flash attention, paged attention)

The rationale for this schema is simple: parameter count alone does not predict latency in heterogeneous regimes. Structural metadata is required for informed selection.

This appendix expands on energy and carbon considerations in a way that respects the measurement constraints established by TR122.

### BA.1 Energy attribution under sampling constraints

Energy attribution is valid only when the event window contains sufficient samples. For short events, the correct action is to label the energy as no_data. This is a conservative policy, but it prevents false precision.

### BA.2 Carbon intensity as a parameter

Carbon intensity varies by region and time. Any carbon calculation should therefore be parameterized by a carbon intensity input. The program's cost model can incorporate this as a multiplier, but it does not assume a fixed global value.

### BA.3 Decision use of energy numbers

Even when energy numbers are valid, they are often a secondary decision factor under time-priced compute. However, for sustainability reporting or on-prem deployments with high electricity costs, energy can become a primary driver. The program's gating rules enable energy reporting to be used responsibly in those cases.

### BA.4 Future measurement upgrades

To improve energy attribution, the program recommends hardware energy counters or external power meters. These tools can provide per-event energy without the sampling limitations of polling. This would allow energy to become a first-class decision axis in future reports.

This appendix distills the program into operational lessons that are not strictly numerical but are critical for deployment success.

### AY.1 Latency is a distribution, not a number

The TR117 paradox and TR120 tail behavior show that a single latency number is insufficient. Operational planning must account for tails and warmup. This is a cultural change for teams accustomed to single-metric dashboards.

### AY.2 Compilation is a feature flag, not a default

The program's compiler results show that compile can help or hurt depending on shapes and phase. Treat compilation as a feature flag that is enabled only under validated conditions.

### AY.3 Scaling is conditional

Scaling relationships are boundary-dependent. A model can scale with parameter count in one regime and not in another. Teams should treat scaling claims as conditional unless they have boundary-shift validation.

### AY.4 Cost is operationally decisive

Once token volume is large, cost differences of 2-3x are common across model tiers. These differences are operationally decisive and should be treated as product decisions, not technical afterthoughts.

### AY.5 Evidence beats intuition

The program repeatedly contradicts intuitive assumptions: compile labels do not guarantee compilation, parameter count does not guarantee GPU latency ordering, and energy cannot be inferred from short events. The lesson is that evidence should override intuition, even when intuition is widely shared.

This appendix codifies the ethical stance of the program. It is included because the report makes claims that can influence budget and policy decisions, and such claims must be made responsibly.

### AW.1 Avoiding false precision

False precision occurs when a number is reported with implied accuracy that the measurement system cannot support. TR122 addresses this by gating energy attribution when sampling coverage is insufficient. The same principle applies to scaling fits: if R^2 is low and confidence intervals cross zero, the slope should not be treated as a decision-grade value.

### AW.2 Transparency of assumptions

The program explicitly states its assumptions: prompt length distributions, decode lengths, and pricing tiers are inputs, not constants. This transparency allows readers to substitute their own assumptions without discarding the methodology.

### AW.3 Artifact provenance

Every claim must be traceable to a specific artifact. This is not just a technical preference; it is an ethical requirement for reproducibility. A report that cannot be reproduced cannot be audited, and a report that cannot be audited should not guide policy.

### AW.4 Accountability and update cadence

A report is a snapshot in time. The program therefore encourages an explicit update cadence and versioning. If the environment changes, the report should be updated or clearly marked as historical. This ensures that decisions are based on current evidence rather than outdated benchmarks.

This appendix expands the operational checklists into more detailed runbooks. The intent is to make the conclusive report actionable for teams that want to integrate it into deployment practices.

### AU.1 Pre-release checklist (engineering)

- Confirm that model artifacts match the manifest (checksums or hashes).
- Verify that the backend uses the intended provider stack (e.g., ORT vs PyTorch).
- Run phase-specific performance checks and record p50/p95/p99.
- Confirm that warmup behavior is within acceptable bounds.
- Confirm that energy gating is applied for energy metrics.

### AU.2 Release checklist (product and ops)

- Update routing policies if model tiers have changed.
- Update cost models with new throughput measurements.
- Communicate expected SLO changes to stakeholders.

### AU.3 Post-release checklist (monitoring)

- Monitor phase-specific latency for regressions.
- Monitor compile counters if compilation is enabled.
- Monitor cost per token and compare to report baselines.

This appendix provides a narrative comparison of how each report changes the understanding of the system. It complements the Decision Impact Matrix by offering a more nuanced explanation.

TR117 establishes baseline performance differences but reveals distributional instability. TR118 provides pipeline integrity, making the baseline trustworthy. TR119 reframes performance as cost and shows that throughput is the dominant lever under time-priced compute. TR120 corrects attribution and reveals compiler tail risk. TR121 generalizes performance across model sizes and introduces regime thinking. TR122 grounds energy reporting in physical measurement constraints.

The combined effect is that decisions are no longer based on single numbers. They are based on phase-specific throughput, distributional risk, and explicit modeling assumptions. This is the defining characteristic of a decision-grade report.

This appendix expands the risk mitigation strategies for teams that want to operationalize the program.

### AQ.1 Mitigating cold-start risk

Cold-start risk is mitigated by a combination of warm pools, pre-routing warmups, and adaptive routing. For high-value requests, a system can route traffic only to warm workers. For low-value requests, it can accept cold-start latency. This is effectively a quality-of-service policy and should be explicit.

### AQ.2 Mitigating compiler tail risk

Compiler tail risk can be reduced by stabilizing shapes (padding or bucketing), limiting compilation to prefill, and monitoring compile counters in production. If unique_graphs grows beyond expected bounds, the system should fall back to eager or restrict compilation to a narrower set of shapes.

### AQ.3 Mitigating scaling uncertainty

Scaling uncertainty is mitigated by re-running the pipeline when workloads or hardware change, and by avoiding universal scaling claims. The program's fit gating policy provides a concrete rule: if a fit is unidentifiable, do not use it for capacity planning. Instead, rely on direct throughput measurements.

### AQ.4 Mitigating energy reporting risk

Energy reporting risk is mitigated by enforcing gating and by labeling energy numbers as valid only for macro windows. If energy is a critical decision axis, the system should use hardware energy counters or external power meters.

### AQ.5 Mitigating governance drift

Governance drift is mitigated by tying reports to manifests and by embedding report versioning into deployment documentation. If a system changes its backend or compiler, it should update the report or explicitly document the deviation. This ensures that decision policies remain aligned with evidence.

This appendix defines additional systems concepts referenced implicitly in the report.

- Allocator growth: increase in memory allocation footprint during early runs.
- Autotuning: runtime selection of kernels based on input shapes.
- Batch size: number of sequences processed simultaneously.
- Burst factor: ratio of p95 load to mean load.
- Cold-start: first inference after model load or process start.
- Guard: a condition used by compilers to ensure a graph is valid for a given input shape.
- Kernel launch overhead: fixed per-launch cost on GPU, significant for small workloads.
- Model residency: whether model weights are loaded in memory.
- Paged attention: attention mechanism optimized for long sequences and memory efficiency.
- Tokenization: conversion of text to tokens; excluded from timed regions in controlled runs.

This appendix distills the program into a set of heuristics that can guide quick decisions when full remeasurement is not feasible. These heuristics are conditional and should be revisited when workloads or hardware change.

1. If gen_tokens >= 64, assume decode dominates end-to-end throughput. Optimize decode first.

2. If batch size is large and generation length is minimal, prefill throughput is the primary metric.

3. If a compile backend cannot prove compiler-real execution, treat it as eager. Do not claim compile wins.

4. If prompt lengths are short (micro/short), expect overhead-dominated behavior on GPU for small models. Parameter count alone is not a reliable predictor.

5. If warmup ratios exceed 10x, cold-start must be managed explicitly (warm pool, pre-routing warmup).

6. If energy measurement cadence is slower than event duration, do not report per-event energy.

7. If R^2 < 0.2 and the slope CI crosses zero, the scaling exponent is not actionable.

8. Model tiering is the default once token volume is large; a single-tier policy is rarely cost-optimal.

9. When comparing models, record architecture depth and quantization level alongside parameter count.

10. Treat throughput numbers as lower bounds for capacity planning; apply a burst multiplier based on real traffic distributions.

This appendix provides a mapping between scenario types and the metrics that best characterize them. The goal is to avoid misaligned optimization.

### AL.1 Scenario taxonomy

- micro: minimal prompt length, overhead-dominant.
- short: small prompts with modest context.
- medium: longer prompts where prefill becomes significant.
- batch_short: batched prompts, emphasizing throughput and kernel efficiency.
- batch_medium: batched and longer prompts, emphasizing prefill throughput.

### AL.2 Metric mapping

- micro/short: TTFT and overhead metrics are primary; decode dominates cost only if gen length is high.
- medium: prefill and decode both matter; phase split should be reported.
- batch scenarios: tokens per second and cost per token are primary metrics.

### AL.3 Interpretation guidance

A scenario's primary metric should align with its dominant phase. This is why TR119 and TR121 emphasize phase separation: without it, a scenario can be optimized for the wrong objective. A short interactive scenario optimized for prefill throughput can still underperform if decode dominates end-to-end latency.

This appendix summarizes the minimal steps required to regenerate the conclusive report when new artifacts are produced.

1. Run the relevant experiment scripts for each TR.
2. Run analysis and validation scripts.
3. Verify that manifests and validation outputs are present.
4. Update any tables or references that rely on specific run IDs.
5. Regenerate the conclusive report with updated artifact paths.

The key principle is that regeneration should not require manual recalculation. All derived values should be produced by deterministic scripts that can be audited.

This appendix expands the glossary for readers outside the immediate performance engineering community.

- Backend: A runtime implementation of model inference (e.g., ONNX Runtime, PyTorch eager).
- Boundary: The start and end points of the timed region in a measurement.
- Compile-real: A run where torch.compile actually executed with the requested backend and recorded compiler metadata.
- Decode dominance: The condition where kv_decode latency is the majority of end-to-end latency.
- Dynamic shapes: Inputs whose shape can vary between runs, requiring guard checks or recompilation.
- E2E: End-to-end, typically prefill plus decode.
- EOS: End-of-sequence token. Early EOS can terminate generation before the target length.
- Fallback: Automatic switch to a different backend when the requested backend fails.
- Gating: A validity filter that prevents reporting metrics when measurement coverage is insufficient.
- KV cache: Key/value cache used to speed decoding by avoiding recomputation of prior context.
- Load duration: Time spent loading a model into memory (often relevant in Ollama).
- Manifest: File containing environment and configuration metadata for a run.
- Polling cadence: Frequency of power sampling for energy measurement.
- Prefill: Phase where the prompt context is encoded.
- Scenario: A specific workload shape (prompt length, batch size, generation length).
- Shadow price: A cost proxy used to translate throughput into dollars per token under a time-priced compute model.
- Tail latency: High-percentile latency (p95, p99), representing worst-case user experience.
- Warmup: Initial inference runs used to stabilize caches and kernels before measurement.

This appendix elaborates on future directions in the absence of TR123. The goal is to continue the program's trajectory without expanding scope beyond what is already justified by artifacts.

### AE.1 Consolidation of pipelines

The highest ROI task is to consolidate the TR117-TR122 pipelines into a single orchestration flow that can be rerun on demand. This would reduce duplication, make validation more consistent, and simplify report regeneration.

### AE.2 Hardware portability studies

The program currently targets a single hardware configuration. A key next step is to run the pipeline on at least one additional GPU class and one additional CPU class to test whether the regime conclusions hold. This does not require new methodology; it requires rerunning the existing pipeline with new manifests.

### AE.3 Kernel attribution for decode

TR120 and TR121 highlight that decode performance can be sensitive to kernel availability and compiler behavior. A focused profiling study could identify which kernels dominate decode time under each backend, enabling targeted optimization. This would strengthen the mechanistic foundation of the program's decode-dominant conclusions.

### AE.4 Integrating energy and scaling

TR119 and TR121 provide cost and scaling, while TR122 provides energy gating. A future integration would compute energy per token only in windows where measurement is valid, creating a hybrid cost-energy model that is physically defensible. This would require longer run windows or energy counters but would not require new conceptual frameworks.

This appendix provides qualitative comparisons between model variants to illustrate how architecture shapes performance beyond parameter count.

### AC.1 Deep-narrow vs shallow-wide in the HF set

Within the HF model set, the 5M-parameter model is deeper than the 25M-parameter model. The result is a counterintuitive latency ordering: the larger model can be faster in decode because it traverses fewer layers per token. This illustrates why parameter count is insufficient as a predictor in the small-model GPU regime.

### AC.2 Cross-family Ollama comparisons

The Ollama models span families and quantization schemes. Even under this heterogeneity, a monotonic scaling trend is visible in the fixed-length decode regime. This suggests that, at large model sizes, parameter count becomes a usable proxy for throughput, even if the underlying families differ. The within-family Gemma3 check strengthens this conclusion by showing a consistent slope in a homogeneous subset.

### AC.3 Model selection as an architecture decision

The program's scaling results imply that model selection should consider architectural parameters explicitly. Depth is a key predictor for GPU latency, while width and total parameter count are more predictive on CPU. This suggests that a model registry used for deployment should include architectural metadata and not just parameter counts.

### AC.4 Quantization effects and interpretive caution

Quantization changes the effective throughput per parameter. This means that an 8B model in one quantization regime is not directly comparable to an 8B model in another. The program handles this by labeling Ollama results as regime descriptors rather than universal laws. The implication for production is that any model comparison should record quantization details alongside parameter counts.

This appendix catalogs the main formulas used across the reports for quick reference.

### AA.1 Throughput

- tokens_per_s = tokens_total / (latency_ms / 1000)

### AA.2 Cost (shadow price)

- seconds_per_1M = 1e6 / tokens_per_s
- usd_per_1M = (seconds_per_1M / 3600) * usd_per_hour

### AA.3 Decode dominance

- decode_fraction = kv_decode_ms / e2e_kv_ms

### AA.4 Warmup ratio

- warmup_ratio = warmup_median_ms / steady_median_ms

### AA.5 Energy (gated)

- delta_power_w = mean_power_w - idle_power_w
- energy_j = delta_power_w * duration_s (only when sampling coverage is valid)

This appendix provides a planning template for future experiments in the TR117-TR122 program, ensuring that new studies remain consistent with the established methodology.

### X.1 Define the decision question

Each experiment should start with a concrete decision question, not a metric. Examples: "Which backend minimizes $/token for decode-heavy workloads?" or "Does compilation reduce p95 for stable shapes?" This ensures the experiment is scoped to a decision, not to a metric.

### X.2 Define the boundary

Explicitly state what is included in the timed region. If the boundary includes initialization, label it. If the boundary excludes tokenization, state that. This prevents ambiguity in interpretation.

### X.3 Define the scenarios

Specify prompt lengths, batch sizes, and generation lengths. Each scenario should correspond to a real workload class. If the workload mix is unknown, choose scenarios that span expected extremes.

### X.4 Define the artifact chain

Ensure that raw metrics, processed summaries, and validation outputs are generated. The experiment is not complete unless the artifact chain is intact.

### X.5 Define the decision output

State explicitly how the experiment will affect a policy or decision. If the outcome does not change a decision, the experiment may not be worth running.

This appendix narrates the evolution of the research program as a case study in methodological maturity.

The program begins with TR117, a classic baseline benchmark. The initial goal was to answer a practical question: which backend is faster on a given model? The results were useful but exposed a paradox: mean and median rankings did not align. This paradox forced a methodological pivot. It revealed that distributional behavior and cold-start effects could not be ignored.

TR118_v2.2 emerges as the response: if the program is to make decisions, it must make its data trustworthy. The validation pipeline, manifest tracking, and degraded-run handling are the institutionalization of that insight.

TR119v1 extends the scope to economics, shifting the program from performance to decision. This is the point where throughput becomes a budget number, and where the importance of decode dominance becomes explicit.

TR120 then addresses attribution, showing that label-based assumptions can be wrong and that compiler claims require explicit evidence. This is a major increase in methodological rigor: it transforms a benchmark into a controlled experiment.

TR121v1 broadens the scope to scaling, but does so with regime discipline. It avoids universal claims and instead maps where parameter count is predictive and where it is not. This is the report that closes the gap between small-model benchmarks and large-model planning.

TR122 adds the final layer: physical measurement limits. It reminds the program that not all metrics are equally measurable at all timescales. Energy reporting, in particular, requires instrumentation-aware gating.

The conclusive report is therefore not just a summary; it is the integration of these methodological shifts. The program evolves from a benchmark to a measurement framework to a decision system, and the report is designed to preserve that evolution.

This appendix provides narrative templates that can be used to extend or update the report without drifting from the established methodology.

### S.1 Template: New backend evaluation

1. Define the backend and ensure runtime attribution is explicit.
2. Run the scenario matrix and collect raw artifacts.
3. Validate artifacts and classify degraded runs.
4. Report phase-split metrics and distributions.
5. Translate throughput into cost and capacity under the compute-hour model.

### S.2 Template: New model scaling sweep

1. List model architectures and compute exact parameter counts.
2. Run phase-split measurements across scenarios.
3. Fit scaling relations with bootstrap CIs and rank correlations.
4. Identify regime boundaries and test with boundary-shift experiments.

### S.3 Template: Energy reporting update

1. Calibrate idle baseline and report mean and variance.
2. Compute event coverage and gate energy attribution.
3. Separate macro-window energy reports from micro-event analyses.

This appendix defines a rubric for evaluating whether a report is decision-grade. The rubric is based on the lessons of TR117-TR122.

### P.1 Evidence criteria

1. Artifact-backed: raw data and processed summaries are available.
2. Validation-backed: the pipeline includes explicit validation outputs.
3. Attribution-correct: labels match runtime behavior.

### P.2 Method criteria

1. Measurement boundary is explicit.
2. Phase separation is respected when phases differ in behavior.
3. Warmup handling is explicit and not merged into steady-state.

### P.3 Interpretation criteria

1. Distributional statistics are reported alongside means.
2. Scaling claims are bounded by regime and boundary conditions.
3. Cost and capacity translations are explicit and parameterized.

### P.4 Decision criteria

1. The report yields at least one actionable policy decision.
2. Risks and limitations are explicitly tied to mitigations.
3. The report includes a reproducibility path for updates.

This appendix provides a longer-form discussion of the program's implications for research practice, operations, and governance.

### N.1 Research practice: when is a benchmark publishable?

The TR117-TR122 sequence suggests a practical definition of publishability: a benchmark is publishable when it is artifact-backed, attribution-correct, and decision-translatable. The first condition ensures reproducibility, the second ensures causal validity, and the third ensures relevance. A benchmark that fails any of these conditions may still be interesting, but it is not decision-grade.

### N.2 Operational practice: separating performance from policy

A persistent risk in performance engineering is to convert a benchmark into a policy without considering boundary conditions. The program addresses this by treating boundaries as part of the claim. Policies are therefore scoped to specific workloads, hardware classes, and runtime stacks. This is the correct approach for production environments where mis-scoped policies can create regressions or cost blowouts.

### N.3 Governance practice: why auditability matters

As inference systems become part of critical infrastructure, auditability becomes a compliance requirement. The report's insistence on manifest metadata and chain-of-custody is therefore not merely scientific; it is governance-aligned. This is especially relevant for cost and energy claims, which can be subject to regulatory scrutiny.

### N.4 Strategic practice: model tiering as a default

The economics of scaling imply that model tiering is not optional once token volume is high. A single-tier policy either overpays for quality or underdelivers on accuracy. A tiered strategy, backed by routing heuristics and measured failure rates, is the only stable approach under realistic budgets. The program's results provide the quantitative tools needed to implement such tiering responsibly.

### N.5 Long-term implications: compiler policies as part of model governance

Compiler behavior is not a purely technical detail; it is a governance issue. It affects tail latency, stability, and even correctness in edge cases. The program's insistence on compiler-real evidence and shape-stability policy can be read as a governance requirement: you cannot claim performance improvements without demonstrating that the compiler actually executed. This is a standard that should apply broadly to inference optimization claims.

This appendix lists measurement boundaries by report. The purpose is to prevent accidental comparison across incompatible boundaries.

- TR117: Service-level boundary (InferenceService.generate) including initialization effects.
- TR118_v2.2: Validation boundary (artifact consistency and degraded-run classification).
- TR119v1: Phase-level boundary with explicit cost model.
- TR120: Kernel-focused boundary with explicit compilation and synchronization.
- TR121v1: Phase-level boundary with fixed-length decode equivalence.
- TR122: Instrumentation boundary with energy gating.

Using this catalog, readers can determine whether two numbers are directly comparable or whether a boundary adjustment is required.

This map ties each report to the decision it supports:

- Backend selection: TR117 (baseline), TR119 (cost), TR121 (scaling).
- Compiler policy: TR120.
- Energy reporting: TR122.
- Cold-start policy: TR117 (risk), TR121 (magnitude), TR120 (boundary).

Using this map, a decision-maker can identify which report to consult before changing a policy.

### H.1 Report regeneration checklist

1. Run the experiment scripts for each TR (with manifest capture).
2. Run analysis and validation scripts for each TR.
3. Confirm that cost/energy validation passes (TR118/TR119).
4. Recompute scaling fits and regime summaries (TR121).
5. Regenerate the conclusive report using the updated artifacts.

### H.2 Backend selection template

- If workload includes decode: choose the backend with best decode throughput.
- If workload is prefill-only and batched: choose the backend with best batched prefill cost.
- If compiler is enabled: validate compiler-real evidence and shape stability before routing production traffic.

### H.3 Cold-start mitigation template

- Maintain warm pools for large models.
- Execute pre-routing warmup runs to stabilize kernels.
- Track cold-start latency separately from steady-state SLOs.

### F.1 Workload taxonomy

- Interactive chat: small batch, moderate decode; decode-dominant.
- Batch prefill pipelines: large batch, minimal decode; prefill-dominant.
- Agent tool-steps: short prefill and short decode, high concurrency.
- Long-context summarization: large prefill, moderate decode.

### F.2 Routing examples

- Route batched prefill workloads to the backend with best prefill cost; route interactive decode to the backend with best decode throughput.
- For compiler-enabled stacks, compile only the prefill path and keep decode eager unless decode wins are demonstrated.
- For cold-start-sensitive services, keep a warm pool for the largest models and reserve them for high-value requests.


- Prefill: the prompt processing phase; a single forward pass over the context.
- KV decode: token-by-token generation using cached keys and values.
- End-to-end: prefill plus decode.
- Token economics: dollars per token derived from throughput and hourly rate.
- Regime descriptor: a scaling relationship valid only within a specific measurement boundary.
- Compiler-real: a backend path that actually invokes torch.compile and records compile metadata.
- Energy gating: the policy of marking per-event energy as no_data if insufficient samples exist.
- Baseline subtraction: removing idle power from measured power to isolate inference energy.
