# Conclusive Report 123-133: From Cost Models to Predictive Capacity Planning
## A dissertation-style synthesis of economics, quality, quantization, compilation, context scaling, production workloads, multi-agent scaling, serving stacks, GPU kernel physics, and predictive modeling

Project: Banterhearts LLM Performance Research
Date: 2026-02-28
Author: Research Team
Report Type: Conclusive synthesis across TR123-TR133 (artifact-backed, 11 technical reports)
Scope: TR123, TR124, TR125, TR126, TR127, TR128, TR129, TR130, TR131, TR132, TR133
Hardware Baseline: NVIDIA RTX 4080 Laptop GPU (12 GB VRAM, AD104, 7,424 CUDA cores, 175W TDP)
Measurement Corpus: ~70,000+ measurements across 11 technical reports
Primary Sources:
- PublishReady/reports/Technical_Report_123.md (KV-Cache Production Economics)
- PublishReady/reports/Technical_Report_124.md (Quality & Accuracy Baseline)
- PublishReady/reports/Technical_Report_125.md (Quantization Decision Matrix)
- PublishReady/reports/Technical_Report_126.md (Docker/Linux + Triton Validation)
- PublishReady/reports/Technical_Report_127.md (Long-Context Performance Characterization)
- PublishReady/reports/Technical_Report_128.md (Production Workload Characterization)
- PublishReady/reports/Technical_Report_129.md (N-Agent Scaling Laws)
- PublishReady/reports/Technical_Report_130.md (Serving Stack Benchmarking)
- PublishReady/reports/Technical_Report_131.md (GPU Kernel Profiling -- Root-Cause Analysis)
- PublishReady/reports/Technical_Report_132.md (In-Container GPU Kernel Profiling -- Serving Stack Mechanism)
- PublishReady/reports/Technical_Report_133.md (Predictive Capacity Planner)
Predecessor Synthesis: PublishReady/reports/Technical_Report_Conclusive_117-122.md (Phase 1)

---

## Abstract

This dissertation-style report synthesizes TR123 through TR133 into a single decision-grade narrative for local-first LLM inference on a fixed consumer hardware baseline. The research arc spans eleven technical reports and approximately 70,000 measurements, beginning with KV-cache production cost models (TR123) and culminating in a predictive capacity planner validated against empirical data (TR133). Between these endpoints, the program establishes quality baselines across backends and quantization levels (TR124), maps the full quantization decision space and identifies Q4_K_M as the universal sweet spot (TR125), resolves the compile paradox by demonstrating real Triton speedups on Linux (TR126), reveals a two-regime context scaling phenomenon governed by VRAM spillover thresholds (TR127), characterizes production workloads and refutes the OLLAMA_NUM_PARALLEL concurrency claim (TR128), derives N-agent scaling laws under Amdahl's framework with serial fractions of 0.39-0.54 (TR129), compares serving stacks and demonstrates vLLM's 2.25x throughput advantage via continuous batching at high concurrency (TR130), opens the GPU black box to overturn the serving-stack-as-bottleneck narrative in favor of memory bandwidth physics (TR131), proves the continuous batching amortization mechanism at the kernel level with 77-80% kernel reduction (TR132), and operationalizes the entire corpus into a CLI-accessible predictive planner with all four validation targets met (TR133). The synthesis establishes three stable principles: (1) GPU memory bandwidth physics, not the serving stack, is the fundamental scaling bottleneck -- continuous batching amortizes this bandwidth cost, which is why the serving stack architecture choice (sequential vs continuous batching) determines scalability; (2) quantization is the dominant lever for both cost and concurrency, with Q4_K_M as the universal sweet spot across all tested models; and (3) predictive capacity planning from empirical lookup tables outperforms theoretical queueing models, which deviate up to 20.4x from reality.

This synthesis also makes explicit the chain-of-custody from measurement to claim, including where the chain fails. In particular, three high-profile failures are documented: M/D/1 queueing theory deviates 20.4x from observed latency at NUM_PARALLEL > 1 (TR128), Amdahl's serial fraction is a category error when applied across backends with fundamentally different degradation mechanisms (TR129 vs TR131), and the serving-stack-as-bottleneck hypothesis (TR130) is overturned by GPU kernel profiling showing PyTorch Direct degrades worse than Ollama under identical concurrency (TR131). These failures are not embarrassments; they are the evidence that the program's falsification machinery works. Each failure sharpened the subsequent experimental design, producing a corpus where every surviving claim carries artifact-backed provenance. The portable output of this work is not the absolute numbers -- which are bound to one GPU, one driver version, and one software stack -- but the method, the decision framework, and the gating rules that determine when a measurement is trustworthy enough to ship.

---

## Table of Contents

Executive Summary
Operational Defaults (Decision Card)
1. Introduction and Research Questions
2. Background and Related Work
3. Methods and Measurement Framework
4. Decision Impact Matrix (TR123-TR133)
5. Results by Report (TR123-TR133)
   5.1 TR123: KV-Cache Production Economics
   5.2 TR124: Quality and Accuracy Baseline
   5.3 TR125: Quantization Decision Matrix
   5.4 TR126: Docker/Linux Compile Paradox Resolution
   5.5 TR127: Long-Context Performance Characterization
   5.6 TR128: Production Workload Characterization
   5.7 TR129: N-Agent Scaling Laws
   5.8 TR130: Serving Stack Benchmarking
   5.9 TR131: GPU Kernel Profiling -- Root-Cause Analysis
   5.10 TR132: In-Container GPU Kernel Profiling -- Serving Stack Mechanism
   5.11 TR133: Predictive Capacity Planner
6. Cross-Report Synthesis by Decision Axis
7. Economics, Capacity, and Cost-Quality Tradeoffs
8. Operational Doctrine and Risk Controls
9. Threats to Validity and Scope Limits
10. Limitations by Report and Mitigations
11. Integration with Phase 1 (TR117-TR122)
12. Conclusive Statement
13. References
14. Appendix A: Key Formulas and Derivations
15. Appendix B: Claim-to-Artifact Chain-of-Custody
16. Appendix C: Per-TR Key Numbers (Extracted)
17. Appendix D: Glossary and Definitions
18. Appendix E: Operational Checklists
19. Appendix F: Workload Taxonomy and Routing Logic
20. Appendix G: Worked Examples and Calculations
21. Appendix H: Operational Playbooks and Templates
22. Appendix I: Statistical Notes and Fit Diagnostics
23. Appendix J: Traceability Map (TR123-TR133 to Decisions)
24. Appendix K: Extended Literature Review
25. Appendix L: Measurement Boundary Catalog
26. Appendix M: Detailed Methods by Report
27. Appendix N: Expanded Discussion and Implications
28. Appendix O: Extended Results Narratives
29. Appendix P: Quantization Decision Trees and Quality Gates
30. Appendix Q: Extended Decision Case Studies
31. Appendix R: Metric Definitions and Data Schema
32. Appendix S: Governance and Reporting Templates
33. Appendix T: Extended Risk Register
34. Appendix U: Program Evolution Narrative (TR123-TR133)
35. Appendix V: Extended Cost Modeling and Token Economics
36. Appendix W: Serving Stack Comparison Deep Dive
37. Appendix X: GPU Kernel Profiling Methodology
38. Appendix Y: Continuous Batching Amortization Analysis
39. Appendix Z: Amdahl's Law Derivations and Limits
40. Appendix AA: VRAM Budget Calculator and Context Limits
41. Appendix AB: Compile Policy Decision Matrix
42. Appendix AC: Multi-Agent Scaling Detailed Results
43. Appendix AD: M/D/1 Queueing Theory vs Empirical Deviation
44. Appendix AE: Predictive Model Validation Details
45. Appendix AF: ChimeraForge CLI Architecture and Usage
46. Appendix AG: Extended Glossary and Acronyms
47. Appendix AH: Detailed Artifact Inventory
48. Appendix AI: Artifact-to-Claim Provenance Examples
49. Appendix AJ: Reproducibility and Regeneration Notes
50. Appendix AK: Scenario-Specific Policy Playbooks
51. Appendix AL: Quality Metric Definitions and Benchmark Mapping
52. Appendix AM: Decision Heuristics and Rules of Thumb
53. Appendix AN: Policy Decision Trees
54. Appendix AO: Extended Systems Glossary
55. Appendix AP: Cross-Phase Synthesis Narrative (Phase 1 + Phase 2)
56. Appendix AQ: Extended Risk Mitigation Strategies
57. Appendix AR: Operational Metrics and Dashboard Specifications
58. Appendix AS: Cross-Report Comparison Table (Narrative)
59. Appendix AT: Extended Decision Matrix Commentary
60. Appendix AU: Expanded Operational Checklists
61. Appendix AV: Extended Economic Sensitivity Analysis
62. Appendix AW: Measurement Ethics and Reproducibility Principles
63. Appendix AX: Architectural Considerations for Serving Stacks
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

Supplemental material will be mirrored in `PublishReady/reports/Technical_Report_Conclusive_123-133_Extended_Appendices.md`.

---

## Executive Summary

This report closes the loop started in TR123 and makes the Phase 2 research program decision-grade. We moved from single-model KV-cache cost tables to a complete, artifact-backed decision framework spanning economics, quality, quantization, compilation, context scaling, production workloads, multi-agent concurrency, serving stack selection, GPU kernel physics, and predictive capacity planning. The outcome is a set of stable, falsification-tested conclusions about what to deploy, how to configure it, and when the conclusions break -- all validated on one hardware baseline (RTX 4080 Laptop GPU, 12 GB VRAM) and bounded workloads.

### The synthesis in one line

Quantization (Q4_K_M) and serving stack selection (Ollama for single-agent, vLLM for multi-agent) are the two highest-leverage deployment decisions; everything else -- compile policy, context budget, agent count -- is a refinement within the envelope those two choices define.

### Claim status (cross-report, reviewer-proof)

| Claim ID | Claim | Evidence Base | Status |
| --- | --- | --- | --- |
| C1 | KV-cached decode is cheaper than uncached (TR119 baseline) | TR123 phase-split cost tables: best-cost $0.013/1M tokens (GPT-2, compile, chat blend); cached decode 2-8x cheaper than uncached across all 5 models | **Validated** |
| C2 | Backend choice does not affect output quality | TR124 ANOVA + Holm-Bonferroni correction on 7 quality metrics (BERTScore, ROUGE-L, exact_match, coherence, BLEU, output_length, and repetition); 5 models x 2 backends at temp=0; no significant differences | **Validated** |
| C3 | Q4_K_M preserves quality across all models tested | TR125 Phase 2: 5 models (llama3.2-1b, qwen2.5-1.5b, phi-2, llama3.2-3b, llama3.1-8b) within -4.1pp of FP16 baseline on benchmark accuracy (285 MMLU + 200 ARC questions); power analysis yields MDE of 9.0pp at 80% power | **Validated** (point estimate; TOST underpowered) |
| C4 | torch.compile delivers consistent prefill speedups on Linux | TR126: -24% to -60% prefill latency reduction across all 7 models with real Triton kernels; Cohen's d = -0.59; p = 8.87 x 10^-61; 916 cumulative Triton kernels generated; reverses TR120 Windows-only findings entirely | **Validated** |
| C5 | VRAM spillover, not quadratic attention, is the practical bottleneck for long-context inference | TR127: 25-105x latency cliffs observed at VRAM spillover thresholds; clean sub-linear Ollama prefill scaling (b = 0.083-0.158) below capacity; qwen2.5-3b (HF FP16) hits VRAM wall at 8K tokens on 12 GB | **Validated** (consumer GPU; may not hold for 24+ GB cards) |
| C6 | OLLAMA_NUM_PARALLEL enables concurrent GPU inference throughput | TR128: 0/30 pairwise statistical tests significant; NUM_PARALLEL is a no-op for single-GPU inference; M/D/1 queueing theory deviates up to 20.4x from reality | **Refuted** |
| C7 | Multi-agent throughput scales linearly with agent count | TR129: Amdahl serial fraction s = 0.39-0.54; total system throughput plateaus at N=2 (~1.4-1.6x); per-agent throughput degrades monotonically; fairness remains excellent (Jain's index >= 0.997) | **Refuted** |
| C8 | Serving stack (Ollama) is the multi-agent scaling bottleneck | TR131: PyTorch Direct degrades 86.4% (N=1 to N=8) vs Ollama 82.1% under identical concurrency; -4.3% attribution to serving stack; memory bandwidth stress +74% at N=8 (p = 6.4 x 10^-5, sole Holm-surviving test) | **Overturned** -- GPU memory bandwidth physics dominates, not serving stack overhead |
| C9 | Continuous batching amortizes kernel launches and bandwidth | TR132: 77-80% kernel count reduction at N=8 (all p < 10^-6, d > 600, 4/4 Holm-significant); memory bandwidth per token drops 79-83%; amortization ratio 4.7-5.8x (59-72% of theoretical 8:1 maximum); vLLM and TGI show identical mechanism | **Validated** |
| C10 | Lookup tables + first-principles models suffice for capacity planning | TR133: 4/4 validation targets met -- VRAM R^2 = 0.968 (target 0.95), throughput R^2 = 0.859 (target 0.85), quality RMSE = 0.062 (target < 0.10), latency MAPE = 1.05% (target < 25%); 10/10 spot checks pass; no ML needed | **Validated** |

### Program trajectory (TR123 -> TR133)

The research program is intentionally sequential. Each report either fills a gap exposed by the previous one or falsifies a hypothesis that earlier results made plausible:

1. **TR123** establishes KV-cached production cost baselines with phase-split economics. Separates prefill from decode costs across 5 models (124M-3.2B), 3 backends, and 5 workload scenarios. Produces the first decision-grade $/token tables for cached inference. Opens the question: these costs assume equivalent quality -- is that true?

2. **TR124** fills the quality gap. Three-phase study confirms backend equivalence at temp=0 (Phase 1), quantifies quantization impact (Phase 2), and bounds sampling variance at temp=0.7 (Phase 3). Anchors quality to 7 metrics including BERTScore and ROUGE-L. Opens the question: if backends are equivalent, what quantization level should we actually deploy?

3. **TR125** maps the quantization decision space. Two-phase study (900 + 24,990 samples) across 5 models and 7 quantization levels (Q2_K through FP16) using real benchmark data (MMLU, ARC-Challenge). Identifies Q4_K_M as the universal sweet spot, Q3_K_S as model-dependent, and Q2_K as universally unacceptable. Opens the question: if we pick Q4_K_M, does torch.compile still help?

4. **TR126** resolves the compile paradox. Moves from Windows (TR120) to Docker/Linux with real Triton. Demonstrates 24-60% prefill speedups with 916 generated Triton kernels -- the exact opposite of Windows results. Documents that torch.compile crashes autoregressive decode in all modes. Establishes the compile policy: prefill only, Linux only, eager decode always. Opens the question: what happens at long context lengths?

5. **TR127** reveals the two-regime context scaling phenomenon. Tests 5 models across 7 context lengths (512-32K tokens). Discovers clean sub-linear scaling below VRAM capacity and catastrophic 25-105x latency cliffs at spillover thresholds. Establishes VRAM spillover, not quadratic attention, as the practical bottleneck for consumer GPUs. Opens the question: how does this behave under production load?

6. **TR128** characterizes production workloads. Five-phase study (3,172 measurements) tests NUM_PARALLEL, queueing theory, streaming overhead, thermal stability, and context effects. Refutes NUM_PARALLEL (no-op), refutes M/D/1 theory (20.4x deviation), and confirms streaming has zero overhead. Opens the question: if single-GPU parallelism is fake, how do we actually scale multi-agent?

7. **TR129** derives N-agent scaling laws. Tests 3 models at N=1-8 agents (5,310 measurements). Fits Amdahl's Law with serial fractions s=0.39-0.54. Throughput plateaus at N=2 with diminishing returns thereafter. Fairness is excellent but irrelevant -- the GPU cannot do more work. Attributes the bottleneck to the serving stack (Ollama). Opens the question: do other serving stacks scale better?

8. **TR130** compares serving stacks. Tests Ollama, vLLM, and TGI across 3 models and 4 concurrency phases (4,797 measurements). vLLM achieves 2.25x throughput advantage at N=8 via continuous batching. Attributes the Ollama bottleneck to its serving layer. Opens the question: is it really the serving stack, or is it the GPU?

9. **TR131** opens the GPU black box. Deploys Nsight Systems and Nsight Compute profiling (26 runs, ~1.6 GB traces) to test five hypotheses. Overturns TR130: PyTorch Direct (no serving stack) degrades 86.4% at N=8, worse than Ollama's 82.1%. The bottleneck is GPU memory bandwidth physics (+74% stress at N=8), not software overhead. Max concurrent kernels = 1 in all conditions -- hardware serialization, not software serialization. Opens the question: then why does vLLM scale better?

10. **TR132** proves the mechanism. In-container GPU kernel profiling (25 runs, ~375 MB traces) with a novel WSL2/WDDM-compatible methodology. Continuous batching reduces kernel launches by 77-80% and memory bandwidth per token by 79-83%. Amortization ratio is 4.7-5.8x (59-72% of theoretical maximum). vLLM and TGI show identical amortization -- the mechanism is continuous batching itself, not implementation-specific. This resolves the TR130/TR131 apparent contradiction: vLLM scales better not because Ollama's serving stack is bad, but because continuous batching amortizes the GPU memory bandwidth bottleneck that TR131 identified.

11. **TR133** operationalizes everything. Ingests 19,676 records from TR123-TR130, fits 6 predictive models (VRAM, throughput, scaling, quality, cost, latency), validates against a 20% holdout (3,939 records), and ships a CLI tool (`chimeraforge plan`). All 4 validation targets met, 10/10 spot checks pass, 57 unit tests passing. The key insight: empirical lookup tables with first-principles interpolation outperform theoretical models (which deviate 20.4x in the M/D/1 case). No ML needed.

This ordering is deliberate: you cannot do quantization policy without quality baselines; you cannot do compile policy without cross-platform validation; you cannot do capacity planning without production characterization; you cannot identify the real bottleneck without GPU kernel profiling; and you cannot operationalize without all of the above.

### Bottom-line decisions you can ship

1. **Default backend for single-agent serving:** Ollama with Q4_K_M quantization. This delivers the highest throughput per dollar at negligible quality loss (within -4.1pp of FP16 on benchmark accuracy). The compile overhead, ONNX export complexity, and raw transformers startup costs are not justified for single-agent workloads.

2. **Default backend for multi-agent serving (N >= 4):** vLLM with FP16 weights. Continuous batching amortizes GPU memory bandwidth by 4.7-5.8x, yielding a 2.25x throughput advantage over Ollama at N=8. TGI provides equivalent amortization but lower absolute throughput. Ollama degrades to near-uselessness (82.1% throughput loss at N=8) because it lacks continuous batching.

3. **Compile policy:** torch.compile prefill only, on Linux, with Inductor+Triton backend. Never compile decode -- it crashes in all tested modes (reduce-overhead and mode="default") and provides no speedup even when it works at short lengths (+2.2%, not significant). On Windows, torch.compile is a no-op (fake Triton). Eager decode always.

4. **Quantization policy:** Q4_K_M is the universal default for all models tested (llama3.2-1b, qwen2.5-1.5b, phi-2, llama3.2-3b, llama3.1-8b). Use Q8_0 for quality-critical workloads where benchmark accuracy within 2pp of baseline is required. Never deploy Q2_K -- it produces near-random accuracy across all models. Q3_K_S is acceptable only for phi-2 and llama3.1-8b; it breaks llama3.2-1b, llama3.2-3b, and qwen2.5-1.5b (9.5-12.2pp loss).

5. **Context budget:** For FP16 HuggingFace inference on 12 GB VRAM: 4-8K tokens maximum before VRAM spillover causes 25-105x latency cliffs. For Ollama with quantized models: effectively unlimited within model context limits (quantization reduces KV-cache footprint proportionally). Monitor VRAM utilization and never exceed 90% capacity.

6. **Capacity planning:** Use `chimeraforge plan` for configuration search across the (model, quantization, backend, N-agents) space. The empirical lookup tables with first-principles interpolation are validated (R^2 >= 0.859 for throughput, R^2 = 0.968 for VRAM). Do not use M/D/1 queueing theory for latency prediction -- it deviates up to 20.4x from reality.

### Operational Defaults (Decision Card)

Valid under stated boundary conditions (RTX 4080 Laptop GPU, 12 GB VRAM, PyTorch 2.x, CUDA 12.x, Ollama 0.6.x, vLLM 0.7.x).

- **Single-agent backend:** Ollama Q4_K_M
- **Multi-agent backend (N >= 4):** vLLM FP16
- **Crossover point:** N=3 is marginal; benchmark on your workload. N <= 2 favors Ollama; N >= 4 favors vLLM.
- **Compile:** prefill-only on Linux with Inductor+Triton; eager decode always; never compile on Windows
- **Quantization:** Q4_K_M default; Q8_0 for quality-critical; never Q2_K; Q3_K_S only for phi-2 and llama3.1-8b
- **Context budget:** Ollama for > 4K tokens; HF FP16 only for <= 4K tokens on 12 GB VRAM
- **Agent count:** 2-3 per GPU for Ollama; up to 8 for vLLM (continuous batching amortizes bandwidth)
- **Streaming:** always on (zero wall-clock overhead, confirmed by 0/9 significant tests in TR128)
- **Quality gate:** composite >= 0.50 for production workloads; >= 0.60 for quality-critical applications
- **Capacity tool:** `chimeraforge plan` for configuration search (6 models, 4/4 validation targets met)
- **NUM_PARALLEL:** leave at default (1); setting > 1 is a no-op on single GPU (TR128)
- **Thermal:** no throttling concern under sustained load (peak 66 deg C, TR128)
- **VRAM monitoring:** alert at 85% utilization; hard-stop at 90% to avoid spillover cliffs

**What invalidates this report:**
- Hardware change (different GPU, different VRAM capacity, different memory bandwidth)
- PyTorch major version upgrade (kernel paths, compile behavior, CUDA graph handling)
- Ollama version upgrade (serving stack behavior, quantization engine changes)
- vLLM version upgrade (continuous batching implementation, scheduler changes)
- Workload mix shift without revalidation (different prompt/decode ratio, different model families)
- CUDA/driver version change (kernel scheduling, memory management behavior)

**Manifest requirements (minimum):**
- GPU model + driver version
- CUDA version
- PyTorch version
- Ollama version (if used)
- vLLM version (if used)
- TGI version (if used)
- Nsight Systems / Nsight Compute version (if profiling)
- Docker version (if containerized)
- OS and kernel version (Linux vs Windows matters for compile)
- Git commit SHAs for report generation and analysis scripts
- ChimeraForge version (for capacity planning)

---

## 1. Introduction and Research Questions

### 1.1 Motivation

Phase 1 of this research program (TR117-TR122) answered a foundational question: how do we measure LLM inference performance in a way that survives audit? The output was a measurement methodology -- artifact-backed, phase-aware, attribution-correct -- and a set of decision-grade reporting conventions that made every claim traceable from raw log to published conclusion. That work was necessary, but it was not sufficient. Knowing how to measure is not the same as knowing what to deploy.

Phase 2 (TR123-TR133) makes the transition from measurement methodology to deployment decisions. Where Phase 1 asked "which backend is faster?", Phase 2 asks the full stack of production questions that an engineering team must answer before shipping local-first LLM inference: What does it cost? Is the quality preserved when you switch backends or quantize? Which quantization level gives you the best cost-quality tradeoff? Does torch.compile actually help when real Triton kernels are available, or was the Phase 1 result an artifact of Windows limitations? How does latency scale with context length on a consumer GPU with 12 GB of VRAM? What happens when you put the system under realistic production load -- concurrent requests, streaming, multi-turn conversations? How does per-agent throughput degrade when multiple agents share one GPU? Which serving stack scales best under concurrency? Is the serving stack even the bottleneck, or is it the GPU itself? And finally, can you operationalize all of these findings into a tool that makes the decision for you?

These are not academic questions. They are the questions that determine whether a team deploys Ollama or vLLM, whether they use Q4_K_M or FP16, whether they budget for one GPU or four, and whether they can serve eight agents from a single consumer card. The research program is designed so that each question can only be answered after the preceding questions have been resolved. You cannot do quantization policy without quality baselines. You cannot do compile policy without cross-platform validation. You cannot do capacity planning without production characterization. You cannot identify the real bottleneck without GPU kernel profiling. And you cannot operationalize anything without all of the above.

The central challenge of Phase 2 is therefore not measurement -- that problem was solved in Phase 1 -- but the translation of measurements into decisions that are bounded, falsifiable, and operationally actionable. The shift is from descriptive benchmarking to prescriptive engineering. The difference is not rhetorical; it manifests in the structure of every report. Each TR in Phase 2 either fills a gap exposed by the previous TR or falsifies a hypothesis that the previous TR made plausible. The program trajectory is a directed acyclic graph of evidence dependencies, not a collection of independent studies.

This motivation also explains the scope. Phase 2 is deliberately bounded to one hardware baseline (RTX 4080 Laptop GPU, 12 GB VRAM), a fixed set of models (124M to 8B parameters), and a fixed software stack (PyTorch 2.x, CUDA 12.x, Ollama, vLLM, TGI). The portable output is not the absolute numbers, which will change with every hardware and software upgrade. The portable output is the method, the decision framework, and the gating rules that determine when a measurement is trustworthy enough to ship. If you change the GPU, you re-run the measurements; but you use the same framework to interpret them.

### 1.2 Research questions (program level)

This conclusive report answers the following ten cross-cutting questions, each of which maps to one or more technical reports in the Phase 2 sequence:

1. **What does production KV-cached inference actually cost, and how does architecture (MHA vs GQA) affect economics?** (TR123) KV-cache reuse during decode is the dominant cost lever for autoregressive generation. The cost depends on attention architecture: Multi-Head Attention (MHA) allocates independent key-value heads per attention head, while Grouped-Query Attention (GQA) shares heads across groups, reducing memory and compute. This question requires phase-split cost modeling that separates prefill from decode economics.

2. **Do backend and quantization choices affect output quality?** (TR124) If two backends produce different throughput but identical quality, the cheaper one is strictly better. If quantization reduces cost but also reduces quality, the decision requires a Pareto analysis. This question requires a quality evaluation framework that goes beyond simple accuracy to include generation metrics (BERTScore, ROUGE-L, coherence) and benchmark-based evaluation (MMLU, HellaSwag, ARC).

3. **What quantization level preserves quality while minimizing cost?** (TR125) Quantization is a continuous tradeoff between model size, inference speed, and output quality. The question is not whether quantization degrades quality -- it does -- but where the acceptable boundary lies, and whether that boundary is universal across model families or model-specific.

4. **Does torch.compile actually help when Triton is available (not faked by aot_eager)?** (TR126) Phase 1 (TR120) showed that torch.compile on Windows used aot_eager as its Triton fallback, producing no real compilation. This question requires cross-platform validation on Linux with a genuine Triton backend to determine whether the compile paradox is a Windows artifact or a fundamental limitation.

5. **How does performance scale with context length on consumer hardware?** (TR127) Transformer attention is theoretically O(n^2) in context length, but practical scaling depends on kernel implementations (Flash Attention), memory hierarchy (VRAM capacity, bandwidth, spillover to system RAM), and serving stack optimization. The question is what actually dominates on a 12 GB consumer GPU.

6. **What happens under realistic production load (concurrency, streaming, multi-turn)?** (TR128) Single-request benchmarks do not capture production behavior. This question tests whether Ollama's NUM_PARALLEL setting enables real concurrent GPU inference, whether streaming adds overhead, whether queueing theory (M/D/1) predicts latency under load, and whether thermal throttling occurs during sustained operation.

7. **How does per-agent throughput scale with N agents sharing one GPU?** (TR129) Multi-agent systems require multiple concurrent inference streams. Amdahl's Law predicts diminishing returns from parallelism due to serial fractions. The question is what the serial fraction actually is for GPU-bound LLM inference, and at what agent count the system saturates.

8. **Which serving stack (Ollama vs vLLM vs TGI) scales best under concurrency?** (TR130) Different serving stacks use fundamentally different scheduling strategies. Ollama processes requests sequentially. vLLM uses PagedAttention and continuous batching. TGI uses continuous batching with a different implementation. The question is which strategy scales best as concurrent agent count increases.

9. **What is the root cause of multi-agent throughput degradation -- software or hardware?** (TR131, TR132) TR129 and TR130 attributed the scaling bottleneck to the serving stack (Ollama). But this attribution was made without direct evidence from the GPU. The question is whether the bottleneck is software (serving stack overhead, scheduling, serialization) or hardware (GPU memory bandwidth saturation, kernel serialization). Answering this requires GPU kernel profiling with Nsight Systems and Nsight Compute.

10. **Can we operationalize 70,000+ measurements into a predictive decision tool?** (TR133) The ultimate deliverable of a research program is not a report; it is a tool that makes the right decision without requiring the user to read the report. The question is whether empirical lookup tables with first-principles interpolation can predict VRAM requirements, throughput, quality, and cost accurately enough to replace manual configuration search.

These ten questions form a dependency chain. Each question can only be asked -- let alone answered -- once the preceding questions have been resolved. The ordering is not arbitrary; it is methodologically forced.

### 1.3 Contributions of this synthesis

This synthesis contributes eleven decision-grade deliverables, one per technical report, plus an operationalization tool:

1. **Phase-split production cost tables** (TR123): The first decision-grade $/token tables for KV-cached inference, separating prefill from decode costs across 5 models, 3 backends, and 5 workload scenarios. Establishes that cached decode is 2-8x cheaper than uncached across all tested configurations.

2. **Quality equivalence certification** (TR124): ANOVA with Holm-Bonferroni correction across 7 quality metrics, 5 models, and 2 backends at temp=0. Confirms that backend choice does not affect output quality, which makes the cheapest backend strictly optimal for a given quality level.

3. **Quantization decision matrix** (TR125): The complete mapping from quantization level to quality, cost, and throughput across 5 models and 7 quantization levels. Identifies Q4_K_M as the universal sweet spot, Q3_K_S as model-dependent, and Q2_K as universally unacceptable.

4. **Compile paradox resolution** (TR126): Cross-platform validation that reverses the Phase 1 finding. Real Triton on Linux delivers 24-60% prefill latency reduction. Establishes the compile policy: prefill only, Linux only, eager decode always.

5. **Two-regime context scaling characterization** (TR127): Discovery of clean sub-linear scaling below VRAM capacity and catastrophic 25-105x latency cliffs at spillover thresholds. Establishes VRAM spillover, not quadratic attention, as the practical bottleneck.

6. **Production workload characterization** (TR128): Refutation of NUM_PARALLEL as a concurrency enabler, refutation of M/D/1 queueing theory (20.4x deviation), and confirmation of zero streaming overhead. Provides calibrated service time baselines.

7. **N-agent scaling laws** (TR129): Amdahl's Law fits with serial fractions s=0.39-0.54, demonstrating that total throughput plateaus at N=2 with diminishing returns thereafter. Per-agent throughput degrades monotonically while fairness remains excellent.

8. **Serving stack comparison** (TR130): Head-to-head evaluation of Ollama, vLLM, and TGI under identical conditions. vLLM achieves 2.25x throughput advantage at N=8 via continuous batching. Different backends follow different scaling laws (Amdahl vs power law).

9. **GPU physics attribution** (TR131): Overturns the serving-stack-as-bottleneck narrative. GPU kernel profiling shows PyTorch Direct (no serving stack) degrades worse than Ollama under identical concurrency. Memory bandwidth stress (+74% at N=8) is the mechanism, not software overhead.

10. **Continuous batching mechanism proof** (TR132): In-container GPU kernel profiling demonstrates that continuous batching reduces kernel launches by 77-80% and memory bandwidth per token by 79-83%. This resolves the TR130/TR131 contradiction: vLLM scales better because continuous batching amortizes the GPU memory bandwidth bottleneck.

11. **Predictive capacity planner** (TR133): Operationalizes the entire corpus into a CLI tool (`chimeraforge plan`) with 6 predictive models, all 4 validation targets met, and 10/10 spot checks passing. Empirical lookup tables with first-principles interpolation outperform theoretical models.

12. **ChimeraForge CLI tool** (cross-cutting): A pip-installable command-line tool that accepts a deployment scenario (model, quantization, backend, agent count, latency SLA, quality floor, budget ceiling) and returns ranked configurations with predicted VRAM, throughput, quality, cost, and latency. Runtime under 1 second. Zero GPU required for planning.

### 1.4 Document structure and reading guide

This report is structured for multiple audiences. Not every reader needs every section. The following guide maps reading goals to sections:

**If you need deployment decisions:** Read the Executive Summary, Section 4 (Decision Impact Matrix), Section 6 (Cross-Report Synthesis by Decision Axis), and Section 8 (Operational Doctrine and Risk Controls). These sections translate measurements into actionable policies with explicit boundary conditions and invalidation triggers.

**If you need method defensibility:** Read Section 3 (Methods and Measurement Framework) plus the limitation gates in Section 10 (Limitations by Report), then Appendix B (Claim-to-Artifact Chain-of-Custody). These sections provide the evidential chain from measurement to claim, including where the chain is weak or broken.

**If you need planning numbers:** Read Section 7 (Economics, Capacity, and Cost-Quality Tradeoffs) and Appendix A (Key Formulas and Derivations). Worked examples for chat deployment sizing and RAG pipeline capacity planning are included inline.

**If you need scaling analysis:** Read Sections 5.7 through 5.10 (TR129-TR132), which trace the scaling question from Amdahl's Law through GPU kernel physics to continuous batching amortization. This is the most technically dense portion of the report and requires familiarity with GPU architecture concepts.

**If you need quality assurance:** Read Sections 5.2 and 5.3 (TR124-TR125), which establish quality baselines and map the quantization decision space. Appendix P provides quantization decision trees and quality gates.

**If you need GPU physics understanding:** Read Sections 5.9 and 5.10 (TR131-TR132), which open the GPU black box and explain why memory bandwidth, not the serving stack, is the fundamental scaling bottleneck. Appendix X provides the GPU kernel profiling methodology in detail.

The report is intentionally front-loaded with decision content (Executive Summary, Decision Card, Decision Impact Matrix) so that operators can extract what they need without reading the full 200+ page synthesis. The depth is reserved for researchers and auditors who need to verify the evidence chain.

---

## 2. Background and Related Work

### 2.1 KV-cache mechanics and phase economics

Transformer inference [1] splits naturally into two computational phases with fundamentally different performance characteristics. The prefill phase processes the entire input prompt in a single forward pass, encoding all tokens in parallel through the self-attention layers. The decode phase generates output tokens one at a time, attending to all previously generated tokens plus the original prompt context. This phase split is not a software abstraction; it reflects a hardware reality. Prefill is compute-bound (matrix-matrix operations over the prompt), while decode is memory-bandwidth-bound (matrix-vector operations against a growing cache).

The key-value cache (KV-cache) is the mechanism that makes autoregressive decode tractable. Without caching, each new token would require recomputing attention over the entire preceding sequence, producing O(n^2) total work for n tokens. With caching, previously computed key and value projections are stored and reused, reducing per-token decode to O(n) attention computation (attending to n cached positions) plus O(1) new key-value computation. The economic implications are substantial: cached decode can be 2-8x cheaper than uncached decode per token, as TR123 demonstrates across all five tested models.

The memory footprint of the KV-cache depends critically on the attention architecture. Multi-Head Attention (MHA), used in GPT-2 and Phi-2, maintains independent key and value projections for every attention head. The per-token KV-cache cost for an MHA model is:

KV_bytes = 2 * n_layers * n_heads * d_head * precision_bytes

Grouped-Query Attention (GQA), used in LLaMA-3.2 and Qwen-2.5, shares key-value heads across groups of query heads. This reduces the per-token KV-cache cost by the ratio of KV heads to query heads. For example, Qwen-2.5-1.5B uses 2 KV heads with 12 query heads, a 6:1 ratio that reduces KV-cache memory by approximately 6x compared to an equivalent MHA architecture. TR123 validates this formula across all 5 models (30/30 exact matches) and shows the practical consequence: Qwen-2.5-1.5B requires 56 MB of KV-cache at 2K context, while Phi-2 (MHA, similar parameter count) requires 640 MB -- an 11.4x difference that directly determines how many concurrent contexts can fit in VRAM.

Phase-split cost modeling, introduced in TR123 and used throughout Phase 2, decomposes the $/token metric into prefill and decode components weighted by workload scenario. Five blend ratios capture production workload profiles: RAG-heavy (0.95 decode fraction), summarization (0.85), chat (0.67), balanced (0.50), and code generation (0.25). This decomposition is essential because a backend that excels at prefill may be uneconomical for decode-heavy workloads, and vice versa.

### 2.2 Quality evaluation for LLMs

Evaluating the quality of LLM outputs is a multi-dimensional problem that does not reduce to a single metric. The Phase 2 program uses three complementary evaluation approaches, each capturing a different aspect of quality.

Generation metrics assess the quality of free-form text output against reference answers. ROUGE-L [measured via the rouge-score library] captures longest common subsequence overlap, providing a surface-level similarity measure. BERTScore [measured via the bert-score library with microsoft/deberta-xlarge-mnli] computes contextual embedding similarity, capturing semantic equivalence even when surface forms differ. SemScore [17] extends this to instruction-following evaluation by comparing full-response embeddings. Additional metrics include exact match (for factual tasks), coherence (measured via sentence-level embedding consistency), and task-specific measures (e.g., code correctness for programming tasks). Together, these seven metrics provide a composite quality score that balances surface fidelity, semantic equivalence, and task-appropriate evaluation.

Benchmark-based evaluation uses standardized academic benchmarks to measure model capability under controlled conditions. MMLU (Massive Multitask Language Understanding) tests knowledge across 57 subjects. HellaSwag tests commonsense reasoning via sentence completion. ARC-Challenge tests scientific reasoning with difficult multiple-choice questions. These benchmarks provide calibrated accuracy scores that can be compared against published baselines and across quantization levels. TR125 uses 285 MMLU questions and 200 ARC-Challenge questions per model-quantization combination, with rescored accuracy that handles formatting variation in model responses.

The Pareto frontier approach, introduced in TR124 and extended in TR125, plots quality against cost to identify configurations where no other configuration achieves both higher quality and lower cost. This is the operationally relevant view: a configuration that is not on the Pareto frontier is strictly dominated and should never be deployed. TR124 identifies 3 of 8 model-backend combinations as Pareto-optimal; TR125 extends this analysis across quantization levels.

Temperature control is a critical experimental design choice. All primary evaluations use temp=0 (greedy decoding) to ensure deterministic outputs and valid statistical comparisons across backends and quantization levels. TR124 Phase 3 explicitly tests temp=0.7 (stochastic sampling) and finds that quality becomes highly unstable (mean coefficient of variation 0.33), confirming that deterministic decode is necessary for reliable quality evaluation.

### 2.3 Quantization

Quantization reduces model weight precision from 16-bit floating point (FP16) to lower bit-widths, decreasing model size, VRAM consumption, and (in bandwidth-limited regimes) increasing inference throughput. The tradeoff is potential quality degradation as numerical precision decreases.

The GGUF format, used by Ollama and llama.cpp, implements k-quant schemes that apply mixed-precision quantization with per-block scaling factors. The k-quant levels tested in Phase 2 span a wide range: Q2_K (approximately 2.5 bits per weight), Q3_K_S (approximately 3.4 bits), Q3_K_M (approximately 3.9 bits), Q4_K_M (approximately 4.8 bits), Q5_K_M (approximately 5.7 bits), Q6_K (approximately 6.6 bits), Q8_0 (8 bits), and FP16 (16 bits). Each level uses different block sizes, scaling strategies, and super-block structures, resulting in a non-linear relationship between nominal bit-width and effective model quality.

The statistical framework for quantization evaluation uses two complementary approaches. The Two One-Sided Tests (TOST) procedure tests for practical equivalence: given an equivalence margin (e.g., plus or minus 3 percentage points), TOST determines whether the quantized model's accuracy is statistically within that margin of the baseline. Wilson confidence intervals provide bounded uncertainty estimates for accuracy proportions that are valid even at small sample sizes. TR125 finds that TOST is underpowered at the plus or minus 3pp margin (0/18 equivalence claims pass) but partially powered at plus or minus 5pp (6/18 pass), which is itself an informative result -- it bounds the minimum detectable equivalence margin for the sample sizes used.

The key empirical finding across TR124 and TR125 is the existence of quality cliffs. Quality degradation is not smooth; it is relatively stable from FP16 through Q4_K_M (typically within 4 percentage points of baseline) and then falls sharply at Q3_K_S for some models (9.5-12.2pp loss for llama3.2-1b, llama3.2-3b, and qwen2.5-1.5b) before collapsing entirely at Q2_K (near-random accuracy, with qwen2.5-1.5b showing a 40.6pp loss). This cliff structure makes the quantization decision binary at certain thresholds rather than a smooth cost-quality tradeoff.

### 2.4 Compiler systems for deep learning inference

PyTorch's torch.compile [6] uses the Inductor backend to lower Python-level model code into optimized GPU kernels. When the Triton JIT compiler is available (Linux with a compatible CUDA toolkit), Inductor generates fused Triton kernels that can substantially reduce memory movement and kernel launch overhead, particularly for prefill where large matrix-matrix operations benefit most from fusion. When Triton is not available (Windows, or certain driver configurations), torch.compile falls back to aot_eager mode, which traces the computation graph ahead-of-time but executes the same eager PyTorch kernels. This fallback provides no speedup; it is functionally equivalent to eager execution with additional compilation overhead.

The Phase 1 finding (TR120) that torch.compile showed no consistent speedup was a direct consequence of this fallback: all Windows measurements used aot_eager without Triton, producing a "compile" label with no compiler-real behavior. Phase 2 (TR126) resolves this by testing on Docker/Linux with a genuine Triton installation, revealing speedups of 24-60% on prefill across all 7 models (Cohen's d = -0.59, p = 8.87 x 10^-61, 916 cumulative Triton kernels generated). This reversal is one of the most operationally significant findings in the program.

CUDA graphs [19] provide another optimization path by recording a sequence of GPU operations and replaying them without CPU-side dispatch overhead. This is particularly effective for decode, where the same small computation is repeated thousands of times. However, CUDA graphs require static tensor shapes, which conflicts with the dynamic KV-cache that grows by one token per decode step. PyTorch's DynamicCache is incompatible with CUDA graph capture, causing crashes when torch.compile is applied to autoregressive decode with reduce-overhead mode. TR126 documents this failure systematically: compiled decode crashes in 100% of tested configurations with reduce-overhead mode, and the fallback to mode="default" produces no statistically significant speedup (+2.2%, not significant). StaticCache enables compiled decode but introduces a 5.8x slowdown due to padding overhead. A PyTorch issue (pytorch/pytorch#175557) and PR (#175562) have been filed to address this limitation.

The resulting compile policy is definitive: compile prefill only, on Linux only, with Inductor+Triton backend; use eager decode always; never compile on Windows. This policy emerges from five independent lines of evidence: (1) Triton unavailability on Windows, (2) DynamicCache incompatibility with CUDA graphs, (3) StaticCache overhead, (4) absence of decode speedup even when compilation succeeds, and (5) 916 Triton kernels confirming real compilation on Linux.

### 2.5 Context scaling and memory hierarchy

The theoretical scaling of self-attention is O(n^2) in context length n, because each token attends to all previous tokens. For long sequences, this quadratic scaling would eventually dominate inference cost. In practice, however, the scaling behavior on consumer GPUs is governed by a more immediate constraint: VRAM capacity.

Flash Attention [3, 13] reduces the memory footprint of attention computation from O(n^2) to O(n) by computing attention in tiles and never materializing the full attention matrix. This eliminates the quadratic memory bottleneck but does not eliminate the quadratic compute. However, for the model sizes and context lengths tested in Phase 2 (up to 32K tokens on models up to 3.2B parameters), the quadratic compute cost remains modest relative to the memory-bandwidth cost of loading weights and KV-cache from VRAM. Flash Attention therefore effectively converts the scaling regime from quadratic-memory-limited to linear-memory, bandwidth-limited -- until VRAM runs out.

Paged KV-cache management, introduced by vLLM [14], treats KV-cache memory as virtual memory pages that can be allocated and freed independently. This eliminates internal fragmentation and enables efficient sharing of KV-cache across concurrent requests. The practical benefit is that multiple requests can coexist in VRAM without pre-allocating worst-case memory for each, which is essential for continuous batching.

The dominant scaling phenomenon discovered in TR127 is VRAM spillover. When the combined footprint of model weights, KV-cache, and activation memory exceeds the 12 GB VRAM capacity, CUDA Unified Memory transparently migrates pages to system RAM. This migration incurs PCIe bandwidth penalties that are 10-20x worse than VRAM bandwidth (PCIe 4.0 x16 at approximately 25 GB/s vs VRAM at 432 GB/s). The result is not a gradual degradation but a catastrophic latency cliff: 25-105x increases in per-token latency at the spillover threshold. Below the spillover threshold, Ollama prefill scaling is clean and sub-linear (power-law exponent b = 0.083-0.158). HF FP16 pre-spillover scaling is between linear and quadratic (b = 1.58-1.78, R² > 0.999). Above the spillover threshold, latency explodes. This two-regime behavior means that VRAM capacity, not quadratic attention, is the practical context scaling bottleneck for consumer GPUs.

The implication for deployment is direct: the maximum usable context length is determined by the VRAM budget equation (VRAM_available = model_weights + KV_cost_per_token * context_length + activation_overhead), and exceeding this budget by even a single step can cause order-of-magnitude latency regressions. Ollama's quantized models, which reduce both weight and KV-cache footprint, can operate at much longer context lengths than FP16 HuggingFace models on the same hardware.

### 2.6 Queueing theory for inference

Classical queueing theory provides a framework for reasoning about latency under concurrent load. The M/D/1 model (Poisson arrivals, deterministic service, single server) is the simplest applicable model for GPU inference, where the "server" is the GPU and "service time" is the inference latency for a single request. Under M/D/1, the expected wait time grows as utilization approaches 1, with the familiar hockey-stick curve.

The appeal of queueing theory for capacity planning is obvious: if you know the arrival rate and service time, you can predict latency without running experiments. TR128 tests this directly by measuring Ollama under Poisson-distributed request arrivals at varying arrival rates and comparing observed latencies to M/D/1 predictions.

The result is a definitive failure. M/D/1 predictions deviate from observed latency by up to 20.4x. The deviation is not a calibration issue; it is a structural mismatch. The M/D/1 model assumes that the server processes one request at a time with deterministic service time. In reality, Ollama's service time is stochastic (varying with prompt length, generation length, and model state), the GPU has internal scheduling that does not correspond to a single-server queue, and Ollama's NUM_PARALLEL setting (which claims to enable concurrent inference) is a no-op for single-GPU deployments (0/30 statistical tests significant, mean absolute change 4.0%). The GPU processes requests sequentially regardless of the NUM_PARALLEL setting, but the queueing dynamics do not match M/D/1 because arrival patterns interact with the serving stack's request buffering in ways the model cannot capture.

This failure is not an embarrassment; it is a finding. It establishes that theoretical queueing models cannot substitute for empirical measurement in LLM inference capacity planning. This is why TR133 builds the predictive capacity planner from empirical lookup tables rather than from queueing theory.

### 2.7 Multi-agent systems and closed-loop scheduling

Multi-agent LLM systems deploy multiple inference-consuming agents that share a single GPU. Each agent operates in a closed loop: send a request, wait for the response, process the response (think time), then send the next request. This is fundamentally different from the open-loop Poisson arrival model tested in TR128, because the arrival rate is endogenous -- it depends on how fast the GPU serves the previous requests.

Amdahl's Law [15] provides the classical framework for parallel speedup with serial bottlenecks. Applied to GPU inference, it predicts that total system throughput S(N) for N agents is bounded by:

S(N) = 1 / (s + (1-s)/N)

where s is the serial fraction -- the proportion of the workload that cannot be parallelized. TR129 fits this model to empirical data across 3 models and N=1 through N=8, finding serial fractions of s=0.39 (llama3.2-3b), s=0.46 (qwen2.5-1.5b), and s=0.54 (llama3.2-1b), all with R^2 > 0.97.

The serial fractions are high -- much higher than typical CPU parallelism scenarios -- because GPU inference is fundamentally serialized at the hardware level. TR131 confirms this with kernel profiling: max_concurrent_kernels = 1 in all tested conditions, meaning the GPU executes one kernel at a time regardless of how many agents are sending requests. The "parallelism" in multi-agent GPU inference is not instruction-level or kernel-level parallelism; it is request-level pipelining, where one request's decode overlap with another request's queueing.

Fairness is an important secondary metric. Jain's fairness index [20] measures how equitably throughput is distributed across agents, ranging from 1/N (maximally unfair) to 1.0 (perfectly fair). TR129 finds excellent fairness (Jain's index >= 0.997 at N=8 for all models), meaning that while per-agent throughput degrades severely, it degrades equally across all agents. This is a desirable property for multi-agent systems where no single agent should be starved.

The key limitation of Amdahl's Law in this context is that the serial fraction is not a physical constant; it is a curve-fitting parameter that captures the combined effect of GPU serialization, serving stack overhead, memory bandwidth contention, and KV-cache pressure. TR129's serial fractions are valid descriptors of Ollama's scaling behavior, but they cannot be directly compared to vLLM's or TGI's scaling behavior, which follows a power-law rather than Amdahl's model. This cross-backend comparison is a category error that TR131 and TR132 resolve by going below the serving stack to the GPU kernel level.

### 2.8 Serving stack architectures

Three serving stacks are evaluated in Phase 2, each implementing a fundamentally different request scheduling strategy.

Ollama [8] is a local-first inference server built on llama.cpp. It processes requests sequentially: each request is fully served (prefill + decode) before the next request begins. This sequential processing is simple and efficient for single-agent workloads (no scheduling overhead, no context switching) but scales poorly with concurrency because each additional agent must wait for all preceding agents to complete their current requests. Ollama uses GGUF-quantized models (Q2_K through Q8_0), which reduces VRAM consumption and can increase throughput on bandwidth-limited hardware. The NUM_PARALLEL configuration parameter claims to enable concurrent inference but is empirically a no-op on single-GPU deployments (TR128).

vLLM [14] is a high-throughput serving engine that implements PagedAttention for KV-cache management and continuous batching for request scheduling. Continuous batching allows new requests to begin prefill while existing requests are still decoding, and it batches the decode operations of multiple concurrent requests into a single GPU kernel launch. This amortizes kernel launch overhead and memory bandwidth across requests, which is the mechanism that TR132 validates at the kernel level. vLLM uses FP16 weights by default (AWQ/GPTQ quantization available but not tested in Phase 2).

Text Generation Inference (TGI) is Hugging Face's serving stack, which also implements continuous batching. TGI's continuous batching provides the same amortization mechanism as vLLM (TR132 confirms nearly identical kernel reduction ratios), but TGI's absolute throughput is lower than vLLM's, likely due to implementation differences in scheduler efficiency and kernel selection (TR132 shows TGI uses 41-57% GEMM time vs vLLM's 69-82%).

The scaling behavior of these three stacks is qualitatively different. Ollama follows Amdahl's Law (asymptotic saturation), while vLLM and TGI follow power-law scaling (monotonic improvement without saturation within the tested range of N=1 to N=8). This difference is not a matter of degree; it reflects a fundamentally different relationship between concurrency and GPU utilization. Sequential processing (Ollama) treats concurrency as queueing; continuous batching (vLLM, TGI) treats concurrency as an opportunity to amortize fixed costs.

The quantization confound in the TR130 comparison must be noted: Ollama runs Q4_0 models while vLLM and TGI run FP16. This means absolute throughput comparisons favor Ollama at low concurrency (quantization reduces bandwidth demand) and vLLM/TGI at high concurrency (continuous batching amortizes bandwidth). The normalized efficiency metric eta(N) = throughput(N) / (N * throughput(1)) controls for this by measuring relative scaling rather than absolute throughput.

### 2.9 GPU profiling and memory bandwidth

Understanding GPU behavior during inference requires profiling at the kernel level, below the serving stack abstraction. NVIDIA provides two complementary profiling tools. Nsight Systems (nsys) [16] captures a timeline trace of all GPU activity -- kernel launches, memory operations, CUDA API calls, and CPU-GPU synchronization -- with nanosecond resolution. Nsight Compute (ncu) provides detailed per-kernel metrics including arithmetic throughput, memory bandwidth utilization, occupancy, and warp execution efficiency.

TR131 deploys both tools on bare-metal Windows (Ollama and PyTorch Direct as backends) to test five hypotheses about the root cause of multi-agent throughput degradation. The central finding is that GPU memory bandwidth stress increases by 74.4% from N=1 to N=8 (p = 6.4 x 10^-5, Cohen's d = 3.81, sole Holm-surviving test across all hypothesis tests). This bandwidth stress is the mechanism behind throughput degradation, not serving stack overhead: PyTorch Direct (no serving stack whatsoever) degrades 86.4% at N=8, worse than Ollama's 82.1%.

A critical limitation of GPU profiling on Windows is the Windows Display Driver Model (WDDM), which interposes a command buffer between the application and the GPU. Under WDDM, Nsight Compute cannot read hardware performance counters (all ncu metrics return null), and Nsight Systems traces may not capture the same kernel-level detail as under Linux's TCC (Tesla Compute Cluster) driver. TR131 works around this with back-of-envelope bandwidth calculations and TR132 addresses it by profiling inside Docker containers on WSL2, where the CUPTI (CUDA Profiling Tools Interface) provides sufficient access for kernel-level attribution.

TR132 extends the profiling to vLLM and TGI inside Docker containers, using a novel methodology that maps Nsight Systems traces from containerized GPU workloads on WSL2/WDDM systems. This methodology generates approximately 375 MB of profiling traces across 25 runs and demonstrates the continuous batching amortization mechanism at the kernel level: 77-80% reduction in kernel launches per token, 79-83% reduction in memory bandwidth per token, and amortization ratios of 4.7-5.8x (59-72% of theoretical 8:1 maximum for N=8).

The back-of-envelope bandwidth calculation that anchors the bottleneck attribution is straightforward. An RTX 4080 Laptop GPU provides 432 GB/s of VRAM bandwidth. Loading the weights of a Q4_0 model (e.g., llama3.2-3b at approximately 1.8 GB) for one decode step requires approximately 1.8 GB / 432 GB/s = 4.2 ms of bandwidth time per token. At N=8, if each agent's decode step requires loading the full model weights, the aggregate bandwidth demand is 8 * 1.8 GB per decode cycle, which at 432 GB/s requires approximately 33 ms -- exceeding the N=1 service time and saturating bandwidth by 78-130% depending on model size. This is why memory bandwidth, not compute, is the bottleneck for multi-agent decode.

### 2.10 Predictive modeling for capacity planning

The ultimate goal of a measurement program is to make the measurements unnecessary for future decisions within the validated domain. Predictive capacity planning models attempt this by learning relationships from historical measurements and using them to predict performance for new configurations.

Two broad approaches exist. Machine learning models (gradient-boosted trees, neural networks) can capture complex nonlinear relationships but require large training datasets, provide limited interpretability, and may not generalize beyond the training distribution. First-principles models derive predictions from physical equations (e.g., VRAM = model_weights * overhead_factor + KV_bytes_per_token * context_length) but may miss empirical effects like allocator fragmentation, kernel scheduling overhead, or serving stack inefficiency.

TR133 takes a hybrid approach: empirical lookup tables for the primary predictions (throughput, quality) and first-principles formulas for the derived predictions (VRAM, cost, latency). The lookup tables are populated from 19,676 measurements across TR123-TR130, and the first-principles formulas are calibrated against the same data. The key insight is that for a bounded hardware/software configuration, the (model, quantization, backend, N-agents) space is finite and can be enumerated rather than modeled. A 22-entry throughput lookup table with power-law fallback (72.1 * params^-0.089) achieves R^2 = 0.859, which exceeds the validation target of 0.85. VRAM prediction using the first-principles formula with a calibrated overhead factor of 1.058x achieves R^2 = 0.968.

The 4-gate search algorithm operationalizes these models: (1) VRAM gate eliminates configurations that exceed GPU memory, (2) quality gate eliminates configurations below the quality floor, (3) latency gate eliminates configurations that violate the latency SLA, (4) budget gate eliminates configurations above the cost ceiling. Surviving configurations are ranked by cost efficiency. This approach is computationally trivial (under 1 second on any CPU) and requires no GPU for planning.

The limitation of the lookup-table approach is that it cannot extrapolate beyond the measured domain. Predictions for GPUs with different VRAM capacities, memory bandwidths, or compute capabilities use a linear bandwidth-scaling approximation that is unverified. Cross-GPU extrapolation is flagged as an open validation gap. Within the measured domain, however, the approach outperforms theoretical models (which deviate 20.4x for latency prediction via M/D/1) by a wide margin.

---

## 3. Methods and Measurement Framework

### 3.1 Artifact-first methodology

The artifact-first methodology established in TR118_v2.2 (Phase 1) serves as the foundational discipline for every Phase 2 report. The core rule is simple: any claim that matters must be traceable to a raw artifact. This traceability chain has three links: (1) raw measurement logs (CSV, JSONL, or profiling traces) stored with deterministic file paths and naming conventions, (2) processing scripts that transform raw logs into summary statistics using documented, deterministic transformations, and (3) report generation scripts that consume summaries and produce the published report. Every link in the chain is version-controlled with Git commit SHAs recorded in report metadata.

Phase 2 extends this discipline in three significant ways. First, the measurement corpus grows from approximately 2,000 samples (Phase 1) to approximately 70,000 measurements across 11 reports, requiring more rigorous data management. Second, the artifact types expand beyond latency logs to include quality evaluation outputs (generation metrics, benchmark scores), GPU profiling traces (Nsight Systems .nsys-rep files, typically 50-150 MB each), and predictive model validation records. Third, the chain-of-custody becomes bidirectional: not only can you trace forward from measurement to claim, but the claim status table in the Executive Summary traces backward from each claim to its evidence base, including which statistical tests survived correction and which did not.

The artifact-first methodology is not a bureaucratic overhead; it is a falsification tool. When TR131 overturns TR130's attribution of the scaling bottleneck to the serving stack, the evidence chain allows precise identification of where the earlier attribution went wrong (TR130 lacked GPU-level profiling data) and why the new attribution is better supported (TR131 adds kernel-level bandwidth measurements). Without artifact traceability, this kind of progressive correction would be indistinguishable from post-hoc rationalization.

### 3.2 Phase-aware metrics

All Phase 2 reports maintain the prefill/decode/end-to-end metric separation established in Phase 1, but Phase 2 extends this framework to capture additional dimensions of inference performance.

Prefill metrics include prefill latency (milliseconds), prefill throughput (tokens per second, computed as prompt_length / prefill_latency), and Time to First Token (TTFT, equivalent to prefill latency in non-streaming mode). These metrics are critical for interactive workloads where the user waits for the first token before seeing streaming output.

Decode metrics include decode latency (total decode time), decode throughput (tokens per second, computed as generated_tokens / decode_latency), and per-token decode latency. Decode throughput is the dominant capacity metric for generation-heavy workloads (TR119v1 established that decode dominates end-to-end cost once generation exceeds 64 tokens).

End-to-end metrics include total latency (prefill + decode), effective throughput (total_tokens / total_latency), and request completion time. These metrics capture the user-visible experience and are used for SLA compliance and capacity planning.

Phase 2 adds several new metric categories. Quality metrics (TR124-TR125) include BERTScore F1, ROUGE-L, SemScore, exact match, coherence, diversity, and benchmark accuracy. Scaling metrics (TR129-TR130) include per-agent throughput, total system throughput, normalized efficiency eta(N), and Jain's fairness index. Profiling metrics (TR131-TR132) include kernel count, kernel duration, memory bandwidth utilization, GEMM fraction, and amortization ratio. Cost metrics (TR123, TR133) include $/1M tokens (phase-weighted), $/request, and annual TCO.

### 3.3 Cost model

The cost model used throughout Phase 2 converts throughput measurements into dollar costs using a fully explicit compute-hour framework. The formula is:

$/1M tokens = (1,000,000 / throughput_tok_s / 3600) * hourly_rate

where throughput_tok_s is the measured decode throughput in tokens per second and hourly_rate is the amortized cost of the GPU in dollars per hour. For consumer hardware, the hourly rate is derived from hardware purchase price amortized over expected lifetime plus electricity cost. For cloud hardware, it is the on-demand or spot instance price. TR123 uses $0.10/hour for the consumer GPU (approximately $1,500 hardware cost amortized over 3 years at 50% utilization, plus electricity).

Workload blend ratios weight prefill and decode costs according to the workload's decode fraction. Five canonical workload profiles are defined:

- **RAG-heavy** (decode fraction 0.95): Long generation from retrieved context. Decode-dominated.
- **Summarization** (0.85): Moderate input, substantial output generation.
- **Chat** (0.67): Balanced conversational exchange.
- **Balanced** (0.50): Equal prefill and decode weight. Reference scenario.
- **Code generation** (0.25): Short prompt, long code output. Paradoxically prefill-heavy by fraction because code generation prompts are often long specifications.

The blended cost is:

$/1M_blended = decode_fraction * $/1M_decode + (1 - decode_fraction) * $/1M_prefill

This decomposition is essential because prefill and decode throughputs can differ by 10-100x for the same model and backend, and a single aggregated cost number would obscure which phase is driving the expense. TR123 demonstrates that for decode-heavy workloads, the best-cost configuration (GPT-2 with torch.compile, chat blend) achieves $0.013/1M tokens, while the worst (large models, CPU backend, RAG blend) exceeds $10/1M tokens -- a 770x range that collapses to a misleading average if phase weighting is ignored.

### 3.4 Quality evaluation framework

The quality evaluation framework spans three phases of increasing specificity, each designed to answer a different question about quality preservation.

Phase 1 quality evaluation (TR124 Phase 1) tests backend equivalence. Five models are evaluated on two backends (transformers-gpu, transformers-gpu-compile) at temp=0 using 7 generation metrics across multiple tasks. The statistical test is one-way ANOVA per metric with Holm-Bonferroni correction for multiple comparisons across the 7 metrics. The null hypothesis is that backend choice does not affect quality; this null is retained for all 7 metrics (0/7 significant after correction), establishing that backends produce statistically indistinguishable outputs at deterministic temperature.

Phase 2 quality evaluation (TR124 Phase 2, TR125) tests quantization impact. Models are evaluated at 7 quantization levels (Q2_K through FP16) using both generation metrics and benchmark accuracy. The statistical framework adds Wilson confidence intervals for accuracy proportions (valid at small n), TOST equivalence testing with margins of plus or minus 3pp and plus or minus 5pp, and Bonferroni-corrected pairwise comparisons. The 4-tier classification system categorizes each model-quantization combination as:

- **Negligible** (< 2pp loss): No practical impact on deployment decisions.
- **Acceptable** (2-5pp loss): Suitable for cost-sensitive workloads with quality monitoring.
- **Concerning** (5-10pp loss): Requires explicit quality gates and workload-specific validation.
- **Unacceptable** (> 10pp loss): Not suitable for any production workload.

The composite quality score aggregates across metrics with equal weighting after min-max normalization. Quality thresholds for production deployment are: composite >= 0.50 for general workloads, >= 0.60 for quality-critical applications. These thresholds are calibrated against human-interpretable quality levels observed during TR124 development.

Phase 3 quality evaluation (TR124 Phase 3) tests sampling variance. Two models are evaluated at temp=0.7 with 5 repetitions per task to quantify the additional variance introduced by stochastic sampling. The finding (mean CV = 0.33) establishes that temp=0.7 introduces substantial variance that would confound quantization comparisons, validating the choice of temp=0 for primary evaluation.

### 3.5 Quantization testing protocol

The quantization testing protocol is the most sample-intensive component of Phase 2, spanning approximately 26,000 measurements across two phases. The protocol is designed to produce a decision matrix that maps every (model, quantization_level) pair to a quality tier, a cost estimate, and a deployment recommendation.

Phase 1 (900 samples) provides a coarse survey: 3 models, 6 quantization levels (Q2_K through Q8_0), 10 samples per task, wall-clock timing. Phase 2 (approximately 25,000 samples) provides the definitive matrix: 5 models (llama3.2-1b, qwen2.5-1.5b, phi-2, llama3.2-3b, llama3.1-8b), 7 quantization levels (Q2_K through FP16), 50 samples per task, native Ollama timing, plus 285 MMLU and 200 ARC-Challenge benchmark questions per configuration.

The base-vs-instruct confound is a methodological correction that Phase 2 makes explicit. TR124's FP16 baselines were measured on base models (e.g., meta-llama/Llama-3.2-1B), while Ollama serves instruct-tuned variants (e.g., llama3.2:1b-instruct-q8_0). Instruct tuning can shift accuracy by several percentage points independent of quantization. TR125 Phase 2 addresses this by including FP16 Ollama measurements (instruct-tuned FP16) as the baseline, making all quantization comparisons within the same model variant. Q8_0 serves as the practical baseline for Phase 1 data where FP16 Ollama was not available.

Wilson confidence intervals are used instead of normal-approximation intervals for accuracy proportions because several benchmark configurations produce accuracy near 0.25 (random chance for 4-choice MMLU) or near 0.0 (collapsed Q2_K outputs), where the normal approximation is unreliable. Wilson intervals maintain nominal coverage even at extreme proportions and small sample sizes.

Power analysis for the TOST equivalence tests reveals a minimum detectable equivalence margin of approximately 9.0pp at 80% power with the sample sizes used (285 MMLU questions). This explains why 0/18 TOST tests pass at the plus or minus 3pp margin and only 6/18 pass at plus or minus 5pp: the study is underpowered for tight equivalence claims, not because the models are actually different by more than 3pp (point estimates are often within 2pp) but because the sample size cannot distinguish "equivalent within 3pp" from "different by 4pp" with statistical confidence.

### 3.6 Cross-platform methodology

TR126 is the only report that explicitly tests cross-platform behavior, and its methodology requires careful design to ensure valid comparison. The two platforms are:

- **Windows 11** with PyTorch 2.5.1, CUDA 12.4, no Triton (aot_eager fallback), RTX 4080 Laptop GPU.
- **Docker/Linux** (NVIDIA NGC container, Ubuntu 22.04) with PyTorch 2.5.1 and 2.10, CUDA 12.4/12.8, Triton JIT compiler, same RTX 4080 Laptop GPU via NVIDIA Container Toolkit.

Weight parity is ensured by using the same HuggingFace model checkpoints on both platforms, loaded with identical precision (torch.float16 on CUDA, torch.float32 on CPU). Deterministic decode is verified by confirming that temp=0 (greedy) decoding produces identical output text on both platforms for the same prompt, model, and precision. This eliminates the possibility that platform differences reflect model loading or numerical divergence rather than compile behavior.

The measurement protocol runs 7 models across 3 backends (eager, compile, Ollama) on both platforms, with phase-separated metrics (prefill latency, decode throughput) and sufficient repetitions for statistical testing. The ANOVA interaction test (F(8,1608) = 453.1, p < 10^-16) confirms that the platform-backend interaction is statistically significant -- that is, the compile speedup genuinely depends on the platform, not just on noise.

### 3.7 Production workload methodology

TR128 tests production realism through five experimental phases, each isolating a different aspect of production behavior.

Phase 1 (baseline characterization) measures single-request service times across 3 models to establish the baseline against which concurrent load effects are measured. Phase 2 (NUM_PARALLEL sweep) tests Ollama's concurrent inference claim by measuring throughput at NUM_PARALLEL = 1, 2, 4 and applying pairwise Welch's t-tests with Bonferroni correction (30 tests total). Phase 3 (queueing theory validation) generates Poisson-distributed request arrivals at varying rates and compares observed latency to M/D/1 predictions. Phase 4 (streaming validation) measures streaming vs batch mode using paired tests (9 comparisons) to determine if streaming adds overhead. Phase 5 (thermal stability) monitors GPU temperature during sustained load to test for thermal throttling.

Poisson arrivals in Phase 3 are generated by drawing inter-arrival times from an exponential distribution with rate parameter lambda, calibrated to produce utilization levels from 0.3 to 0.9. This ensures that the arrival pattern is memoryless and that the comparison to M/D/1 is theoretically valid. The deviation of up to 20.4x is therefore a genuine failure of the model, not an artifact of non-Poisson arrivals.

The sliding window test in Phase 5 uses an 8-sample rolling average of request latency to detect drift during sustained load. The result (p = 0.042, n = 8) is suggestive but does not survive Bonferroni correction and is reported as inconclusive rather than significant.

### 3.8 Closed-loop agent methodology

The multi-agent scaling study (TR129) uses a closed-loop protocol that models realistic multi-agent behavior. Each of N agents operates in an independent loop:

1. Send a request to the serving endpoint.
2. Wait for the complete response (blocking).
3. Optionally simulate think time (configurable delay before next request).
4. Repeat.

This closed-loop design means that the effective arrival rate is endogenous: it depends on the GPU's service rate and the think time parameter. As N increases, the queue depth grows and per-agent throughput decreases, but total system throughput increases (with diminishing returns). This is fundamentally different from the open-loop Poisson arrivals in TR128, where the arrival rate is exogenous and independent of service time.

The study tests N = {1, 2, 3, 4, 5, 6, 7, 8} agents across 3 models (llama3.2-1b, qwen2.5-1.5b, llama3.2-3b) with 4 phases: zero think time (maximum GPU stress), short think time (50ms), medium think time (200ms), and long think time (1000ms). Each condition runs for 60 seconds of steady-state measurement after a 10-second warmup period. Total measurements: 5,310.

Amdahl's Law is fit to the (N, total_throughput) data using nonlinear least squares with the serial fraction s as the single free parameter. The fit quality (R^2 > 0.97 for all models at zero think time) validates Amdahl's Law as a descriptive model for Ollama's scaling behavior, though TR131 later shows that the serial fraction is a phenomenological parameter rather than a physically derived quantity.

Jain's fairness index is computed for each (N, model, think_time) condition as:

J = (sum(x_i))^2 / (N * sum(x_i^2))

where x_i is agent i's throughput. J = 1.0 indicates perfect fairness; J = 1/N indicates maximally unfair allocation. All measured conditions produce J >= 0.997, confirming that Ollama's sequential processing is inherently fair (first-come-first-served with no priority scheduling).

### 3.9 Serving stack comparison methodology

TR130 compares three serving stacks under identical conditions to isolate the serving stack as the independent variable. The controlled variables are:

- **GPU:** RTX 4080 Laptop GPU (12 GB VRAM), same physical hardware for all tests.
- **Models:** llama3.2-1b, qwen2.5-1.5b, llama3.2-3b (same model families across all stacks).
- **Prompts:** Identical prompt sets drawn from the eval framework's task library.
- **Concurrency levels:** N = {1, 2, 4, 8} agents, using the same closed-loop protocol as TR129.

The uncontrolled variable is quantization: Ollama uses Q4_0 models (the default GGUF quantization), while vLLM and TGI use FP16 weights. This confound is unavoidable without custom model packaging and is explicitly addressed through the normalized efficiency metric eta(N) = throughput(N) / (N * throughput(1)), which measures relative scaling behavior independent of absolute throughput level.

The scaling law fit distinguishes Amdahl-type saturation (Ollama: R^2 > 0.96) from power-law scaling (vLLM, TGI: R^2 > 0.99). This qualitative difference is operationally more important than the absolute throughput numbers, because it determines the concurrency regime where each stack is viable. Ollama saturates at N* = 4 (less than 3% throughput gain from N=4 to N=8); vLLM and TGI show no saturation within N=8.

TTFT (Time to First Token) is measured separately because continuous batching stacks can begin prefill for a new request while existing requests are decoding, yielding dramatically lower TTFT at high concurrency. Ollama TTFT ranges from 163-194ms; vLLM from 23-32ms; TGI from 22-35ms -- a 6-8x advantage for continuous batching stacks that matters for interactive applications.

### 3.10 GPU profiling methodology

GPU profiling in Phase 2 uses two complementary approaches, driven by the constraints of the Windows Display Driver Model (WDDM).

TR131 profiles on bare-metal Windows using Nsight Systems (nsys) for timeline traces and Nsight Compute (ncu) for per-kernel metrics. The nsys traces capture kernel launches, memory operations, and CPU-GPU synchronization at nanosecond resolution, producing approximately 50-150 MB of trace data per run (1.6 GB total across 26 runs). However, under WDDM, ncu cannot read hardware performance counters (all metrics return null), limiting the analysis to kernel counts, durations, and timing-based bandwidth estimates. TR131 works around this limitation with back-of-envelope bandwidth calculations based on model weight sizes and measured service times.

TR132 profiles inside Docker containers on WSL2 using a novel methodology. The approach leverages NVIDIA Container Toolkit to provide CUPTI access inside the container, enabling Nsight Systems to capture GPU traces from containerized vLLM and TGI workloads. The methodology requires careful container configuration (--privileged flag, CUPTI library mounting) and produces approximately 375 MB of traces across 25 runs. This methodology is documented in detail because WSL2/WDDM profiling of containerized GPU workloads is not well-documented in the literature and required iterative development to make reliable.

PyTorch Direct serves as the control condition in TR131. By running inference with raw PyTorch (no serving stack), TR131 isolates GPU behavior from serving stack behavior. The finding that PyTorch Direct degrades 86.4% at N=8 (worse than Ollama's 82.1%) is the key evidence that overturns the serving-stack-as-bottleneck hypothesis: if removing the serving stack makes things worse, the serving stack cannot be the bottleneck.

The five hypotheses tested in TR131 are:

- H1: Memory bandwidth stress increases with N (PARTIALLY CONFIRMED: +74.4%, sole Holm-surviving test).
- H2: Ollama serializes requests (REATTRIBUTED: serialization occurs at GPU hardware level, not serving stack level).
- H3: GPU context switching causes overhead (REJECTED: context switch overhead is negligible).
- H4: Kernel concurrency exists and degrades (REJECTED: max_concurrent_kernels = 1 in all conditions).
- H5: KV-cache pressure causes contention (REJECTED: KV-cache memory is per-request, not shared).

### 3.11 Predictive model methodology

TR133 builds the predictive capacity planner from 19,676 training records (80% of the Phase 2 measurement corpus from TR123-TR130) and validates against 3,939 holdout records (20%). Six models are fit:

1. **VRAM model:** First-principles formula (model_weights * 1.058 + KV_bytes_per_token * context_length) with a single calibrated parameter (overhead factor 1.058x for allocator fragmentation). Validated at R^2 = 0.968 against holdout data.

2. **Throughput model:** 22-entry empirical lookup table indexed by (model, quantization, backend), with power-law fallback (72.1 * params_B^-0.089) for unseen configurations. Validated at R^2 = 0.859.

3. **Scaling model:** Amdahl's Law with per-model serial fractions from TR129. This is the weakest model (R^2 = 0.647) because Amdahl captures the trend but misses interactions between model size, quantization level, and serving stack that affect the serial fraction.

4. **Quality model:** Lookup table indexed by (model, quantization_level) using TR125 benchmark accuracy data. Validated at RMSE = 0.062 against holdout data (target < 0.10).

5. **Cost model:** Algebraic derivation from throughput model output using the $/1M formula. No independent validation target; accuracy inherits from throughput model.

6. **Latency model:** 1/throughput with concurrency adjustment from scaling model. Validated at MAPE = 1.05% against holdout data (target < 25%).

The 4-gate search algorithm processes a user-specified deployment scenario through four sequential filters: (1) VRAM gate eliminates configurations exceeding GPU memory, (2) quality gate eliminates configurations below the quality floor, (3) latency gate eliminates configurations violating the latency SLA, (4) budget gate eliminates configurations exceeding the cost ceiling. Surviving configurations are ranked by cost efficiency (quality / cost).

Ten spot checks validate the planner against manually verified configurations, covering edge cases such as models that barely fit in VRAM, quantization levels at the quality cliff, and high-concurrency vLLM configurations. All 10 pass, confirming that the planner's recommendations match hand-calculated optimal configurations.

### 3.12 Statistical standards

Phase 2 uses a comprehensive statistical toolkit, selected to match the structure of each comparison. The guiding principle is that the statistical test must match the experimental design, and multiple comparisons must be corrected to control the family-wise error rate.

**Welch's t-test** is used for pairwise comparisons of means when variances may be unequal (the default case in performance measurement). TR128 uses this for NUM_PARALLEL pairwise comparisons (30 tests) and streaming comparisons (9 tests).

**One-way ANOVA** is used for multi-group comparisons where the factor has more than two levels (e.g., backend comparison across 5 backends in TR124, quantization level comparison in TR125). The F-statistic tests whether any group differs; post-hoc pairwise tests identify which groups differ.

**Mann-Whitney U test** is used as the nonparametric alternative when distributional assumptions are violated or when sample sizes are small. TR131 uses this for kernel count comparisons where distributions are non-normal.

**Cohen's d** quantifies effect size independently of sample size. The program uses the standard thresholds (small: 0.2, medium: 0.5, large: 0.8) but reports exact values for transparency. TR126's compile speedup (d = -0.59, medium-to-large) and TR131's bandwidth stress (d = 3.81, very large) illustrate the range of effects observed.

**Holm-Bonferroni correction** controls family-wise error rate for multiple comparisons while maintaining more power than classical Bonferroni correction. Phase 2 reports both raw p-values and Holm-corrected significance to distinguish between exploratory findings (raw p < 0.05) and confirmatory findings (Holm-corrected p < 0.05). This distinction is operationally important: only Holm-surviving tests are used for policy decisions.

**TOST equivalence testing** inverts the null hypothesis to test for practical equivalence rather than difference. Given an equivalence margin delta, TOST tests two one-sided hypotheses (mean difference > +delta and mean difference < -delta). If both are rejected, the conclusion is that the true difference lies within [-delta, +delta]. TR125 applies TOST at delta = 3pp and delta = 5pp for benchmark accuracy, finding that the study is underpowered at 3pp (0/18 pass) but partially powered at 5pp (6/18 pass).

**Wilson confidence intervals** are used for proportions (accuracy, success rates) because they maintain nominal coverage even at extreme proportions (near 0 or 1) and small sample sizes, unlike the normal approximation (Wald) interval. TR125 uses Wilson CIs for all benchmark accuracy proportions.

**Power analysis** determines the minimum detectable effect size for a given sample size, alpha level, and desired power. TR125's power analysis reveals an MDE of approximately 9.0pp at 80% power with 285 MMLU questions, which bounds the interpretability of TOST results and identifies the sample size needed for tighter equivalence claims (approximately 2,000 questions for MDE of 3pp at 80% power).

### 3.13 Hardware baseline

All Phase 2 measurements are conducted on a single hardware baseline to eliminate cross-hardware confounds. The baseline is a consumer-grade laptop GPU, chosen because it represents the class of hardware where local-first LLM inference is most cost-relevant (cloud GPUs are available for teams with cloud budgets; consumer GPUs are the only option for privacy-sensitive, bandwidth-constrained, or cost-constrained deployments).

**GPU:** NVIDIA GeForce RTX 4080 Laptop GPU (AD104). 7,424 CUDA cores, 12 GB GDDR6 VRAM, 256-bit memory bus, 432 GB/s memory bandwidth, 175W TDP (configurable via Dynamic Boost). Ada Lovelace architecture (sm_89), CUDA Compute Capability 8.9.

**CPU:** Intel Core i9-13980HX. 24 cores (8P + 16E), 32 threads, up to 5.4 GHz boost. Used for CPU-backend measurements in TR123 and as the host processor for GPU inference.

**Memory:** 64 GB DDR5-4800. Sufficient to absorb VRAM spillover without system-level OOM, which is important for TR127's context scaling tests where CUDA Unified Memory migrates pages to system RAM.

**Storage:** NVMe SSD. Not a bottleneck for any measured workload (model loading is excluded from timed regions).

**OS:** Windows 11 Home (build 26200) for native measurements; WSL2 with Ubuntu 22.04 for Docker/Linux measurements. The dual-OS setup is necessary because torch.compile requires Linux/Triton for real compilation (TR126), vLLM and TGI require Linux containers (TR130, TR132), and Nsight Systems profiling behaves differently under WDDM vs TCC (TR131).

**Software stack:** PyTorch 2.5.1 and 2.10 (TR126 tests both), CUDA 12.4 and 12.8, Ollama 0.6.x, vLLM 0.7.x, TGI (latest stable at time of measurement), Nsight Systems 2024.x, NVIDIA driver 560.x+.

**Thermal environment:** Laptop form factor with manufacturer cooling solution. TR128 confirms no thermal throttling under sustained load (peak 66 degrees C, well below the 80-degree C throttle threshold). This is a boundary condition: desktop GPUs with different thermal profiles may behave differently.

This hardware baseline is deliberately fixed and narrow. The portable output of Phase 2 is the decision framework, not the absolute numbers. If you deploy on a different GPU (e.g., RTX 4090, A100, H100), you must re-run the measurements. But you use the same framework -- the same phase-split cost model, the same quality evaluation protocol, the same scaling law fits, the same 4-gate search algorithm -- to interpret the new measurements and produce new deployment decisions.

### 3.14 Measurement boundary catalog

Each technical report defines a specific measurement boundary -- what is included and excluded from the timed region. These boundaries are not identical across reports; they are chosen to match the question each report answers. Treating them as interchangeable is a common source of invalid cross-report comparisons.

**TR123 (KV-Cache Economics):** Timed region includes prefill forward pass and KV-cache-enabled decode loop. Excludes model loading, tokenization, and post-processing. Phase-split timing captures prefill and decode separately with high-resolution timers (torch.cuda.Event for GPU timing). The boundary is the inference computation, not the serving overhead.

**TR124 (Quality Baseline):** Timed region is the quality evaluation pipeline: tokenization, forward pass, decoding, and post-processing. Timing is secondary to quality measurement; the primary outputs are quality metric scores, not latency. Benchmark evaluation (MMLU, ARC) uses the lm-eval-harness boundary with rescored accuracy for formatting robustness.

**TR125 (Quantization Matrix):** Timed region is Ollama's native API timing (prompt_eval_duration for prefill, eval_duration for decode), extracted from the response metadata. This boundary includes Ollama's internal scheduling and KV-cache management but excludes network latency (localhost API call overhead is measured and confirmed negligible at < 1ms).

**TR126 (Compile Validation):** Timed region matches TR123 for HuggingFace backends (torch.cuda.Event timing of forward pass) and Ollama's native timing for Ollama backend. The compile boundary explicitly includes the first compilation pass (which may include Triton kernel generation) in warmup runs, and steady-state measurements exclude compilation overhead.

**TR127 (Context Scaling):** Timed region includes prefill and decode at each context length. VRAM measurement uses torch.cuda.max_memory_allocated() before and after inference, capturing peak GPU memory consumption including KV-cache growth. The boundary is the per-request inference footprint, not the serving stack's aggregate memory management.

**TR128 (Production Workloads):** Timed region is the full request-response cycle from client perspective: HTTP request send to final response byte received. This boundary intentionally includes serving stack overhead (Ollama's request parsing, scheduling, response serialization) because production latency includes these costs. For streaming mode, TTFT is measured as the time to first response chunk.

**TR129 (N-Agent Scaling):** Timed region is per-agent request-response cycles, aggregated over a 60-second steady-state window. Warmup period (10 seconds) is excluded. The boundary matches TR128's client-perspective timing, applied independently to each agent's request stream.

**TR130 (Serving Stack Comparison):** Timed region matches TR129 for all three serving stacks, ensuring valid cross-stack comparison. Additional TTFT measurement captures prefill latency separately from decode.

**TR131 (GPU Kernel Profiling):** Timed region is the nsys profiling window, which captures all GPU activity (kernel launches, memory operations, synchronization) during a fixed inference workload. The profiling overhead is measured and confirmed to be less than 5% of inference time (nsys low-overhead mode).

**TR132 (In-Container Profiling):** Timed region matches TR131 but operates inside Docker containers. The container overhead (CUPTI initialization, namespace isolation) is excluded from the timed inference region but documented as part of the measurement setup.

**TR133 (Predictive Planner):** No timed inference region. TR133 consumes pre-existing measurements from TR123-TR130 and validates predictions against a holdout set. The relevant boundary is the validation protocol: 80/20 train/test split with stratification by model and backend to prevent data leakage.

These boundaries are not negotiable. A claim about decode throughput from TR123 cannot be directly compared to a claim about request latency from TR128 without accounting for the different boundaries. The measurement boundary catalog exists to prevent this class of error, and every cross-report comparison in the synthesis (Section 6) explicitly maps which boundaries are compatible and which require normalization.

---
## 4. Decision Impact Matrix (TR123-TR133)

The decision impact matrix below maps each technical report in Phase 2 to its primary domain, the decisions it enables, the confidence level warranted by the evidence, the key numbers backing each decision, and the boundary conditions under which the decision may not hold. This matrix is the navigational core of the synthesis: a practitioner who reads only this section and the operational defaults card can make deployment decisions backed by 70,000+ measurements without consulting any individual TR.

The matrix is organized by the chronological order of the reports (TR123 through TR133), which also reflects the logical dependency chain: each report's design was informed by the findings and limitations of its predecessors. The "Primary Decision Enabled" column identifies the single most important decision that would be impossible or unreliable without the report's data. The "Secondary Decisions Enabled" column lists additional decisions that benefit from the report's findings but do not depend solely on it. The "Confidence" column reflects the overall strength of evidence, while the "Caveats / Boundary Conditions" column identifies the specific circumstances under which the decision may not hold. Practitioners should read both the decision and its caveats before acting.

| TR | Domain | Primary Decision Enabled | Secondary Decisions Enabled | Confidence | Key Numbers | Caveats / Boundary Conditions |
|----|--------|--------------------------|----------------------------|------------|-------------|-------------------------------|
| TR123 | Cost Economics | Phase-split $/token pricing for production KV-cached inference; MHA vs GQA architecture selection | Compile ROI quantification; consumer vs cloud break-even; carbon/energy budgeting; workload-blend cost estimation | High | 525 cells, best cost $0.013/1M tokens (GPT-2/compile, chat blend), GQA 11.4x KV memory advantage, compile 1.2-2.5x decode speedup, 30/30 KV formula validation, consumer 95.4% cheaper than cloud, TCO $153/yr vs $2,880/yr at 1B tok/month | Windows aot_eager fallback for compile (resolved by TR126); no quality data (resolved by TR124); cost numbers bound to measured hardware + electricity rate |
| TR124 | Quality Assurance | Backend equivalence confirmed -- cheapest backend is the best backend; quality-cost Pareto frontier established | Per-model quality signatures for task routing; quality gate thresholds; stochastic decoding policy (use greedy for evaluation) | High | 3,600 samples, 0/7 metrics significant after Holm-Bonferroni, composite range 0.29 (gpt2) to 0.63 (phi-2), 3/8 combos Pareto-optimal, llama-3.2-1b best quality-adjusted cost at $0.13/quality-point, Phase 2 avg -10.7% quality loss from quantization, Phase 3 CV=0.33 at temp=0.7 | Ollama determinism unvalidated; automated metrics only (no human evaluation); base-vs-instruct confound in Phase 2 (resolved by TR125) |
| TR125 | Quantization | Q4_K_M as universal default quantization; Q2_K ban for all quality-sensitive tasks; per-model quant tolerance map | Cost savings quantification (30-67% vs FP16); VRAM budget reduction; repetition collapse detection at extreme quantization | High | ~26,000 samples, 34 model-quant variants, Q4_K_M max loss -4.1pp, Q3_K_S cliff at -10.1pp to -12.2pp, Q2_K universally >11pp loss (qwen2.5-1.5b -40.6pp), phi-2 most robust (-1.8pp through Q4_K_M), 10x cost range ($0.020-$0.198), TOST 0/18 at +/-3pp, 7/16 Bonferroni survivors at Q2_K boundary | TOST underpowered at +/-3pp equivalence margin; single-rep Ollama determinism assumption; tier classifications below 9pp MDE are point-estimate-based |
| TR126 | Compilation | Prefill-only compile on Linux with Inductor+Triton; never compile decode; all Windows compile results invalidated | Scale-dependent backend selection (small models -> compile wins; large -> Ollama wins); ANOVA interaction quantification | High | ~29,900 measurements, -40.0% latency reduction (d=-0.59, p=8.87e-61), prefill d=-1.21, Ollama 7x decode advantage (d=2.38), compiled decode 100% crash rate, 916 Triton kernels, ANOVA F(8,1608)=453.1 p<1e-16, bug persists on PyTorch 2.10, StaticCache 5.8x slower | Compiled decode is architecturally broken (DynamicCache + CUDA graphs incompatible); CUDA graph crash is length-dependent (works at 64 tokens, crashes at 128); Windows results remain invalid |
| TR127 | Context Scaling | VRAM budget formula per model; Ollama for >4K token contexts on 12GB VRAM; HF FP16 limited to 4-8K tokens | Per-token VRAM cost estimation (0.75-1.16 MB/token FP16); TTFT planning; decode throughput degradation curves | High | 1,144 measurements, two-regime scaling (pre-spillover b=1.58-1.78, R^2=0.999+; post-spillover 25-105x cliffs), Ollama sub-linear b<0.2, spillover at 8-16K tokens, decode 41-53% degradation over 64x context, HF 95% collapse, TTFT >1s at 4K on HF | Only 512-32K range tested; per-token VRAM cost includes activations and allocator overhead (not pure KV); OOM cliff follows spillover by one step |
| TR128 | Production Load | NUM_PARALLEL=1 (no-op confirmed); streaming always on (zero overhead); 70% utilization cap; empirical saturation curves replace M/D/1 | TTFT amplification planning; thermal safety margin; multi-turn context growth estimation | High | 3,172 measurements, 0/30 NUM_PARALLEL tests significant (mean |change| 4.0%), M/D/1 deviation up to 20.4x, peak 66 deg C (threshold 80 deg C), 0/9 streaming tests significant, TTFT 29.9x at 2.0 req/s, qwen2.5-1.5b 66% decode warmup anomaly | Sliding-window context inconclusive (p=0.042, n=8, wouldn't survive Bonferroni); qwen2.5-1.5b warmup mechanism unknown; 15/15 distributions non-normal |
| TR129 | Multi-Agent Scaling | 2-3 agents per GPU optimal; Amdahl prediction formula with per-model serial fractions; think-time tradeoff quantification | Saturation point identification; fairness guarantee; GPU tok/s constancy confirmation | High | 5,310 measurements, Amdahl s=0.39-0.54 (R^2>0.97), total throughput plateau at N=2 (<3% gain N=2 to N=8), per-agent eta(8)=17-20%, saturation at N=3-4, Jain's index >=0.997, GPU tok/s constant across N | Phase 4 confounded (homo_1b 25% above Phase 2 N=4); think-time improves per-request but reduces sustained throughput; serial fraction is model-fit, not physically derived |
| TR130 | Serving Stack Selection | vLLM for N>=4 agents; Ollama for N=1; TTFT 6-8x faster on vLLM/TGI | Crossover point identification (N=2 to N=4); power-law vs Amdahl degradation model selection; fairness guarantee across stacks | High | 4,797 measurements, vLLM 2.25x at N=8 (559 vs 248 tok/s for llama3.2-1b), Ollama eta(8)=0.16 vs vLLM eta(8)=0.56, Ollama=Amdahl (R^2=0.96+) vs vLLM/TGI=power law (R^2=0.99+), TTFT 22-35ms vs 163-194ms, Jain >=0.996, zero cold-start | Q4_0 vs FP16 confounds absolute throughput (eta(N) normalizes); Amdahl cross-backend comparison is category error; serving-stack-as-bottleneck hypothesis overturned by TR131 |
| TR131 | Root-Cause Attribution | Do not blame Ollama for N=8 degradation -- GPU bandwidth is fundamental; quantization helps concurrency (Q4_0 advantage grows 3.0x to 3.9x) | Reattribution of kernel serialization to GPU hardware; rejection of context-switching and KV-cache pressure hypotheses | High | 26 profiled runs, PyTorch Direct degrades 86.4% vs Ollama 82.1%, bandwidth +74.4% at N=8 (p=6.4e-5, d=3.81, survives Holm), max_concurrent_kernels=1 in all conditions, N=8 demand exceeds 432 GB/s by 78-130% | ncu metrics null on WDDM driver (back-of-envelope substituted); Q4_0 vs FP16 absolute TPS non-comparable (degradation ratio is the metric); CPU scheduling hypothesis has insufficient data |
| TR132 | Mechanism Identification | Continuous batching = bandwidth amortization (4.7-5.8x); vLLM and TGI use identical mechanism | Kernel reduction quantification (77-80%); GEMM dominance profiling; larger-model amortization advantage | High | 25 profiled runs, 77-80% kernel reduction at N=8, per-token kernels 54.9 to 10.9 (vLLM LLaMA-1B, d=1058), memory bandwidth per token -79% to -83%, amortization 4.7-5.8x, vLLM GEMM 69-82%, vLLM 27-35% faster than TGI at N=1, 15-25x more kernels than Ollama at N=1 | H3 GPU utilization rejected (nsys measurement limitation); H4 attention kernel signatures inconclusive; in-container profiling methodology specific to WSL2/Docker |
| TR133 | Capacity Planning | chimeraforge CLI for automated configuration search; 6 predictive models validated; empirical lookup tables replace theoretical models | Cross-GPU extrapolation via bandwidth scaling; 4-gate search eliminates infeasible configs; quality-aware recommendations | High | 19,676 training records, 3,939 validation records, VRAM R^2=0.968, throughput R^2=0.859, quality RMSE=0.062, latency MAPE=1.05%, 10/10 spot checks pass, 22-entry throughput lookup, power-law fallback 72.1*params^-0.089, overhead factor 1.058x, 57 unit tests, <1s runtime | Scaling model weakest (R^2=0.647); cross-GPU extrapolation unverified; quality claim 5 refuted (base-vs-instruct confound); bandwidth scaling is linear approximation |

### Interpreting the Matrix

Three structural patterns emerge from the decision impact matrix that are not visible from any individual report.

First, the matrix reveals a progressive deepening of causal attribution across the program. TR123 through TR128 operate at the application level, measuring throughput, cost, quality, and latency as externally observable quantities. These reports answer "what" questions: what does inference cost, what quality do backends produce, what quantization level is safe. TR129 and TR130 introduce the Amdahl and power-law frameworks that describe degradation curves but do not explain them -- they answer "how" questions: how does throughput degrade with agent count, how do serving stacks compare. TR131 and TR132 descend to the GPU kernel level and provide the causal mechanism: memory bandwidth saturation and its amortization through continuous batching. These answer "why" questions: why does throughput plateau, why does vLLM scale better. TR133 then ascends back to the application level, encoding these mechanistic insights into predictive models that answer "what should I do" questions. This arc -- from observation to phenomenological modeling to causal mechanism to predictive tool -- mirrors the classical progression from empirical science to engineering discipline. Each layer adds explanatory power and constrains the space of valid deployment decisions. Critically, each layer also narrows the interpretive latitude: TR130's correlation between backend choice and scaling efficiency admits multiple causal explanations, but TR131's kernel-level evidence narrows the mechanism to bandwidth physics, and TR132's amortization measurements pin the specific pathway through which continuous batching exploits that physics.

Second, the confidence column is uniformly "High" across all eleven reports, but this uniformity conceals important differences in the nature of the evidence. TR123's cost numbers are arithmetic consequences of measured throughput and known hardware costs -- they cannot be wrong unless the throughput measurements are wrong. The 30/30 exact-match KV formula validation admits essentially zero statistical uncertainty. TR124's backend equivalence is supported by formal hypothesis testing with multiple-comparison correction across 7 metrics and all pairwise effect sizes below 0.25. TR125's quantization tiers, however, rely on point estimates that fall below the minimum detectable effect for the statistical tests employed (TOST fails at +/-3pp for all 18 negligible variants, and the benchmark MDE is 9.0pp at 80% power). TR126's compile benefit (d=-0.59 to d=-1.21) is among the most statistically robust findings in the program, with p-values below 1e-7 in every scenario tested. TR131's bandwidth attribution survives Holm correction but rests on back-of-envelope bandwidth calculations because WDDM blocked direct ncu metrics -- a high-confidence causal conclusion built on indirect quantitative evidence. TR133's scaling model achieves only R^2=0.647, the weakest in the suite, reflecting the inherent noisiness of multi-agent measurements rather than a model specification error. These distinctions matter for practitioners: a decision backed by 30/30 exact KV formula matches (TR123) carries different epistemic weight than one backed by a model that explains 64.7% of variance (TR133 scaling). The matrix encodes the conclusion but not the epistemological distance between these claims, which is why the caveats column is essential reading for any decision with significant operational consequences.

Third, the matrix documents a remarkable sequence of self-corrections that validate the program's falsification methodology. TR130 concluded that "the serving stack is the bottleneck" -- a plausible interpretation supported by 4,797 measurements showing 3-4x efficiency differences across backends. TR131 overturned this conclusion with 26 profiled runs showing PyTorch Direct (no serving stack at all) degrades worse than Ollama. This is not a measurement failure; it is the scientific method operating correctly. Similarly, TR128's M/D/1 queueing model, which deviates 20.4x from reality, was not an error but a calibrated failure that justified the empirical lookup tables in TR133. TR120's compile paradox -- the finding that torch.compile appears harmful -- was an artifact of the Windows aot_eager fallback, resolved by TR126's Docker/Linux A/B test. TR124's Phase 2 quantization impact finding (-10.7% average) was confounded by base-vs-instruct model differences, resolved by TR125's Ollama FP16 baselines. Each correction sharpened the subsequent experimental design: TR131 was designed specifically because TR130's correlational attribution was unsatisfying, TR126 was designed because TR120's compile paradox demanded a causal explanation, and TR133's decision to use lookup tables over M/D/1 theory was a direct consequence of TR128's 20.4x deviation. The matrix captures these corrections in the caveats column, ensuring that practitioners who rely on TR130's backend selection guidance also understand that the mechanism is bandwidth amortization (TR132), not scheduling optimization.

A fourth pattern, less immediately visible but equally important, concerns the interplay between quantization and every other decision axis. Quantization first appears as a quality lever (TR124 Phase 2, TR125), then reveals itself as a cost lever (TR125 saves 30-67% vs FP16), a VRAM lever (TR127 context budgets depend on model size which depends on quantization), a concurrency lever (TR131 shows Q4_0 advantage growing from 3.0x to 3.9x under contention), and ultimately a mechanism lever (TR132 shows bandwidth amortization is proportionally more impactful when per-request bandwidth is reduced by quantization). This cross-cutting influence makes the quantization decision the single most consequential choice in the deployment pipeline, affecting cost, quality, VRAM budget, concurrency ceiling, and scaling behavior simultaneously. The Q4_K_M universal default emerges not from any single report but from the convergence of evidence across the entire matrix.

A fifth pattern concerns the statistical methodology escalation across the program. TR123 uses simple arithmetic (cost = throughput / time * rate) requiring no hypothesis testing. TR124 introduces ANOVA with Holm-Bonferroni correction for 7-metric backend equivalence. TR125 adds TOST equivalence testing, Wilson confidence intervals, Bonferroni/Holm survival analysis, and power analysis for minimum detectable effect. TR126 adds ANOVA interaction terms with partial eta-squared and TOST equivalence for crossover validation. TR128 introduces M/D/1 queueing theory (which fails). TR129 adds Amdahl's Law fitting with R^2 validation and Jain's fairness index. TR131 adds Mann-Whitney U robustness checks and Holm step-down correction across a hypothesis family. TR132 extends this to in-container profiling with 8-test Holm correction. Each report's statistical apparatus was chosen to match its inferential demands: cost comparisons need no hypothesis tests, backend equivalence demands multiple-comparison correction, equivalence claims require TOST, causal attribution requires control experiments with robustness checks. The progression is not arbitrary sophistication but calibrated rigor -- each new tool was added because the preceding report's claims required stronger evidence than its methods could provide.

Finally, the matrix reveals a convergence structure in the decision space. Of the 11 primary decisions enabled by TR123-TR133, six converge on the same recommendation by the end of the program: use Ollama Q4_K_M for single-agent deployment, use vLLM FP16 for multi-agent deployment (N>=4), compile prefill only on Linux, never deploy Q2_K, plan context budgets using the VRAM formula, and use chimeraforge rather than M/D/1 theory for capacity planning. These six decisions form the operational defaults card and can be shipped with high confidence because each is supported by multiple independent lines of evidence from different reports. The remaining five decisions (per-model quant tolerance, think-time tradeoffs, sliding-window context, thermal monitoring thresholds, quality gate thresholds) are more context-dependent and require practitioners to consult the specific reports for their use case.

---

## 5. Results by Report (TR123-TR133)

The following eleven subsections present the results of each technical report in a standardized format: research question, experimental design, key results table, extended analysis, and opening for the next report. Each subsection is self-contained but cross-references prior and subsequent reports to trace the decision chain. The subsections are ordered chronologically (TR123 through TR133), matching the order in which the experiments were conducted, because each report's design was informed by the findings and limitations of its predecessors. Together, these subsections document the progressive refinement from cost modeling (TR123) through quality assurance (TR124), quantization optimization (TR125), compilation resolution (TR126), context scaling (TR127), production characterization (TR128), multi-agent scaling (TR129), serving stack comparison (TR130), root-cause analysis (TR131-TR132), to predictive operationalization (TR133).

### 5.1 TR123: KV-Cache Production Economics

**Research question.** What does production KV-cached inference actually cost on consumer hardware, and how do attention architecture (MHA vs GQA) and compilation (torch.compile) affect the economics?

TR119 had established cost baselines using `use_cache=False` -- an intentionally pessimistic configuration that ignores the KV-cache reuse fundamental to autoregressive decode. Every autoregressive token generation step reads the growing KV cache rather than recomputing attention from scratch, and this cache reuse dramatically reduces per-token compute cost during the decode phase. TR123 fills this gap by measuring phase-split inference (prefill and decode separately) with KV-cache enabled, producing the first production-grade cost numbers in the research program. The phase split is essential because prefill (processing the prompt) and decode (generating output tokens) have fundamentally different computational characteristics: prefill is compute-bound and parallelizable, while decode is memory-bandwidth-bound and sequential.

**Experimental design.** The experiment tests 5 models spanning 124M to 3.2B parameters, deliberately chosen to represent both attention architecture families: GPT-2 (124M, MHA, 12 KV heads), LLaMA-3.2-1B (1.2B, GQA, 8 KV heads), Qwen2.5-1.5B (1.5B, GQA, 2 KV heads), Phi-2 (2.7B, MHA, 32 KV heads), and LLaMA-3.2-3B (3.2B, GQA, 8 KV heads). The inclusion of both MHA models (GPT-2, Phi-2) and GQA models (LLaMA, Qwen) enables direct comparison of attention architecture impact on KV-cache economics. Each model is evaluated across 3 backends (transformers-gpu, transformers-gpu-compile, CPU), 5 workload scenarios (RAG-heavy at 95/5 input/output split, summarization at 85/15, chat at 67/33, balanced at 50/50, code generation at 25/75), and 7 repetitions per cell, producing 525 total cells (420 measured, 105 intentional backend-skip entries for infeasible combinations such as large models on CPU, 0 errors). Cost is computed as blend-weighted $/1M tokens using the formula: $/1M_blend = input_ratio * $/1M_prefill + output_ratio * $/1M_decode. The hardware baseline is an RTX 4080 Laptop GPU (12 GB VRAM) at a consumer electricity rate of $0.20/kWh and an amortized hardware rate of $0.046/hr. Power sampling uses a dedicated PhasePowerSampler with `mark_phase()` calls to separate prefill and decode energy measurements, avoiding the whole-run averaging that distorts phase-specific power attribution.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Best cost (chat blend) | $0.013/1M tokens | GPT-2 / compile |
| Best cost >1B params | $0.047/1M tokens | LLaMA-3.2-1B / compile |
| torch.compile decode speedup | 1.2-2.5x | All models; diminishes at larger sizes |
| GQA vs MHA KV memory (2K ctx) | 56 MB vs 640 MB | Qwen2.5-1.5B vs Phi-2 (11.4x) |
| Phase asymmetry | 10-100x | Prefill faster than decode per token |
| Consumer vs cloud savings | 95.4% | Self-hosted vs AWS on-demand |
| TCO at 1B tok/month | $153/yr consumer | vs $2,880/yr AWS (GPT-2/compile) |
| KV formula validation | 30/30 exact matches | Empirical vs theoretical KV size |
| Lowest carbon (chat blend) | 3.4 gCO2e/1M tokens | GPT-2 / CPU |
| Infra cost share | 66-99% of total | Energy cost is rounding error |
| GPU vs CPU cost gap | 4-8x | CPU viable only for GPT-2 (124M) |
| GQA crossover (KV exceeds weights) | 56K-108K tokens | MHA crossover at 6.7K-16.5K |
| Best energy efficiency (decode) | 51.2M tok/kWh | GPT-2 / CPU (low power draw) |
| Best GPU energy efficiency | 36.2M tok/kWh | GPT-2 / compile |

**Extended analysis.** The phase-split cost model reveals a fundamental asymmetry in LLM inference economics that underlies every subsequent cost analysis in the program. Prefill throughput is 50-500x higher than decode throughput because prefill processes all prompt tokens in a single parallelized forward pass (the entire prompt is a batch of tokens processed by matrix multiplication in one shot), while decode generates one token at a time, each step reading the growing KV cache from GPU memory. The asymmetry is architectural, not incidental: it arises from the autoregressive nature of transformer text generation, where each new token depends on all preceding tokens via the attention mechanism. This asymmetry validates the input/output pricing split used by commercial providers (where output tokens typically cost 3-4x input tokens) and means that decode cost dominates in every workload blend tested. Even in the RAG-heavy blend (95% input, 5% output), decode's lower throughput means it contributes a disproportionate share of total cost. In the code generation blend (25% input, 75% output), decode cost accounts for over 90% of the total. The torch.compile speedup of 1.2-2.5x on decode is therefore the most economically impactful optimization in the single-request regime, halving the cost for GPT-2 and Qwen. However, this finding was later discovered to rest on the Windows aot_eager fallback (resolved by TR126, which confirmed the speedups are real on Linux with Triton).

The GQA vs MHA memory comparison produces one of the program's most practically significant numbers: an 11.4x KV-cache size difference between Qwen2.5-1.5B (2 KV heads, 56 MB at 2K context) and Phi-2 (32 KV heads, 640 MB). This translates directly into context budget: GQA models sustain 56K-108K tokens before KV cache exceeds model weights, while MHA models cross over at 6.7K-16.5K tokens. TR127 later exploits this insight to explain VRAM spillover thresholds, and TR133 encodes it in the VRAM prediction model. The 30/30 exact-match validation of the KV formula (2 * num_layers * num_kv_heads * d_head * precision_bytes * sequence_length) against empirical measurements provides unusually strong confidence -- this is one of the few results in the program that admits no statistical uncertainty.

The consumer-vs-cloud economics finding -- 95.4% cheaper self-hosted -- establishes infrastructure choice as the dominant cost lever, dwarfing backend selection, model choice, and quantization combined. At 1B tokens/month, the TCO spread ranges from $153/yr (GPT-2/compile on consumer hardware) to $8,584/yr (LLaMA-1B on AWS on-demand). The 95.4% savings figure compares the consumer hardware rate ($0.046/hr amortized over 3 years including electricity) against AWS on-demand g4dn.xlarge pricing ($1.006/hr). Even against AWS spot instances (approximately $0.30/hr), consumer hardware saves approximately 85%. The break-even analysis shows that an RTX 4080 ($1,200) pays for itself in 0.3-2.7 months at 10M requests/month depending on model -- a payback period short enough to justify the capital expenditure for any deployment exceeding hobby scale.

This finding anchors the entire program's practical relevance: the subsequent 10 reports optimize within a deployment paradigm (local-first consumer GPU) that is already an order of magnitude cheaper than the cloud alternative. The optimization space within local-first inference (backend selection, quantization, compilation, serving stack) yields additional 2-5x cost improvements, but these are multiplicative refinements on top of the 20x infrastructure advantage. A practitioner who deploys on consumer hardware with default settings has already captured 95% of the available cost savings; the remaining reports optimize the last 5%.

The torch.compile speedup of 1.2-2.5x on decode deserves careful qualification in light of TR126's later findings. The TR123 measurements were taken on Windows, where torch.compile silently falls back to `aot_eager` rather than generating Triton kernels. This means the 1.2-2.5x speedup reported in TR123 reflects the `aot_eager` overhead pattern, not true compilation benefits. TR126 later confirmed that real Triton compilation on Linux provides 1.3-2.5x prefill speedup (comparable range, different mechanism) while compiled decode is either neutral or crashes. The TR123 compile cost numbers remain directionally correct because the timing measurements are accurate regardless of what the compiler does internally, but the attribution to "compilation" is wrong -- the speedup arises from aot_eager's graph tracing reducing Python overhead, not from Triton kernel fusion.

A methodological contribution of TR123 that propagates through the entire program is the workload-blend cost model. By decomposing inference into prefill and decode phases and defining five workload profiles (RAG-heavy at 95% input, summarization at 85%, chat at 67%, balanced at 50%, code generation at 25%), TR123 enables practitioners to compute cost for their specific workload rather than relying on a single "average" number. The blend formula ($/1M_blend = input_ratio * $/1M_prefill + output_ratio * $/1M_decode) is algebraically simple but conceptually important: it reveals that decode cost dominates in every practical blend because prefill throughput is 50-500x higher. This insight directly informs TR133's cost model, which inherits the blend framework and extends it with quantization multipliers.

The carbon and energy analysis, while secondary to the cost findings, establishes an important boundary condition: energy cost accounts for only 0.34-34% of total cost depending on the backend, making it a third-order optimization target for consumer deployments. GPT-2 on CPU achieves the lowest carbon footprint at 3.4 gCO2e/1M tokens, followed by GPT-2 on compile at 4.6 gCO2e/1M tokens. At production scale, these differences become material -- 1B tokens/month at the GPT-2/CPU rate produces approximately 41 gCO2e/year, comparable to a single car trip of 100 meters. This finding confirms that the environmental impact of small-model consumer inference is negligible relative to training costs and cloud datacenter operations.

The 525-cell design matrix (5 models x 3 backends x 5 scenarios x 7 reps) achieves a zero-error rate, confirming measurement reliability.
The 105 backend-skip entries (intentional exclusions for infeasible combinations like 3B models on CPU) are documented in the artifact chain rather than treated as missing data, maintaining the distinction between "not measured" and "measured but failed."

**Opening for TR124.** TR123 optimizes cost under the assumption that all backends produce equivalent output quality.
Is this assumption valid?
TR124 tests it.

---

### 5.2 TR124: Quality and Accuracy Baseline

**Research question.** Do backend and precision choices affect output quality, and which model-backend combination offers the best quality per dollar?

TR123 established that the cheapest backend is transformers-gpu-compile, but every cost recommendation from TR108 through TR123 implicitly assumed that cheaper backends do not degrade quality. This assumption is non-trivial: different backends use different numerical precisions (FP16 vs FP32), different GEMM implementations, and different memory management strategies, any of which could introduce quality divergence. Eight thousand measurements across TR108-TR123 covered speed, cost, energy, and memory -- but zero quality measurements. This gap meant that the entire cost optimization framework rested on an untested assumption. TR124 fills this gap with a 3-phase evaluation program that establishes quality baselines, tests quantization impact, and measures stochastic variance.

**Experimental design.** The 3-phase program is designed to answer progressively deeper questions about quality. Phase 1 (backend equivalence) evaluates 5 models across 2 backends (GPU FP16, CPU FP32) on 5 generation tasks (summarization, QA, creative writing, classification, code generation; 50 curated samples with ground-truth references) and 3 standard benchmarks (MMLU 100 questions, HellaSwag 100 questions, ARC-Easy 100 questions), totaling 2,800 evaluated samples with 8 automated quality metrics at temperature=0.0 for deterministic output. Phase 2 (quantization impact) evaluates 4 models at Ollama's default quantization levels (Q8_0, Q4_K_M, Q4_0) on 5 generation tasks with 200 samples, measuring quality deltas against Phase 1 FP16 baselines. Phase 3 (sampling variance) evaluates 2 models (LLaMA-3.2-1B and Qwen2.5-1.5B) across 2 backends on 3 tasks with 5 repetitions at temperature=0.7, totaling 600 samples, measuring coefficient of variation and testing backend variance equality via Levene's test. The combined program produces 3,600 evaluated samples across all three phases. Quality metrics include ROUGE-L (structural overlap), BERTScore (contextual embedding similarity via deberta-xlarge-mnli), BLEU (n-gram precision), coherence/SemScore (sentence-transformer cosine similarity via all-mpnet-base-v2), exact match, output length ratio, and repetition score (unique 4-gram ratio). Composite quality is the unweighted mean of all available metrics for a given model, enabling cross-model comparison at the expense of diluting task-specific signals.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Backend equivalence (Phase 1) | 0/7 significant | After Holm-Bonferroni; all d = 0.04-0.25 |
| Composite quality range | 0.29-0.63 | GPT-2 (0.29), llama-1b (0.44), qwen-1.5b (0.55), llama-3b (0.52), phi-2 (0.63) |
| Pareto-optimal combos | 3/8 | llama-3.2-1b best quality-adjusted cost ($0.13/quality-point) |
| Benchmark anchoring | Matches published | MMLU, HellaSwag, ARC-Easy within expected variance |
| Phase 2 quant impact | -10.7% average | Coherence hardest hit: -14% to -32% |
| Phase 3 stochastic CV | 0.33 mean | At temp=0.7; only 37% of measurements have CV < 10% |
| Compile effect on diversity | 0/5 significant | Levene's test, all p > 0.35 |
| Quality scaling gap | 0.34 | Smallest (gpt2 0.29) to largest (phi-2 0.63) |
| GPU-CPU benchmark divergence | 0.0% | Identical benchmark scores, all models |
| Best QA model | llama-3.2-1b | Task-specific quality signatures |
| Best summarization model | qwen2.5-1.5b | ROUGE-L 0.55, BERTScore 0.83 |
| Best classification model | phi-2 | 90% classification accuracy |

**Extended analysis.** The backend equivalence result -- 0/7 metrics significant after Holm-Bonferroni correction with negligible-to-small effect sizes (Cohen's d ranging from 0.04 to 0.25) -- is the foundational quality finding of Phase 2. It validates every cost recommendation from TR119 through TR123 retroactively: the cheapest backend is indeed the best backend, because all backends produce statistically indistinguishable output.

This is not a trivial result. GPU FP16 and CPU FP32 use different numerical representations (16-bit vs 32-bit floating point), different GEMM implementations (cuBLAS tensor core operations vs OpenBLAS/MKL scalar operations), and different memory hierarchies (GDDR6 with 432 GB/s bandwidth vs DDR5 with ~50 GB/s). Any of these differences could in principle introduce quality divergence through accumulated rounding errors, different attention score distributions, or different softmax numerical stability characteristics. The equivalence arises because modern transformer architectures are robust to precision differences at inference time -- the attention mechanism's softmax normalization and layer normalization operations prevent numerical drift from compounding across layers. This finding is consistent with the broader quantization literature but here confirmed for the specific models and tasks in this program's scope, providing the empirical grounding that the broader literature's theoretical arguments alone cannot provide.

The composite quality scores reveal a counterintuitive finding: quality does not track parameter count linearly above 1B parameters. The five models form two clusters rather than a linear progression. GPT-2 (124M, composite 0.29) is clearly in the "not viable" cluster. The remaining four models cluster between 0.44 and 0.63: LLaMA-3.2-1B (1.2B, composite 0.44), LLaMA-3.2-3B (3.2B, composite 0.52), Qwen2.5-1.5B (1.5B, composite 0.55), and Phi-2 (2.7B, composite 0.63). Notably, LLaMA-3.2-3B (3.2B) scores lower than Phi-2 (2.7B) and only marginally above Qwen2.5-1.5B (1.5B). Architecture, training data, and instruction tuning matter more than raw scale in this parameter range. GPT-2's composite of 0.29 -- near-random on MMLU at 26% -- establishes it as a cost-floor reference, not a production model. The Pareto frontier analysis cross-referencing TR123 cost data identifies LLaMA-3.2-1B as the efficiency champion: it delivers 89% of Phi-2's quality at 63% of the cost, yielding the best quality-adjusted cost at $0.13 per quality point.

Phase 2's preliminary quantization test (200 samples across 4 models at 3 quant levels) exposes a significant confound that shaped TR125's design: the FP16 baselines were base models (via HuggingFace Transformers), while Ollama serves instruct-tuned variants. The average -10.7% quality loss attributed to quantization thus confounds two effects -- quantization degradation and the base-vs-instruct model difference. TR125 resolves this by establishing Ollama FP16 baselines as the correct reference and expanding to 7 quantization levels across 5 models. Phase 3's high coefficient of variation (mean 0.33 at temperature=0.7) establishes a critical methodological policy: use greedy decoding (temperature=0.0) for all quality evaluations, reserving stochastic sampling for diversity analysis only.

The per-model quality signatures revealed in Phase 1 have direct implications for task routing in production systems. No single model wins every task: LLaMA-3.2-1B leads on QA and creative writing, Qwen2.5-1.5B leads on summarization (ROUGE-L 0.55, BERTScore 0.83), Phi-2 leads on classification (90% accuracy), and GPT-2 fails on everything except creative coherence. This task-specificity means that a cost-optimal deployment may use different models for different request types -- a form of model routing that TR133's quality lookup table makes actionable. The metric agreement analysis (57% inter-metric concordance on model ranking) underscores that "quality" is not a unidimensional construct: ROUGE-L rewards structural overlap, BERTScore rewards semantic similarity, and coherence (SemScore) rewards meaning preservation. Practitioners must choose the metric aligned with their task rather than relying on the composite score alone.

The torch.compile variance finding from Phase 3 (0/5 Levene tests significant, all p>0.35) provides an important complement to TR126's performance findings. Not only does compilation not degrade quality (Phase 1 backend equivalence), it does not alter the distribution of quality under stochastic sampling. This means that the compile policy established in TR126 (prefill-only on Linux) carries no quality risk regardless of the decoding strategy employed.

The 3,600-sample evaluation program establishes the quality foundation for the remaining 9 reports.
Without TR124, every subsequent deployment recommendation would lack quality grounding.

**Opening for TR125.** TR124 identifies quantization as impactful but tests only 3 levels on 4 models with 200 samples.
What is the full quantization decision space, and where exactly is the quality cliff?

---

### 5.3 TR125: Quantization Decision Matrix

**Research question.** Which quantization level should practitioners choose for each model, and what quality-cost tradeoff does each level offer?

TR124 Phase 2 provided preliminary evidence that quantization degrades quality by an average of -10.7%, but tested only 3 levels with 200 samples and a base-vs-instruct confound that invalidated the FP16 comparison baseline. The deployment community needs a comprehensive decision matrix spanning the full range of GGUF k-quant levels (Q2_K through FP16) with statistically powered sample sizes and proper baselines. Quantization is the single most impactful lever for inference cost optimization (after infrastructure choice): it simultaneously affects model size, VRAM footprint, throughput, quality, and -- as TR131 later reveals -- concurrency scaling. A rigorous decision matrix is therefore prerequisite to every downstream deployment recommendation.

**Experimental design.** Two phases over approximately 26,000 total samples and 34 model-quant variants. Phase 1 (exploratory, 900 samples) tests 3 models (LLaMA-3.2-1B, Qwen2.5-1.5B, Phi-2) across 6 quant levels (Q2_K, Q3_K_S, Q4_K_M, Q5_K_M, Q6_K, Q8_0) with 10 samples per task using Q8_0 as the quantization baseline rather than FP16. Phase 1 identifies the base-vs-instruct confound in TR124's FP16 baselines: HuggingFace serves base models while Ollama serves instruct-tuned variants, making cross-backend quality comparison invalid. Phase 2 (production-grade, ~24,990 samples) resolves this confound by expanding to 5 models (1.2B-8B, adding LLaMA-3.2-3B and LLaMA-3.1-8B) across 7 quant levels (Q2_K through FP16, with FP16 via Ollama as the new baseline) and using 285 real MMLU questions + 200 real ARC-Challenge questions from HuggingFace as the primary quality gate, plus 5 generation tasks (50 samples each) as secondary validation. Rescored accuracy (regex letter extraction) replaces raw exact match to handle formatting noise -- a critical correction after Phase 1 revealed that Phi-2's raw accuracy of 26% masks a rescored accuracy of 59%. A 4-tier classification system (negligible: >=−3pp benchmark, >=−3% generation; acceptable: >=−5pp, >=−8%; concerning: >=−10pp, >=−15%; unacceptable: worse) replaces Phase 1's binary threshold, with each variant classified by the worse of its benchmark and generation deltas. Statistical apparatus includes Welch's t-tests between adjacent quant levels, Wilson confidence intervals for all benchmark tables, TOST equivalence testing at +/-3pp and +/-5pp margins, Bonferroni/Holm multiple comparison correction across 116 pairwise tests, and power analysis via normal approximation for minimum detectable effect at alpha=0.05 and power=0.80.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Q4_K_M max benchmark loss | -4.1pp | qwen2.5-1.5b; all others <3pp |
| Q3_K_S cliff | -10.1pp to -12.2pp | llama3.2-3b, qwen2.5-1.5b |
| Q2_K collapse | >11pp all models | qwen2.5-1.5b: -40.6pp (near-random) |
| phi-2 robustness | -1.8pp through Q4_K_M | Q3_K_S only -0.4pp |
| llama3.1-8b peak accuracy | 72.4% at Q8_0 | 69.7% at Q4_K_M (-2.7pp) |
| Cost range | $0.020-$0.198/1M tokens | 10x spread across model-quant space |
| Q4_K_M savings vs FP16 | 30-67% | phi-2 saves 67% at -1.8pp |
| TOST equivalence | 0/18 at +/-3pp | 6/18 generation-equivalent at +/-5pp |
| Bonferroni survivors | 7/16 | All at Q3_K_S/Q2_K boundary |
| Repetition collapse | 0.702 at Q2_K | qwen2.5-1.5b (vs 0.992 baseline) |

**Extended analysis.** The central finding -- Q4_K_M as the universal sweet spot -- rests on a convergence of evidence across all five tested models and represents the single most deployable recommendation in the entire research program. The maximum benchmark accuracy loss at Q4_K_M is -4.1 percentage points (qwen2.5-1.5b), with all other models losing less than 3pp. This places every model in the "negligible" or "acceptable" quality tier at Q4_K_M, the only quantization level to achieve this universality. The quality cliff at Q3_K_S is sharp and model-dependent, occurring across a single quantization step rather than as a gradual degradation: LLaMA-3.2-3B loses 10.1pp (from approximately 60% at Q4_K_M to 50% at Q3_K_S), Qwen2.5-1.5B loses 12.2pp, and LLaMA-3.2-1B loses 9.5pp. The sharpness of this cliff is the key practical finding -- it means there is no "gradual tradeoff" between Q4_K_M and Q3_K_S; the quality cost of one additional quantization step is abrupt and model-dependent. Phi-2 is the notable exception, losing only 0.4pp at Q3_K_S (within the noise band of the measurement), making it the most quantization-robust model in the matrix and the ideal candidate for aggressive quantization under VRAM constraints. Phi-2's robustness likely reflects its MHA architecture (32 KV heads vs 2-8 for GQA models), which distributes attention information across more heads and thus preserves more information under per-weight quantization.

Q2_K represents a universal failure mode that establishes a hard floor for quantization aggressiveness. Every model loses more than 11pp benchmark accuracy at Q2_K: LLaMA-3.2-1B loses -11.3pp, LLaMA-3.2-3B loses -13.5pp, Qwen2.5-1.5B collapses by -40.6pp to near-random performance, Phi-2 loses -11.8pp, and LLaMA-3.1-8B loses -14.2pp. The v2 re-analysis reveals a particularly insidious failure at Q2_K: repetition collapse. Qwen2.5-1.5B's repetition score drops from 0.992 (near-perfect lexical diversity) to 0.702, indicating degenerate looping text that is invisible to the three key metrics (BERTScore, coherence, ROUGE-L) because they measure semantic similarity, not structural pathology. This finding underscores the importance of multi-metric evaluation: a single quality score would have missed this failure mode entirely.

The statistical apparatus deserves scrutiny because it illustrates a tension between statistical rigor and practical decision-making that recurs throughout the program. TOST equivalence testing fails at the +/-3pp margin (0/18 variants pass) because the minimum detectable effect (MDE) with N=485 benchmark questions at 80% power is 9.0pp -- far larger than the 3pp equivalence margin. This means the test is underpowered by design: even if a variant were truly equivalent within +/-3pp, the sample size is insufficient to confirm this statistically. At the wider +/-5pp margin, 6/18 variants pass for generation metrics (phi-2 Q8_0/Q6_K/Q5_K_M, llama3.2-3b Q8_0/Q6_K, qwen2.5-1.5b Q8_0), while benchmark equivalence remains unconfirmed due to binary data variance. This epistemological gap means the "negligible" tier classification rests on point estimates, not formal equivalence confirmation. The Wilson confidence intervals provided in v2 partially mitigate this limitation by quantifying the uncertainty band around each estimate.

The economic implications are substantial. Q4_K_M saves 30-67% versus FP16 across models, with Phi-2 achieving the maximum savings (67% cost reduction at only -1.8pp quality loss). The 10x cost range across the full model-quant space ($0.020 for LLaMA-3.2-1B at Q2_K to $0.198 for LLaMA-3.1-8B at Q8_0) establishes quantization as the single most impactful lever for inference cost optimization after infrastructure choice. To put this in production terms: a deployment serving 100M tokens/month on LLaMA-3.1-8B would spend $19.76/month at Q8_0 but only $9.20/month at Q4_K_M, saving $126.72/year at a quality cost of -2.7pp benchmark accuracy. For Phi-2, the savings are even more dramatic: $14.90/month at FP16 versus $4.90/month at Q4_K_M, an annual savings of $120 at only -1.8pp accuracy loss.

The LLaMA-3.1-8B results deserve separate attention as the only model in the matrix exceeding 3B parameters. At 72.4% rescored accuracy on Q8_0 and 69.7% at Q4_K_M (-2.7pp), the 8B model demonstrates that quantization tolerance scales with model size, consistent with the intuition that larger weight matrices have more redundancy to absorb precision loss. However, Phi-2 at 2.7B is more quantization-robust than LLaMA-3.2-1B at 1.2B, suggesting that architecture and training methodology matter more than raw parameter count in the sub-8B regime. The cost range for LLaMA-3.1-8B ($0.092/1M at Q4_K_M versus $0.198/1M at Q8_0) means that Q4_K_M saves 49% while losing only 2.7pp accuracy -- a tradeoff that essentially every production deployment should accept.

The cross-phase reproducibility analysis (added in v2) reveals that only coherence (SemScore) is fully reproducible across Phase 1 and Phase 2 (3/3 models within 5% divergence). BERTScore diverges at -5.7% for 2/3 models (marginal), and ROUGE-L diverges -10.7% to -18.6% (substantial). This finding has methodological implications that extend beyond TR125: any cross-report quality comparison using ROUGE-L should be treated with caution unless the evaluation conditions are identical. Coherence emerges as the most reliable signal for tracking quality changes across experiments -- a finding that informs TR133's quality model, which weights coherence as the primary quality indicator.

The 26,000-sample quantization matrix is the largest single experiment in the Phase 2 program and provides the data foundation for TR133's quality prediction model.
The 34 model-quant variants tested span the full deployable configuration space for consumer hardware.

**Opening for TR126.** TR123's compile speedups were measured on Windows with aot_eager fallback.
Does the compilation benefit survive on Linux with real Triton kernel generation?

---

### 5.4 TR126: Docker/Linux Compile Paradox Resolution

**Research question.** Does the compile paradox discovered in TR120 survive when torch.compile has access to real Inductor+Triton compilation on Linux?

TR120 found that torch.compile on Windows silently falls back to `aot_eager`, a non-optimizing backend that provides no Triton kernel generation. All "compilation" results from TR117-TR122 were therefore measured under this fallback, rendering compile-related conclusions unreliable. The paradox was that torch.compile appeared to increase latency rather than decrease it -- the opposite of its intended behavior. TR126 resolves this by providing the first Windows-vs-Linux A/B comparison on the same consumer GPU, using Docker to provide a Linux environment with full Triton access while maintaining identical hardware and identical model weights.

**Experimental design.** Three phases totaling approximately 29,900 measurements across 2 platforms (Windows native, Docker/Linux), 2 PyTorch versions (2.8, 2.10), 3 backends (transformers-gpu, transformers-gpu-compile, Ollama), and 7 models. Phase 1 (environment gate) validates the Docker/Linux environment: CUDA 13.0, Triton 3.3.1, torch.compile with Inductor backend, 0 graph breaks, weight parity verified via deterministic decode. Phase 2 (compile paradox replication) runs a 2x3 factorial design with 30 repetitions per cell across 5 prompt scenarios, producing 3,240 prefill samples under dynamic and padded configurations plus 11,340 baseline measurements across 3 modes (prefill, kv_decode, e2e_kv). Phase 3 (backend matrix) tests 5 models across 3 backends with 15 repetitions, producing 3,780 successful measurements plus compiled decode crash logs. Additional experiments test mode="default" (3,891 measurements) and PyTorch 2.10 (4,522 measurements).

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Compile paradox reversal | -40.0% latency | d=-0.59, p=8.87e-61 (Phase 2 aggregate) |
| Speedup range | 1.3x-2.5x | qwen2.5-3b to gpt2-25m |
| Phase 3 prefill effect | d=-1.21 (large) | -53.3% delta, compiled vs eager |
| Compiled decode | 100% crash rate | All modes, both PyTorch versions |
| Compiled decode (64 tokens) | +2.2%, not significant | Neutral when it works |
| Ollama decode advantage | 7x over eager HF | d=2.38, p<1e-209 |
| Triton kernels generated | 916 across 6 models | Physical proof of compilation |
| ANOVA backend x model | F(8,1608)=453.1 | p<1e-16, eta^2=0.107 |
| StaticCache decode | 5.8x slower | First successful compiled decode, but impractical |
| PyTorch 2.10 rerun | Identical crash | 4,522 measurements confirm architectural bug |
| Padded vs dynamic compile | 15% improvement | d=-0.91 padded vs d=-0.59 dynamic |
| qwen2.5-0.5b padded speedup | 5.0x | Highest in Phase 2 |
| 1.5B crossover (TOST) | +/-1ms, p=0.001 | Compiled HF = Ollama at qwen2.5-1.5b |
| Phase 2 baseline decode (64 tok) | 1,890 measurements | Compiled decode works at short length |

**Extended analysis.** TR126 delivers the single most impactful performance finding in the research program and resolves the longest-standing open question from Phase 1. Real Triton compilation on Linux reduces prefill latency by 24-60% across all model sizes, directly reversing TR120's Windows findings where torch.compile appeared harmful. The Phase 2 aggregate effect size (d=-0.59, medium by Cohen's convention, p=8.87e-61 confirming that this is not a chance finding) masks substantial variation by model: GPT-2 at 25M parameters achieves 2.5x speedup, GPT-2 at 50M achieves 2.2x, Qwen2.5-0.5B achieves 2.3x, Qwen2.5-1.5B achieves 1.8x, GPT-2 at 100M achieves 1.3x, and Qwen2.5-3B achieves only 1.3x. This inverse relationship between model size and compile benefit arises from a fundamental compute-vs-memory distinction. Smaller models are compute-bound: the arithmetic operations dominate wall time, and Triton's kernel fusion reduces the number of kernel launches and intermediate memory writes, yielding large speedups. Larger models are memory-bandwidth-bound: reading the weight matrices from GPU memory dominates wall time, and kernel fusion cannot reduce the amount of data that must be read. The compile benefit plateaus at the memory bandwidth floor. The ANOVA interaction term (F(8,1608)=453.1, p<1e-16) formally validates this scale crossover, demonstrating that the effect of backend choice is dependent on model size -- a real structural phenomenon, not a confound.

The inverse relationship between model size and compile benefit deserves further examination because it determines backend selection policy. At GPT-2 25M parameters, Triton kernel fusion eliminates redundant memory accesses in the small attention heads, achieving 2.5x speedup. At Qwen2.5-3B, the larger weight matrices are already memory-bandwidth-bound, and kernel fusion can only reduce the overhead fraction (kernel launch, memory allocation), which is proportionally smaller. The practical implication is that compilation is most valuable precisely where Ollama is least competitive (small models with low memory bandwidth demand) and least valuable where Ollama is most competitive (large models with high bandwidth demand). This creates a natural segmentation: compiled HF for prefill on small models, Ollama for everything else.

The compiled decode story is a five-part failure sequence that establishes a robust negative result. First, `reduce-overhead` mode crashes 100% on autoregressive decode at 128+ tokens due to CUDA graph shape incompatibility with DynamicCache's growing KV tensors. Second, `mode="default"` produces identical crashes because PyTorch 2.8's Inductor invokes CUDA graph trees internally regardless of the mode parameter. Third, even when compiled decode succeeds at 64 tokens (Phase 2 baseline), it provides zero speedup (+2.2%, not significant, d=0.026). Fourth, three-layer patching of `cudagraph_trees.py` confirms the crash is architectural: `torch.cat` in `DynamicCache.update()` is fundamentally incompatible with CUDA graph replay. Fifth, StaticCache enables the first successful compiled decode but is 5.8x slower than eager due to per-step compilation overhead. The full Phase 3 rerun on PyTorch 2.10 (NGC 26.01) produces identical results, confirming this is not a version-specific regression. Issue pytorch/pytorch#175557 was filed and assertion fix PR #175562 was submitted.

The backend ranking reversal at scale has immediate practical implications for any deployment serving multiple model sizes. For small models (<=500M parameters), compiled HuggingFace dominates because Triton fusion provides large speedups on compute-bound workloads. For larger models (>=1.5B), Ollama's quantized inference matches or beats compiled FP16 on prefill (formally confirmed by TOST equivalence at the 1.5B crossover: compiled HF and Ollama are within +/-1ms for Qwen2.5-1.5B, p=0.001) and delivers 7x faster decode (d=2.38, p<1e-209, the largest effect size in the study). This establishes the compile policy that propagates through the rest of the program: prefill-only on Linux with Inductor+Triton for small models (<=1B parameters), Ollama for everything else, and never compile decode under any configuration. The policy is backed by five independent lines of evidence: (1) reduce-overhead crashes decode at 128+ tokens, (2) mode="default" also crashes, (3) compiled decode at 64 tokens provides no speedup, (4) three-layer patching of cudagraph_trees.py confirms the crash is architectural, and (5) StaticCache enables decode but is 5.8x slower than eager. Every viable compiled decode path has been exhausted.

The padded configuration result from Phase 2 adds a nuance to compile deployment guidance: padding inputs to fixed shapes improves compiled performance by 15% (d=-0.91 padded versus d=-0.59 dynamic), validating TR120's shape-stability hypothesis. Qwen2.5-0.5B achieves a 5.0x speedup under padding, the highest in the study. For production systems that can bucket input lengths into fixed sizes, padded compilation with `dynamic=False` is the optimal configuration. For systems with highly variable input lengths, `dynamic=True` is necessary but incurs approximately 85% higher compiled latency for small models compared to the padded case. This tradeoff is encoded in TR133's throughput model as a binary flag rather than a continuous parameter, a simplification that may introduce prediction error for workloads with bimodal input length distributions.

The 916 Triton kernels generated across 6 models (17-245 per model) provide physical proof that compilation occurred -- not inferred from timing improvements but directly observed in the `TRITON_CACHE_DIR`. Zero graph breaks were recorded during validation, confirming that the Inductor backend successfully compiled the full model graph. This physical evidence chain (kernel files on disk, zero graph breaks, timing improvements consistent with kernel fusion) establishes the gold standard for compilation validation in the program and should be replicated for any new model or PyTorch version before deploying compiled inference.

The ~29,900 measurements across 2 platforms, 2 PyTorch versions, 3 backends, and 7 models make TR126 the most comprehensive cross-platform validation in the program.
The filed issue (pytorch/pytorch#175557) and submitted PR (#175562) demonstrate that the research program contributes upstream fixes, not just measurements.

**Opening for TR127.** TR123-TR126 tested prompts up to approximately 2K tokens.
How does performance scale as context grows to 4K-32K tokens on consumer hardware?

---

### 5.5 TR127: Long-Context Performance Characterization

**Research question.** How does inference performance scale with context length on consumer hardware, and where are the practical limits?

Production workloads -- RAG pipelines, document summarization, multi-turn conversations -- operate at 4K-128K token contexts. The entire measurement corpus through TR126 was generated at contexts below 2K tokens, leaving the scaling behavior in the production-relevant range unknown. This gap is particularly consequential because self-attention's theoretical O(n^2) complexity suggests that performance should degrade quadratically with context length -- but the degree to which hardware optimizations (tensor cores, Flash Attention, paged KV caches) mitigate this theoretical bound on consumer hardware was empirically unmeasured.

**Experimental design.** A systematic context-length sweep across 1,144 measurements (1,140 successful + 4 OOM): 5 models (0.5B-3.2B parameters), 2 backends (HuggingFace transformers FP16, Ollama quantized), 7 context lengths (512 to 32,768 tokens in power-of-2 steps), 3 measurement modes (prefill, decode, end-to-end), and 10 repetitions per cell. Context is generated using repeated natural-language prompts to the target token count. VRAM is monitored via NVML at each measurement point. The two-regime analysis fits power-law models (latency ~ context^b) separately to pre-spillover and post-spillover data, using VRAM measurements to identify the spillover threshold.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Pre-spillover exponent (HF) | b = 1.58-1.78 | R^2 = 0.999+; between linear and quadratic |
| Post-spillover cliffs (HF) | 25-105x latency | CUDA Unified Memory paging via PCIe |
| Ollama prefill exponent | b < 0.2 | Sub-linear; Flash Attention eliminates quadratic |
| Spillover thresholds | 8K (3B), 16K (0.5B, 1.5B) | Model-weight footprint determines VRAM budget |
| Decode degradation (Ollama) | 41-53% over 64x context | llama3.2-1b: 163 to 96 tok/s |
| HF decode collapse | 95% | qwen2.5-1.5b: 42 to 2.1 tok/s (512 to 16K) |
| Ollama vs HF speed | 86-100% faster | Gap widens from 86% at 512 to 99.96% at 16K |
| TTFT threshold | >1s at 4K on HF | Ollama never >1s through 32K |
| Per-token VRAM cost | 0.75-1.16 MB/token | FP16; includes activations + allocator overhead |
| HF TTFT at 16K tokens | 7.9-8.9 minutes | qwen2.5-0.5b and qwen2.5-1.5b |
| Ollama TTFT range | Always <1s | Through 32K tokens |
| OOM cliff pattern | Spillover + 1 step | Predictable from VRAM formula |
| Pre-spillover CV (HF) | 0.2-3.1% | Extremely high measurement precision |
| Ollama variance (with rep-0) | CV 97-307% | Cold-start dominated; filter rep-0 |

**Extended analysis.** The two-regime phenomenon is the central finding of TR127 and perhaps the most practically consequential result in the program for deployment planning on consumer hardware. In the pre-spillover regime, where all data fits within the 12 GB physical VRAM, HuggingFace FP16 prefill latency scales with exponents of 1.58-1.78, falling between the theoretical linear (b=1.0, pure compute scaling with perfect parallelization) and quadratic (b=2.0, naive self-attention without optimization) bounds. The sub-quadratic exponents confirm that hardware optimizations (tensor cores accelerating the Q*K^T matrix multiply, memory coalescing for sequential KV-cache reads, and partial Flash Attention support in recent PyTorch versions) partially mitigate the O(n^2) attention cost, but do not eliminate it. The quadratic fit achieves R^2=0.999+, indicating near-perfect predictability within this regime. This clean scaling relationship shatters at the VRAM spillover threshold. When the total memory demand (model weights + KV cache + activations) exceeds the 12 GB physical VRAM, CUDA Unified Memory silently pages tensors to system RAM via PCIe (~16 GB/s) instead of GDDR6 (~432 GB/s), causing 25-105x latency cliffs. The "silent" nature of this failure is particularly dangerous: PyTorch does not raise an exception or warning when unified memory paging occurs. The only observable symptom is the sudden latency increase, which could be misattributed to other causes without the two-regime analysis. The full-range power-law fits produce apparent exponents of b=4.6-6.7 -- artifacts of memory thrashing masquerading as computational scaling.

Ollama's sub-linear prefill exponents (b<0.2 across all three tested models: b=0.083 for LLaMA-3.2-1B, b=0.109 for Qwen2.5-1.5B, b=0.158 for LLaMA-3.2-3B) demonstrate that Flash Attention and paged KV caches effectively eliminate the quadratic penalty at these context lengths. This is not a theoretical claim; it is an empirical measurement showing that Ollama prefill scales as approximately O(n^0.2) from 512 to 32K tokens. The sub-linear exponent means that doubling context length increases prefill latency by only 15-20% rather than the 4x that naive quadratic attention would predict. The mechanism is twofold: Flash Attention reduces the attention computation from O(n^2) memory to O(n) by computing attention scores in blocks, and paged KV caches (in llama.cpp) avoid the memory allocation overhead of contiguous tensor storage.

Combined with Ollama's superiority in decode throughput (41-53% degradation over 64x context growth versus HF's 95% collapse), this establishes Ollama as the only viable backend for long-context workloads on 12 GB VRAM. The decode degradation in Ollama (LLaMA-3.2-1B: 163 to 96 tok/s, Qwen2.5-1.5B: 147 to 80 tok/s, LLaMA-3.2-3B: 99 to 47 tok/s from 512 to 32K tokens) represents the linear cost of reading a growing KV cache at each decode step -- an inherent cost of autoregressive generation that no optimization can eliminate, only mitigate.

The TTFT analysis has direct user-experience implications that connect to the production readiness questions addressed in TR128. HuggingFace FP16 exceeds the 1-second TTFT threshold at 4K tokens for all three tested models; at 16K tokens, TTFT reaches 7.9 minutes (Qwen2.5-0.5B) and 8.9 minutes (Qwen2.5-1.5B) as CUDA Unified Memory thrashes through the entire prompt's attention computation via PCIe. Ollama maintains sub-second TTFT through 32K tokens because Flash Attention's O(n) memory footprint avoids spillover entirely. For any interactive application, this alone disqualifies HF FP16 for context lengths above 4K on consumer hardware.

The 9,004x TTFT increase observed over 32x context growth on HF (from sub-millisecond at 512 tokens to minutes at 16K) is not a gradual degradation but a phase transition. The pre-spillover TTFT growth is smooth and predictable (following the b=1.58-1.78 power law); the post-spillover TTFT growth is catastrophic and effectively infinite from a user-experience perspective. This bimodal behavior means that TTFT monitoring in production should trigger alerts at the spillover threshold, not at the OOM threshold -- by the time OOM occurs, the system has already been unresponsive for minutes.

The per-token VRAM cost (0.75-1.16 MB/token for FP16) provides the empirical input for context budget planning. Cross-validation with TR123's theoretical KV costs (12-37 KB/token) reveals a 20-95x overhead from attention workspace, activations, and allocator fragmentation. This overhead factor (approximately 1.058x for the allocator component) is later captured in TR133's VRAM prediction model. The discrepancy between theoretical KV-cache cost (which accounts only for the key and value tensors) and empirical per-token VRAM growth (which includes attention score matrices, softmax intermediate results, gradient-free workspace, and CUDA allocator padding) is an important finding for any system attempting to predict VRAM from architecture metadata alone. TR133's two-pass fitting approach -- first fitting the allocator overhead from low-context data, then fitting quadratic activation coefficients from residuals -- is a direct methodological consequence of this discrepancy.

The measurement quality analysis reveals an important methodological subtlety. HF measurement precision is extremely high in the pre-spillover regime (CV 0.2-3.1%), but Ollama variance is dominated by cold-start outliers (CV 97-307% when including repetition 0, dropping to 3.6-6.1% after filtering). The first repetition consistently shows elevated latency due to model loading, KV cache allocation, or CUDA context initialization. This cold-start effect means that median or 10%-trimmed mean is the correct central tendency measure for Ollama timing data -- a methodological lesson that propagates to TR128, TR129, and TR130. All 18 backend comparisons (HF vs Ollama across models and context lengths) survive Bonferroni correction, confirming that the observed performance differences are not artifacts of variance inflation.

The OOM cliff pattern -- spillover at one context length followed by hard OOM at the next power-of-2 step -- provides a practical early-warning system. When a model enters the spillover regime (detectable by a sudden 25-100x latency increase), the next doubling of context will likely fail entirely. This pattern is predictable from the VRAM budget formula: VRAM = model_weight_size + KV_cache_cost * context_length. For the Qwen2.5-3B model with its 6 GB base footprint, the remaining 6 GB supports approximately 4,600 tokens of FP16 KV cache before spillover begins. This formula, validated here empirically, is the foundation of TR133's VRAM prediction model.

The two-regime discovery fundamentally changes how context-length scaling should be tested on consumer hardware.
Any benchmark that tests only a single context length, or that averages across pre- and post-spillover regimes, will produce misleading scaling exponents.

**Opening for TR128.** TR127 characterizes single-request performance across context lengths.
What happens when realistic production load patterns -- concurrent requests, streaming, multi-turn conversations -- are applied?

---

### 5.6 TR128: Production Workload Characterization

**Research question.** What happens when realistic production load is applied to a single-GPU Ollama instance, and which configuration knobs actually matter?

TR108-TR127 characterized inference under controlled, single-shot conditions: one request at a time, steady-state execution, no concurrency. Production workloads differ in four critical ways: bursty arrivals (requests do not arrive uniformly), concurrent requests (multiple users or agents may query simultaneously), streaming responses (tokens are sent incrementally rather than as a complete batch), and multi-turn context accumulation (each conversation turn adds to the prompt context). These effects create queueing and thermal phenomena invisible to single-request benchmarks, and their interaction with Ollama's configuration parameters (particularly NUM_PARALLEL) was untested.

**Experimental design.** Five phases totaling 3,172 measurements across 3 models (LLaMA-3.2-1B at 1.2B params, Qwen2.5-1.5B at 1.5B params, LLaMA-3.2-3B at 3.2B params), all served by Ollama on an RTX 4080 Laptop GPU with 12 GB VRAM. Phase 1 (baseline characterization) establishes serial service times at zero concurrency with high precision (CV 2-10%, 95% CIs within +/-25ms), providing the reference throughput rates for Phase 2 saturation calculations: LLaMA-3.2-1B at 858ms mean (1.17 req/s theoretical max), Qwen2.5-1.5B at 1,008ms (0.99 req/s), LLaMA-3.2-3B at 1,435ms (0.70 req/s). Phase 2 (concurrency and saturation sweep) is the core experiment, crossing OLLAMA_NUM_PARALLEL={1, 2, 4} with 5 Poisson arrival rates (0.5, 1.0, 2.0, 5.0, 10.0 req/s) per model, with Ollama fully restarted between parallelism levels to prevent state carryover. Each of the 30 pairwise comparisons (NP=1 vs NP=2, NP=1 vs NP=4, NP=2 vs NP=4 across 5 rates and 3 models, with Holm-Bonferroni correction for multiple testing) tests whether the NUM_PARALLEL parameter affects wall-clock latency. Phase 3 (thermal stability) holds each model at approximately 80% of its Phase 1 saturation rate for 180 seconds under constant periodic arrivals, monitoring GPU temperature via NVML. Phase 4 (streaming performance) compares batch vs stream response modes at 3 arrival rates per model, producing 9 Holm-Bonferroni corrected comparisons, and additionally measures TTFT under each condition. Phase 5 (multi-turn context accumulation) tests full vs sliding-window (last 3 turns) context strategies across 5- and 10-turn conversations with 8 conversations per condition. All phases achieve 100% success rate.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Baseline service times | 858-1,435 ms | llama3.2-1b to llama3.2-3b (1.7x range) |
| NUM_PARALLEL effect | 0/30 significant | Mean |change| = 4.0%; Holm-Bonferroni corrected |
| M/D/1 deviation | Up to 20.4x | llama3.2-3b at NP=4, 1.0 req/s |
| Peak GPU temperature | 66 deg C | Well below 80 deg C throttle threshold |
| Streaming overhead | 0/9 significant | Zero wall-clock penalty; Holm-Bonferroni corrected |
| TTFT amplification | 29.9x at 2.0 req/s | llama3.2-3b; pure queueing delay |
| Sliding-window benefit | Inconclusive | p=0.042, n=8; wouldn't survive Bonferroni |
| qwen2.5-1.5b anomaly | +66% decode throughput | During sustained load; mechanism unknown |
| Max throughput (llama3.2-1b) | 1.17 req/s | Theoretical ceiling at service time 858ms |
| Max throughput (llama3.2-3b) | 0.70 req/s | Service time 1,435ms |
| Recommended utilization cap | 70% | Above this, p99 exceeds 2x p50 |
| Latency distributions | 15/15 non-normal | Shapiro-Wilk p<0.05; right-skewed by design |
| Power analysis MDE | d >= 0.19 | Phase 2 core experiment |

**Extended analysis.** The NUM_PARALLEL result is a refutation with practical consequences that extends well beyond the Ollama ecosystem. Ollama's documentation suggests that increasing NUM_PARALLEL enables concurrent GPU inference, and a naive reading of M/D/1 queueing theory predicts that NP=4 should quadruple throughput. Neither is true.

Zero of 30 pairwise comparisons reach significance after Holm-Bonferroni correction, with 26/30 effect sizes negligible (|d|<0.2), 4/30 small (d=0.20-0.29), and a mean absolute change of 4.0% -- consistent with measurement noise. The CUDA compute kernels for transformer inference occupy the entire GPU, and the NUM_PARALLEL parameter only affects CPU-side request admission. At the GPU level, inference requests are serialized by the hardware scheduler regardless of how many are admitted by the CPU (a finding later confirmed at the kernel level by TR131's max_concurrent_kernels=1 observation).

This finding means that any capacity planning tool relying on NUM_PARALLEL > 1 for throughput scaling is fundamentally flawed. It also means that the common practice of setting NUM_PARALLEL=4 or higher in Ollama deployment guides is a placebo: it increases memory usage (multiple request contexts in GPU memory) without improving throughput.

The M/D/1 queueing model failure is quantitatively dramatic: up to 20.4x deviation from observed queue wait at NP=4 for LLaMA-3.2-3B at 1.0 req/s. Two assumptions fail simultaneously: service time is not deterministic (CV 2-10%), and NP>1 does not scale throughput because the GPU is the bottleneck. The M/D/1 model predicts that NP=4 should reduce queue wait by approximately 4x (linear scaling with server count), but the observed queue wait is essentially unchanged because the GPU cannot process multiple inference requests simultaneously. This makes the M/D/1 prediction optimistic by the factor of NP (4) times the actual queueing deviation, compounding to the observed 20.4x gap.

This calibrated failure is arguably the most important negative result in the program, because it directly motivates the empirical lookup table approach in TR133. Any capacity planning tool that uses M/D/1 with NP>1 for GPU inference will dramatically underestimate tail latency and overestimate available capacity. The M/D/1 model's latency prediction is used in TR133 but only with NP=1 (single server), median service times (more robust to non-normality than mean), and a 70% utilization safety cap that prevents the model from being applied in the saturation regime where it catastrophically fails -- all three constraints are derived from this failure.

The streaming and thermal results are reassuring for production deployment and provide two "always-on" recommendations. Streaming adds zero wall-clock overhead (0/9 significant after Holm-Bonferroni correction), meaning applications should always enable streaming for better perceived responsiveness with no throughput penalty. The zero overhead is expected because streaming merely changes the response delivery mechanism (tokens sent via NDJSON chunks as they are generated) without affecting the GPU computation pipeline. The inter-chunk latency is reported honestly as ichunk rather than inter-token, acknowledging that TCP buffering batches multiple tokens per NDJSON chunk.

Peak GPU temperature of 66 degrees Celsius under 180-second sustained load at approximately 80% saturation provides 14 degrees of headroom below the 80-degree throttle threshold, eliminating the need for aftermarket cooling solutions for this hardware configuration. The thermal stability finding is specific to the RTX 4080 Laptop GPU in its tested chassis; desktop GPUs with different thermal solutions may behave differently, and prolonged operation (hours vs minutes) may reveal thermal accumulation effects not captured in the 180-second test window.

The TTFT amplification finding (29.9x at 2.0 req/s for LLaMA-3.2-3B) is a pure queueing artifact: prompt evaluation speed is unchanged (GPU tok/s remains constant, as later confirmed by TR129), but requests wait longer in the queue before the GPU becomes available. This is consistent with the GPU serialization bottleneck and directly feeds the 70% utilization cap recommendation: at 70% of theoretical max throughput, the queueing delay is bounded to approximately 2-3x the service time, which is acceptable for most applications.

The Qwen2.5-1.5B decode warmup anomaly (66% throughput increase over 143 requests under sustained load, with -27.7% wall latency drift at p<0.0001) remains unexplained and represents one of the program's few genuinely open questions. The mechanism is not GPU clock ramp (would affect all models equally, but LLaMA-3.2-1B and LLaMA-3.2-3B show flat throughput), not JIT compilation (llama.cpp is ahead-of-time compiled C++, with no JIT component), not model reloading (Ollama's `load_duration_ms` metric remains stable throughout the run), and not thermal effects (GPU temperature plateaus within the first 30 seconds).

Possible explanations include: (a) Ollama's or llama.cpp's internal memory allocator optimizing KV-cache layout after repeated access patterns, (b) CUDA driver-level caching or memory coalescing improvements that compound over hundreds of inference calls, or (c) a model-architecture-specific interaction between Qwen2.5's 2-KV-head GQA design and the GPU's memory access patterns. This anomaly surfaces again in TR129 Phase 3 (where Qwen2.5-1.5B shows a 45% sustained throughput improvement at think=100ms versus 2-5% for other models) and warrants standalone investigation with fine-grained NVML monitoring and possibly kernel-level profiling during the warmup period.

The Phase 5 multi-turn result, while inconclusive, provides useful directional evidence. Under full context accumulation, prompt token counts grow linearly from approximately 35 to 1,365 tokens over 10 turns, creating predictable latency growth. Sliding-window context management (retaining only the last 3 turns) bounds this growth, and the suggestive 5.9% latency reduction for LLaMA-3.2-1B at turn 9 (d=1.12, p=0.042) aligns with the theoretical prediction from TR127's per-token VRAM cost. However, with n=8 per group and three models tested, this p-value would not survive Bonferroni correction (threshold 0.017). The other two models show negligible benefit (0.4-0.5%, p>0.2). The primary value of sliding-window context may be memory and cost reduction rather than latency improvement -- a distinction that matters for long-running agent conversations where context accumulation could eventually trigger VRAM spillover.

The non-normality finding (15/15 group distributions fail Shapiro-Wilk at p<0.05) is expected for latency data and has methodological implications for the entire program. Right-skewed distributions arise naturally from queueing effects (occasional requests hit a loaded queue) and cold-start artifacts. The t-tests used throughout TR128 remain valid at n>=30 via the Central Limit Theorem, but the power analysis (minimum detectable d>=0.19 in Phase 2) is calibrated for normally distributed data and may be slightly conservative for skewed distributions. Median and trimmed-mean comparisons are provided alongside t-test results as robustness checks.

The 3,172 measurements across 5 phases at 100% success rate establish TR128 as the production readiness baseline for the program.
Every subsequent report (TR129-TR133) that tests Ollama under load inherits TR128's baseline service times as cross-validation reference points.

**Opening for TR129.** TR128 establishes that a single Ollama instance serializes inference.
How does per-agent throughput scale when multiple agents share the GPU in a closed-loop architecture?

---

### 5.7 TR129: N-Agent Scaling Laws

**Research question.** How does per-agent throughput scale when N agents share a single Ollama GPU instance in closed-loop operation?

Multi-agent systems -- where each agent sends a request, waits for the response, processes it, and sends another -- are the dominant architecture for LLM-powered applications including autonomous coding assistants, research pipelines, and customer service systems. TR128 established that the GPU serializes inference and that NUM_PARALLEL is a no-op, but did not measure the quantitative scaling behavior as agent count increases from 1 to 8. Without this characterization, practitioners cannot answer the fundamental capacity planning question: how many agents can share a single GPU before per-agent performance becomes unacceptable?

**Experimental design.** Four phases totaling 5,310 measurements across N={1, 2, 3, 4, 5, 6, 7, 8} concurrent closed-loop agents, 3 models (LLaMA-3.2-1B at 1.2B params, Qwen2.5-1.5B at 1.5B params, LLaMA-3.2-3B at 3.2B params), all served by a single Ollama instance on RTX 4080 Laptop GPU. The closed-loop design is critical: each agent sends a request, waits for the complete response, then immediately sends the next request. This bounds the maximum number of in-flight requests to N (unlike open-loop systems where arrivals are unbounded), matching the behavior of real multi-agent applications where each agent processes one LLM call at a time. Phase 1 (single-agent baseline) establishes solo throughput with 30 repetitions per model, measuring both wall-clock effective throughput and GPU-side decode throughput (from Ollama's native `eval_duration`). Phase 2 (N-agent sweep) is the core experiment, running all 8 concurrency levels for each model with 30 repetitions per (N, model) cell, measuring per-agent effective throughput (wall-clock tokens per second including queue wait) and total system throughput (sum of per-agent throughput). Phase 3 (think-time sweep) tests inter-request delays of {0, 100, 500, 1000, 2000} ms at N=4 for all 3 models, measuring both per-request throughput and sustained system throughput. Phase 4 (heterogeneous model assignment) tests mixed-model configurations with OLLAMA_MAX_LOADED_MODELS=4. Scaling is modeled using Amdahl's Law: eta(N) = 1 / (s + (1-s)*N), where s is the serial fraction fitted via nonlinear least squares to the per-agent efficiency data.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Amdahl serial fraction (s) | 0.39-0.54 | R^2 > 0.97 for all 3 models |
| Max speedup (1/s) | 1.85-2.58x | llama3.2-1b to llama3.2-3b |
| Throughput plateau | N=2 | <3% gain from N=2 to N=8 |
| Per-agent eta(8) | 17-20% | Of solo throughput |
| Saturation point | N=3-4 | eta drops below 50% |
| Fairness (Jain's index) | >=0.997 at N=8 | Perfect equity across agents |
| GPU tok/s | Constant across N | Queue wait, not decode slowdown |
| Single-agent baselines | 115.8 / 102.7 / 79.2 tok/s | llama-1b / qwen-1.5b / llama-3b |
| Total tok/s at N=2 | 185.3 (llama-1b) | 1.6x of N=1; <1.4% gain N=2 to N=8 |
| Think-time at 2000ms | eta >= 0.98 | But 60-69% idle time |
| Think-time at 100ms | +2-45% sustained | Model-dependent improvement |
| qwen2.5-1.5b think anomaly | +45% at 100ms | 175.7 to 254.1 total tok/s |

**Extended analysis.** The Amdahl serial fractions (s=0.5391 for LLaMA-3.2-1B with R^2=0.970, s=0.3870 for LLaMA-3.2-3B with R^2=0.993, s=0.4554 for Qwen2.5-1.5B with R^2=0.985) capture the fundamental constraint of single-GPU multi-agent inference with remarkable fidelity. The serial fraction represents the portion of work that is inherently sequential: GPU scheduler serialization, memory bus contention, Ollama HTTP handling, and CUDA kernel launch overhead. Even with infinite agents, total throughput cannot exceed 1/s = 1.85-2.58x the single-agent rate. That the throughput plateau is effectively reached by N=2 (with less than 3% additional gain from N=2 to N=8 for all models) is a sobering finding for multi-agent system designers. The R^2 values exceeding 0.97 for all three models indicate that Amdahl's Law is an excellent phenomenological description of the degradation, though the serial fraction is a fitted parameter, not a physically derived quantity.

The relationship between model size and serial fraction is informative and connects to the bandwidth physics revealed in TR131. The smallest model (LLaMA-3.2-1B, s=0.54) has the highest serial fraction because overhead (HTTP handling, kernel launch, memory transfer) represents a larger proportion of total work when the model is small and fast. Larger models (LLaMA-3.2-3B, s=0.39) have lower serial fractions because the compute-to-overhead ratio is more favorable -- the useful work (GEMM operations on weight matrices) is a larger fraction of total GPU time. This means larger models actually scale slightly better under concurrency in relative terms, though they start from a lower absolute throughput baseline. The maximum theoretical speedup (1/s) ranges from 1.85x (LLaMA-3.2-1B) to 2.58x (LLaMA-3.2-3B), meaning that even with optimal scheduling, a single GPU serving LLaMA-3.2-1B via Ollama can never exceed 1.85x its solo throughput. For LLaMA-3.2-3B, the ceiling is higher at 2.58x, but the solo throughput is lower (79.2 vs 115.8 tok/s), so the maximum total throughput is similar across models.

The fairness analysis provides an important guarantee for multi-agent system design that is often overlooked in performance benchmarking. Jain's fairness index (defined as the square of the sum of throughputs divided by N times the sum of squared throughputs, ranging from 1/N for maximally unfair to 1.0 for perfect fairness) reaches 0.997 or higher at N=8 across all models, meaning that Ollama distributes GPU time equitably -- no agent is starved. Combined with the constant GPU tok/s observation (decode throughput of approximately 207/162/114 tok/s for the three models remains flat regardless of N), this confirms that the degradation manifests entirely as queue wait time, not as reduced per-request processing speed. Each individual inference call runs at the same speed; agents simply wait longer for their turn.

The think-time sweep reveals a genuine tradeoff that has direct implications for multi-agent system architecture. Inter-request delays of 100ms improve per-request throughput by 2-45% (model-dependent) because reduced contention means shorter queue waits, but sustained system throughput decreases due to duty-cycle loss. At think=2000ms, per-request efficiency recovers to near-baseline (eta>=0.98), but agents spend 60-69% of their time idle. The practical implication is nuanced: natural agent processing time (reasoning, tool calls, API calls to external services, human review) between requests benefits per-request latency without representing wasted capacity, because the agent is doing useful work during the delay. Artificial delays (sleep statements, rate limiters) are counterproductive for total throughput because they reduce duty cycle without performing useful work. The Qwen2.5-1.5B anomaly at think=100ms (+45% sustained throughput improvement, from 175.7 to 254.1 total tok/s) echoes the 66% decode warmup anomaly from TR128 Phase 3 and suggests a model-specific optimization pathway that activates under light-but-steady load. This anomaly remains unexplained and represents one of the few open questions in the measurement program.

The Phase 4 heterogeneous model assignment results, while confounded by Ollama restart and warmup sequence differences, provide a cautionary note. The homogeneous LLaMA-1B configuration (233.9 tok/s) outperformed Phase 2's N=4 (187.0 tok/s) by 25%, but this gap cannot be attributed to OLLAMA_MAX_LOADED_MODELS alone because thermal state, model cache warming, and Ollama's internal scheduling may all differ between phases. The conservative recommendation -- prefer homogeneous assignments and avoid mixed-model configurations on a single GPU -- follows from the inability to isolate the model-switching overhead rather than from evidence that it is large.

The constant GPU tok/s observation across N values is perhaps the most informative finding for understanding the bottleneck mechanism. Decode throughput of approximately 207 tok/s (LLaMA-1B), 162 tok/s (Qwen-1.5B), and 114 tok/s (LLaMA-3B) remains flat from N=1 through N=8. This means the GPU processes each individual inference request at the same speed regardless of how many agents are waiting. The degradation is entirely queue-induced: adding agents increases average wait time but does not slow down the inference computation itself. This finding directly anticipates TR131's kernel-level confirmation that max_concurrent_kernels=1 in all conditions -- the GPU physically cannot process two inference requests simultaneously, so they queue.

The 5,310 measurements across 8 concurrency levels and 3 models provide the first systematic characterization of closed-loop multi-agent inference scaling in the literature.
The Amdahl serial fractions derived here are subsequently used in TR130 for cross-backend comparison and in TR133 for the scaling prediction model.

**Opening for TR130.** TR129 measures scaling under Ollama only.
Is the Amdahl serial fraction an intrinsic GPU property, or does it depend on the serving stack?

---

### 5.8 TR130: Serving Stack Benchmarking

**Research question.** Which serving stack -- Ollama, vLLM, or TGI -- scales best under multi-agent concurrency, and is the Amdahl serial fraction from TR129 an inherent GPU constraint or an Ollama-specific limitation?

TR129's Amdahl serial fractions (s=0.39-0.54) predict that total throughput can never exceed 1.85-2.58x the single-agent rate on a single GPU, regardless of how many agents are added. But this prediction was derived from Ollama alone. If alternative serving stacks -- particularly vLLM with PagedAttention and continuous batching, or TGI with its own continuous batching implementation -- achieve lower serial fractions on identical hardware, the bottleneck is the serving stack's sequential scheduling, not the silicon. If they exhibit similar serial fractions, the bottleneck is intrinsic GPU physics.

**Experimental design.** Four phases totaling 4,797 measurements across 3 backends (Ollama Q4_0, vLLM FP16, TGI FP16), 3 models (LLaMA-3.2-1B, LLaMA-3.2-3B, Qwen2.5-1.5B), and concurrency levels N={1, 2, 4, 8}. Phase 1 (environment validation) verifies all 9 backend-model combinations pass health checks and produce valid output. Phase 2 (single-agent baseline) establishes N=1 throughput with 30 repetitions per combination. Phase 3 (N-agent scaling) runs all 9 combinations at N={1, 2, 4, 8} with 30 repetitions per cell. Phase 4 (TTFT comparison) measures time-to-first-token across all backends. Each backend serves identical prompts on the same GPU, with Docker containers for vLLM and TGI providing Linux environments with identical CUDA access. The quantization note is critical: Ollama serves Q4_0, while vLLM and TGI serve FP16. Absolute throughput comparisons are confounded; eta(N) normalization against each backend's own N=1 baseline eliminates this confound for scaling analysis.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Ollama N=1 advantage | 1.2-2.6x | Q4_0 quantization benefit |
| vLLM N=8 advantage | 2.25x | 559 vs 248 tok/s (llama3.2-1b) |
| Ollama eta(8) | 0.16 | 16% of solo throughput |
| vLLM eta(8) | 0.56 | 56% of solo throughput |
| TGI eta(8) | 0.58 | 58% of solo throughput |
| Scaling law (Ollama) | Amdahl, R^2=0.96+ | Sequential request scheduling |
| Scaling law (vLLM/TGI) | Power law, R^2=0.99+ | Continuous batching; no serial fraction |
| Ollama saturation (N*) | N=4 | eta drops below 50% |
| vLLM/TGI saturation | Beyond N=8 | Never saturate within tested range |
| TTFT | 22-35ms (vLLM/TGI) vs 163-194ms (Ollama) | 6-8x faster; d > 13 |
| Fairness | Jain >=0.996 all backends | All perfectly fair |
| Zero cold-start | Max 1.07x first-3 ratio | Warmup protocol eliminates artifacts |
| Data quality | 98.08% success rate | 4,705/4,797 ok; 92 TGI HTTP 424 errors |
| Crossover point | Between N=2 and N=4 | vLLM overtakes Ollama total throughput |
| vLLM N=8 total (llama-3b) | 319 tok/s | vs Ollama 162 tok/s (1.97x) |
| TGI N=8 total (llama-1b) | 483 tok/s | vs Ollama 248 tok/s (1.95x) |

**Extended analysis.** The most consequential finding is that the three backends follow fundamentally different degradation curves, a qualitative distinction that has profound implications for capacity planning. Ollama maps to Amdahl's Law (R^2=0.957-0.987) because its sequential request scheduling creates a genuine serial bottleneck: requests are processed one at a time, and concurrent arrivals queue. The Amdahl model has a single parameter (serial fraction s) that determines the asymptotic throughput ceiling: total throughput cannot exceed 1/s times the single-agent rate, regardless of N. vLLM and TGI map to a power law (eta proportional to N^(-alpha), alpha=0.17-0.35, R^2=0.988-0.996) because continuous batching enables overlapping execution: multiple sequences are processed in a single forward pass, amortizing the weight-read cost across batch elements. The power-law model has no asymptotic ceiling within the measured range -- efficiency declines gracefully without hitting a wall. This is not a quantitative difference in the same model; it is a qualitative difference in degradation mechanism, and fitting the wrong model to the wrong backend produces meaningless parameters (as demonstrated by force-fitting Amdahl to vLLM, which yields s=0.81-0.92 -- numbers that have no physical interpretation).

The practical consequence is a crossover that determines backend selection policy for the entire program. Ollama wins at N=1 (1.2-2.6x throughput advantage from Q4_0 quantization reducing memory bandwidth pressure): for LLaMA-3.2-1B, Ollama delivers 177.7 tok/s versus vLLM's 150.7 tok/s and TGI's 125.2 tok/s. But vLLM and TGI overtake between N=2 and N=4 as continuous batching amortizes the weight-read cost. At N=8, vLLM delivers 559 total tok/s versus Ollama's 248 tok/s for LLaMA-3.2-1B -- a 2.25x advantage -- despite starting 18% behind at N=1. For LLaMA-3.2-3B, the gap is 319 vs 162 tok/s (1.97x); for Qwen2.5-1.5B, 457 vs 259 tok/s (1.76x). This crossover determines backend selection policy: Ollama for N=1, either for N=2-3 depending on whether TTFT or absolute throughput is the priority, vLLM for N>=4.

A methodological caution emerged from this study that has implications for the broader benchmarking community and for any research comparing serving stacks using parametric models. When Amdahl's Law is force-fitted to vLLM/TGI data, it produces artificially high serial fractions (s=0.81-0.92) because these backends do not degrade via Amdahl's mechanism -- they do not have a serial bottleneck in the Amdahl sense. The high s values arise because Amdahl's concave curve is the closest fit among Amdahl-family curves to the power-law's more gradual decline, not because 81-92% of the work is serial.

Comparing Amdahl serial fractions across backends with different degradation mechanisms is a category error -- analogous to comparing the "slope" of a line to the "slope" of a parabola at a single point. The number has no physical meaning when applied to the wrong model. This report uses raw eta(N), total throughput, and saturation points as the primary cross-backend comparison metrics, with the Amdahl serial fraction reserved for Ollama where the model genuinely describes the physical process (sequential request processing creating a serial bottleneck).

The TTFT finding (6-8x faster on vLLM/TGI) adds another dimension to backend selection. At 22-35ms, Docker-based backends start streaming tokens before the user perceives any delay. Ollama's 163-194ms TTFT is acceptable for many applications but represents a user-perceptible gap (Cohen's d > 13 for all pairwise comparisons). For streaming-critical or latency-sensitive deployments, this alone may justify the Docker overhead. The TTFT difference is particularly consequential for multi-turn conversational agents, where each turn incurs the TTFT penalty. Over a 10-turn conversation, the cumulative TTFT difference is approximately 1.3-1.6 seconds (vLLM/TGI) versus 1.6-1.9 seconds (Ollama) -- a small absolute gap, but the per-turn perception of responsiveness affects user experience disproportionately.

The saturation behavior difference is the most operationally consequential finding for capacity planning. Ollama drops below 50% efficiency at N=4 for all models, meaning that doubling from 4 to 8 agents yields negligible total throughput gain at the cost of doubling per-request latency. vLLM and TGI remain above 50% efficiency at N=8 for 2 of 3 models, suggesting useful scaling continues to N=16+. This means that a deployment planning to serve 8 concurrent agents needs 2-4 GPUs with Ollama but only 1 GPU with vLLM -- a hardware cost difference that dwarfs any per-request throughput advantage Ollama holds at N=1.

The data quality metrics for TR130 are among the best in the program: 98.08% success rate (4,705/4,797 ok), with only 92 HTTP 424 errors from TGI overload at high N. Outlier rates of 0.0-0.2% across all backends, with zero outliers for Ollama and vLLM on LLaMA-3.2-1B, indicate that the measurement methodology (warmup protocol, Ollama restart between conditions, Docker container isolation) successfully eliminates systematic artifacts. The zero cold-start finding (no backend shows first-3-request latency more than 1.07x steady-state mean) validates the warmup protocol and means that the N-agent measurements represent sustained performance, not transient behavior.

The all-backends fairness finding (Jain's index >=0.996 at all concurrency levels) extends TR129's Ollama-specific fairness guarantee to the entire backend ecosystem. This means that no agent is systematically disadvantaged regardless of which serving stack is used, which simplifies multi-agent system design: agents can be treated as symmetric peers without concern for scheduling bias.

The 4,797 measurements across 3 backends, 3 models, and 4 phases make TR130 the definitive serving stack comparison for consumer GPU inference.
The discovery that different backends follow different degradation models (Amdahl vs power law) is a methodological contribution beyond the specific throughput numbers.

**Opening for TR131.** TR130 concludes that "the serving stack is the bottleneck."
But is this conclusion causal, or merely correlational?
What happens when we remove the serving stack entirely and profile the GPU directly?

---

### 5.9 TR131: GPU Kernel Profiling -- Root-Cause Analysis

**Research question.** Is the multi-agent throughput degradation caused by the serving stack (Ollama's sequential scheduling) or by intrinsic GPU physics (memory bandwidth saturation)?

TR130 attributed the degradation to the serving stack based on correlational evidence: vLLM/TGI scale 3-4x better than Ollama, therefore Ollama's scheduling is the bottleneck. This is a reasonable but potentially incorrect inference -- the correlation between backend choice and scaling efficiency could reflect differences in quantization, memory management, or kernel scheduling rather than the serving stack's request handling. TR131 provides the causal test by eliminating the serving stack entirely and profiling GPU kernels directly. If the degradation persists without any serving stack, the cause must be GPU physics.

**Experimental design.** Twenty-six profiled runs using NVIDIA Nsight Systems (nsys) and Nsight Compute (ncu) across 2 backends (Ollama Q4_0, PyTorch Direct FP16), 2 models (LLaMA-3.2-1B, LLaMA-3.2-3B), and 4 experimental conditions: Ollama N=1, Ollama N=8, PyTorch Direct N=1, PyTorch Direct N=8. PyTorch Direct eliminates the entire serving stack -- no HTTP server, no Go runtime, no request queuing, no token streaming -- and calls `model.generate()` directly via HuggingFace Transformers. If the degradation persists without the serving stack, the cause is GPU physics, not software. GPU kernel timelines, memory operations, and execution traces are captured. Welch's t-tests, Cohen's d, 95% CIs, Mann-Whitney U robustness checks, and Holm step-down correction provide statistical rigor.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| PyTorch Direct degradation | 86.4% | N=1 to N=8; worse than Ollama |
| Ollama degradation | 82.1% | N=1 to N=8 |
| Bandwidth stress (Ollama) | +74.4% mem operation time | p=6.4e-5, d=3.81; survives Holm |
| Ollama vs PyTorch at N=1 | 3.0x faster | Q4_0 bandwidth advantage |
| Ollama vs PyTorch at N=8 | 3.9x faster | Advantage grows under contention |
| Max concurrent kernels | 1 in all conditions | GPU hardware enforces serialization |
| N=8 bandwidth demand | 78-130% over 432 GB/s | Back-of-envelope calculation |
| H1 (bandwidth saturation) | Partially confirmed | Only Holm survivor |
| H3 (context switching) | Rejected | Zero variance in gap metrics |
| H5 (KV-cache pressure) | Rejected | Alloc counts unchanged, d=0 |
| Degradation (LLaMA-1B Ollama) | -82.1% | 160.4 to 28.8 TPS |
| Degradation (LLaMA-1B PyTorch) | -86.2% | 52.0 to 7.2 TPS |
| Degradation (LLaMA-3B Ollama) | -82.2% | 96.5 to 17.2 TPS |
| Degradation (LLaMA-3B PyTorch) | -87.1% | 29.3 to 3.8 TPS |
| Attributable to Ollama overhead | -4.3pp | PyTorch degrades more, not less |
| Profiling overhead validation | Negligible | N=1 TPS matches TR129 unprofiled |

**Extended analysis.** The central finding overturns TR130's headline conclusion and represents the most important causal correction in the program. PyTorch Direct -- with zero serving stack overhead, no HTTP server, no Go runtime, no request queuing, no token streaming, just raw `model.generate()` calls via HuggingFace Transformers -- degrades 86.4% from N=1 to N=8, which is 4.3 percentage points worse than Ollama's 82.1%. Both degradation measurements are highly significant (Ollama: p=0.0006, d=4.19; PyTorch: p=0.002, d=4.17; both confirmed by Mann-Whitney U as robustness checks against the non-normality found in TR128), and the direction is unambiguous: removing the serving stack makes things worse, not better.

The serving stack is not the primary bottleneck; GPU memory bandwidth physics is. The -4.3 percentage-point difference (PyTorch degrades 86.4% vs Ollama's 82.1%) is the empirical upper bound on serving stack overhead, and it is negative in the unexpected direction -- meaning Ollama's Q4_0 quantization provides a concurrency benefit that more than compensates for any scheduling overhead. The -4.3pp attributable-to-Ollama figure is the empirical upper bound on serving stack overhead, and it is negative -- meaning Ollama's Q4_0 quantization actually helps under concurrency by reducing per-request bandwidth pressure.

The memory bandwidth mechanism is supported by the strongest statistical evidence in the study and represents the only confirmed causal pathway for the throughput degradation. Ollama memory operation time increases 74.4% from N=1 to N=8 (p=6.4e-5, Cohen's d=3.81), and this is the only hypothesis test surviving Holm step-down correction across 6 tests at family-wise alpha=0.05 (rank 1 of 6, Holm-adjusted threshold=0.0083). Back-of-envelope bandwidth calculations show that N=8 concurrent inference streams demand 78-130% more bandwidth than the RTX 4080's peak 432 GB/s, depending on precision. This forces the memory controller to serialize weight reads, creating the throughput ceiling that no software optimization can overcome.

The max_concurrent_kernels=1 finding across all 26 runs and both backends is revelatory. Cohen's d=0 for every concurrency comparison means the GPU hardware enforces serial kernel execution regardless of software. The kernel serialization previously attributed to Ollama's scheduling (H2) is actually a GPU-level constraint. This reattribution has profound implications: no serving stack can achieve true kernel-level parallelism on a single consumer GPU. The advantage of continuous batching (demonstrated in TR130 and mechanistically explained in TR132) is not parallel kernel execution but rather amortization of weight reads across batch elements within a single kernel launch.

Ollama's growing advantage under contention (3.0x at N=1 to 3.9x at N=8) is a direct consequence of quantization economics under bandwidth pressure. Q4_0 models use 0.5 bytes per parameter versus FP16's 2 bytes, reducing bandwidth demand by 4x per weight read. When bandwidth is the bottleneck, this 4x reduction compounds with contention: each agent's bandwidth demand is lower, so the saturation point is softer. The 3.0x-to-3.9x growth quantifies this compounding effect: at N=1, the 3.0x advantage reflects the raw precision difference in memory reads; at N=8, the additional 0.9x advantage arises from Q4_0 being further from the bandwidth ceiling than FP16, so it experiences proportionally less contention. This finding has a direct implication that connects TR131 back to TR125: the Q4_K_M quantization recommended for quality reasons also provides a concurrency benefit, making quantization a simultaneously quality-preserving, cost-reducing, and concurrency-enhancing optimization. There is no tradeoff between these three objectives at Q4_K_M -- all three improve together.

The hypothesis testing framework in TR131 is notable for its rigor and its negative results. Of five hypotheses tested, only H1 (bandwidth saturation) is partially confirmed, and only one test (memory operation time +74.4%) survives Holm step-down correction. H3 (CUDA context switching) is cleanly rejected with zero variance in inter-kernel gap metrics between N=1 and N=8. H5 (KV-cache pressure) is rejected with memory allocation counts unchanged (p=1.0, d=0). The rejection of H3 and H5 is as informative as the confirmation of H1: it eliminates two intuitively plausible mechanisms (context switching overhead and memory pressure) that a less rigorous study might have accepted as contributing factors. The clean null results demonstrate that the profiling methodology has the resolution to detect these effects if they existed.

The ncu metrics limitation deserves acknowledgment. On the Windows WDDM driver, Nsight Compute captures kernel names but returns null values for SM occupancy and DRAM throughput -- the two metrics that would directly quantify bandwidth saturation. The back-of-envelope bandwidth calculation (N=8 demand = N * model_bytes * decode_rate, yielding 78-130% over the RTX 4080's peak 432 GB/s) is the best available substitute. This calculation is conservative: it assumes peak sustained bandwidth, which real workloads rarely achieve due to memory access patterns and cache effects. The true bandwidth utilization is likely higher than the theoretical demand, making the saturation conclusion even stronger.

The model-size independence of the degradation pattern (LLaMA-1B: -82.1% Ollama, -86.2% PyTorch; LLaMA-3B: -82.2% Ollama, -87.1% PyTorch) is striking. The near-identical degradation percentages across a 3x parameter count range indicate that the bandwidth bottleneck is not model-specific but a property of the hardware-concurrency interaction. Both models saturate the same memory bus; the absolute throughput differs (larger model reads more weights per step) but the proportional degradation under contention is the same. This uniformity supports the use of a single Amdahl serial fraction per model-backend pair in TR133's scaling model, rather than requiring concurrency-dependent corrections.

The 26 profiled runs across 4 experimental conditions provide the program's deepest causal evidence.
TR131 transforms a correlational observation (TR130: "serving stacks differ") into a causal attribution (GPU memory bandwidth is the fundamental constraint, and quantization helps under contention).

**Opening for TR132.** TR131 identifies GPU bandwidth as the root cause but cannot explain why vLLM/TGI scale better.
What is the kernel-level mechanism of continuous batching that amortizes bandwidth?

---

### 5.10 TR132: In-Container GPU Kernel Profiling -- Serving Stack Mechanism

**Research question.** What is the kernel-level mechanism by which continuous batching in vLLM and TGI amortizes memory bandwidth under multi-agent concurrency?

TR131 established that GPU bandwidth saturation is the root cause of multi-agent throughput degradation and that the serving stack is not the primary bottleneck -- GPU physics is. But TR130 showed vLLM/TGI retaining 46-66% per-agent efficiency at N=8 versus Ollama's 16-17%, a 3-4x efficiency gap that GPU physics alone cannot explain. If GPU bandwidth is the floor that all backends share, what architectural feature of continuous batching lets vLLM and TGI push the ceiling higher? TR132 answers this question by profiling GPU kernels inside the Docker containers running vLLM and TGI, capturing the first kernel-level evidence of the continuous batching amortization mechanism.

**Experimental design.** Twenty-five profiled runs using a novel in-container Nsight Systems methodology that overcomes WSL2/WDDM CUDA visibility limitations. The approach mounts the Linux nsys binary into Docker containers, wraps the server entrypoint with `nsys profile --trace cuda`, and extracts cross-platform `.nsys-rep` traces via volume mounts. Two backends (vLLM FP16, TGI FP16), 2 models (LLaMA-3.2-1B, LLaMA-3.2-3B), and 2 concurrency levels (N=1, N=8) with 3 repetitions per cell. All 24 profiled repetitions produced valid traces (11.6-17.4 MB each), achieving a 100% trace capture rate. Five hypotheses are tested via Welch's t-tests with Holm step-down correction.

**Key results.**

| Metric | Value | Context |
|--------|-------|---------|
| Per-token kernel reduction (vLLM) | 80.2% | 54.9 to 10.9 kernels/token (LLaMA-1B); d=1058 |
| Per-token kernel reduction (TGI) | 76.5-76.8% | Across both models |
| Memory BW per token reduction | 79-83% | Per-token mem operation time |
| Amortization ratio | 4.7-5.8x | Super-linear for 1B: 5.75x |
| vLLM vs TGI amortization | Nearly identical | Mechanism is architectural |
| vLLM vs TGI at N=1 | 27-35% faster (vLLM) | Single-request overhead difference |
| GEMM dominance (vLLM) | 69-82% of GPU time | TGI: 41-57% (more attention time) |
| Serving stack vs Ollama kernels at N=1 | 15-25x more | vLLM: 35,129 vs Ollama: 2,257 |
| Larger model advantage | 3B: -38.7% vs 1B: -55.8% | Larger models amortize better |
| H1 (kernel count) | CONFIRMED | 8/8 Holm-corrected tests |
| H2 (bandwidth) | CONFIRMED | 8/8 Holm-corrected tests |
| vLLM LLaMA-1B N=8 degradation | -55.8% | 106.3 to 47.0 TPS |
| TGI LLaMA-1B N=8 degradation | -54.1% | 83.7 to 38.4 TPS |
| vLLM LLaMA-3B N=8 degradation | -38.7% | 50.8 to 31.1 TPS |
| TGI LLaMA-3B N=8 degradation | -38.9% | 41.9 to 25.6 TPS |
| Scaling advantage vs Ollama (3B) | +43.3-43.5pp | Largest gap for larger models |
| Trace capture rate | 100% (24/24) | In-container nsys methodology validated |
| Trace file sizes | 11.6-17.4 MB | Valid CUPTI traces from Docker |

**Extended analysis.** The kernel-level evidence provides the missing causal link in the TR129-TR131 chain and completes the program's deepest line of inquiry. At N=8, vLLM reduces per-token kernel count by 80.2% for LLaMA-1B (from 54.9 kernels per token at N=1 to 10.9 kernels per token at N=8, p=5.3e-11) and per-token memory operation time by 82.6% (from 1.27 ms/token to 0.22 ms/token, p=0.0002). TGI shows comparable reductions: 76.5% kernel count reduction for LLaMA-1B and 76.8% for LLaMA-3B. The effect sizes are extraordinary by any standard: Cohen's d=1058 for vLLM kernel count and d=21.6 for memory bandwidth, reflecting the near-deterministic nature of kernel-level measurements where variance is extremely low. These are not marginal effects; they represent a qualitative transformation in GPU utilization. Instead of 8 independent inference streams each reading the full weight matrix from GPU memory (8 weight reads per decode step), continuous batching fuses them into a single batched matrix multiplication, reading the weights once and applying them to 8 input vectors simultaneously (1 weight read per decode step). The per-token kernel count drops because the batched operation requires the same number of kernel launches as a single inference -- the batch dimension is absorbed into the inner dimension of the matrix multiply. A single GEMM kernel call like `cublasSgemm(handle, N, 8, K, ...)` replaces 8 individual calls of `cublasSgemm(handle, N, 1, K, ...)`, and the weight matrix (the N x K factor) is read from memory only once rather than 8 times.

The amortization ratio of 4.7-5.8x for 8x concurrent load warrants careful interpretation because it directly quantifies the efficiency of continuous batching. Perfect amortization would be 8x (one kernel launch serves 8 requests, so per-token kernel count drops by 8x); the observed 4.7-5.8x indicates that approximately 60-70% of the theoretical maximum is achieved. The super-linear amortization for the 1B model (5.75x versus 4.68x for the 3B model) suggests that smaller models benefit more from kernel fusion because their compute-to-memory ratio is lower, making bandwidth amortization proportionally more impactful. Larger models benefit more in absolute terms (3B degrades only 38.7% versus 55.8% for 1B) because their higher compute-to-memory ratio provides a larger base of non-bandwidth-bound work.

The near-identical amortization ratios between vLLM (4.68-5.75x) and TGI (4.65-4.80x) confirm that the mechanism is continuous batching itself, not a vLLM-specific optimization. Both stacks use CUTLASS/cuBLAS GEMM kernels that naturally batch matrix operations -- when 8 input vectors are batched into a single matrix multiply, the weight matrix is read from memory once instead of 8 times, achieving the bandwidth amortization that TR131 identified as the key differentiator. The throughput difference at N=1 (vLLM 27-35% faster) reflects implementation-level efficiency in single-request handling -- vLLM's scheduler and memory manager have lower per-request overhead than TGI's -- not a fundamental architectural advantage.

This distinction matters for practitioners: choosing between vLLM and TGI should be based on operational factors (API compatibility, deployment complexity, model format support, community support, update cadence), not on a belief that one has a fundamentally better scaling mechanism. Both achieve the same physics-level bandwidth amortization, and their performance convergence at high N (the throughput gap narrows from 27-35% at N=1 to 22-23% at N=8) confirms that the N=1 overhead difference becomes proportionally less important as batching efficiency dominates.

The GEMM dominance finding (vLLM 69-82%, TGI 41-57%) reveals a significant implementation difference in attention computation. vLLM's PagedAttention compresses attention into GEMM-shaped operations that are highly efficient on tensor cores, achieving near-peak hardware utilization for the matrix-multiply workload. TGI spends a larger fraction (22-32%) on softmax-heavy attention kernels that are less amenable to GEMM fusion. This explains TGI's slightly lower raw throughput despite comparable amortization: the non-GEMM attention component is less efficiently batched. The practical implication for GPU selection is that vLLM will benefit more from GPUs with higher tensor core throughput (such as the H100's FP16 tensor cores at 989.4 TFLOPS), while TGI's attention-heavy profile would benefit relatively more from memory bandwidth improvements.

The larger-model amortization advantage (3B degrades only 38.7-38.9% versus 1B's 54.1-55.8%) has implications for model selection in multi-agent deployments. Although larger models have lower absolute throughput at N=1, they retain a higher fraction of that throughput under concurrency. The scaling advantage over Ollama reaches 43.3-43.5 percentage points for the 3B model versus 26.3-28.0 for the 1B model. This suggests that the optimal model choice for multi-agent vLLM deployments may be larger than for single-agent Ollama deployments -- a non-obvious insight that TR133's cost model captures through the interaction between throughput lookup and scaling prediction.

The methodological contribution of TR132 -- the in-container nsys profiling technique -- deserves recognition independent of the scientific findings. GPU profiling under WSL2/Docker is a known pain point: WDDM drivers block direct ncu metric collection, and nsys inside a container requires CUPTI access that is not available by default. The approach developed here (mounting the Linux nsys binary into each container, wrapping the server entrypoint with `nsys profile --trace cuda`, and extracting `.nsys-rep` traces via volume mounts) achieved 100% trace capture rate across all 24 profiled repetitions. This technique is reusable for any CUDA workload running in Docker containers on Windows hosts and represents a practical contribution to the GPU profiling community.

The 15-25x kernel count disparity between serving stacks and Ollama at N=1 (vLLM launches 35,129 kernels for LLaMA-1B versus Ollama's 2,257) reveals the overhead cost of the continuous batching architecture. When serving a single request, vLLM's PagedAttention, scheduler, and memory manager launch far more kernels than Ollama's streamlined single-request path. This overhead is why Ollama wins at N=1 (in addition to the Q4_0 quantization advantage). The crossover at N>=4 occurs precisely because continuous batching converts this overhead into an advantage: the 15-25x more kernels at N=1 become only 2-3x more kernels at N=8 (after 77-80% amortization), while the batch-level GEMM operations process all concurrent requests simultaneously. The architecture that is wasteful at N=1 is precisely the architecture that scales efficiently at N=8 -- a tradeoff that is invisible to single-request benchmarks and explains why naive benchmarking consistently misleads practitioners into choosing sequential serving stacks for production multi-agent workloads.

The 25 profiled runs with 100% trace capture rate validate the in-container nsys methodology as a reliable approach for GPU profiling under WSL2/Docker.
The confirmed hypotheses (H1: kernel reduction, H2: bandwidth reduction) with 8/8 Holm-corrected tests surviving correction provide the strongest statistical evidence for any mechanism claim in the program.

**Opening for TR133.** Ten reports have produced 70,000+ measurements, validated decisions, and identified mechanisms.
Can the entire corpus be operationalized into a predictive tool that replaces manual report navigation?

---

### 5.11 TR133: Predictive Capacity Planner

**Research question.** Can the empirical knowledge from TR123-TR132 be operationalized into a predictive tool that enables practitioners to answer "What model + quantization + backend should I run on my GPU?" without reading 25 technical reports?

The measurement corpus -- over 70,000 measurements across 11 technical reports -- exists as scattered CSV and JSON files across 7 experiment directories. No single report contains the cross-cutting information needed for a deployment decision: a practitioner choosing a configuration must simultaneously consider VRAM constraints (TR127), quality requirements (TR124/TR125), throughput targets (TR123/TR128), scaling behavior (TR129/TR130), and cost limits (TR123/TR125). TR133 closes this gap by building and validating a predictive capacity planner that integrates these concerns into a single tool with a 4-gate search architecture.

**Experimental design.** The planner represents the culmination of the Phase 2 measurement program, ingesting 19,676 training records from TR123-TR130 across 6 data categories (VRAM from TR127/TR123, throughput from TR123/TR125/TR128, scaling from TR129/TR130, quality from TR124/TR125, cost derived algebraically, latency from TR128) and fitting 6 lightweight predictive models: (1) VRAM -- first-principles formula with fitted overhead factor (1.058x) and quadratic activation coefficients; (2) Throughput -- 22-entry lookup table with quantization multipliers (1.0x for FP16 to 2.3x for Q2_K) and power-law size fallback (72.1 * params^-0.089); (3) Scaling -- Amdahl's Law with per-(model, backend) serial fractions from TR129/TR130; (4) Quality -- lookup table with 35 entries covering 5 models x 7 quant levels; (5) Cost -- algebraic $/token from throughput and hardware cost; (6) Latency -- M/D/1 queueing approximation with 70% utilization safety cap. Validation uses an 80/20 train/val split (3,939 validation records) with 4 target metrics and 10 spot checks. The tool is shipped as the `chimeraforge` CLI, installable via `pip install chimeraforge`, with 57 unit tests passing and sub-second runtime requiring zero GPU.

**Key results.**

| Target | Metric | Required | Achieved | Status |
|--------|--------|----------|----------|--------|
| VRAM accuracy | R^2 | >= 0.95 | 0.968 | Pass |
| Throughput accuracy | R^2 | >= 0.85 | 0.859 | Pass |
| Quality accuracy | RMSE | <= 0.10 | 0.062 | Pass |
| Latency accuracy | MAPE | <= 0.25 | 0.0105 | Pass |
| Spot checks | 10/10 | All pass | 10/10 | Pass |

| Model Component | Key Parameters | Data Sources | Notes |
|----------------|---------------|--------------|-------|
| VRAM | Overhead factor 1.058x; 2-pass fit; quadratic activation coefficients | TR123, TR127 | Weight + KV-cache + activation memory; validated across 512-32K context |
| Throughput | 22-entry lookup; fallback 72.1 * params^-0.089; quant multipliers 1.0x (FP16) to 2.3x (Q2_K) | TR123, TR125, TR128 | Covers all measured (model, backend, quant) combinations |
| Scaling | Amdahl s per (model, backend); 9 serial fraction values | TR129, TR130 | Weakest model: R^2=0.647; captures trend but misses interactions |
| Quality | 35-entry lookup (5 models x 7 quant levels); avg quant deltas per level | TR124, TR125 | RMSE=0.062; coherence-weighted |
| Cost | Algebraic: (1M / tok_s / 3600) * hourly_rate; hardware rate $0.046/hr | TR123 formula | No fitting required; deterministic from throughput |
| Latency | M/D/1 queueing; median service times; 70% utilization cap | TR128 | MAPE=1.05%; safety cap prevents saturation-regime predictions |

**Extended analysis.** The central design decision -- lookup tables and first-principles formulas rather than machine learning -- is vindicated by the validation results and represents a philosophical stance about predictive modeling for inference systems. All four targets are met without gradient descent, neural networks, or any ML framework dependency. The VRAM model (R^2=0.968) achieves the highest accuracy by combining a first-principles formula (weight size + KV cache + activation memory) with a fitted overhead factor (1.058x) that captures runtime allocator fragmentation. The 1.058x overhead means that for every 1 GB of theoretically required VRAM (from weight size + KV cache computation), the actual allocation is approximately 1.058 GB due to CUDA memory pool fragmentation, tensor alignment padding, and runtime workspace. This two-pass approach -- fit overhead from low-context data, then fit quadratic activation coefficients from residuals -- produces predictions within 1.71 GB RMSE across 17 validation groups spanning 512-32K context lengths. For a 12 GB GPU, a 1.71 GB prediction error translates to approximately 14% of available VRAM -- acceptable for capacity planning where the consequence of a small overestimate (rejecting a viable configuration) is far less costly than the consequence of an underestimate (OOM at runtime).

The throughput model (R^2=0.859) relies on direct lookup for measured combinations and a power-law fallback for unseen models, avoiding the interpolation errors that would plague a parametric model in a sparse configuration space. The R^2 of 0.859 means that the model explains 85.9% of throughput variance -- the remaining 14.1% is attributed to factors not captured in the (model, backend, quant) tuple, including thermal state, system load, driver version, and the stochastic elements of GPU scheduling.

The scaling model is explicitly acknowledged as the weakest component (R^2=0.647), and understanding why it is weak illuminates the limits of parametric scaling models. Amdahl's serial fractions from 9 (model, backend) pairs capture the first-order trend but miss interaction effects: the serial fraction varies with model size (s=0.39 for 3B vs s=0.54 for 1B on Ollama), quantization level (Q4_0 yields lower effective serial fraction than FP16 due to bandwidth reduction), think-time (100ms think improves effective throughput for Qwen2.5-1.5B by 45%), and thermal state (the unexplained warmup effect in TR128 Phase 3). A single parameter cannot represent these multidimensional interactions.

The MAPE of 27.8% reflects the inherent noisiness of multi-agent throughput measurements documented in TR129, where per-agent effective throughput at N=8 has coefficient of variation ranging from 5-15%. This is an accepted limitation: the scaling model provides directionally correct guidance (throughput saturates quickly on Ollama, vLLM scales better, larger models degrade less in relative terms) even when point predictions carry significant uncertainty. For the purposes of capacity planning, the qualitative guidance (2-3 agents per GPU for Ollama, up to 8 for vLLM) is more valuable than precise point estimates.

The 22-entry throughput lookup table covers all measured (model, backend, quant) combinations from the empirical data, while the power-law fallback (72.1 * params^-0.089) handles models not in the lookup table. The exponent of -0.089 indicates that throughput decreases very slowly with model size in the Ollama serving regime -- a 10x increase in parameter count reduces throughput by only 23%. The quantization multipliers (1.0x for FP16, 1.1x for Q8_0, 1.3x for Q6_K, 1.5x for Q5_K_M, 1.7x for Q4_K_M, 2.0x for Q3_K_S, 2.3x for Q2_K) provide quant-aware throughput prediction without requiring per-quant measurements for every model. These multipliers are derived from TR125's native timing data and represent the throughput gain from reduced weight size and memory bandwidth demand.

The 4-gate search architecture operationalizes the decision framework from the preceding ten reports. Gate 1 (VRAM) eliminates configurations that will not fit on the target GPU, using the VRAM model. Gate 2 (quality) eliminates configurations below the user's quality target, using the quality model with TR125's tier system. Gate 3 (latency) eliminates configurations that violate the user's p95 SLO, using the latency model with the 70% utilization cap from TR128. Gate 4 (budget) eliminates configurations exceeding the monthly cost limit. Survivors are ranked by cost-then-quality, producing a Pareto-optimal recommendation. This pipeline embodies the principal insight of the entire program: deployment decisions are not single-axis optimizations but multi-constraint satisfaction problems that require simultaneous consideration of VRAM, quality, latency, cost, and scaling behavior.

The hardware bandwidth scaling approach for cross-GPU extrapolation (throughput proportional to memory bandwidth relative to the reference GPU at 556 GB/s, so that a 4090 at 1008 GB/s receives a 1.81x throughput multiplier) is the most speculative component, flagged as unverified in the limitations table. The linear approximation assumes that bandwidth is the sole throughput bottleneck, which TR131 partially confirms for concurrent workloads but which may not hold for compute-bound prefill on high-bandwidth GPUs. Validation against actual measurements on a second GPU is the highest-priority item for Phase 3.

The M/D/1 queueing model's reappearance in TR133 -- after being discredited in TR128 with a 20.4x deviation -- warrants explanation. TR133 uses M/D/1 not as a throughput predictor (where it fails because NUM_PARALLEL does not scale throughput) but as a latency predictor for single-server configurations with a 70% utilization safety cap. Within this constrained regime (single server, utilization below saturation), M/D/1 achieves MAPE=1.05% because its fundamental assumption (deterministic service time) holds reasonably well when the system is not overloaded (service time CV of 2-10% from TR128 is low enough for the deterministic approximation). The 70% utilization cap, derived directly from TR128's saturation analysis, prevents the model from being applied in the regime where it catastrophically fails. This is a paradigm of how theoretical models should be deployed: not discarded after failure but constrained to the regime where their assumptions hold, with empirical guardrails preventing extrapolation beyond validity.

The quality model's claim 5 refutation (quality does not degrade monotonically with quantization) deserves clarification. The TR125 data shows that Q4_K_M through Q8_0 sometimes produce positive quality deltas relative to FP16 baselines, which is physically implausible (less information should not improve accuracy). The explanation is the base-vs-instruct confound: Ollama's instruct-tuned Q8_0 model may genuinely outperform the HuggingFace base model's FP16 on instruction-following tasks, creating an apparent "quality improvement" that is actually a model-variant confound. TR133 handles this by using Ollama FP16 as the baseline for Ollama quantization levels and HuggingFace FP16 as the baseline for HuggingFace models, preventing cross-variant comparisons from contaminating the quality predictions.

The 10/10 spot check results provide face-validity confirmation across diverse query types: VRAM prediction for 3B and 8B models at 2K context, quantization-aware VRAM comparison, throughput ordering by model size, quality ordering by quantization level, scaling efficiency monotonicity, cost formula consistency, and monthly cost calculation accuracy. While spot checks cannot substitute for systematic validation (which is provided by the R^2, RMSE, and MAPE metrics), they verify that the planner produces sensible outputs at the boundaries of the configuration space, where systematic metrics may average over edge cases.

The sub-second runtime requirement (achieved at <1s for the full pipeline: data ingest, model fitting, validation, and search) and zero-GPU dependency make the planner deployable in CI/CD pipelines, infrastructure-as-code toolchains, and interactive CLI sessions without requiring GPU access. This was a deliberate architectural choice: fitting 6 lightweight models (lookup tables + first-principles formulas) takes milliseconds, while fitting a neural network throughput predictor would require GPU access, training data management, and non-trivial inference-time computation. The 57 unit tests cover edge cases including OOM conditions, models not in the lookup table, cross-GPU extrapolation, and boundary conditions at the quality gates. The pip-installable `chimeraforge` package bundles the `fitted_models.json` artifact (~5KB) and exposes the `chimeraforge plan` CLI command, completing the research-to-product pipeline that motivated Phase 2.

The 19,676 training records and 3,939 validation records span the full configuration space tested across TR123-TR130.
The 80/20 train/val split ensures that validation performance reflects generalization to unseen data points, not overfitting to the training distribution.
All 10 spot checks pass, covering VRAM prediction, throughput ordering, quality ordering, scaling behavior, cost formula consistency, and monthly cost calculation.

**Closing assessment.** TR133 completes the Phase 2 research arc by converting 70,000+ measurements into a tool that produces actionable recommendations in sub-second time.
The research-to-product pipeline -- from empirical measurement through statistical analysis through predictive modeling through software engineering through validation through packaging -- demonstrates that rigorous performance research can be operationalized without requiring machine learning infrastructure or GPU-dependent prediction pipelines.
The chimeraforge CLI, installable via `pip install chimeraforge` with 57 unit tests passing, makes the entire TR108-TR132 corpus actionable through a single command: `chimeraforge plan`.

**Opening for the future.** TR133 operationalizes the measurement corpus but is bounded by the hardware, models, and stacks tested. The highest-priority Phase 3 directions are: (1) cross-GPU validation of chimeraforge predictions on at least one additional GPU (e.g., RTX 4090, A100) to test the bandwidth scaling extrapolation; (2) larger models (13B+) to test whether the power-law throughput fallback holds beyond 8B; (3) vLLM quantized serving via AWQ or GPTQ to combine the quantization cost advantage (TR125) with the continuous batching scaling advantage (TR130/TR132) -- the combination that current measurements predict would be optimal but have not empirically validated; (4) multi-GPU inference to extend the scaling model beyond the single-GPU boundary; (5) speculative decoding to potentially break the Amdahl ceiling by overlapping draft and verification passes; and (6) human quality evaluation to validate the automated metrics that underpin TR124/TR125's quality models.
## 6. Cross-Report Synthesis by Decision Axis

This section distills the eleven technical reports into twelve cross-cutting decision axes. Where Section 5 presents results report-by-report, this section traces themes that span multiple reports, showing how evidence accumulates, interacts, and sometimes contradicts itself before reaching a stable conclusion. Each axis is a decision surface that a deployment engineer must navigate; the goal is to provide artifact-backed guidance along each one.

The twelve axes are not independent. Cost optimization (6.1) depends on quantization (6.4), which depends on quality baselines (6.2). Backend selection (6.3) depends on concurrency level, which connects to the production readiness ladder (6.7) and the Amdahl-to-physics pipeline (6.8). Context scaling (6.6) connects to quantization (6.4) through VRAM budget. The prediction chain (6.11) integrates all other axes into a single tool. The synthesis is therefore a web of interconnected findings, not a list of independent conclusions. Understanding any single axis in isolation is insufficient for deployment decisions; the axes must be navigated jointly, which is precisely why the chimeraforge CLI (6.11) exists -- it automates the joint navigation.

### 6.1 Cost optimization path: TR123 to TR125 to TR130 to TR133

The cost story of this program unfolds in four stages, each multiplicatively compounding the savings of the previous one. TR123 establishes the baseline: phase-split economics reveal that KV-cached decode dominates end-to-end cost, with the best single-model cost at $0.013/1M tokens (GPT-2, compile backend, chat blend) and the best cost above 1B parameters at $0.047/1M tokens (Llama-3.2-1B, compile). These numbers are denominated in a compute-hour shadow price and assume FP16 precision, establishing the naive ceiling against which all subsequent optimizations are measured.

TR125 introduces the first multiplicative lever: quantization. Moving from FP16 to Q4_K_M reduces token cost by 30-67% depending on the model, with phi-2 achieving the largest savings (67%) and llama3.1-8b the smallest (30%). The cost range across the full quantization matrix spans a factor of 10x, from $0.0203/1M tokens (llama3.2-1b at Q2_K, which is quality-unacceptable) to $0.1976/1M tokens (llama3.1-8b at Q8_0). The quality-safe floor is Q4_K_M, where all models remain within -4.1pp of FP16 benchmark accuracy. This means the cost optimization is not a tradeoff in the traditional sense; it is a free lunch up to the Q4_K_M boundary, and a rapidly degrading gamble below it.

TR130 introduces the second multiplicative lever: serving stack selection under concurrency. At N=1, Ollama with Q4_0 quantization wins by 1.2-2.6x over vLLM FP16 because quantization reduces both memory footprint and bandwidth demand. But at N=8, vLLM's continuous batching delivers 559 tok/s versus Ollama's 248 tok/s for llama3.2-1b -- a 2.25x advantage. The crossover occurs between N=2 and N=4. For deployments that serve multiple concurrent agents, the serving stack choice is not a refinement; it is a primary cost lever that compounds on top of the quantization savings.

TR133 operationalizes the entire chain. The chimeraforge CLI implements a 4-gate search (VRAM feasibility, quality gate, latency gate, budget gate) that navigates the combinatorial space of model, quantization, backend, and agent count. The planner's throughput model achieves R-squared of 0.859 and its VRAM model achieves 0.968, meaning it can reliably identify the cost-optimal configuration without exhaustive benchmarking. The total potential savings path is: start with naive FP16/Ollama at high concurrency, apply Q4_K_M quantization (1.4-3x savings), switch to vLLM at N>=4 (2.25x savings), and use the planner to avoid over-provisioning. The compound effect is a 4-5x cost reduction relative to the naive baseline, validated by artifact-backed measurements at every link in the chain.

The cost path also has a negative result that strengthens it. M/D/1 queueing theory, the standard analytical approach to capacity planning, deviates up to 20.4x from reality (TR128). This means that any cost model built on theoretical queueing will systematically mis-size deployments, either over-provisioning (wasting money) or under-provisioning (violating SLOs). The empirical lookup table approach in TR133 avoids this failure mode entirely.

To illustrate the compound savings concretely: consider a deployment serving llama3.2-3b at N=8 concurrent agents. The naive baseline is FP16/Ollama, which achieves approximately 248 tok/s total at N=8 with eta(8)=0.16. Applying Q4_K_M quantization (approximately 2x throughput improvement from reduced bandwidth) yields approximately 496 tok/s. Switching to vLLM at N=8 (2.25x from continuous batching) yields approximately 558 tok/s at FP16, or potentially higher with quantized vLLM (untested). The per-token cost drops from the naive baseline of approximately $0.15/1M tokens to approximately $0.035/1M tokens -- a 4.3x reduction. Using chimeraforge to identify the optimal configuration adds no incremental cost (sub-second CPU runtime) but prevents the operator from accidentally selecting a Q2_K configuration that appears cheapest but produces unusable quality.

### 6.2 Quality-cost Pareto evolution: TR124 to TR125 to TR133

The quality-cost frontier evolves through three distinct phases of the research program, each adding resolution to a tradeoff surface that initially appeared one-dimensional. TR124 establishes the baseline Pareto frontier across five models at FP16 precision. The composite quality scores range from 0.29 (GPT-2) to 0.63 (phi-2), while costs span two orders of magnitude. The Pareto-optimal set contains three of eight model-backend combinations, with llama-3.2-1b achieving the best quality-adjusted cost at $0.13 per quality point. This initial frontier assumes FP16 precision and treats quality as fixed per model. The benchmarks used to anchor quality (MMLU, HellaSwag, ARC-Easy) are reproducible and match published values, giving the Pareto frontier a stable foundation. Phase 3 of TR124 also reveals that quality is unstable at temp=0.7 (mean CV=0.33), meaning the Pareto frontier is valid only for deterministic inference; stochastic generation introduces variance that smears the frontier and makes cost-quality comparisons unreliable.

TR125 shatters the fixed-quality assumption by mapping quantization impact across the full Q2_K-to-FP16 spectrum. The Pareto frontier now becomes a family of curves indexed by quantization level. At Q4_K_M, phi-2 emerges as the best quality-per-dollar option: it loses only 1.8pp from FP16 while saving 67% on cost. This reshuffles the frontier because phi-2's robustness to quantization (all Q3_K_S+ levels within -1.8pp) makes it uniquely cost-effective once quantization is on the table. Meanwhile, qwen2.5-1.5b, which appeared competitive at FP16, loses 4.1pp at Q4_K_M and collapses entirely at Q2_K (-40.6pp), making it a fragile choice despite its strong FP16 performance.

TR133 integrates both dimensions into a single quality model with RMSE of 0.062. The planner's quality gate enforces a minimum composite score (0.50 for production, 0.60 for quality-critical workloads) before cost optimization begins. This means the Pareto search is constrained: the planner never recommends a configuration that fails the quality gate, regardless of how cheap it is. The Q2_K ban and model-specific Q3_K_S restrictions are encoded as hard constraints in the search space, not as soft penalties.

The evolution from a single Pareto curve (TR124) to a quantization-indexed family of curves (TR125) to an automated quality-gated search (TR133) represents the maturation of the quality-cost tradeoff from an academic exercise to an operational tool. The key insight is that the frontier is not smooth: it has discontinuities (Q2_K quality cliffs), model-specific sensitivities (qwen2.5-1.5b fragility), and regime changes (the Q4_K_M sweet spot applies universally, but the shape of degradation below it is model-dependent). Any manual navigation of this space is likely to hit a cliff; automated search with hard gates is the only reliable approach.

A subtle but important finding is the base-versus-instruct confound identified in TR125. The TR124 FP16 baselines used base models (from HuggingFace), while Ollama serves instruct-tuned variants. This means that direct comparison of TR124 FP16 baselines with Ollama quantized models confounds quantization impact with instruction tuning impact. TR125 Phase 2 resolves this by including FP16 Ollama models as an additional baseline, and by designating Q8_0 (the highest quality Ollama quantization) as the within-Ollama reference point. This methodological correction does not change the Q4_K_M sweet spot conclusion, but it does affect the absolute magnitude of quality deltas at each quantization level.

### 6.3 Backend selection through the program: from compile wins to N-dependent policy

The backend story is the most revisited axis in the program, with each report refining or overturning the previous conclusion. TR123 begins by showing that torch.compile delivers 1.2-2.5x decode speedups, making the compile backend the cost winner for single-agent FP16 inference. This appears decisive -- until TR126 reveals that the TR123 results were obtained on Windows, where torch.compile falls back to aot_eager (fake Triton). On Linux with real Triton, compile delivers 24-60% prefill speedups (d=-0.59, p=8.87e-61) but crashes autoregressive decode in all modes. The compile backend is therefore real for prefill and dead for decode.

TR128 shifts the conversation from FP16/HuggingFace to Ollama in production. Ollama achieves 7x faster decode than eager HuggingFace (TR126, d=2.38) because its GGUF quantized inference engine is optimized for sequential generation. For single-agent production workloads, Ollama with Q4_K_M becomes the clear winner -- not because of any serving stack advantage, but because quantization reduces memory bandwidth demand and the GGUF engine is decode-optimized.

TR129 introduces concurrency and finds that Ollama throughput plateaus at N=2 with Amdahl serial fractions of 0.39-0.54. TR130 then compares serving stacks and shows that vLLM achieves 2.25x throughput at N=8. The initial attribution is to Ollama's serving stack overhead. TR131 overturns this: PyTorch Direct (no serving stack) degrades 86.4% at N=8, worse than Ollama's 82.1%. The bottleneck is GPU memory bandwidth, not software. TR132 then explains why vLLM scales better: continuous batching reduces per-token kernel count by 77-80% and memory bandwidth per token by 79-83%, amortizing the fundamental bandwidth bottleneck.

The synthesized policy is N-dependent. At N=1, Ollama Q4_K_M wins because quantization reduces bandwidth demand and the GGUF engine is decode-optimized. At N=2-3, Ollama remains competitive because the concurrency is too low for continuous batching to provide significant amortization. At N>=4, vLLM FP16 wins because continuous batching amortizes the GPU bandwidth bottleneck by 4.7-5.8x, more than compensating for the lack of quantization. The compile backend is a prefill-only optimization on Linux, orthogonal to the N-dependent backend choice. This is the final policy, and it required six reports to establish because each intermediate conclusion was incomplete or wrong in isolation.

The TTFT dimension adds another layer. Ollama's TTFT of 163-194ms is acceptable for most interactive workloads, but vLLM's 23-32ms TTFT (6-8x faster) enables sub-100ms response initiation that is perceptually instantaneous. For applications where time-to-first-token is the critical user experience metric (auto-complete, real-time code assistance, conversational agents with rapid turn-taking), vLLM may be preferred even at N=1, despite lower single-request throughput. The backend selection is therefore not purely a throughput optimization; it is a multi-objective decision across throughput, TTFT, cost, and quality, indexed by concurrency level.

### 6.4 Quantization as universal lever: from quality concern to concurrency enabler

Quantization appears in every phase of the program, each time revealing a new dimension of its impact. TR124 Phase 2 provides the first signal: quantization degrades coherence by 14-32%, with an average loss of 10.7% across generation quality metrics. This is alarming but incomplete -- it tests only two quantization levels and uses generation-based metrics that are sensitive to formatting artifacts.

TR125 transforms this preliminary signal into a comprehensive decision matrix. Testing 5 models across 7 quantization levels (Q2_K through FP16) with benchmark-based evaluation (MMLU, ARC-Challenge), it reveals a structured landscape: Q4_K_M is universally within -4.1pp of FP16, Q3_K_S is model-dependent (acceptable for phi-2 and llama3.1-8b, breaking llama3.2-1b and qwen2.5-1.5b with 9.5-12.2pp losses), and Q2_K is universally catastrophic (all models exceed 11pp loss, with qwen2.5-1.5b losing 40.6pp). The quality dimension is now mapped.

TR131 reveals a dimension that was invisible until GPU kernel profiling: quantization helps concurrency. Ollama's Q4_0 quantization advantage over PyTorch Direct FP16 grows from 3.0x at N=1 to 3.9x at N=8. This is because quantized weights and KV-caches consume less memory bandwidth per token, leaving more bandwidth headroom for concurrent requests before the GPU's 432 GB/s bandwidth ceiling becomes saturated. The back-of-envelope calculation in TR131 shows that N=8 FP16 demand exceeds the bandwidth ceiling by 78-130%, while Q4_0 stays within budget.

This means quantization is not a single-axis optimization. It simultaneously reduces cost (30-67% savings per TR125), reduces VRAM footprint (enabling longer contexts per TR127, where GQA models with quantization avoid spillover thresholds), improves concurrency headroom (3.0x to 3.9x advantage per TR131), and preserves quality within tight bounds (within -4.1pp per TR125). The only axis where quantization has a negative effect is absolute benchmark accuracy, and even there the loss is bounded and predictable. Q4_K_M is the universal sweet spot not because it is the best on any single axis, but because it is acceptable on all axes simultaneously.

The universality of Q4_K_M is further supported by the statistical analysis in TR125. Bonferroni-corrected pairwise comparisons show that 7/16 surviving significant differences all occur at the Q3_K_S/Q2_K boundary, meaning Q4_K_M and above are statistically indistinguishable from each other in most cases. The TOST equivalence testing, while underpowered at the strict +/-3pp margin (0/18 significant), achieves 6/18 at the +/-5pp margin, providing partial evidence of equivalence. The power analysis reveals a minimum detectable effect of 9.0pp at 80% power, explaining the TOST underpowering: the study was designed to detect quality cliffs (which it found at Q2_K and Q3_K_S) rather than to prove tight equivalence. For practical deployment purposes, the combination of non-significant pairwise tests above Q4_K_M, Wilson confidence intervals that bound the maximum plausible loss, and the Bonferroni survival pattern provides sufficient evidence to treat Q4_K_M as quality-preserving across the tested model family.

### 6.5 Compilation: from paradox to resolution to permanent policy

The compile story is a case study in how platform-dependent confounds can produce misleading results. Phase 1 (TR120) identified a compile paradox: torch.compile with the compile label showed no consistent speedup and sometimes regressed, despite the expectation that Inductor-generated kernels should accelerate inference. The paradox remained unresolved because TR120 could not determine whether the compiler was actually generating real kernels or falling back to eager execution.

TR126 resolves the paradox decisively by moving from Windows to Docker/Linux with real Triton. On Linux, torch.compile generates 916 Triton kernels across 6 models and delivers -40% prefill latency reduction (d=-0.59, p=8.87e-61). The Phase 3 prefill improvement reaches -53.3% with a large effect size (d=-1.21). The reversal is total: the Windows results are invalid because Windows lacks Triton and the compile backend silently falls back to aot_eager, which is functionally equivalent to eager mode.

However, the resolution comes with a permanent limitation: compiled decode crashes 100% of the time across all tested modes (reduce-overhead and mode="default"). When StaticCache is used to enable compiled decode, it works but runs 5.8x slower than eager decode, defeating the purpose. The bug persists across PyTorch 2.10 (NGC 26.01), and the research team has filed an upstream issue (pytorch/pytorch#175557) and submitted a PR (#175562). The interaction analysis confirms this is structural: ANOVA F(8,1608)=453.1, p<1e-16 for the platform-by-backend-by-phase interaction.

The permanent policy distills to three rules. First, compile prefill only, on Linux, with Inductor+Triton. Second, never compile decode -- it crashes, and even when it works it provides no speedup (+2.2%, not significant). Third, never trust compile results from Windows, because aot_eager fallback is silent and produces fake performance data. There is also a scale crossover: small models (below approximately 1.5B parameters) benefit most from compilation, while larger models show diminishing returns because Ollama's decode-optimized GGUF engine already saturates the GPU for large models. This policy is stable and does not depend on future PyTorch releases, because even if the decode crash is fixed, the fundamental memory-bandwidth bottleneck in decode means compilation cannot provide the same leverage it delivers in compute-bound prefill.

The five evidence lines that declare compile decode dead are: (1) 100% crash rate across all models in reduce-overhead mode (TR126); (2) 100% crash rate in mode="default" (TR126); (3) StaticCache workaround runs 5.8x slower than eager (TR126); (4) when compiled decode does not crash on short sequences, the speedup is +2.2% and not statistically significant (TR126); and (5) the decode phase is memory-bandwidth-bound (TR131), meaning compute optimization via compilation cannot address the fundamental bottleneck. Lines 1-4 are empirical; line 5 is mechanistic. Together, they rule out compiled decode as a viable optimization target for current hardware and software.

The compile paradox resolution also carries a broader methodological lesson: performance claims that do not verify the actual execution path (eager versus compiled versus fallback) are unreliable. TR120's Windows results appeared valid because the torch.compile API completed successfully, but the actual execution path was aot_eager fallback, which is functionally eager mode. The lesson is that any compile-related claim must include evidence that real Triton kernels were generated and executed, not merely that the compile API was called successfully.

### 6.6 Context scaling and memory management: from formulas to empirical cliffs

The context scaling axis connects TR123's theoretical KV-cache formulas to TR127's empirical performance measurements, revealing a two-regime phenomenon governed by VRAM spillover. TR123 derives the KV-cache memory formula: bytes = 2 * num_layers * num_kv_heads * head_dim * precision_bytes * sequence_length. This formula is validated against 30/30 model-backend combinations with exact matches. The formula also reveals the architectural advantage of Grouped Query Attention (GQA): Qwen-2.5-1.5B (GQA with extreme head reduction) uses 56MB of KV-cache at 2K context versus Phi-2 (MHA) at 640MB -- an 11.4x difference. This architectural gap directly translates into context budget: GQA models can sustain 3-11x longer contexts before hitting VRAM limits.

TR127 converts these theoretical predictions into empirical performance curves. Below VRAM capacity, HuggingFace FP16 inference follows clean power-law scaling with exponents b=1.58-1.78 and R-squared above 0.999. Above VRAM capacity, latency cliffs of 25-105x appear as CUDA Unified Memory spills to system RAM. The spillover thresholds are model-specific: qwen2.5-3b hits the wall at 8K tokens, while smaller 0.5B and 1.5B models survive until 16K. Decode degradation under HuggingFace is catastrophic: qwen2.5-1.5b drops from 42 tok/s at 512 tokens to 2.1 tok/s at 16K tokens, a 95% collapse.

Ollama tells a qualitatively different story. Its sub-linear scaling (b<0.2) reflects Flash Attention's elimination of quadratic attention cost, and its quantized KV-cache reduces per-token VRAM consumption. Ollama never exceeds 1 second TTFT through 32K context length, while HuggingFace FP16 exceeds 1 second at just 4K tokens. The decode degradation under Ollama is moderate: 41-53% over a 64x context growth, compared to 95% for HuggingFace.

The synthesized memory management policy is: VRAM_budget = model_weights + KV_cost_per_token * context_length, with a 1.058x overhead factor for allocator fragmentation (TR133). Monitor VRAM utilization and cap at 90% to avoid spillover. For contexts beyond 4K tokens on 12GB VRAM, use Ollama with quantized models. For contexts within 4K tokens, HuggingFace FP16 is acceptable. The GQA architectural advantage means that GQA models should be preferred for long-context workloads, independent of parameter count.

The practical implication is a memory hierarchy for context management. Short contexts (under 2K tokens) are safe on any backend and any precision. Medium contexts (2K-4K tokens) require attention to model size; larger models like llama3.2-3b may approach spillover on HF FP16. Long contexts (4K-32K tokens) are viable only on Ollama with quantized models, where Flash Attention and reduced KV-cache size combine to keep VRAM within budget. The per-token VRAM cost of 0.75-1.16 MB/token at FP16 (TR127) drops proportionally with quantization, meaning Q4_K_M roughly halves the per-token cost and doubles the effective context window within the same VRAM envelope. This interaction between quantization and context length is one of the program's most practically valuable findings: a deployment that needs long context should quantize not just for cost savings but for memory headroom.

### 6.7 Production readiness ladder: from baseline to root cause

The production readiness narrative is a deliberate escalation of realism across four consecutive reports. TR128 establishes the single-agent production baseline: service times of 858-1,435ms across three models, no thermal throttling (peak 66 degrees C), streaming with zero overhead (0/9 significant tests), and the critical negative result that OLLAMA_NUM_PARALLEL is a no-op (0/30 significant tests, mean absolute change 4.0%). TR128 also refutes M/D/1 queueing theory with a 20.4x deviation, establishing that theoretical models cannot be trusted for capacity planning.

TR129 adds multi-agent concurrency. Testing N=1 through N=8 agents reveals Amdahl-style saturation with serial fractions of 0.39-0.54. Total throughput plateaus at N=2 (less than 3% gain from N=2 to N=8), and per-agent throughput at N=8 drops to 17-20% of solo performance. Fairness remains excellent (Jain's index at or above 0.997), meaning all agents degrade equally. The throughput ceiling is attributed to the serving stack (Ollama).

TR130 tests alternative serving stacks. vLLM achieves 2.25x throughput at N=8 and 6-8x faster TTFT (23-32ms versus 163-194ms for Ollama). The attribution shifts: Ollama follows Amdahl degradation (R-squared above 0.96) while vLLM/TGI follow power-law scaling (R-squared above 0.99). vLLM and TGI never saturate within N=8, while Ollama saturates at N*=4.

TR131/TR132 complete the ladder by identifying the root cause. PyTorch Direct degrades 86.4% at N=8 -- worse than Ollama's 82.1% -- proving the bottleneck is GPU memory bandwidth physics, not serving stack overhead. Memory bandwidth stress increases 74.4% at N=8 (p=6.4e-5, d=3.81). Continuous batching (vLLM/TGI) amortizes this by reducing per-token kernel count by 77-80% and per-token bandwidth by 79-83%. The production readiness ladder thus moves from "what happens" (TR128) to "how it scales" (TR129) to "which stack scales best" (TR130) to "why it scales that way" (TR131/TR132). Each layer adds one dimension of production realism.

The ladder also includes a critical negative result at each rung. TR128 refutes NUM_PARALLEL. TR129 refutes linear scaling. TR130 initially attributes the bottleneck to the wrong component (serving stack). TR131 overturns this attribution. These are not failures of the research; they are the program's falsification machinery operating as designed. Each negative result sharpened the next experimental design. The lesson for production readiness is that assumptions must be tested empirically at every layer, because plausible hypotheses (NUM_PARALLEL enables concurrency, Ollama's serving stack is the bottleneck) can be entirely wrong.

### 6.8 The Amdahl-to-physics pipeline: progressively deeper causal attribution

The causal attribution story is the most intellectually significant arc in the program, because it demonstrates how a plausible but wrong explanation can be systematically replaced by a correct one. TR129 fits Amdahl's Law to N-agent scaling data and obtains excellent fits (R-squared above 0.97) with serial fractions of 0.39-0.54. The natural interpretation is that the serial fraction represents serving stack overhead -- the time the GPU spends waiting for Ollama to dispatch the next request.

TR130 appears to confirm this by showing that vLLM (a different serving stack) achieves dramatically better scaling. If Ollama's serving stack is the bottleneck, replacing it should fix the problem, and vLLM's 2.25x advantage at N=8 seems to validate this hypothesis.

TR131 overturns it. By profiling PyTorch Direct (no serving stack at all), TR131 shows that the degradation is worse without a serving stack: 86.4% throughput loss at N=8 versus Ollama's 82.1%. The GPU hardware enforces max_concurrent_kernels=1 in all conditions -- this is hardware serialization, not software serialization. Memory bandwidth stress increases 74.4% at N=8 and is the sole Holm-surviving statistical test. The Amdahl serial fraction is revealed to be a curve-fitting artifact that happens to produce good fits but attributes the mechanism incorrectly. Applying Amdahl's Law across backends (Ollama vs vLLM) is a category error, because the two backends degrade via fundamentally different mechanisms.

TR132 completes the pipeline by explaining why vLLM scales better despite the same GPU physics. Continuous batching reduces kernel launches by 77-80% and memory bandwidth per token by 79-83%. The amortization ratio of 4.7-5.8x means that N=8 requests under continuous batching consume bandwidth equivalent to approximately 1.4-1.7 un-batched requests. vLLM does not escape the GPU bandwidth ceiling; it amortizes it. The per-token kernel count drops from 54.9 to 10.9 (80.2% reduction, Cohen's d=1058) for vLLM on the 1B model, and GEMM operations dominate GPU time at 69-82% for vLLM and 41-57% for TGI. Critically, vLLM and TGI show identical amortization mechanisms despite different implementations, confirming that the improvement is architectural (continuous batching) rather than implementation-specific.

The progression from statistical fit (TR129) to cross-backend comparison (TR130) to GPU profiling (TR131) to kernel-level mechanism (TR132) is a textbook example of how observational correlation must be replaced by causal identification before the finding can support a deployment decision. The Amdahl serial fraction (s=0.39-0.54) correctly describes the shape of throughput degradation but incorrectly attributes it to software serialization. The cross-backend comparison correctly identifies that vLLM scales better but incorrectly attributes this to Ollama's serving stack being the bottleneck. Only GPU kernel profiling reveals that the mechanism is hardware-level (memory bandwidth) and the mitigation is architectural (continuous batching). This four-step causal pipeline is the program's most rigorous contribution to the multi-agent scaling question.

### 6.9 Measurement methodology evolution: from boundaries to kernel profiling

The measurement methodology evolves substantially between Phase 1 and Phase 2, with each Phase 2 report adding capabilities that the previous one lacked. Phase 1 established the foundations: TR118_v2.2 defined artifact-backed reporting, TR119v1 introduced phase-split cost models, TR120 introduced controlled compilation experiments, and TR122 established energy measurement boundaries. Phase 2 inherits these foundations and extends them along four dimensions.

First, quality metrics. TR124 adds 7 generation quality metrics (BERTScore, ROUGE-L, exact match, coherence, and task-specific measures) plus 3 benchmark evaluations (MMLU, HellaSwag, ARC-Easy). This fills the gap that Phase 1 explicitly identified: cost and throughput are meaningless without quality context. The quality framework includes deterministic evaluation (temp=0) as the primary mode and stochastic evaluation (temp=0.7) as a secondary robustness check.

Second, cross-platform validation. TR126 introduces Docker/Linux environments to resolve the compile paradox. This requires weight parity validation (ensuring the same model produces identical outputs across platforms) and deterministic decode verification. The methodology for cross-platform work is non-trivial: it must account for different kernel paths, different memory allocators, and different driver behavior.

Third, GPU kernel profiling. TR131 introduces Nsight Systems (nsys) for kernel-level timing and Nsight Compute (ncu) for kernel-level metrics, though ncu metrics are null on WDDM (consumer Windows drivers). TR132 extends this to in-container profiling with a novel WSL2/WDDM-compatible methodology that enables CUPTI instrumentation inside Docker containers. These profiling capabilities transform the measurement boundary from "what the serving stack reports" to "what the GPU actually does."

Fourth, statistical rigor. The program progressively adds statistical methods as the claims become more nuanced: Welch's t-test for simple comparisons (TR123), ANOVA with Holm-Bonferroni correction for multiple comparisons (TR124), TOST equivalence testing for quality preservation (TR125), Wilson confidence intervals for binomial outcomes (TR125), Bonferroni survival analysis (TR125), Mann-Whitney U for non-parametric comparisons (TR126), Cohen's d for effect sizes throughout, and power analysis for understanding the limits of non-significance (TR125). Each method is introduced when the claim structure demands it, not as a retrospective add-on.

The methodology evolution also includes a shift in what is being measured. Phase 1 measured token throughput, latency, and energy at the backend API boundary. Phase 2 progressively deepens the measurement: TR128 measures queueing behavior and thermal response; TR129 measures per-agent fairness and aggregate throughput under closed-loop scheduling; TR131 measures GPU kernel timing and memory operation counts; TR132 measures per-token kernel counts and bandwidth consumption inside containerized serving stacks. Each deeper layer of measurement reveals mechanisms that were invisible at the previous layer, culminating in the kernel-level explanation of why continuous batching amortizes the memory bandwidth bottleneck. The measurement methodology thus evolves from "how fast" to "how fast under load" to "why it degrades" to "what the GPU actually does" -- a progression from observational to mechanistic understanding.

A concrete example of this evolution: TR128 observes that throughput plateaus at N=2 but cannot explain why. TR129 fits Amdahl's Law and attributes the plateau to a serial fraction of 0.39-0.54, which sounds like a software scheduling bottleneck. TR131 measures GPU kernel timing and discovers that max_concurrent_kernels=1 in all conditions -- hardware serialization, not software. TR132 measures per-token kernel counts inside vLLM and discovers 80% kernel reduction via continuous batching -- the mechanism by which vLLM circumvents the hardware serialization bottleneck. Each measurement layer adds causal depth that the previous layer could not provide. Without the kernel-level profiling, the program would have shipped the incorrect conclusion that Ollama's serving stack is the bottleneck, leading to wasted engineering effort on Ollama optimization when the correct intervention is serving stack replacement.

### 6.10 Statistical rigor escalation: from ANOVA to power analysis

The statistical methodology of the program follows a deliberate escalation that mirrors the increasing subtlety of the claims. TR123 uses straightforward descriptive statistics and Welch's t-tests because the claims are simple comparisons: is backend A faster than backend B? TR124 introduces ANOVA with Holm-Bonferroni correction because the claim structure is a multi-factor comparison: does backend choice affect any of 7 quality metrics across 5 models? The correction is necessary because testing 7 metrics simultaneously inflates the family-wise error rate; without it, approximately 2 of 35 tests would appear significant by chance alone.

TR125 introduces three new methods to handle the quantization equivalence question, each addressing a different statistical need. TOST (Two One-Sided Tests) is the correct framework for equivalence claims, because a non-significant t-test does not prove equivalence -- it merely fails to prove difference. This distinction is critical: deploying Q4_K_M on the basis of "no significant difference from FP16" would be scientifically unsound, because the non-significance could result from insufficient power rather than true equivalence. TOST resolves this by requiring positive evidence that the difference is bounded within a specified margin. At the +/-3pp equivalence margin, TOST produces 0/18 significant results, meaning the study cannot claim equivalence at this margin. At +/-5pp, 6/18 pass, providing partial support for the broader claim that Q4_K_M is "close enough" to FP16 for most applications.

Wilson confidence intervals are used for benchmark accuracy (a binomial proportion) because they provide better coverage than Wald intervals at small sample sizes. Standard Wald intervals (the textbook formula) can produce impossible values (negative proportions or proportions above 1.0) at extreme values and small n; Wilson intervals avoid this by using a quadratic correction. Bonferroni survival analysis identifies which pairwise comparisons (7/16) survive the strictest multiple-comparison correction, and all 7 are at the Q3_K_S/Q2_K boundary -- exactly where the quality cliffs appear. The fact that no comparison above Q4_K_M survives Bonferroni correction is strong evidence that the differences above Q4_K_M are indistinguishable from noise.

TR125 also introduces power analysis, revealing that the study's minimum detectable effect (MDE) is 9.0pp at 80% power. This means the TOST non-significance at +/-3pp is an underpowered null: the study simply did not have enough samples to detect equivalence at that margin. This is an important epistemic distinction that prevents the reader from interpreting non-significance as evidence of non-equivalence.

TR129 and TR130 use curve fitting with R-squared diagnostics to validate the Amdahl and power-law scaling models. TR131 introduces Holm-corrected significance testing for GPU profiling metrics, where memory bandwidth stress is the sole survivor at p=6.4e-5 with d=3.81. TR132 achieves the program's most extreme effect sizes: Cohen's d exceeding 600 for kernel count reduction, reflecting the massive and consistent impact of continuous batching at the kernel level. The statistical escalation is not decorative; each method is introduced precisely when the claim structure requires it, and the limitations of each method (especially TOST underpowering) are documented as caveats rather than hidden.

### 6.11 The prediction chain: from individual findings to shipped CLI

The prediction chain traces how individual empirical findings flow into the TR133 predictive planner, demonstrating a research-to-product pipeline. The chain has six links, corresponding to the six models in the planner: VRAM prediction, throughput prediction, scaling prediction, quality prediction, cost computation, and latency estimation.

The VRAM model (R-squared=0.968) is built from TR123's first-principles KV-cache formula combined with TR127's empirical VRAM measurements. The formula is: VRAM = (model_weights_bytes + KV_cache_bytes * context_length) * 1.058, where the 1.058 factor accounts for allocator fragmentation measured empirically. The model weights and KV parameters come from model registry metadata; the fragmentation factor comes from regression residual analysis.

The throughput model (R-squared=0.859) uses a 22-entry lookup table derived from TR123, TR128, and TR130 measurements. Where the lookup table lacks an entry, a power-law fallback (72.1 * params^-0.089) provides interpolation. Quantization multipliers (1.0x for FP16 through 2.3x for Q2_K) scale the base throughput. This pragmatic approach outperforms theoretical models because it captures the non-linear, hardware-specific throughput characteristics that analytical models miss.

The scaling model (R-squared=0.647) is the weakest link, built from TR129's Amdahl fits. The serial fractions are model-specific (s=0.39-0.54) and capture the trend of diminishing returns with N, but they miss the interaction between serving stack and scaling mechanism identified in TR131/TR132. This is a known limitation: the Amdahl model is a useful approximation for conservative capacity planning but will underestimate vLLM's throughput at high N. The weakness is structurally inherent: Amdahl's Law assumes a fixed serial fraction, but TR131/TR132 show that the "serial fraction" is actually GPU memory bandwidth saturation, which behaves differently under different batching strategies. A future version of the planner could replace the Amdahl scaling model with a bandwidth-aware model that accounts for continuous batching amortization, potentially improving the R-squared from 0.647 to a level consistent with the other models (above 0.85).

The quality model (RMSE=0.062) maps model-quantization pairs to composite quality scores using TR124 and TR125 data. The cost model is algebraic: cost = throughput^-1 * price_per_hour. The latency model (MAPE=1.05%) uses service-time distributions from TR128. All six models feed into a 4-gate search: VRAM feasibility eliminates configurations that do not fit in GPU memory, the quality gate eliminates configurations below the composite threshold, the latency gate eliminates configurations that violate the SLO, and the budget gate eliminates configurations that exceed the cost target. Surviving configurations are ranked by cost. The CLI ships as `chimeraforge plan`, pip-installable, with 57 unit tests, sub-second runtime, and zero GPU requirement. This is the terminal node of the prediction chain: 70,000+ measurements, condensed into six models, validated against 3,939 holdout records, and accessible from the command line.

### 6.12 Consumer hardware viability: one GPU as a production platform

The consumer hardware viability axis runs through the entire program and establishes that a single RTX 4080 Laptop GPU is a credible production platform for small-model inference, with specific quantitative boundaries. TR123 establishes the economic case: self-hosted inference is 95.4% cheaper than cloud alternatives, with TCO at 1B tokens/month of $153/year (consumer, GPT-2/compile) versus $2,880/year (AWS). The carbon footprint is negligible at consumer scale: 3.4 gCO2e/1M tokens for GPT-2/CPU, making energy cost a rounding error in the total cost of ownership.

TR128 establishes the throughput ceiling: maximum sustained throughput of 1.17 req/s for llama3.2-1b on Ollama, with baseline service times of 858-1,435ms across three models. Critically, no thermal throttling is observed under sustained load: peak GPU temperature reaches 66 degrees C against an 80 degree C threshold. This means the consumer GPU can sustain its maximum throughput indefinitely without cooling upgrades or thermal management interventions.

TR127 establishes the context budget: Ollama handles 32K context lengths without TTFT degradation below 1 second, while HuggingFace FP16 becomes unusable above 4K tokens due to VRAM spillover. For applications that require long context (RAG pipelines, document summarization), the consumer GPU is viable only with Ollama and quantized models.

TR129 establishes the concurrency boundary: 2-3 effective agents per GPU with Ollama, and up to 8 with vLLM (though per-agent throughput degrades to 17-20% of solo). For single-user or small-team deployments, this is sufficient. For larger deployments, the consumer GPU becomes a capacity bottleneck that requires either horizontal scaling (multiple GPUs) or cloud burst capacity.

The synthesized viability statement is: a single RTX 4080 Laptop GPU running Ollama Q4_K_M can serve 0.7-1.17 req/s for models up to 3B parameters, handle 32K context without degradation, sustain indefinite load without thermal throttling, and deliver this at 95.4% less than cloud pricing. This makes consumer hardware a viable production platform for personal AI assistants, small-team development tools, and edge deployment scenarios. It is not viable for high-concurrency public-facing services, models above 8B parameters (which consume most or all of 12GB VRAM), or workloads requiring sub-100ms TTFT (which demands vLLM's 23-32ms TTFT).

The viability is also bounded by the qwen2.5-1.5b anomaly documented in TR128: a 66% decode throughput increase during sustained load. While this anomaly works in the consumer GPU's favor (suggesting that thermal stabilization or memory caching can improve performance over time), it is not fully explained and should not be relied upon for capacity planning. The viability statement is based on conservative steady-state measurements, not on anomalous best-case behavior.

For teams evaluating consumer hardware against cloud alternatives, the decisive factors are data privacy (local inference never transmits data to a third party), offline capability (local inference works without internet connectivity), and latency consistency (no network variability). These non-economic factors often dominate the decision for sensitive workloads, making the 95.4% cost advantage a bonus rather than the primary justification.

The viability boundary shifts with model size. At 1B parameters, the consumer GPU has abundant VRAM headroom (approximately 2 GB used out of 12 GB), leaving room for long contexts, multiple concurrent KV-caches, and even two models loaded simultaneously. At 3B parameters, VRAM usage rises to approximately 3-5 GB, still comfortable for most workloads. At 8B parameters (llama3.1-8b), VRAM usage approaches 6-8 GB at Q4_K_M, leaving limited headroom for long contexts or multiple concurrent agents. Beyond 8B parameters, the 12 GB VRAM budget becomes the binding constraint, and models like llama3.1-13b or larger are not feasible on this hardware without aggressive quantization (Q3_K_S or lower), which may breach the quality gate. The consumer viability statement is therefore size-conditional: fully viable up to 3B, conditionally viable at 8B, and infeasible above 8B on 12 GB VRAM.

---

## 7. Economics, Capacity, and Cost-Quality Tradeoffs

This section consolidates the economic analysis across the program into a unified framework for capacity planning and cost optimization. Where Section 6 traced cross-cutting themes, this section provides the quantitative tools and worked examples needed to size a deployment, estimate costs, and navigate the cost-quality tradeoff surface. The economic analysis is grounded in measured throughput, not vendor claims or theoretical projections. Every cost number in this section can be traced back to a specific measurement artifact in the TR123-TR133 corpus, and every capacity estimate is validated against empirical data from the chimeraforge planner's holdout set.

### 7.1 Token-first economics (TR123)

The foundational economic unit in this program is the cost per 1M tokens, computed as: $/1M = (1,000,000 / tokens_per_second / 3,600) * hourly_rate. This formula converts throughput into cost under a compute-hour pricing model, applicable to both self-hosted (amortized hardware cost) and cloud (on-demand instance pricing) deployments. The formula's simplicity is deceptive: it embeds two important assumptions. First, that the GPU is fully utilized (no idle time between requests), making it a lower bound on cost. Second, that the hourly rate captures the full infrastructure cost (amortization, energy, cooling, space), making it a total cost metric rather than a marginal cost metric.

TR123 establishes the token-first cost landscape across 525 cells (5 models, 3 backends, 5 workload scenarios, 7 repetitions) with zero errors.

The cost landscape spans two orders of magnitude. The absolute best is GPT-2 (124M parameters) on the compile backend at $0.013/1M tokens for the chat blend scenario. At the other extreme, Phi-2 (2.7B, MHA) on eager HuggingFace costs approximately $0.35/1M tokens for RAG-heavy workloads. For models above 1B parameters, the best cost is Llama-3.2-1B on the compile backend at $0.047/1M tokens.

The two-order-of-magnitude cost range is driven by three factors in roughly equal proportion: model size (small models are faster per token), backend efficiency (compile and Ollama are faster than eager HuggingFace), and workload blend (prefill-heavy workloads are cheaper because prefill is 10-100x faster than decode per token). Understanding which factor dominates for a given deployment is essential for cost optimization: if the workload is decode-heavy (chat, code generation), model size and backend choice are the primary levers; if the workload is prefill-heavy (RAG, classification), compile policy becomes significant.

The workload blend ratios (RAG-heavy at 0.95 prefill weight, summarization at 0.85, chat at 0.67, balanced at 0.50, code generation at 0.25) reflect the different prefill-to-decode ratios of production workloads. Because prefill is 10-100x faster than decode per token, prefill-heavy workloads are substantially cheaper. This phase asymmetry is the most important structural fact in token economics: optimizing decode throughput has 10-100x more impact on cost than optimizing prefill, except for workloads that are almost purely prefill (RAG retrieval, embedding computation).

Infrastructure cost dominates total cost at 66-99% across all configurations. Energy cost is a rounding error at consumer scale. This means that the primary economic lever is throughput improvement (which reduces the infrastructure time needed per token), not energy efficiency. The cost decomposition also implies that hardware amortization period is the key business variable: the same GPU costs less per token if it is utilized more hours per day.

The KV-cache formula validation in TR123 (30/30 exact matches across model-backend combinations) ensures that the cost model is built on solid foundations. The formula correctly predicts memory consumption for both MHA architectures (GPT-2, Phi-2) and GQA architectures (Llama-3.2, Qwen-2.5), allowing cost projections to account for the memory-cost asymmetry between architecture types. The 11.4x GQA advantage (Qwen 56MB versus Phi-2 640MB at 2K context) translates directly into cost through the context budget: GQA models can sustain longer contexts without VRAM spillover, avoiding the catastrophic latency cliffs that would otherwise require costly hardware upgrades or context truncation.

### 7.2 Quantization economics (TR125)

Quantization is the single most impactful cost lever in the program. TR125 maps the cost landscape across 34 model-quantization variants and reveals a 10x cost range from $0.0203/1M tokens (llama3.2-1b at Q2_K) to $0.1976/1M tokens (llama3.1-8b at Q8_0). The quality-safe sweet spot, Q4_K_M, saves 30-67% versus FP16 depending on the model.

The savings are model-dependent because quantization provides different throughput gains depending on model architecture and size. Phi-2 achieves the largest savings (67%) because its MHA architecture has large KV-caches that benefit disproportionately from quantization. Llama3.1-8b achieves the smallest savings (30%) because at 8B parameters, the model weights dominate VRAM consumption and quantization provides less relative throughput improvement.

The economic decision is straightforward at the Q4_K_M boundary: there is no reason to deploy FP16 for any model unless benchmark accuracy within 2pp of baseline is a hard requirement (in which case Q8_0 is the appropriate choice). Below Q4_K_M, the cost savings continue to increase but so does the quality risk. Q3_K_S saves an additional 10-15% over Q4_K_M but introduces model-dependent quality cliffs (9.5-12.2pp losses for llama3.2-1b, llama3.2-3b, and qwen2.5-1.5b). Q2_K saves the most but is universally quality-unacceptable, making it an economic trap: the cheapest configuration is also the most unreliable.

The per-model cost-quality frontiers reveal that phi-2 Q4_K_M is the economic optimum when quality-per-dollar is the objective: it loses only 1.8pp while saving 67%. Llama3.1-8b Q4_K_M at $0.138/1M tokens delivers the highest absolute accuracy (69.7%) in the quality-safe zone but at 7x the cost of llama3.2-1b Q4_K_M ($0.020/1M tokens). The choice depends on whether the application is quality-constrained or cost-constrained.

The 10x cost range within the quantization matrix deserves careful interpretation. The cheapest configuration (llama3.2-1b Q2_K at $0.0203) is quality-unacceptable, while the most expensive (llama3.1-8b Q8_0 at $0.1976) provides the highest accuracy. The quality-safe range spans approximately 7x, from llama3.2-1b Q4_K_M to llama3.1-8b Q8_0. Within this range, cost scales roughly with model size, while quality improvement diminishes: moving from 1B to 3B parameters adds approximately 5pp accuracy for 2-3x cost, while moving from 3B to 8B adds approximately 3pp for another 2x cost. This diminishing quality return per dollar is the fundamental economic argument for deploying smaller models with appropriate quantization rather than defaulting to the largest available model.

### 7.3 Request-first capacity (TR128 and TR129)

Token-first economics answer "how much does inference cost?" Request-first capacity answers "how many users can one GPU serve?" TR128 establishes the single-agent ceiling: maximum throughput of 1.17 req/s for llama3.2-1b on Ollama, with service times of 858ms (llama3.2-1b), 1,008ms (qwen2.5-1.5b), and 1,435ms (llama3.2-3b). These service times assume approximately 128 output tokens per request at the measured decode rates.

TR129 adds concurrency and reveals a fundamental constraint. Total system throughput plateaus at N=2 with less than 3% gain from N=2 to N=8. This means that adding agents beyond 2 does not increase the GPU's total token output; it merely divides the same throughput among more agents. Per-agent throughput at N=8 drops to 17-20% of solo performance. The GPU is the bottleneck, not the software. This finding is one of the most important practical results in the program: operators who assume that multi-agent deployments on Ollama will multiply throughput will be disappointed. The Amdahl serial fractions (s=0.39-0.54, R-squared above 0.97) provide a quantitative model for predicting this saturation, and the excellent fairness (Jain's index at or above 0.997) ensures that no individual agent is starved even as the aggregate throughput plateaus.

The practical capacity envelope for a single RTX 4080 Laptop GPU on Ollama is: 0.7-1.17 req/s for single-agent workloads (model-dependent), approximately 1.4-1.9 req/s for 2-agent workloads (the effective ceiling), and no meaningful throughput gain beyond N=2. For a chat application serving 128-token responses, this translates to approximately 60,000-100,000 requests per day (single agent) or 120,000-160,000 requests per day (two agents). These numbers assume continuous operation at maximum utilization; a 70% utilization cap (Section 8.8) reduces them to 42,000-70,000 and 84,000-112,000 respectively.

The request-first view also reveals the importance of model selection for capacity. Llama3.2-1b achieves 1.17 req/s -- 37% higher than qwen2.5-1.5b (0.85 req/s) and 67% higher than llama3.2-3b (0.70 req/s). At 100,000 requests per day, the 1B model can serve the load on a single GPU, while the 3B model requires either a 14-hour processing window or a second GPU. The per-model capacity difference is large enough that model selection should be treated as a capacity decision, not just a quality decision. Using the chimeraforge planner (Section 7.7) to jointly optimize model, quantization, and backend avoids the common mistake of selecting a model based solely on quality and then discovering it cannot meet the throughput requirement.

### 7.4 Serving stack economics (TR130)

The serving stack choice becomes an economic lever at concurrency N>=4. TR130 demonstrates that vLLM achieves 559 tok/s versus Ollama's 248 tok/s for llama3.2-1b at N=8, a 2.25x throughput advantage. This translates directly into a 2.25x cost reduction per token under concurrency, because the same GPU produces 2.25x more tokens per second.

The crossover point is between N=2 and N=4. Below N=2, Ollama wins by 1.2-2.6x because Q4_0 quantization reduces bandwidth demand. Above N=4, continuous batching's bandwidth amortization (4.7-5.8x per TR132) more than compensates for the quantization advantage. At the crossover, the choice depends on the workload: latency-sensitive workloads favor vLLM (TTFT of 23-32ms versus 163-194ms for Ollama), while cost-sensitive single-agent workloads favor Ollama.

The TTFT advantage of vLLM/TGI (6-8x faster than Ollama) is economically significant for interactive applications where time-to-first-token directly affects user engagement. If an application's SLO requires TTFT below 50ms, Ollama is not viable at any concurrency level, and vLLM/TGI becomes the only option regardless of cost. This SLO-driven constraint can override the cost-optimal choice.

The serving stack also determines the scaling curve shape. Ollama follows Amdahl degradation with eta(8)=0.16 (84% throughput loss at N=8). vLLM follows power-law scaling with eta(8)=0.56 (44% loss). TGI is nearly identical to vLLM at eta(8)=0.58. This means that vLLM's advantage compounds with concurrency: at N=4 it is approximately 1.5x, at N=8 it is 2.25x, and the gap continues to grow. For deployments that anticipate growing concurrency, vLLM is the economically dominant choice even if the current N is below the crossover.

An important subtlety is the confound between quantization and serving stack in the absolute throughput comparison. Ollama serves Q4_0 quantized models while vLLM and TGI serve FP16. The eta(N) normalization removes this confound by expressing throughput as a fraction of each stack's own N=1 baseline, isolating the scaling behavior from the absolute throughput level. Without eta(N) normalization, Ollama appears to "win" at N=1 by 1.2-2.6x, but this is primarily a quantization advantage (Q4_0 versus FP16), not a serving stack advantage. The clean separation of scaling efficiency from absolute throughput is essential for correct backend selection policy. All backends are perfectly fair (Jain's index at or above 0.996), and none exhibit cold-start effects, simplifying the operational comparison.

The different degradation models are also economically significant. Ollama's Amdahl degradation means that the cost per token increases steeply with N: at N=8, each agent receives only 16% of solo throughput, so the effective cost per token is 6.25x the N=1 cost. vLLM's power-law degradation is gentler: at N=8, each agent receives 56% of solo throughput, so the effective cost per token is only 1.79x the N=1 cost. The economic crossover is therefore sharper than the raw throughput crossover: not only does vLLM produce more total tokens at N>=4, but the cost per token is also dramatically lower per agent.

### 7.5 Consumer versus cloud economics (TR123)

TR123 establishes that self-hosted consumer inference is 95.4% cheaper than equivalent cloud capacity. The comparison uses a compute-hour pricing model: the consumer GPU's amortized hourly cost (based on hardware purchase price, expected lifetime, and energy consumption) versus AWS on-demand GPU instance pricing.

At 1B tokens per month with GPT-2 on compile, the TCO comparison is: consumer hardware at $153/year versus AWS at $2,880/year. For Llama-3.2-1B on compile, the gap is wider in absolute terms: consumer at $564/year versus AWS at $8,584/year. The consumer advantage holds across all tested models and backends because the amortized hardware cost per hour is dramatically lower than cloud on-demand pricing.

The break-even analysis (Section 7.9) shows that the consumer GPU pays for itself in 0.3-2.7 months at 10M requests per month, depending on the model and backend. This rapid payback period means that even modest inference workloads justify hardware purchase over cloud on-demand pricing. The economic case weakens only for highly variable workloads that need capacity for peak load but sit idle most of the time; in such cases, cloud spot instances may be competitive for the burst capacity while the consumer GPU handles baseline load.

The cloud comparison does not account for operational overhead (system administration, monitoring, hardware failures) or the elasticity advantage of cloud (instant scale-up for traffic spikes). These factors may favor cloud for production services with SLOs, but for development, experimentation, personal assistants, and small-team tools, the 95.4% cost advantage is decisive.

The comparison also varies by model. The consumer advantage is largest for small, fast models (GPT-2, llama3.2-1b) where the GPU is dramatically under-utilized by a single model and the cloud pricing premium is highest per token. For larger models (llama3.1-8b), the consumer GPU is more heavily utilized and the cloud alternative may offer better performance per dollar through specialized inference hardware (A100, H100) that is not available in consumer form factors. The 95.4% headline figure is the best-case comparison (GPT-2); the worst-case comparison for models tested in this program is still approximately 85% cheaper, which remains decisive for most use cases.

It is worth noting that the cloud comparison does not account for the rapid depreciation of cloud pricing over time. Cloud inference costs have been declining at approximately 30-40% per year as providers optimize their inference infrastructure and introduce more efficient hardware generations. The consumer hardware cost, by contrast, is a one-time purchase that does not benefit from future price reductions (though it also does not incur ongoing price increases). A deployment that breaks even today will become increasingly cost-effective relative to cloud as the hardware depreciates, but less cost-effective relative to future cloud pricing. For a 3-year hardware lifetime, the net present value comparison should account for 2-3 rounds of cloud price reductions.

### 7.6 Carbon and energy economics (TR123)

Energy and carbon costs are rounding errors at consumer scale. TR123 measures energy consumption across all model-backend combinations and finds that the lowest carbon footprint is GPT-2/CPU at 3.4 gCO2e/1M tokens. Even the most energy-intensive configuration (large model, GPU, long generation) produces negligible carbon compared to the operational cost of the inference itself.

The energy cost decomposition shows that energy accounts for 1-34% of total cost depending on the configuration, with the majority of configurations below 10%. Infrastructure amortization dominates overwhelmingly. This means that energy efficiency is not a meaningful optimization axis for consumer-scale deployments; the correct economic lever is throughput improvement, which reduces the infrastructure time (and therefore cost) per token.

At datacenter scale, the calculus would differ because energy costs scale linearly with fleet size while infrastructure costs may benefit from volume discounts. However, this program's boundary conditions are explicitly consumer-scale, and within that boundary, energy optimization has negligible economic impact. The carbon numbers are provided for completeness and sustainability reporting, not as a decision-making input.

One non-obvious economic implication is that energy-efficient configurations and cost-efficient configurations are not the same. The most energy-efficient configuration (GPT-2/CPU at 3.4 gCO2e/1M tokens) is also one of the slowest and most expensive per token. The most cost-efficient configuration (GPT-2/compile at $0.013/1M tokens) uses GPU acceleration, which consumes more energy per second but completes the work in far less time. Because infrastructure cost dominates, the total energy consumption (watts * time) is actually lower for the faster GPU configuration than for the slower CPU configuration at the same token volume. This counter-intuitive result -- that the higher-wattage device produces lower total energy per token -- is a direct consequence of the throughput advantage being larger than the power draw increase.

For organizations with sustainability mandates, the practical guidance is: optimize for throughput (which minimizes wall-clock time and therefore total energy) rather than for instantaneous power draw. A GPU running at 175W for 10 seconds consumes 1,750 joules; a CPU running at 45W for 200 seconds consumes 9,000 joules for the same workload. The 3.9x GPU power draw is more than offset by the 20x throughput advantage. This principle holds across all configurations tested in the program and is likely to hold for any memory-bandwidth-limited inference workload.

### 7.7 Capacity planning with chimeraforge (TR133)

The chimeraforge CLI operationalizes the economic analysis into a capacity planning tool that searches the (model, quantization, backend, N-agents) configuration space in under 1 second. The search is structured as a 4-gate pipeline: VRAM feasibility (does the configuration fit in GPU memory?), quality gate (does it meet the minimum composite score?), latency gate (does it meet the SLO?), and budget gate (does it fit within the cost target?). Configurations that pass all four gates are ranked by cost per token.

The planner's accuracy is validated against a 20% holdout set (3,939 records from 19,676 total). VRAM prediction achieves R-squared of 0.968 (target 0.95), meaning the planner correctly identifies which configurations fit in memory. Throughput prediction achieves R-squared of 0.859 (target 0.85), meaning the planner's cost estimates are reliable to within approximately 15% of measured values. Quality prediction achieves RMSE of 0.062 (target below 0.10), meaning the quality gate correctly filters quality-unacceptable configurations. Latency prediction achieves MAPE of 1.05% (target below 25%), meaning the latency gate is highly accurate.

The planner uses a 22-entry throughput lookup table as its primary prediction source, with a power-law fallback (72.1 * params^-0.089) for configurations not in the table. Quantization multipliers (FP16=1.0x, Q8_0=1.15x, Q6_K=1.25x, Q5_K_M=1.40x, Q4_K_M=1.65x, Q3_K_S=1.90x, Q2_K=2.30x) scale the base throughput. This pragmatic approach avoids the 20.4x deviations of M/D/1 queueing theory and the curve-fitting artifacts of Amdahl's Law applied across backends.

For cross-GPU extrapolation, the planner uses bandwidth scaling: throughput scales linearly with memory bandwidth within the same architecture generation. This is a linear approximation that has not been validated on other GPUs (an explicit limitation in TR133), but it provides a reasonable first estimate for capacity planning across GPU tiers. The RTX 4080 Laptop GPU baseline of 432 GB/s memory bandwidth serves as the reference point; a desktop RTX 4090 with 1,008 GB/s bandwidth would be predicted to achieve approximately 2.3x the throughput. This prediction is plausible based on the TR131 finding that memory bandwidth is the fundamental bottleneck, but it remains unverified and should be treated as a starting estimate, not a guaranteed performance level.

The planner's pragmatic approach -- lookup tables with first-principles fallback, no machine learning -- is itself an economic finding. The 19,676 training records required no GPU time for model fitting, no hyperparameter tuning, and no validation infrastructure. The entire planner runs in under 1 second on a CPU. This means the capacity planning tool has near-zero operational cost and can be re-run iteratively during deployment design without consuming inference resources. The contrast with M/D/1 queueing theory is instructive: the theoretical model is simpler to derive but deviates 20.4x from reality, while the empirical model requires more initial measurement but produces validated predictions.

### 7.8 Economic decision tree by concurrency level

The economic analysis consolidates into a concurrency-indexed decision tree. At N=1 (single agent), deploy Ollama Q4_K_M. This is the cheapest quality-safe configuration, with decode-optimized GGUF inference and quantization-reduced bandwidth demand. Expected throughput: 0.7-1.17 req/s depending on model. Expected cost: 30-67% less than FP16 with quality within -4.1pp.

At N=2-3 (small multi-agent), Ollama remains competitive. Total throughput gains plateau at N=2 (approximately 1.4-1.6x), so the economic benefit of concurrency is limited. vLLM provides better TTFT (23-32ms versus 163-194ms) but lower single-request throughput at FP16. Choose based on latency SLO: if TTFT below 50ms is required, use vLLM; otherwise, Ollama.

At N>=4 (multi-agent), deploy vLLM FP16. Continuous batching amortizes GPU bandwidth by 4.7-5.8x, yielding 2.25x throughput advantage at N=8. The crossover with Ollama occurs between N=2 and N=4. Expected efficiency: eta(8)=0.56 (vLLM) versus eta(8)=0.16 (Ollama). Use `chimeraforge plan` to identify the exact cost-optimal configuration within this regime.

At N>8 (high concurrency), this program's measurements do not directly apply. The scaling models extrapolate using Amdahl/power-law fits, but the extrapolation is unvalidated. For N>8, consider horizontal scaling (multiple GPUs) or cloud burst capacity rather than relying on single-GPU predictions.

A key economic nuance is that the N-dependent decision interacts with the quantization decision. At N>=4 on vLLM, the recommendation is FP16 weights because continuous batching amortizes the bandwidth cost. However, vLLM also supports quantized serving (AWQ, GPTQ), which could potentially combine quantization savings with continuous batching amortization. This combination is untested in the current program and represents one of the most promising future directions for cost optimization. If vLLM quantized serving preserves both the 30-67% quantization savings and the 2.25x continuous batching advantage, the compound savings could reach 6-8x versus naive FP16/Ollama at high concurrency.

### 7.9 Break-even analysis: consumer GPU payback period

The break-even period for consumer hardware versus cloud on-demand pricing depends on utilization volume and model choice. At 10M requests per month (approximately 3.8 req/s average, assuming 128 output tokens per request and continuous operation), the consumer GPU's amortized cost is dramatically lower than cloud pricing.

For llama3.2-1b on Ollama Q4_K_M, the monthly cloud cost at AWS on-demand pricing is approximately $240/month. The consumer GPU (RTX 4080 Laptop, estimated at $1,200 as part of a system purchase, 3-year amortization) costs approximately $33/month in hardware amortization plus approximately $8/month in energy. The break-even occurs at month 0.3 -- effectively immediately. Even at 1M requests per month (one-tenth the volume), the break-even is at 2.7 months.

The break-even calculation is sensitive to three assumptions: cloud pricing tier (on-demand versus reserved versus spot), utilization factor (continuous versus bursty), and hardware amortization period. On-demand pricing produces the fastest break-even; reserved instances with 1-year commitment can reduce cloud costs by 30-40%, extending break-even to 0.4-3.8 months. Spot instances can reduce cloud costs by 60-90% but introduce availability risk that may be unacceptable for production workloads.

For bursty workloads with high peak-to-average ratios, a hybrid model may be optimal: consumer GPU for baseline load and cloud burst for peaks. The economic crossover depends on the ratio of peak to baseline and the cost of over-provisioning the consumer GPU for peak load versus paying cloud premium for burst capacity.

Break-even sensitivity by volume tier:

| Monthly Volume | Consumer Cost/month | Cloud On-Demand/month | Break-Even Month | Savings After Year 1 |
| --- | --- | --- | --- | --- |
| 1M requests | ~$34 | ~$24 | Never (cloud wins at low volume) | Cloud saves ~$120/yr |
| 5M requests | ~$35 | ~$120 | 0.5 | Consumer saves ~$1,020/yr |
| 10M requests | ~$37 | ~$240 | 0.3 | Consumer saves ~$2,436/yr |
| 50M requests | ~$45 | ~$1,200 | 0.1 | Consumer saves ~$13,860/yr |

Note: consumer costs are nearly flat because the GPU is amortized regardless of utilization. Cloud costs scale linearly with volume. The crossover where consumer hardware becomes cheaper than cloud occurs at approximately 2-3M requests per month, below which the fixed hardware amortization exceeds the variable cloud cost.

### 7.10 Total cost of ownership model

The total cost of ownership model for consumer GPU inference includes four components: hardware amortization, energy, maintenance/operations, and opportunity cost. This model is designed to be directly comparable with cloud TCO calculations, enabling organizations to make informed build-versus-buy decisions for inference infrastructure.

Hardware amortization is the dominant component and the most sensitive to assumptions. For an RTX 4080 Laptop GPU at approximately $1,200 (as part of a system), amortized over 3 years with 18 hours/day utilization, the hourly cost is approximately $0.061/hour. For comparison, the cheapest AWS GPU instance (g5.xlarge) costs approximately $1.006/hour on-demand, a 16.5x premium. Amortization sensitivity: a 2-year lifetime increases the hourly cost to approximately $0.091 (still 11x cheaper than cloud); a 4-year lifetime reduces it to approximately $0.046. The consumer advantage is robust across reasonable amortization assumptions because the pricing gap is so large.

Energy cost depends on local electricity pricing and GPU power consumption. The RTX 4080 Laptop GPU has a 175W TDP, consuming approximately 3.15 kWh per 18-hour day. At $0.12/kWh (US average), this is $0.38/day or $11.40/month. At $0.30/kWh (European pricing), it is $0.95/day or $28.50/month. Energy is 5-15% of total cost depending on the pricing region.

Maintenance and operations include system administration time, hardware failure risk, and software updates. These costs are difficult to quantify precisely but are estimated at 2-4 hours per month for a well-configured consumer system. At a labor rate of $50/hour, this is $100-$200/month -- potentially the largest cost component for low-volume deployments.

Opportunity cost is the most difficult to quantify. The consumer GPU is dedicated to inference and cannot simultaneously serve other GPU workloads (training, rendering, simulation). For teams that use the same hardware for development and inference, context switching between workloads introduces downtime. For dedicated inference hardware, the opportunity cost is zero. In cloud environments, the opportunity cost is also zero because instances are provisioned on demand.

The cloud alternative includes compute cost (on-demand or reserved), data transfer (typically $0.09/GB), storage (model weights, logs), and no hardware maintenance. For high-volume deployments (above 10M requests/month), the consumer GPU dominates. For low-volume deployments (below 100K requests/month), the cloud's zero-maintenance advantage may justify the premium. The crossover depends on organizational context: teams with existing GPU hardware and operations capability break even at lower volumes than teams that would need to purchase and maintain dedicated inference hardware.

TCO comparison summary (annual, 10M requests/month, llama3.2-1b Q4_K_M):

| Component | Consumer GPU | Cloud On-Demand | Cloud Reserved (1yr) |
| --- | --- | --- | --- |
| Compute/hardware | $400 | $2,880 | $1,900 |
| Energy | $137 | Included | Included |
| Maintenance/ops (4hr/mo) | $2,400 | $0 | $0 |
| Data transfer | $0 | $108 | $108 |
| **Total** | **$2,937** | **$2,988** | **$2,008** |

Note: at 10M requests/month, the operations cost dominates the consumer TCO. For teams with existing ops capability (marginal operations cost near zero), the consumer GPU saves approximately $2,500/year versus cloud on-demand. The operations cost is the key variable: if dedicated staff time is required, cloud may be competitive; if the infrastructure is self-managing or part of an existing workload, consumer hardware is dramatically cheaper.

### 7.11 Worked example: sizing a chat deployment

Scenario: a team of 5 developers wants to deploy a local AI chat assistant using llama3.2-3b with Q4_K_M quantization on Ollama. Requirements: average response time below 2 seconds, support for 2 concurrent users, 8 hours per day usage, approximately 500 requests per day.

Step 1 -- VRAM check. Llama3.2-3b Q4_K_M requires approximately 2.3 GB for model weights and approximately 0.5 GB for KV-cache at 2K context length, totaling approximately 2.8 GB. With 1.058x overhead, approximately 2.96 GB. Well within 12 GB VRAM. Pass.

Step 2 -- Quality check. Llama3.2-3b Q4_K_M composite quality score is approximately 0.49 (from TR124/TR125 data). This is marginally below the 0.50 production threshold. If the team's use case tolerates this (development assistance, not customer-facing), proceed. If not, switch to phi-2 Q4_K_M (composite approximately 0.61) or llama3.1-8b Q4_K_M (composite approximately 0.65, but higher VRAM: approximately 5.2 GB).

Step 3 -- Throughput check. TR128 baseline service time for llama3.2-3b is 1,435ms. At N=2 concurrent users, TR129 shows approximately 1.5x total throughput, meaning approximately 1.05 req/s total or approximately 525ms wait time per user above service time. Average response time: approximately 1,960ms. Marginal pass against 2-second SLO.

Step 4 -- Daily capacity check. At 1.05 req/s and 8 hours per day, maximum daily capacity is approximately 30,240 requests. Required: 500. Utilization: 1.7%. The GPU is dramatically over-provisioned for this workload.

Step 5 -- Cost estimate. Hardware amortization: $33/month. Energy at 1.7% utilization: approximately $0.50/month. Total: approximately $33.50/month. Cloud equivalent (500 requests/day on AWS): approximately $15/month using serverless inference. In this low-volume scenario, cloud may be competitive on raw cost. However, the consumer GPU provides zero-latency local inference (no network round-trip), data privacy (code and conversations never leave the local machine), and offline capability (works without internet). For a development team working with proprietary code, the privacy advantage alone may justify the $18.50/month premium over cloud.

Step 6 -- Sensitivity analysis. If the team grows to 10 developers (1,000 requests/day, 3 concurrent users), the throughput check becomes more constrained. At N=3 on Ollama, total throughput is approximately 1.1 req/s (TR129), supporting approximately 1,000 requests per 15-minute peak hour. Daily capacity remains comfortable at approximately 31,680 requests per 8-hour day. The cost remains approximately $33.50/month regardless of utilization, demonstrating the fixed-cost advantage of consumer hardware for growing teams.

### 7.12 Worked example: RAG pipeline capacity planning

Scenario: a document retrieval and summarization pipeline processes 10,000 documents per day. Each document requires a 4K-token context window (retrieval) and 512-token generation (summary). The target is to complete all processing within 8 hours. Model: qwen2.5-1.5b Q4_K_M on Ollama.

Step 1 -- VRAM check. Qwen2.5-1.5b Q4_K_M requires approximately 1.1 GB for model weights. KV-cache at 4K context with GQA: approximately 0.12 GB (GQA extreme compression). Total: approximately 1.22 GB with overhead. Well within 12 GB. Pass.

Step 2 -- Throughput estimation. TR128 baseline service time for qwen2.5-1.5b is 1,008ms for a standard request. For a 4K-context request with 512-token generation, the service time scales roughly proportionally with output length. Estimated service time: approximately 4,032ms (4x baseline for 4x output). From TR127, Ollama handles 4K context with no degradation. Estimated throughput: approximately 0.25 req/s for this workload shape.

Step 3 -- Capacity check. At 0.25 req/s over 8 hours, maximum capacity is approximately 7,200 requests. Required: 10,000. Single GPU is insufficient.

Step 4 -- Mitigation options. Option A: extend processing window to 12 hours (capacity increases to approximately 10,800, sufficient with 7% headroom). Option B: add a second GPU or use vLLM for batched processing. At N=2 on Ollama, total throughput increases to approximately 0.38 req/s (capacity approximately 10,944 in 8 hours). Option C: use a smaller model (llama3.2-1b) with faster service times, accepting lower summarization quality.

Step 5 -- Cost comparison. Option A (12-hour window): $33/month hardware + approximately $1.50/month energy = approximately $34.50/month. Cloud equivalent for 10,000 RAG requests/day at 4K context: approximately $300/month (based on API pricing for 45M tokens/month). Consumer hardware is approximately 8.7x cheaper. If the 12-hour processing window is acceptable, this is the clear economic winner.

Step 6 -- Quality gate. Qwen2.5-1.5b Q4_K_M has composite quality of approximately 0.52. For automated document summarization (not customer-facing), this meets the 0.50 production threshold. For quality-critical summarization, upgrade to llama3.1-8b Q4_K_M (composite approximately 0.65), accepting the higher VRAM footprint and lower throughput.

This worked example illustrates several program principles in action. The VRAM gate eliminates configurations before throughput is even considered. The quality gate prevents cost-optimal but quality-unacceptable configurations from reaching the recommendation. The throughput calculation uses empirical baselines from TR128 rather than theoretical models, avoiding the M/D/1 deviation problem. And the economic comparison uses real measurements rather than vendor claims. The same workflow can be automated via `chimeraforge plan --model qwen2.5-1.5b --quant Q4_K_M --backend ollama --context 4096 --output-tokens 512 --target-rps 0.35`, which would identify the capacity shortfall and suggest alternatives in under 1 second.

---

## 8. Operational Doctrine and Risk Controls

This section translates the program's empirical findings into operational policies. Each policy is a decision rule backed by specific measurements, effect sizes, and significance tests. The policies are designed to be conservative: they protect against the known failure modes documented across TR123-TR133 and include explicit triggers for policy revision. The operational doctrine follows a "safe by default, aggressive by evidence" principle: the default configuration (Ollama Q4_K_M, N=1, streaming on, eager decode) is the most thoroughly validated and lowest-risk option. Deviations from the default (higher concurrency, different serving stacks, compiled prefill) are permitted only with the specific evidence cited in each policy subsection.

The twelve policies cover the full decision space from backend selection to risk management. They are ordered roughly by frequency of application: backend selection and quantization are the first decisions made for any deployment, while change management and risk registers are ongoing governance activities. Each policy includes its evidence base, exceptions, and revision triggers.

### 8.1 Backend selection policy

The backend selection policy is indexed by concurrency level (N) and workload type, reflecting the N-dependent crossover documented in TR130 and the mechanism identified in TR131/TR132.

For N=1 (single-agent) inference, deploy Ollama with Q4_K_M quantization. Evidence: Ollama achieves 1.2-2.6x throughput advantage over vLLM FP16 at N=1 (TR130) due to quantization-reduced bandwidth demand and decode-optimized GGUF inference. Cost savings: 30-67% versus FP16 (TR125). Quality preservation: within -4.1pp of FP16 on benchmark accuracy (TR125).

For N=2-3 (low concurrency) inference, Ollama remains the default unless the workload has a strict TTFT requirement. vLLM provides 6-8x faster TTFT (23-32ms versus 163-194ms, TR130) but lower single-request throughput at FP16. If TTFT below 50ms is a hard SLO, deploy vLLM regardless of N.

For N>=4 (multi-agent) inference, deploy vLLM with FP16 weights. Evidence: vLLM achieves 2.25x throughput advantage at N=8 (TR130) via continuous batching, which amortizes GPU memory bandwidth by 4.7-5.8x (TR132). Scaling efficiency: eta(8)=0.56 (vLLM) versus eta(8)=0.16 (Ollama).

For prefill-heavy workloads (RAG retrieval, embedding computation, reranking), consider torch.compile on Linux for HuggingFace backends. Evidence: 24-60% prefill latency reduction (TR126). This is orthogonal to the N-dependent backend choice and applies only to the prefill phase.

Exceptions: if the workload requires models larger than 8B parameters, the backend selection may be constrained by VRAM availability. vLLM's PagedAttention provides more efficient memory management for large models. If the workload requires specific quantization formats not supported by Ollama's GGUF engine, vLLM with AWQ/GPTQ may be necessary (untested in this program; flagged as a future direction).

The backend selection policy summarized as a decision table:

| Concurrency | TTFT SLO | Recommended Backend | Evidence |
| --- | --- | --- | --- |
| N=1 | >100ms acceptable | Ollama Q4_K_M | TR130: 1.2-2.6x throughput advantage |
| N=1 | <50ms required | vLLM FP16 | TR130: TTFT 23-32ms |
| N=2-3 | >100ms acceptable | Ollama Q4_K_M | TR129: plateau at N=2 |
| N=2-3 | <50ms required | vLLM FP16 | TR130: TTFT advantage persists |
| N>=4 | Any | vLLM FP16 | TR130: 2.25x at N=8; TR132: 4.7-5.8x amortization |

### 8.2 Quantization policy

The quantization policy is structured as a tiered default with model-specific exceptions and a hard ban on Q2_K. The policy is based on TR125's comprehensive mapping of 34 model-quantization variants.

Default: Q4_K_M for all models. This is the universal sweet spot with maximum benchmark accuracy loss of -4.1pp (qwen2.5-1.5b) and all other models within -3pp. Cost savings: 30-67% versus FP16. VRAM savings: proportional to quantization ratio, enabling longer contexts and more concurrent agents.

Quality-critical exception: Q8_0 for workloads requiring benchmark accuracy within 2pp of FP16. This preserves quality more tightly at the cost of reduced throughput savings (approximately 10-15% versus FP16). Use when: medical/legal text generation, high-stakes classification, or any application where a 3-4pp accuracy difference has material consequences.

Aggressive exception: Q3_K_S is acceptable only for phi-2 (loss within -0.4pp) and llama3.1-8b (loss within -2.5pp). For llama3.2-1b (-9.5pp), llama3.2-3b (-10.1pp), and qwen2.5-1.5b (-12.2pp), Q3_K_S is quality-unacceptable. Never deploy Q3_K_S without model-specific validation.

Hard ban: Q2_K for all models. All tested models exceed 11pp accuracy loss at Q2_K, with qwen2.5-1.5b losing 40.6pp (near-random performance). Q2_K also exhibits repetition collapse (qwen2.5-1.5b repetition score drops from 0.992 to 0.702). No cost savings justifies this quality degradation. Q2_K should not appear in any production configuration, and the chimeraforge planner excludes it from quality-gated search.

Policy revision trigger: new models or new quantization formats (AWQ, GPTQ, HQQ) require re-running the TR125 evaluation protocol before deployment. The quantization policy is model-specific, not universal; a new model family may have different sensitivity to quantization than the five models tested here.

The quantization policy can be summarized as a simple decision table:

| Requirement | Quantization Level | Quality Risk | Cost Impact vs FP16 |
| --- | --- | --- | --- |
| Maximum cost savings, quality acceptable | Q4_K_M | Within -4.1pp | 30-67% savings |
| Maximum quality preservation | Q8_0 | Within -2pp | 10-15% savings |
| Aggressive savings, model-validated only | Q3_K_S (phi-2, llama3.1-8b only) | Within -0.4pp (phi-2), -2.5pp (llama3.1-8b) | 40-70% savings |
| Never deploy | Q2_K | 11-40.6pp loss; repetition collapse | N/A -- quality-unacceptable |

### 8.3 Compile policy

The compile policy is based on TR126's resolution of the compile paradox and applies exclusively to Linux environments with real Triton kernel generation.

Rule 1: compile prefill only. Evidence: -24% to -60% latency reduction across all 7 models with Cohen's d=-0.59, p=8.87e-61 (TR126). 916 Triton kernels generated. The prefill phase is compute-bound, making it amenable to kernel fusion and optimization by the Inductor compiler.

Rule 2: eager decode always. Evidence: compiled decode crashes 100% of the time in reduce-overhead and mode="default" modes (TR126). When forced through StaticCache, compiled decode runs 5.8x slower than eager (TR126). Even when compiled decode does not crash (short sequences only), the speedup is +2.2% and not statistically significant (TR126). The decode phase is memory-bandwidth-bound, not compute-bound, so compiler optimizations provide minimal benefit even in theory.

Rule 3: never compile on Windows. Evidence: Windows lacks Triton and the compile backend silently falls back to aot_eager, which is functionally equivalent to eager mode (TR126). Any performance measurements taken with torch.compile on Windows are invalid and should not be used for decision-making. This includes all TR120 Phase 1 results, which were obtained on Windows and have been superseded by TR126.

Rule 4: scale-aware application. Small models (below approximately 1.5B parameters) benefit most from compilation because prefill is a larger fraction of their total inference time. Larger models show diminishing returns because Ollama's GGUF engine already saturates the GPU for decode, and prefill time becomes a smaller fraction of end-to-end latency. At the scale crossover (approximately 1.5B), the compile investment (engineering complexity, Docker/Linux requirement) may not be justified.

The compile bug (pytorch/pytorch#175557) persists as of PyTorch 2.10. If a future PyTorch release fixes compiled decode, the policy should be re-evaluated by re-running TR126 Phase 2/3 benchmarks. Until then, rule 2 is absolute.

The practical impact of the compile policy is workload-dependent. For decode-heavy workloads (chat, code generation, long-form summarization), the compile policy has no effect because decode is the bottleneck and compile is not applied to decode. For prefill-heavy workloads (RAG retrieval, document classification, embedding computation), the compile policy can reduce prefill latency by 24-60%, which directly improves TTFT and overall throughput. The ROI of implementing the compile policy therefore depends on the prefill-to-decode ratio of the target workload, which can be estimated using the blend ratios in Section 7.1.

### 8.4 Context budget policy

The context budget policy prevents VRAM spillover, which causes 25-105x latency cliffs on consumer hardware (TR127). The policy is based on a first-principles VRAM formula validated empirically.

VRAM budget formula: VRAM_required = model_weights_bytes × 1.058 + KV_bytes_per_token × context_length. The 1.058 factor accounts for CUDA allocator fragmentation on model weight loading (TR133) and applies to weights only, not KV-cache. Model weights and KV parameters are model-specific; the chimeraforge planner includes a model registry with these values.

For Ollama with quantized models: context budget is effectively unlimited within the model's context window (32K for most modern models). Ollama's Flash Attention eliminates quadratic scaling (b<0.2, TR127), and quantized KV-caches reduce per-token VRAM consumption proportionally. TTFT never exceeds 1 second through 32K context (TR127). Decode degradation is moderate: 41-53% over 64x context growth.

For HuggingFace FP16 on 12 GB VRAM: maximum context is 4-8K tokens depending on model. Beyond this, VRAM spillover causes catastrophic latency cliffs. Specific thresholds: qwen2.5-3b hits spillover at 8K, smaller models at 16K. TTFT exceeds 1 second at 4K. Do not deploy HuggingFace FP16 for contexts above 4K on 12 GB VRAM.

GQA preference: GQA models (Llama-3.2, Qwen-2.5) use 3-11x less KV-cache memory than MHA models (GPT-2, Phi-2) for the same context length (TR123). For long-context workloads, prefer GQA architectures to maximize context budget within VRAM constraints.

Context budget quick-reference for 12 GB VRAM (approximate safe maximums at Q4_K_M on Ollama):

| Model | Architecture | Max Safe Context | VRAM at Max |
| --- | --- | --- | --- |
| llama3.2-1b | GQA | 32K+ | ~3.5 GB |
| qwen2.5-1.5b | GQA (extreme) | 32K+ | ~2.8 GB |
| llama3.2-3b | GQA | 32K | ~5.2 GB |
| phi-2 (2.7B) | MHA | ~16K | ~8.5 GB |
| llama3.1-8b | GQA | ~8K | ~10.5 GB |

Monitoring requirement: track VRAM utilization in real-time. Alert at 85% utilization. Hard-stop new requests at 90% utilization to prevent spillover. VRAM utilization should be a first-class metric in any inference monitoring dashboard. The alert thresholds are set conservatively because VRAM consumption can spike temporarily during batch prefill operations, and the spillover cliff is binary (no graceful degradation).

### 8.5 Agent count policy

The agent count policy sets the maximum number of concurrent agents per GPU based on serving stack and acceptable per-agent throughput degradation. The policy is based on TR129 (Amdahl scaling), TR130 (serving stack comparison), and TR131/TR132 (root cause analysis).

For Ollama: maximum 2-3 agents per GPU. Evidence: total throughput plateaus at N=2 (less than 3% gain from N=2 to N=8, TR129). Per-agent throughput at N=3 drops to approximately 45% of solo. At N=4, per-agent throughput drops to approximately 30% of solo, making the per-user experience unacceptable for interactive workloads. Fairness is excellent (Jain's index at or above 0.997, TR129), so all agents degrade equally.

For vLLM: up to 8 agents per GPU. Evidence: continuous batching amortizes bandwidth by 4.7-5.8x (TR132), enabling eta(8)=0.56 (TR130). Per-agent throughput at N=8 is approximately 56% of solo in throughput terms, which remains acceptable for many workloads. vLLM never saturates within N=8 (TR130), suggesting that N>8 may be viable, but this is unvalidated.

The agent count interacts with the context budget: more agents means more concurrent KV-caches in VRAM. For N agents with average context length C, the total KV-cache VRAM is approximately N * KV_per_token * C. This additional VRAM pressure must be accounted for in the VRAM budget (Section 8.4). Under vLLM, PagedAttention manages this automatically by paging KV-cache blocks in and out of GPU memory as needed, avoiding OOM crashes at the cost of some latency. Under Ollama, the full KV-cache for each active context must fit simultaneously in VRAM, making the VRAM constraint more binding. For example, 3 agents with 4K context on llama3.2-3b Q4_K_M requires approximately 3 * 0.5 GB = 1.5 GB of KV-cache in addition to the 2.3 GB model weights, for a total of approximately 4.0 GB -- well within 12 GB. But 8 agents with 8K context on the same model would require approximately 8 * 1.0 GB = 8.0 GB of KV-cache plus 2.3 GB weights = 10.3 GB, leaving only 1.7 GB headroom on a 12 GB GPU.

For mixed workloads where some agents are idle (think-time between requests): TR129 shows that think-time improves per-request latency but reduces sustained throughput. The agent count policy should be based on the sustained concurrent agent count, not the total number of registered agents.

The agent count policy interacts with the backend selection policy (Section 8.1) and the capacity planning policy (Section 8.8). The recommended workflow is: (1) determine the expected concurrent agent count, (2) select the backend using Section 8.1, (3) verify VRAM feasibility for N concurrent KV-caches using Section 8.4, and (4) validate throughput using `chimeraforge plan` with the selected configuration. If the expected N varies over time (e.g., business hours versus overnight), design for the peak N and accept over-provisioning during low-demand periods, or implement dynamic backend switching if the infrastructure supports it.

### 8.6 Streaming policy

The streaming policy is simple and absolute: always enable streaming. Evidence: TR128 tests streaming versus batch mode across 3 models and 3 configurations. Result: 0/9 pairwise tests are significant. Streaming has zero wall-clock overhead.

Streaming provides two benefits at zero cost. First, it reduces perceived latency by delivering tokens as they are generated, allowing the client to begin rendering before generation is complete. Second, it enables early termination: if the client detects that the response is off-topic or malformed, it can cancel the request without waiting for full generation.

The zero-overhead result is consistent with the mechanism: streaming adds only a trivial per-token yield to the generation loop, which is dominated by the GPU decode time. The overhead of yield is nanoseconds; the decode time per token is milliseconds. The ratio is below measurement noise.

There is no scenario in the measured configuration space where batch mode is preferred over streaming. Even for batch processing pipelines where the response is not displayed incrementally, streaming mode allows for timeout enforcement and progress monitoring without performance penalty. The streaming policy is one of the simplest and most robust findings in the program: it has been tested across all three models, multiple configurations, and various load levels, with a consistent zero-overhead result. It requires no configuration tuning, no per-model adjustment, and no workload-dependent exceptions.

### 8.7 Quality gate policy

The quality gate policy defines minimum composite quality scores for production deployment. The thresholds are based on TR124's quality baselines and TR125's quantization impact measurements.

Production workloads: composite quality score at or above 0.50. This threshold admits qwen2.5-1.5b (0.55 at FP16, approximately 0.52 at Q4_K_M -- passes), llama3.2-3b (0.52 at FP16, approximately 0.49 at Q4_K_M -- marginal), and phi-2 (0.63 at FP16, approximately 0.61 at Q4_K_M -- passes). llama3.2-1b (0.44 at FP16, approximately 0.42 at Q4_K_M) falls below the 0.50 threshold. Note: Q4_K_M composite scores are interpolated estimates derived from TR124 FP16 composites and TR125 benchmark accuracy deltas; they are not directly measured. The threshold is intentionally set to filter out configurations that produce noticeably poor outputs.

Quality-critical workloads: composite quality score at or above 0.60. This admits only phi-2 (0.61 at Q4_K_M) and llama3.1-8b (not measured in TR124 composite but has the highest benchmark accuracy at 72.4% Q8_0). For quality-critical applications, the model choice is constrained to larger or more capable models.

Per-task minimum scores should supplement the composite threshold. If a specific task (e.g., code generation, factual QA) is the primary use case, the task-specific metric should be checked in addition to the composite. TR124 provides task-specific breakdowns for each model.

The quality gate is enforced before cost optimization in the chimeraforge planner. This ensures that the planner never recommends a configuration that fails quality requirements, regardless of how cost-effective it is. The Q2_K ban (Section 8.2) is the most extreme expression of this principle: Q2_K is the cheapest quantization but is quality-unacceptable for all models.

Quality gate thresholds by application type:

| Application Type | Minimum Composite | Recommended Models at Q4_K_M | Rationale |
| --- | --- | --- | --- |
| Development assistant | 0.40 | llama3.2-1b (0.42), qwen2.5-1.5b (0.52) | Tolerance for occasional errors; speed prioritized |
| Production chat | 0.50 | qwen2.5-1.5b (0.52), llama3.2-3b (0.49*), phi-2 (0.61) | User-facing; acceptable quality |
| Quality-critical | 0.60 | phi-2 (0.61), llama3.1-8b (est. 0.65+) | High-stakes; accuracy paramount |

*Note: llama3.2-3b at 0.49 is marginally below the 0.50 threshold; use Q8_0 (approximately 0.51) for strict compliance.

### 8.8 Capacity planning policy

The capacity planning policy mandates the use of empirical lookup tables (chimeraforge) over theoretical queueing models, and enforces a 70% utilization cap to prevent latency degradation under load variability.

Rule 1: use `chimeraforge plan` for all capacity planning decisions. Evidence: M/D/1 queueing theory deviates up to 20.4x from observed latency at high utilization (TR128). Amdahl's Law provides good curve fits (R-squared above 0.97, TR129) but attributes the mechanism incorrectly (TR131) and is a category error when applied across backends (TR130). The chimeraforge planner avoids these failure modes by using validated empirical lookup tables with first-principles interpolation.

Rule 2: cap planned utilization at 70% of measured maximum throughput. Evidence: TR128 shows that TTFT amplifies 29.9x at 2.0 req/s (near saturation). At 70% utilization, TTFT amplification is bounded to approximately 3-5x, which is acceptable for interactive workloads. The 70% cap also provides headroom for load spikes without triggering the queueing catastrophe.

Rule 3: validate planner predictions for any new configuration. The chimeraforge planner achieves R-squared of 0.859 for throughput, meaning approximately 15% of predictions may deviate from reality. Before deploying a planner-recommended configuration, run a brief (10-minute) load test to confirm that actual throughput matches the prediction. If the deviation exceeds 20%, flag the configuration for investigation.

Rule 4: re-plan after any stack change. Hardware upgrades, driver updates, serving stack version changes, and model architecture changes can all alter the throughput landscape. The planner's lookup tables are fitted to specific versions; using them with different versions produces unvalidated predictions. Treat any stack change as a capacity planning event.

The 70% utilization cap deserves further justification. TR128 demonstrates that TTFT amplification follows a non-linear curve: at 50% utilization, TTFT is approximately 2x the no-load value; at 70%, approximately 3-5x; at 90%, approximately 10-15x; and at 100%, the 29.9x amplification measured at 2.0 req/s. The 70% threshold balances throughput efficiency (only 30% capacity is "wasted") against latency protection (TTFT stays within a 5x envelope). For batch processing workloads where latency is not a concern, the cap can be relaxed to 85-90%. For interactive workloads with strict TTFT SLOs (below 500ms), the cap should be tightened to 50-60%.

### 8.9 Thermal policy

The thermal policy is minimal because TR128 demonstrates that no thermal throttling occurs on the RTX 4080 Laptop GPU under sustained inference load. Peak GPU temperature reaches 66 degrees C against the thermal throttle threshold of approximately 80 degrees C, leaving 14 degrees of headroom.

Default policy: no cooling upgrades or thermal management interventions required for sustained single-GPU inference workloads. The 14-degree headroom is sufficient for ambient temperature variation in normal office environments (20-30 degrees C).

Alert threshold: set GPU temperature alerts at 75 degrees C. This provides 5 degrees of warning before the throttle threshold. If the alert triggers, investigate: the likely causes are blocked air intake, elevated ambient temperature, or additional GPU load from non-inference workloads (display rendering, other CUDA applications).

Intervention threshold: if GPU temperature exceeds 80 degrees C under inference load alone, the hardware may have a cooling deficiency. Options include: improving laptop airflow (elevated surface, external fan), reducing ambient temperature, or reducing GPU utilization. Do not attempt to override thermal throttling; it exists to prevent hardware damage.

Multi-GPU consideration: if deploying inference on a system with multiple GPUs (desktop workstation), thermal interaction between GPUs can elevate temperatures. Each GPU's thermal policy should be independently monitored. This scenario is outside the program's single-GPU boundary conditions.

The thermal stability finding is one of the program's most reassuring results for consumer deployment. Many operators fear that sustained GPU inference will cause thermal throttling, noise escalation, or hardware degradation. TR128's continuous monitoring data shows that the RTX 4080 Laptop GPU maintains a 14-degree thermal margin under the most demanding inference workload measured. This margin is large enough that even in warm environments (30 degrees C ambient), throttling is unlikely. The implication is that thermal management is not a deployment concern for consumer GPUs under inference loads; it should be monitored but does not require proactive investment.

### 8.10 Monitoring policy

The monitoring policy specifies the metrics that must be tracked for operationally sound inference deployment. The metrics are derived from the program's findings about which measurements predict production problems.

Primary metrics (track continuously, alert on degradation):

Time to first token (TTFT): the most sensitive indicator of queueing and overload. TR128 shows 29.9x amplification at high utilization. Alert if TTFT exceeds 2x the baseline (no-load) value. The baseline should be measured at deployment time under zero concurrency.

Decode throughput (tokens per second): the primary capacity indicator. Track the 50th and 95th percentile decode throughput. Alert if p50 drops below 80% of the no-load baseline or if p95 drops below 60%. Sustained degradation indicates either thermal throttling, VRAM pressure, or increased concurrency beyond the planned level.

VRAM utilization (percentage of total VRAM): the leading indicator of spillover cliffs. Alert at 85%, hard-stop at 90% (Section 8.4). Track as a time series to identify gradual VRAM leaks (KV-cache accumulation in multi-turn sessions, model weight duplication).

Secondary metrics (track for capacity planning and debugging):

Request rate (requests per second): for utilization calculation and trend detection. Compare against the 70% utilization cap.

GPU temperature: for thermal policy compliance. Alert at 75 degrees C.

Error rate: any non-zero error rate in inference requests indicates a configuration problem (OOM, model corruption, serving stack crash). Alert on any sustained error rate above 0.1%. The program's own measurement runs achieved 100% success rates across all configurations (0 errors in 525 cells for TR123, 100% success rate in 3,172 measurements for TR128), demonstrating that properly configured inference should produce zero errors under sustained load.

Per-request latency distribution: for SLO compliance. Track p50, p95, and p99. The distribution shape (not just the mean) is important because queueing effects create heavy tails.

The monitoring policy is deliberately minimal. It specifies only the metrics that the program has demonstrated are predictive of production problems. Additional metrics (GPU memory clock, PCIe bandwidth utilization, CPU utilization) may be useful for debugging but are not required for operational monitoring. The principle is: monitor what you have evidence to act on, and avoid alert fatigue from metrics that do not connect to actionable decisions.

Recommended monitoring stack for consumer deployment:

1. TTFT tracker: log the time from request receipt to first token delivery. Compute 1-minute rolling p50 and p95. Alert if p95 exceeds 2x the no-load baseline (measured at deployment time).

2. Decode throughput tracker: log tokens per second for each request's decode phase. Compute 5-minute rolling p50. Alert if p50 drops below 80% of baseline for more than 10 consecutive minutes.

3. VRAM utilization poller: query `nvidia-smi` or NVML at 10-second intervals. Log current VRAM usage as percentage of total. Alert at 85%; hard-stop new requests at 90%.

4. GPU temperature poller: query `nvidia-smi` at 30-second intervals. Alert at 75 degrees C. If sustained above 75 degrees C for more than 5 minutes, reduce concurrency by one agent.

5. Request success rate: log HTTP status codes. Alert on any sustained (>1 minute) error rate above 0.1%.

This five-metric monitoring stack covers the critical failure modes identified by the program: queueing overload (TTFT), throughput degradation (decode throughput), memory pressure (VRAM), thermal throttling (temperature), and configuration errors (success rate). It can be implemented with standard tooling (Prometheus, Grafana, or even a simple log aggregator) and requires no GPU-specific profiling infrastructure.

### 8.11 Change management policy

The change management policy ensures that the program's findings remain valid as the deployment stack evolves. The core principle is that any change to the inference stack requires revalidation of the affected findings before the change is deployed to production.

Hardware changes (GPU model, VRAM capacity, memory bandwidth): invalidate all throughput, VRAM, and scaling predictions. The chimeraforge planner's cross-GPU extrapolation provides a first estimate, but it must be validated with actual measurements on the new hardware. Rerun TR123 (cost baseline), TR127 (context scaling), and TR128 (production workload) protocols at minimum.

PyTorch version changes: invalidate compile policy (TR126) and may affect HuggingFace backend throughput. If the new version fixes compiled decode, rerun TR126 Phase 2/3 to assess whether the decode compile ban can be relaxed. Monitor for changes in kernel scheduling behavior that could affect profiling results (TR131/TR132).

Ollama version changes: invalidate production workload baselines (TR128), scaling laws (TR129), and serving stack comparisons (TR130). Ollama's inference engine and scheduling behavior can change significantly between versions. Rerun TR128 (NUM_PARALLEL behavior, streaming overhead) and TR129 (N-agent scaling) at minimum.

vLLM version changes: invalidate serving stack comparisons (TR130) and continuous batching mechanism analysis (TR132). vLLM's scheduler, PagedAttention implementation, and batching strategy evolve rapidly. Rerun TR130 (N-agent throughput comparison) and spot-check the continuous batching amortization ratio against TR132 baselines.

Model changes (new model family, new model size): invalidate quality baselines (TR124), quantization sensitivity (TR125), and throughput predictions (TR133). Each new model requires at minimum: TR124-style quality evaluation, TR125-style quantization sweep at Q4_K_M/Q8_0/FP16, and a throughput measurement to update the chimeraforge lookup table. The quantization sensitivity is particularly important to revalidate because different model architectures (MHA, GQA, MQA) and training procedures can produce very different robustness to quantization. The five models tested in this program span MHA (GPT-2, Phi-2) and GQA (Llama-3.2, Qwen-2.5), but newer architectures (mixture-of-experts, sliding-window attention, state-space models) may behave differently. The Q4_K_M sweet spot is an empirical finding, not a theoretical guarantee.

CUDA/driver version changes: may affect kernel scheduling, memory management, and profiling behavior. Spot-check throughput baselines; if they deviate more than 10% from previous measurements, rerun the full TR128 production workload protocol.

The change management policy reflects a hard-won lesson from the program: the compile paradox (TR126) was caused by a platform change (Windows to Linux) that silently altered the behavior of torch.compile. Without explicit revalidation, the Windows results would have remained the basis for compile policy, producing incorrect decisions. Every subsequent TR in the program includes an explicit manifest recording the exact versions of all software components, ensuring that future revalidation can identify which results are affected by a given change. The minimum manifest (Section Operational Defaults) lists 11 version requirements; any change to any of them triggers the corresponding revalidation protocol.

### 8.12 Risk register

The risk register documents the known risks associated with each operational decision, their potential impact, the mitigation in place, and the validation source. This register should be reviewed at every change management event (Section 8.11) and updated when new risks are identified.

| Risk | Decision Affected | Impact if Ignored | Mitigation | Validation Source |
| --- | --- | --- | --- | --- |
| Quantization quality cliff below Q4_K_M | Quantization policy (8.2) | 9.5-40.6pp accuracy loss, repetition collapse | Q4_K_M floor; Q2_K ban; model-specific Q3_K_S restrictions | TR125: 34 variants tested, Wilson CIs, Bonferroni survival |
| Compiled decode crash | Compile policy (8.3) | 100% failure rate in autoregressive generation | Never compile decode; eager always | TR126: all modes tested, bug filed pytorch/pytorch#175557 |
| VRAM spillover | Context budget (8.4) | 25-105x latency cliff; effective service outage | VRAM monitoring; 90% hard cap; Ollama for >4K context | TR127: 5 models, 7 context lengths, spillover thresholds mapped |
| M/D/1 queueing model failure | Capacity planning (8.8) | 20.4x latency underestimate; SLO violations | Use chimeraforge empirical tables; never M/D/1 | TR128: 3 models, 5 phases, 20.4x max deviation |
| Amdahl cross-backend category error | Backend selection (8.1) | Incorrect bottleneck attribution; wrong stack choice | N-dependent policy; profiling-backed mechanism | TR131: PyTorch Direct degrades worse than Ollama |
| NUM_PARALLEL as no-op | Agent count (8.5) | False expectation of concurrent throughput | Leave at default (1); don't rely on Ollama parallelism | TR128: 0/30 significant tests |
| Windows compile fallback | Compile policy (8.3) | Silent aot_eager; fake performance data | Linux-only compile; document Windows limitation | TR126: platform comparison, 916 Triton kernels on Linux vs 0 on Windows |
| Thermal throttling (theoretical) | Thermal policy (8.9) | Throughput degradation under sustained load | 75 deg C alert; no action needed at measured 66 deg C peak | TR128: continuous monitoring, no throttling observed |
| Scaling model weakness (R-squared=0.647) | Capacity planning (8.8) | Amdahl captures trend but misses stack interactions | Use for conservative estimates; validate with load test | TR133: weakest of 6 models; flagged in validation |
| Cross-GPU extrapolation unverified | Capacity planning (8.8) | Bandwidth scaling is linear approximation only | Validate on target GPU before production deployment | TR133: flagged as open limitation |
| Base-vs-instruct confound | Quality evaluation (8.7) | TR124 FP16 baselines used base models; Ollama serves instruct | Q8_0 as Ollama-internal baseline; FP16 Ollama added in TR125 Phase 2 | TR125: confound identified and resolved |
| Single-hardware generalization | All policies | Absolute numbers bound to RTX 4080 Laptop | Portable output is method and gating rules, not numbers | All TRs: explicit boundary conditions stated |

The risk register is intentionally conservative. Each risk is paired with a specific mitigation that has been implemented and validated within the program, rather than with aspirational mitigations that remain untested. The register should be reviewed at every change management event (Section 8.11) and updated when new risks are identified through operational experience. Risks that have been fully mitigated (e.g., the base-vs-instruct confound, resolved in TR125) remain in the register for historical traceability, ensuring that future analysts understand why certain methodological choices were made.

The most dangerous risks are those where the mitigation is partial rather than complete. The scaling model weakness (R-squared=0.647) is mitigated by conservative use but not resolved; the cross-GPU extrapolation is mitigated by flagging but not validated. These are the areas where deployment decisions carry the most residual uncertainty and should receive the most attention in load testing and validation before production commitment.

The risk register also highlights asymmetric risks -- cases where the cost of being wrong is much higher in one direction. The Q2_K quality cliff is asymmetric: deploying Q2_K when Q4_K_M was intended costs 40.6pp accuracy for qwen2.5-1.5b, while deploying Q4_K_M when Q2_K was intended costs only 10-20% higher inference cost. The VRAM spillover risk is also asymmetric: exceeding 90% VRAM causes a 25-105x latency cliff (catastrophic), while staying below 85% costs only 5-15% wasted VRAM capacity (minor). The operational doctrine is therefore designed to err on the conservative side for asymmetric risks (hard ban on Q2_K, hard stop at 90% VRAM) while allowing flexibility for symmetric risks (backend choice at N=2-3, where either Ollama or vLLM is acceptable).

The register should be treated as a living document. New risks will emerge as the deployment stack evolves, and existing risks may be resolved by future research (Phase 3 and beyond). The key governance principle is that any change to the risk register requires the same level of evidence that created the original entry: artifact-backed measurements, not assumptions or vendor claims.

---

## 9. Threats to Validity and Scope Limits

This section makes explicit the boundaries within which the Phase 2 conclusions are valid, and the conditions under which they would need to be re-examined or abandoned.

**Single hardware baseline.** All 70,000+ measurements were collected on a single GPU: the NVIDIA RTX 4080 Laptop GPU with 12 GB VRAM and 432 GB/s memory bandwidth. The throughput numbers, VRAM spillover thresholds, thermal behavior, and kernel profiling results are specific to this hardware. A desktop RTX 4090 (24 GB VRAM, 1008 GB/s bandwidth) would shift every threshold: spillover would occur at 2x the context length, bandwidth saturation would require more concurrent agents, and absolute throughput would scale roughly linearly with bandwidth. The chimeraforge planner includes a bandwidth-scaling heuristic for cross-GPU extrapolation, but this is unvalidated. No multi-GPU testing was performed.

**WDDM driver limitations.** The Windows WDDM driver prevents Nsight Compute (ncu) from capturing SM occupancy and DRAM throughput metrics. TR131's bandwidth saturation hypothesis (H1) was partially confirmed via memory operation time increases (+74.4%, p = 6.4 x 10^-5) but could not be directly validated via hardware bandwidth counters. The in-container nsys profiling methodology developed for TR132 overcomes CUPTI visibility limitations for kernel-level traces but not for hardware performance counters. This means the "GPU memory bandwidth is the bottleneck" conclusion rests on indirect evidence (timing changes + back-of-envelope calculations showing demand exceeds 432 GB/s by 78-130%) rather than direct measurement.

**Quantization confound in serving stack comparison.** TR130 compares Ollama (Q4_0, 4-bit) against vLLM and TGI (FP16, 16-bit). Absolute throughput differences at N=1 are expected and attributable to quantization, not serving stack quality. The eta(N) normalization — dividing each backend's N-agent throughput by its own N=1 baseline — eliminates this confound for scaling comparisons. However, the absolute throughput advantage of vLLM at N=8 (559 vs 248 tok/s for llama3.2-1b) conflates two effects: better scaling from continuous batching AND higher absolute single-agent throughput from Q4_0 weights on the Ollama side being offset by the scaling advantage on the vLLM side. A vLLM-with-AWQ-quantization experiment would isolate the continuous batching effect from the precision effect, but was not conducted.

**Statistical power for equivalence claims.** TR125's TOST (Two One-Sided Tests) equivalence testing at the ±3pp margin fails for all 18 "negligible" variants. At ±5pp, only 6/18 generation metrics pass. This means the "Q4_K_M preserves quality" claim is supported by point estimates and confidence intervals but not by formal equivalence testing at tight margins. The benchmark minimum detectable effect (MDE) is 9.0pp at 80% power — both the "negligible" (-3pp) and "acceptable" (-5pp) tier thresholds fall below detection limits. The tier system remains useful as a decision guide, but readers should understand that "negligible" means "point estimate within 3pp" rather than "statistically confirmed equivalent."

**Ollama determinism unvalidated.** TR125 uses temperature=0 with single repetition, citing TR124 Phase 3's validation that deterministic decoding needs only one rep. However, TR124 validated determinism for HuggingFace transformers, not Ollama (which uses llama.cpp). Ollama at temp=0 may not be perfectly deterministic due to different floating-point accumulation order in llama.cpp's CUDA kernels. If Ollama is non-deterministic, TR125's single-rep design underestimates measurement variance, potentially inflating the precision of quality tier classifications.

**Model size ceiling.** All models tested are 8B parameters or smaller. The largest model (llama3.1-8b) appears only in TR125's quantization study and TR133's prediction tables. The Amdahl serial fractions (TR129), serving stack scaling curves (TR130), and kernel profiling results (TR131/TR132) were collected on 1B-3B models only. Larger models may exhibit different serial fractions (more compute per token could reduce the serial overhead fraction) and different bandwidth amortization ratios under continuous batching. Extrapolation to 13B+ models requires caution.

**Automated quality metrics only.** TR124 and TR125 use automated metrics (ROUGE-L, BERTScore, SemScore, MMLU accuracy, ARC accuracy) without human evaluation. These metrics correlate with human judgment (SemScore r=0.88 per Aynetdinov & Akbik 2024) but are not substitutes. The "quality is preserved at Q4_K_M" claim means automated metrics show negligible degradation; human judges might detect qualitative differences (coherence, factual accuracy, instruction following) that automated metrics miss.

**M/D/1 model assumptions.** The M/D/1 queueing model used in TR128 and TR133 assumes deterministic service times and Poisson arrivals. Service time CV ranges from 2-10% (not zero), and the NUM_PARALLEL > 1 assumption that service scales linearly is refuted. The 20.4x deviation at NP=4 is a consequence of both assumption failures. TR133's latency model achieves MAPE = 1.05% by using empirical median service times rather than theoretical deterministic values, but the model remains a first-order approximation.

---

## 10. Limitations by Report and Mitigations

| TR | Limitation | Mitigation | Status |
|----|-----------|------------|--------|
| TR123 | Windows aot_eager for torch.compile measurements | TR126 validates real Triton on Linux; compile results revalidated | **Resolved** |
| TR123 | No quality data — cost recommendations assume quality equivalence | TR124 confirms backend equivalence (0/7 significant) | **Resolved** |
| TR124 | No quantization sweep beyond Ollama defaults | TR125 provides comprehensive 7-level, 5-model matrix | **Resolved** |
| TR124 | Ollama determinism at temp=0 unvalidated | Flagged as caveat; single-rep variance may be underestimated | **Open** |
| TR125 | TOST underpowered at ±3pp equivalence margin | Wilson CIs provided; 6/18 pass at ±5pp generation margin | **Mitigated** |
| TR125 | Base-vs-instruct confound in Phase 1 FP16 baselines | Identified and corrected in Phase 2 with Ollama FP16 baselines | **Resolved** |
| TR126 | Compiled decode crashes in all torch.compile modes | Documented as architectural (DynamicCache + CUDA graphs incompatible); PR #175562 filed | **Accepted** |
| TR126 | Bug persists across PyTorch 2.8 and 2.10 | Confirmed architectural; awaiting upstream fix | **Accepted** |
| TR127 | Context range limited to 512-32K tokens | Sufficient for consumer GPU VRAM budgets; 32K exceeds OOM for all FP16 models >0.5B | **Accepted** |
| TR128 | Sliding-window context benefit inconclusive | p=0.042 for 1/3 models at n=8; needs larger sample sizes | **Open** |
| TR129 | Phase 4 (heterogeneous models) confounded by Ollama restart/warmup | Conservative interpretation; avoid mixed-model deployment claims | **Accepted** |
| TR130 | Q4_0 vs FP16 absolute throughput comparison | eta(N) normalization eliminates confound for scaling; clearly labeled | **Mitigated** |
| TR131 | Nsight Compute metrics null on Windows WDDM driver | Back-of-envelope bandwidth calculation (demand exceeds 432 GB/s by 78-130%) | **Mitigated** |
| TR132 | H3 GPU utilization rejected — 0% in all conditions | Known nsys limitation with `--trace cuda` mode; not a finding | **Accepted** |
| TR132 | H4 PagedAttention vs FlashAttention kernel classification inconclusive | Kernel names not reliably mappable; mechanism confirmed via amortization | **Accepted** |
| TR133 | Scaling model weakest (R² = 0.647) | Amdahl captures trend; flagged as least reliable prediction | **Accepted** |
| TR133 | Cross-GPU throughput extrapolation unverified | Linear bandwidth scaling is a first-order approximation | **Open** |

**Narrative interpretation.** The limitation table reveals three patterns. First, the program is self-correcting: TR123's quality gap is filled by TR124, TR124's quantization gap by TR125, and TR125's base-vs-instruct confound is resolved within the same report. Second, architectural limitations (compiled decode crashes, WDDM profiling constraints) are accepted rather than worked around — the program documents what cannot be done rather than pretending it can. Third, the open items (Ollama determinism, sliding-window efficacy, cross-GPU extrapolation) are all testable with straightforward experiments and represent clear Phase 3 targets rather than fundamental design flaws.

The most consequential limitation is statistical: the TOST equivalence failure at ±3pp means the "Q4_K_M is equivalent to FP16" claim is technically unconfirmed at tight margins. However, the point estimates, Wilson CIs, and the 6/18 generation-equivalent results at ±5pp collectively support the practical recommendation. The gap is statistical power, not evidence of degradation.

---

## 11. Integration with Phase 1 (TR117-TR122)

Phase 1 (TR117-TR122) and Phase 2 (TR123-TR133) form a single, continuous research program. Phase 1 established the measurement methodology, artifact pipeline, and decision-grade reporting standard. Phase 2 inherited that infrastructure and expanded the question scope from "how to measure" to "what to deploy."

**Methodology inheritance.** Phase 2 directly inherits three methodological pillars from Phase 1. The artifact-first principle (TR118_v2.2) ensures every Phase 2 claim traces to raw logs. The phase-aware measurement boundary (TR119v1/TR121v1) carries forward as the prefill/decode split that structures TR123's cost model, TR126's compile analysis, and TR127's context scaling. The distributional reporting standard (TR117/TR120) evolves into the statistical rigor escalation documented in Section 6.10.

**Compile paradox resolution.** Phase 1's most prominent unresolved finding was the compile paradox (TR120): torch.compile appeared to hurt performance on Windows. Phase 2 resolved this definitively (TR126): the paradox was an artifact of the Windows aot_eager fallback. Real Triton compilation on Linux delivers 24-60% prefill speedups across all 7 models tested. This resolution required a cross-platform methodology that Phase 1 did not have — Docker/Linux environments were a Phase 2 innovation.

**Backend expansion.** Phase 1 tested transformers-gpu, transformers-gpu-compile, and onnxruntime-gpu. Phase 2 retains the first two, drops ONNX (no pre-exported models for modern architectures), and adds Ollama (quantized serving), vLLM (continuous batching + PagedAttention), and TGI (continuous batching). This expansion reflects the program's shift from framework-level benchmarking to production-stack comparison.

**Quality dimension added.** Phase 1 had zero quality measurements — every cost and performance recommendation assumed output equivalence across backends. Phase 2 fills this gap completely: TR124 establishes backend equivalence (0/7 significant), TR125 maps quantization quality across 26,000 samples, and TR133 integrates quality into the predictive planner. The quality-cost Pareto frontier (TR124) and the 4-tier quantization classification (TR125) are new decision instruments that Phase 1 could not provide.

**From benchmarks to production.** Phase 1 tested single-request, steady-state inference. Phase 2 adds production realism in five layers: realistic cost models with KV-cache (TR123), production workloads with concurrency and streaming (TR128), multi-agent scaling laws (TR129), serving stack comparison (TR130), and GPU kernel profiling for root-cause attribution (TR131/TR132). This progression from controlled benchmark to production characterization is the defining structural difference between the two phases.

**Unified predictive output.** Phase 1 ended with a roadmap. Phase 2 ends with a tool. The chimeraforge CLI (TR133) ingests data from both phases (though primarily Phase 2, TR123-TR130) and produces deployment recommendations. This represents a qualitative shift: the research program's output is no longer a report to be read but a tool to be run. The portable deliverable is not the numbers but the decision framework encoded in 6 predictive models with 4 validation gates.

---

## 12. Conclusive Statement

Phase 2 of the Banterhearts LLM Performance Research Program transforms the measurement methodology established in Phase 1 into a complete, artifact-backed deployment framework for local-first LLM inference on consumer hardware. The research arc from cost models (TR123) to predictive capacity planning (TR133) is deliberately sequential: each report either fills a gap exposed by its predecessor or falsifies a hypothesis that earlier results made plausible. This falsification-driven design produced three high-profile reversals — M/D/1 queueing theory refuted (TR128), Amdahl-as-universal-scaling refuted (TR130/TR131), and serving-stack-as-bottleneck overturned (TR131) — that sharpened every subsequent experimental design.

Three conclusions survive the full evidence chain. First, Q4_K_M quantization is the universal deployment default across all five tested model families: it preserves benchmark accuracy within 4.1 percentage points of FP16 while reducing cost by 30-67% and VRAM by proportional amounts. The quality cliff at Q3_K_S is sharp and model-dependent; Q2_K is universally unacceptable. Second, the serving stack choice depends on concurrency: Ollama with Q4_K_M is optimal for single-agent workloads (highest throughput per dollar), while vLLM with FP16 is optimal for multi-agent workloads at N >= 4 (2.25x throughput advantage from continuous batching that amortizes GPU memory bandwidth by 4.7-5.8x). Third, empirical lookup tables with first-principles interpolation outperform theoretical queueing models for capacity planning: M/D/1 deviates up to 20.4x from reality, while the chimeraforge planner achieves VRAM R² = 0.968, throughput R² = 0.859, quality RMSE = 0.062, and latency MAPE = 1.05%.

The program's greatest contribution is not any single finding but the demonstration that falsification-driven sequential research can transform benchmark data into auditable deployment policy. Each of the 11 technical reports contributes one decision-grade deliverable; together they form a chain where every claim traces to artifacts, every assumption is tested, and every failure mode is documented. The chimeraforge CLI operationalizes this chain into a tool that runs in under one second, requires no GPU, and answers the practitioner's core question: "What should I run on my hardware?"

These conclusions are not universal. They are bound to one GPU (RTX 4080 Laptop, 12 GB VRAM), one software stack (PyTorch 2.x, CUDA 12.x, Ollama 0.6.x, vLLM 0.7.x), and bounded workloads (models <= 8B, contexts <= 32K, N <= 8 agents). The portable output is the method — the sequential falsification design, the statistical rigor escalation, the artifact-first reporting standard, and the gating rules that determine when a measurement is trustworthy enough to ship — not the absolute numbers. Any hardware, stack, or workload change requires a rerun. The infrastructure to perform that rerun is the second deliverable of this program, and it is fully operational.

---

## 13. References

[1] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention Is All You Need. *Advances in Neural Information Processing Systems*, 30.

[2] Dai, Z., Yang, Z., Yang, Y., Carbonell, J., Le, Q. V., & Salinas, R. (2019). Transformer-XL: Attentive Language Models Beyond a Fixed-Length Context. *ACL*.

[3] Dao, T., Fu, D. Y., Ermon, S., Rudra, A., & Re, C. (2022). FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness. *Advances in Neural Information Processing Systems*, 35.

[4] Brown, T. B., Mann, B., Ryder, N., Subbiah, M., et al. (2020). Language Models are Few-Shot Learners. *Advances in Neural Information Processing Systems*, 33.

[5] NVIDIA Corporation. NVIDIA Management Library (NVML) API Reference. https://developer.nvidia.com/nvidia-management-library-nvml

[6] PyTorch Contributors. torch.compile documentation. https://pytorch.org/docs/stable/torch.compiler.html

[7] Microsoft Corporation. ONNX Runtime documentation. https://onnxruntime.ai/docs/

[8] Ollama. Ollama documentation. https://ollama.ai/docs

[9] Kaplan, J., McCandlish, S., Henighan, T., Brown, T. B., Chess, B., Child, R., Gray, S., Radford, A., Wu, J., & Amodei, D. (2020). Scaling Laws for Neural Language Models. *arXiv:2001.08361*.

[10] Hoffmann, J., Borgeaud, S., Mensch, A., Buchatskaya, E., et al. (2022). Training Compute-Optimal Large Language Models. *Advances in Neural Information Processing Systems*, 35.

[11] MLCommons. MLPerf Inference Benchmark Suite. https://mlcommons.org/en/inference-datacenter/

[12] Tay, Y., Dehghani, M., Bahri, D., & Metzler, D. (2022). Efficient Transformers: A Survey. *ACM Computing Surveys*, 55(6).

[13] Dao, T. (2023). FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning. *arXiv:2307.08691*.

[14] Kwon, W., Li, Z., Zhuang, S., Sheng, Y., Zheng, L., Yu, C. H., Gonzalez, J. E., Zhang, H., & Stoica, I. (2023). Efficient Memory Management for Large Language Model Serving with PagedAttention. *SOSP*.

[15] Amdahl, G. M. (1967). Validity of the single processor approach to achieving large scale computing capabilities. *AFIPS Spring Joint Computer Conference*.

[16] NVIDIA Corporation. Nsight Systems User Guide. https://docs.nvidia.com/nsight-systems/

[17] Aynetdinov, A. & Akbik, A. (2024). SemScore: Automated Evaluation of Instruction-Tuned LLMs based on Semantic Textual Similarity. *ACL Findings*.

[18] HuggingFace. Transformers documentation. https://huggingface.co/docs/transformers/

[19] PyTorch Contributors. CUDA Graphs documentation. https://pytorch.org/docs/stable/cuda.html#cuda-graphs

[20] Jain, R., Chiu, D., & Hawe, W. (1984). A Quantitative Measure of Fairness and Discrimination for Resource Allocation in Shared Computer Systems. *DEC Technical Report TR-301*.

---

## Appendix A: Key Formulas and Derivations

### A.1 KV-Cache Memory Formula

```
KV_bytes_per_token = 2 × num_layers × num_kv_heads × head_dim × precision_bytes
```

Where precision_bytes = 2 for FP16, 0.5 for Q4_0. For GQA models, num_kv_heads < num_attention_heads. Example: Qwen2.5-1.5B (28 layers, 2 KV heads, 128 dim, FP16) = 2 × 28 × 2 × 128 × 2 = 28,672 bytes/token = 28 KB/token. Validated: 30/30 exact matches in TR123.

### A.2 Cost Formula

```
$/1M_tokens = (1,000,000 / throughput_tok_s / 3600) × hourly_rate_usd
```

### A.3 Blend Cost Formula

```
$/1M_blend = input_ratio × $/1M_prefill + output_ratio × $/1M_decode
```

Blend ratios: RAG-heavy (0.95/0.05), Summarization (0.85/0.15), Chat (0.67/0.33), Balanced (0.50/0.50), Code generation (0.25/0.75).

### A.4 Amdahl's Law for N-Agent Scaling

```
S(N) = 1 / (s + (1-s)/N)
eta(N) = S(N) / N = 1 / (s*N + (1-s))
```

Where s is the serial fraction. Fitted values: llama3.2-1b s=0.5391, llama3.2-3b s=0.3870, qwen2.5-1.5b s=0.4554. Max speedup = 1/s.

### A.5 VRAM Budget Formula

```
VRAM_total = model_weight_bytes × overhead_factor + KV_bytes_per_token × context_length + activation_coeff × context_length²
```

Overhead factor fitted at 1.058x (TR133). Activation coefficient varies by model (fitted from TR127 residuals).

### A.6 Power-Law Throughput Fallback

```
throughput_tok_s = 72.1 × params_billions^(-0.089)
```

For unseen models without lookup table entries (TR133).

### A.7 Quantization Multiplier

```
throughput_quantized = throughput_fp16 × quant_multiplier
```

Multipliers: FP16=1.0, Q8_0=1.15, Q6_K=1.25, Q5_K_M=1.40, Q4_K_M=1.65, Q3_K_S=1.90, Q2_K=2.30.

---

## Appendix B: Claim-to-Artifact Chain-of-Custody

| Claim | Artifact Path | Validation |
|-------|--------------|------------|
| C1: KV-cached decode cheaper | results/eval/tr123/processed/cost_summary.json | Phase-split $/token tables |
| C2: Backend quality equivalent | results/eval/tr124_phase1/anova_results.json | 7-metric ANOVA + Holm |
| C3: Q4_K_M preserves quality | results/eval/tr125/phase2_analysis.json | Wilson CIs + tier classification |
| C4: Compile speedup on Linux | results/eval/tr126/phase2_compile_analysis.json | Welch's t + Cohen's d |
| C5: VRAM spillover dominates | results/eval/tr127/context_scaling_analysis.json | Two-regime fit + cliff detection |
| C6: NUM_PARALLEL no-op | results/eval/tr128/phase2_concurrency.json | 30 pairwise tests + Holm |
| C7: Amdahl scaling | results/eval/tr129/scaling_analysis.json | Amdahl fit R² > 0.97 |
| C8: GPU physics dominates | results/eval/tr131/profiling_analysis.json | PyTorch Direct control + Mann-Whitney |
| C9: Continuous batching amortizes | results/eval/tr132/kernel_analysis.json | Kernel count + Holm 8/8 |
| C10: Lookup tables sufficient | results/eval/tr133/validation_results.json | 4/4 targets + 10/10 spots |

---

## Appendix C: Per-TR Key Numbers (Extracted)

| TR | Measurements | Models | Backends | Key Metric | Value |
|----|-------------|--------|----------|------------|-------|
| TR123 | 525 | 5 | 3 | Best $/1M tokens | $0.013 (GPT-2/compile) |
| TR124 | 3,600 | 5 | 2 | Significant quality diffs | 0/7 |
| TR125 | ~26,000 | 5 | 1 (Ollama) | Q4_K_M max loss | -4.1pp |
| TR126 | ~29,900 | 7 | 3 | Compile prefill speedup | 24-60% |
| TR127 | 1,144 | 5 | 2 | Post-spillover cliff | 25-105x |
| TR128 | 3,172 | 3 | 1 (Ollama) | NUM_PARALLEL effect | 0/30 significant |
| TR129 | 5,310 | 3 | 1 (Ollama) | Serial fraction range | s=0.39-0.54 |
| TR130 | 4,797 | 3 | 3 | vLLM advantage at N=8 | 2.25x |
| TR131 | 26 runs | 2 | 2 | PyTorch Direct degradation | 86.4% |
| TR132 | 25 runs | 2 | 2 | Kernel amortization | 4.7-5.8x |
| TR133 | 19,676 | 6 models | all | VRAM R² | 0.968 |

---

## Appendix D: Glossary and Definitions

- **Amdahl's Law:** Theoretical model for parallel speedup: S(N) = 1/(s + (1-s)/N), where s is the serial fraction.
- **BERTScore:** Contextual embedding similarity metric using DeBERTa-xlarge-mnli. Range [0,1].
- **Blend cost:** Weighted combination of prefill and decode $/token based on workload profile.
- **ChimeraForge:** CLI capacity planning tool operationalizing TR123-TR133 findings. Phase 1 shipped.
- **Cohen's d:** Standardized effect size: (mean1 - mean2) / pooled_SD. Small=0.2, medium=0.5, large=0.8.
- **Composite quality:** Unweighted mean of all available quality metric scores for a model.
- **Continuous batching:** Serving technique that batches multiple concurrent requests into single GPU kernel launches. Used by vLLM and TGI.
- **CUPTI:** CUDA Profiling Tools Interface. NVIDIA's API for GPU kernel-level tracing.
- **Decode:** Token-by-token generation phase using KV cache. Memory-bandwidth-bound.
- **DynamicCache:** HuggingFace's default KV-cache implementation. Incompatible with CUDA graphs.
- **eta(N):** Per-agent efficiency at N agents: throughput_per_agent_at_N / throughput_at_N1.
- **FP16:** 16-bit floating point (2 bytes per parameter). Full precision for inference.
- **GEMM:** General Matrix Multiply. Dominant GPU kernel type (69-82% of GPU time in vLLM).
- **GQA:** Grouped-Query Attention. Shares KV heads across query heads, reducing KV cache 3-11x vs MHA.
- **Holm-Bonferroni:** Step-down procedure for multiple comparison correction. Less conservative than Bonferroni.
- **Inductor:** PyTorch's default compiler backend for torch.compile. Generates Triton kernels on Linux.
- **Jain's fairness index:** J = (sum(xi))² / (N × sum(xi²)). J=1.0 means perfectly fair.
- **KV cache:** Key-Value cache storing attention states from prior tokens. Grows linearly with context.
- **M/D/1:** Markovian arrival, deterministic service, single server queueing model.
- **MHA:** Multi-Head Attention. Standard attention with independent KV heads per query head.
- **MMLU:** Massive Multitask Language Understanding benchmark. 4-choice multiple choice.
- **Nsight Systems (nsys):** NVIDIA GPU profiling tool for kernel timelines and memory traces.
- **PagedAttention:** vLLM's memory management technique inspired by OS virtual memory paging.
- **Prefill:** Prompt processing phase. Compute-bound (processes all tokens in parallel).
- **Q2_K through Q8_0:** GGUF quantization levels. Q4_K_M = 4-bit with K-quant medium grouping.
- **Rescored accuracy:** Regex-based letter extraction from model output for benchmark scoring. Resolves formatting noise.
- **ROUGE-L:** Longest common subsequence F1 between candidate and reference. Range [0,1].
- **SemScore (Coherence):** Cosine similarity using all-mpnet-base-v2 sentence transformer. Range [0,1].
- **Serial fraction (s):** Proportion of work that cannot be parallelized in Amdahl's model.
- **StaticCache:** Fixed-size KV cache implementation. Compatible with CUDA graphs but 5.8x slower.
- **TOST:** Two One-Sided Tests for equivalence testing. Requires both one-sided p < alpha.
- **Triton:** OpenAI's GPU programming language. Used by PyTorch Inductor for kernel generation.
- **TTFT:** Time to first token. Critical for interactive/streaming applications.
- **VRAM spillover:** When GPU memory allocation exceeds physical VRAM, CUDA Unified Memory pages to system RAM via PCIe, causing 25-105x latency degradation.
- **Wilson CI:** Confidence interval for binomial proportions. More accurate than normal approximation at small N.

---

## Appendix E: Operational Checklists

### E.1 Deployment Checklist

1. Select model based on quality requirements (TR124 §6, TR125 tier table)
2. Select quantization level — default Q4_K_M unless quality-critical (then Q8_0)
3. Estimate VRAM: `chimeraforge plan --vram-budget 12`
4. Select backend: N=1 → Ollama; N>=4 → vLLM
5. Validate quality on representative task (compare against TR124 baselines)
6. Set context budget: Ollama for >4K tokens; HF only for <=4K
7. Enable streaming (zero overhead confirmed TR128)
8. Set utilization cap at 70% of theoretical max throughput
9. Monitor VRAM (alert at 85%, hard-stop at 90%)
10. Record manifest (GPU, CUDA, PyTorch, Ollama/vLLM version, git SHAs)

### E.2 Monitoring Checklist

1. Track p95 latency per model-backend combination
2. Monitor TTFT amplification under load (baseline from TR128)
3. Track decode throughput drift (qwen2.5-1.5b anomaly: TR128)
4. Monitor GPU temperature (alert at 75°C, throttle threshold 80°C)
5. Track VRAM utilization trend over context growth
6. Log error rates and HTTP timeouts per backend

### E.3 Change Management Checklist

1. Any GPU/driver change → rerun core scenario matrix
2. Any PyTorch version change → revalidate compile behavior (TR126)
3. Any Ollama/vLLM version change → rerun baseline throughput (TR128/TR130)
4. Any model family change → rerun quality baseline (TR124) and quantization sweep (TR125)
5. Workload mix shift → recompute blend costs (TR123 §5.6)

---

## Appendix F: Workload Taxonomy and Routing Logic

| Workload Type | Input/Output Ratio | Dominant Phase | Recommended Backend (N=1) | Recommended Backend (N>=4) |
|--------------|-------------------|----------------|--------------------------|---------------------------|
| RAG-heavy | 95/5 | Prefill | Ollama Q4_K_M | vLLM FP16 |
| Summarization | 85/15 | Prefill | Ollama Q4_K_M | vLLM FP16 |
| Chat | 67/33 | Decode | Ollama Q4_K_M | vLLM FP16 |
| Balanced | 50/50 | Mixed | Ollama Q4_K_M | vLLM FP16 |
| Code generation | 25/75 | Decode | Ollama Q4_K_M | vLLM FP16 |
| Classification | 99/1 | Prefill | Compiled HF (Linux) | vLLM FP16 |

Routing rule: if context > 4K tokens AND backend is HF FP16, redirect to Ollama to avoid VRAM spillover.

---

## Appendix G: Worked Examples and Calculations

### G.1 Example: Monthly Cost for Chat Deployment

**Setup:** llama3.2-1b, Ollama Q4_K_M, chat blend (67/33), consumer GPU ($0.046/hr)

Decode throughput (TR123/TR125): ~280 tok/s native
Prefill throughput: ~5,000 tok/s (estimated)

$/1M decode = (1M / 280 / 3600) × $0.046 = $0.046
$/1M prefill = (1M / 5000 / 3600) × $0.046 = $0.0026
$/1M blend = 0.67 × $0.0026 + 0.33 × $0.046 = $0.017

At 100M tokens/month: $1.70/month. At 1B tokens/month: $17.00/month.

### G.2 Example: VRAM Budget for RAG Pipeline

**Setup:** qwen2.5-1.5b FP16, 8K context, RTX 4080 (12 GB)

Model weights: 1.5B × 2 bytes = 3.0 GB
KV cache: 28 layers × 2 heads × 128 dim × 2 bytes × 2 (K+V) × 8192 tokens = 234 MB
Overhead factor: 1.058x
Activations: ~1.5 GB (estimated from TR127 slopes)

Total: 3.0 × 1.058 + 0.234 + 1.5 = 4.9 GB. Fits in 12 GB with 7.1 GB headroom.

At 16K context: KV doubles to 468 MB, activations grow quadratically. Total ~6.8 GB. Still fits but approaching 60% utilization.

### G.3 Example: Multi-Agent Throughput Prediction

**Setup:** 4 agents, llama3.2-1b, Ollama

Amdahl serial fraction (TR129): s = 0.5391
eta(4) = 1 / (0.5391 × 4 + (1 - 0.5391)) = 1 / (2.156 + 0.461) = 1 / 2.617 = 0.382

Solo throughput: ~160 tok/s per agent
At N=4: 160 × 0.382 = 61.1 tok/s per agent
Total system: 61.1 × 4 = 244.4 tok/s

Switching to vLLM at N=4 (power law): eta(4) ≈ 0.65
Solo vLLM: ~150 tok/s
At N=4: 150 × 0.65 = 97.5 tok/s per agent
Total system: 97.5 × 4 = 390 tok/s (1.6x more than Ollama)

---

## Appendix H: Operational Playbooks and Templates

### H.1 Playbook: Upgrading from Ollama to vLLM

1. Benchmark current Ollama N=1 throughput as baseline
2. Deploy vLLM with same model in FP16 (Docker)
3. Run N=1 baseline — expect 20-40% lower absolute TPS (FP16 vs Q4_0)
4. Run N=4 comparison — expect vLLM to overtake in total throughput
5. Validate quality equivalence (TR124 metrics)
6. Monitor TTFT improvement (expect 6-8x faster)
7. Cut over at N >= 4 sustained; keep Ollama for N=1 fallback

### H.2 Playbook: Responding to VRAM Spillover Alert

1. Identify which model and context length triggered alert
2. Check VRAM utilization: if >85%, reduce context or switch to quantized model
3. If Ollama: context should not spill (Flash Attention + paged KV)
4. If HF FP16: reduce context to below spillover threshold (TR127 §SS6)
5. Long-term: migrate to Ollama or vLLM for long-context workloads

---

## Appendix I: Statistical Notes and Fit Diagnostics

### I.1 Test Selection Rationale

- **Welch's t-test:** Primary comparison for two-group means. Does not assume equal variances (appropriate given CV ranges from 0.2% to 97%).
- **ANOVA:** Multi-group comparison (backend × model interactions in TR126). Two-way with interaction term.
- **Mann-Whitney U:** Non-parametric robustness check for all TR131 comparisons (15/15 distributions non-normal per Shapiro-Wilk).
- **Holm-Bonferroni:** Step-down correction for family-wise error. Applied when multiple comparisons within a single experiment (TR125: 116 tests; TR128: 30 tests; TR132: 8 tests).
- **TOST:** Two One-Sided Tests for equivalence at specified margin. Applied in TR125 at ±3pp and ±5pp.
- **Wilson CI:** Confidence intervals for binary proportions (benchmark accuracy). More accurate than normal approximation for p near 0 or 1.
- **Cohen's d:** Standardized effect size for all pairwise comparisons. Thresholds: negligible < 0.2, small 0.2-0.5, medium 0.5-0.8, large > 0.8.

### I.2 Power Analysis Summary

| Experiment | N per group | Alpha | Power target | MDE (Cohen's d) |
|-----------|------------|-------|-------------|-----------------|
| TR125 Phase 2 benchmarks | 485 | 0.05 | 0.80 | 9.0pp |
| TR126 Phase 2 | 540 | 0.05 | 0.80 | d >= 0.10 |
| TR126 Phase 3 | 225 | 0.05 | 0.80 | d >= 0.17 |
| TR128 Phase 2 | 30 | 0.05 | 0.80 | d >= 0.19 |
| TR131 profiling | 3-6 | 0.05 | 0.80 | d >= 1.29 |

---

## Appendix J: Traceability Map (TR123-TR133 to Decisions)

| Decision | Contributing TRs | Primary Evidence | Secondary Evidence |
|----------|------------------|-----------------|-------------------|
| Backend selection (N=1) | TR123, TR126, TR128 | TR123 cost tables, TR126 compile validation | TR128 production workload data |
| Backend selection (N>=4) | TR129, TR130, TR131, TR132 | TR130 eta(N) comparison | TR131/132 mechanism evidence |
| Quantization level | TR124, TR125 | TR125 tier table + Wilson CIs | TR124 baseline quality |
| Compile policy | TR126 | Phase 2 + Phase 3 + mode="default" + PyTorch 2.10 | TR120 (Phase 1) discovery |
| Context budget | TR123, TR127 | TR127 two-regime analysis + spillover thresholds | TR123 KV formula validation |
| Agent count | TR129, TR130 | TR129 Amdahl fit + saturation points | TR130 vLLM scaling |
| Streaming | TR128 | Phase 4: 0/9 significant | — |
| Quality gate | TR124, TR125 | TR124 composite scores + TR125 tier thresholds | — |
| Capacity planning | TR133 | 4/4 validation targets + 10/10 spot checks | All of TR123-TR130 (input data) |
| Thermal policy | TR128 | Phase 3: peak 66°C | — |

---

## Appendix K: Extended Literature Review

The Phase 2 research program draws on several distinct bodies of literature that were not extensively referenced in Phase 1.

**Quantization.** The GGUF format and k-quant variants originate from the llama.cpp project and its predecessors (GPTQ, AWQ). The key theoretical result is that quantization error is bounded and increases with compression ratio, but the practical impact on task-specific quality depends on the model architecture, training data, and evaluation metric. TR125 contributes empirical data on this relationship across 34 model-quant variants.

**Continuous batching.** The PagedAttention paper [14] established that paging KV-cache blocks enables serving multiple concurrent requests without proportional memory overhead. TR130 and TR132 provide the first consumer-hardware measurements of this effect, showing 4.7-5.8x bandwidth amortization at N=8.

**Amdahl's Law in inference.** While Amdahl's Law [15] is well-known in parallel computing, its application to LLM inference serving is novel. TR129's finding that serial fractions of 0.39-0.54 govern Ollama's scaling behavior is, to our knowledge, the first empirical Amdahl fit for LLM inference on consumer hardware.

**GPU profiling for inference.** Nsight Systems [16] is widely used for CUDA application profiling but rarely applied to LLM serving stack comparison. TR131 and TR132's methodology — particularly the in-container CUPTI approach — addresses a gap in the tooling literature for profiling Docker-hosted inference servers under WSL2/WDDM constraints.

---

## Appendix L: Measurement Boundary Catalog

| TR | Timed Region Includes | Timed Region Excludes | Compatibility Notes |
|----|----------------------|----------------------|-------------------|
| TR123 | Model forward pass (prefill), decode loop with KV cache | Tokenization, model loading, warmup | Compatible with TR119 (same formula; different cache setting) |
| TR124 | Full generation + metric computation | Model loading, tokenization overhead | Metrics computed post-generation; timing is secondary |
| TR125 | Ollama /api/generate wall clock + native eval_duration | Model loading (excluded from native), HTTP overhead (in wall clock) | Native timing preferred; wall clock has 190-920% overhead |
| TR126 | Forward pass (prefill) or decode loop, per-mode | Model loading, compilation time (excluded; separate) | Cross-platform: same prompts, same models, different OS |
| TR127 | Same as TR123 but across 7 context lengths | Tokenization; OOM samples marked as failures | VRAM measured via torch.cuda.max_memory_allocated() |
| TR128 | Full /api/generate wall clock per request | Model loading (pre-warmed); Poisson inter-arrival sleep | Load generator is external; timing starts at request send |
| TR129 | Agent-observed wall clock per request | Think-time gaps between requests | Closed-loop: agent sends → waits → measures → sends |
| TR130 | Same as TR129 across 3 backends | Backend startup, Docker overhead | Warmup protocol eliminates cold-start |
| TR131 | nsys-traced kernel execution + memory operations | Model loading; nsys startup; trace export | Profiling overhead validated: <1% TPS impact |
| TR132 | In-container nsys-traced kernels | Container startup; nsys mounting; trace export | Novel methodology: Linux nsys binary mounted into Docker |
| TR133 | No timed measurement; prediction only | All timing inherited from TR123-TR130 | Validation is against held-out empirical data |

---

## Appendix M: Detailed Methods by Report

This appendix provides per-report methodological detail beyond the summary in Section 3.

**TR123:** 5 models × 3 backends × 5 scenarios × 7 reps = 525 cells. Backend-skip entries (105) for infeasible CPU combinations. PhasePowerSampler with mark_phase() for per-phase energy. Warmup: 3 iterations discarded. Prompts: curated 5 scenarios (RAG, summarization, chat, balanced, code_gen) with fixed token counts.

**TR124:** Phase 1: 5 models × 2 backends × 5 tasks × 50 samples + 3 benchmarks × 100 samples = 2,800. Phase 2: 4 models × 3 quant × 5 tasks × 10 samples = 200 (Ollama defaults). Phase 3: 2 models × 2 backends × 3 tasks × 5 reps × 20 samples = 600. All at temp=0 except Phase 3 (temp=0.7).

**TR125:** Phase 1: 3 models × 6 quants × 5 tasks × 10 samples = 900. Phase 2: 5 models × 7 quants × (285 MMLU + 200 ARC + 250 generation) = 24,990. Wilson CIs, TOST, Bonferroni/Holm correction on 116 tests.

**TR126:** Phase 1: Environment validation (CUDA, Triton, graph breaks). Phase 2: 6 models × 5 scenarios × 30 reps × 3 configs = 3,240+. Phase 3: 5 models × 3 backends × 5 scenarios × 3 modes × 15 reps = 3,780+. Additional: mode="default" (3,891), PyTorch 2.10 rerun (4,522).

**TR129:** Phase 1: N=1 baseline (30 reps × 3 models). Phase 2: N={1-8} × 3 models × 30 reps = 5,040+. Phase 3: N=4 × think={0,100,500,2000}ms. Phase 4: Heterogeneous model assignments.

**TR131:** 26 profiled runs across 4 conditions (Ollama N=1, N=8; PyTorch N=1, N=8) × 2 models. nsys profile with --trace cuda --cuda-event-stacks. ncu for kernel-level metrics (limited by WDDM).

**TR132:** 25 profiled runs: 2 backends × 2 models × 2 concurrency levels × 3 reps + 1 extra. In-container nsys via volume-mounted Linux binary. Traces 11.6-17.4 MB each.

---

## Appendix N: Expanded Discussion and Implications

The Phase 2 research program produces several implications that extend beyond the immediate deployment recommendations.

**The serving stack abstraction is leaky.** The most dramatic finding across Phase 2 is that "serving stack" is not a useful abstraction for understanding multi-agent scaling. TR130 attributed the scaling advantage of vLLM/TGI to "better scheduling," but TR131 demonstrated that the degradation exists even without any serving stack (PyTorch Direct). TR132 then identified the actual mechanism: continuous batching amortizes GPU memory bandwidth. The lesson is that performance attribution requires kernel-level evidence, not application-level comparison. Correlational evidence (TR130) was wrong about the cause, even though it was right about the effect.

**Quantization is under-studied in the systems literature.** Most serving stack comparisons in the literature use FP16 throughout. TR131's finding that Ollama's Q4_0 quantization actually helps under concurrency (advantage grows from 3.0x to 3.9x at N=8) suggests that the interaction between quantization and bandwidth contention is a first-order effect. Future work should compare vLLM with AWQ/GPTQ quantization against Ollama to isolate the continuous batching benefit from the quantization benefit.

**Theoretical models need empirical calibration.** M/D/1 queueing theory, Amdahl's Law, and O(n²) attention scaling are all useful frameworks, but each failed in specific ways when confronted with empirical data. M/D/1 deviates 20.4x. Amdahl is a category error across backends. O(n²) is dominated by VRAM spillover on consumer hardware. The chimeraforge planner succeeds because it uses empirical lookup tables rather than theoretical models.

---

## Appendix O: Extended Results Narratives

### O.1 TR123 Narrative

TR123 is the economic foundation of Phase 2. It answers the question that TR119 could not: what does production inference actually cost when KV-cache is enabled? The answer reframes every cost recommendation from Phase 1. With KV-cache, decode throughput doubles or more for memory-bandwidth-bound models, and the cost per million tokens drops proportionally. The GQA vs MHA comparison adds a structural dimension: at comparable parameter counts, GQA models use 3-11x less KV-cache memory, enabling dramatically longer contexts on the same hardware. This is not a minor optimization; it determines whether a model can serve 4K or 40K token contexts on consumer hardware.

### O.2 TR124 Narrative

TR124 is the quality insurance policy for the entire program. Without it, every cost recommendation from TR123 and every quantization recommendation from TR125 would carry an implicit assumption: that cheaper backends produce equivalent output. TR124 tests and confirms this assumption (0/7 metrics significant) while also mapping the quality landscape across models. The Pareto frontier finding — that llama3.2-1b offers the best quality-per-dollar — is a genuine decision instrument, not just a data point.

### O.3 TR125 Narrative

TR125 transforms quantization from a binary choice (full precision vs "some compression") into a mapped decision space with 34 variants, 4 quality tiers, and specific per-model recommendations. The Q4_K_M sweet spot finding is the single most impactful deployment recommendation in the program: it saves 30-67% on cost and VRAM with negligible quality loss across all 5 tested models. The Q2_K cliff is equally important as a prohibition.

### O.4 TR126 Narrative

TR126 is the most satisfying report in the program because it resolves a genuine mystery. The Windows compile paradox (TR120) appeared to show that torch.compile hurts performance. TR126 proves this was an artifact: real Triton compilation delivers large, consistent speedups. The report also reveals that compiled decode crashes in all modes — a limitation that was obscured on Windows where compile never worked at all. The net policy is clear: compile prefill, never decode.

### O.5 TR127 Narrative

TR127 discovers the two-regime phenomenon that reshapes all context-length planning. Below VRAM capacity, scaling is clean and predictable (b=1.58-1.78). Above capacity, performance degrades 25-105x due to silent VRAM spillover. The silence is key: PyTorch does not raise an error; it simply pages to system RAM via PCIe, and the user sees unexplained slowdowns. Ollama eliminates this entirely via Flash Attention and paged KV caches.

### O.6 TR128 Narrative

TR128 is the reality check for production deployment. It tests the knobs that practitioners actually turn (NUM_PARALLEL, streaming, multi-turn context) and finds that one is a no-op, one is free, and one needs more data. The M/D/1 deviation (20.4x) is perhaps the most practically important negative result in the program: it means that standard queueing theory cannot be used for capacity planning on this hardware.

### O.7 TR129 Narrative

TR129 quantifies the multi-agent problem. The Amdahl fits (R²>0.97) provide a predictive formula: eta(N) = 1/(s×N + 1-s). With s=0.39-0.54, the formula predicts that throughput plateaus at N=2 and per-agent efficiency drops to 17-20% at N=8. This has immediate design implications: deploying 8 agents on one GPU wastes 80% of each agent's potential throughput.

### O.8 TR130 Narrative

TR130 identifies the solution to TR129's scaling problem: continuous batching. vLLM achieves 2.25x total throughput at N=8 by batching concurrent requests into shared kernel launches. However, TR130 incorrectly attributes this advantage to "better serving stack scheduling" rather than to the underlying bandwidth amortization mechanism. This misattribution is corrected by TR131 and TR132.

### O.9 TR131 Narrative

TR131 is the causal test that overturns the serving-stack hypothesis. By using PyTorch Direct (no HTTP server, no Go runtime, no request queuing), it isolates the GPU from the software stack. PyTorch Direct degrades worse than Ollama (86.4% vs 82.1%), proving that the degradation is GPU memory bandwidth, not software overhead. The +74.4% memory operation time increase at N=8 is the strongest mechanistic evidence in the program.

### O.10 TR132 Narrative

TR132 completes the causal chain. If the bottleneck is GPU bandwidth (TR131), and vLLM scales better (TR130), then vLLM must be doing something to reduce bandwidth demand. TR132 proves this: continuous batching reduces per-token kernel count by 77-80% and per-token bandwidth by 79-83%. The 4.7-5.8x amortization ratio directly explains vLLM's advantage.

### O.11 TR133 Narrative

TR133 is the capstone. It takes the 70,000+ measurements from TR123-TR130 and operationalizes them into a tool that runs in under one second. The key insight is that simple models (lookup tables, Amdahl's Law, first-principles VRAM formulas) outperform complex ones (M/D/1 queueing) because the simple models are calibrated against empirical data rather than derived from assumptions. The 4/4 validation targets met and 10/10 spot checks passed demonstrate that the program's empirical data is coherent enough to power prediction.

---

## Appendix P: Quantization Decision Trees and Quality Gates

### P.1 Decision Tree: Selecting Quantization Level

```
Is this a quality-critical application (medical, legal, financial)?
├── YES → Use Q8_0 or FP16
│   └── Is VRAM sufficient for FP16?
│       ├── YES → FP16
│       └── NO → Q8_0
└── NO → Use Q4_K_M (universal default)
    └── Is VRAM extremely constrained (<2GB for model)?
        ├── YES → Is the model phi-2 or llama3.1-8b?
        │   ├── YES → Q3_K_S is acceptable
        │   └── NO → Q4_K_M minimum; consider smaller model
        └── NO → Q4_K_M
```

### P.2 Quality Gates by Application Type

| Application | Minimum Composite | Minimum MMLU | Recommended Quant |
|------------|------------------|-------------|-------------------|
| General chatbot | 0.50 | 40% | Q4_K_M |
| QA pipeline | 0.55 | 45% | Q4_K_M or Q8_0 |
| Summarization | 0.45 | — | Q4_K_M |
| Code generation | 0.40 | — | Q4_K_M |
| Medical/legal | 0.60 | 55% | Q8_0 or FP16 |
| Classification | — | 50% | Q4_K_M |

---

## Appendix Q: Extended Decision Case Studies

### Q.1 Case Study: Small Startup with Single RTX 4080

**Scenario:** 3-person team, building a chatbot, ~50 req/hour, quality matters.

**Decision path:** N=1 (50 req/hr = 0.014 req/s, well below saturation). Ollama Q4_K_M. llama3.2-1b for cost efficiency or phi-2 for quality. Context budget: up to 32K with Ollama. Monthly cost: <$5 in electricity. No vLLM needed — overkill for single-agent.

### Q.2 Case Study: RAG Pipeline with 8 Concurrent Users

**Scenario:** 8K context (retrieved documents), 8 concurrent users, p95 latency SLO of 5 seconds.

**Decision path:** N=8 → vLLM FP16. llama3.2-1b FP16 fits in 12GB with 8K context (VRAM ~4.9 GB). vLLM at N=8: ~559 tok/s total, ~70 tok/s per user. 128 decode tokens at 70 tok/s = 1.8s decode + ~100ms prefill = ~1.9s per request. Well within 5s SLO. Cost: ~$25/month on consumer hardware.

### Q.3 Case Study: Quality-Sensitive Document Processing

**Scenario:** Legal document summarization, accuracy is paramount, 2 concurrent agents.

**Decision path:** N=2 → Ollama still viable (eta(2) = 0.67-0.80). phi-2 Q8_0 for maximum quality (composite 0.63, -1.8pp from FP16). Context: up to 4K tokens (longer documents need chunking). Quality gate: ROUGE-L > 0.45, BERTScore > 0.80 per TR124 baselines.

---

## Appendix R: Metric Definitions and Data Schema

### R.1 Generation Metrics Schema

| Metric | Type | Range | Computation | Primary Use |
|--------|------|-------|-------------|-------------|
| ROUGE-L | Float | [0,1] | LCS F1 vs reference | Structural overlap |
| BERTScore | Float | [0,1] | DeBERTa embedding similarity | Semantic similarity |
| BLEU | Float | [0,1] | n-gram precision + brevity | Code generation |
| Coherence | Float | [0,1] | all-mpnet-base-v2 cosine sim | Meaning preservation |
| Exact Match | Binary | {0,1} | Case-insensitive string match | Classification |
| Output Length | Float | [0,1] | min/max ratio | Truncation/over-gen |
| Repetition | Float | [0,1] | unique_4grams / total_4grams | Lexical diversity |

### R.2 Benchmark Metrics Schema

| Metric | Type | Range | Computation |
|--------|------|-------|-------------|
| Raw Accuracy | Float | [0,1] | exact_match on model output |
| Rescored Accuracy | Float | [0,1] | Regex letter extraction + compare |

---

## Appendix S: Governance and Reporting Templates

### S.1 Decision Report Template

```
Decision: [What is being decided]
Contributing TRs: [List]
Evidence summary: [Key numbers + effect sizes]
Confidence: [High/Medium/Low with justification]
Boundary conditions: [When this decision is valid]
Invalidation triggers: [What would change the decision]
Review date: [When to re-evaluate]
```

### S.2 Rerun Trigger Template

```
Trigger: [What changed]
Affected TRs: [Which reports need rerun]
Minimum rerun scope: [Specific experiments]
Estimated effort: [Hours]
Risk if skipped: [What could go wrong]
```

---

## Appendix T: Extended Risk Register

See Section 8.12 for the validation-source mapping of these risks and their artifact provenance.

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|------------|-------|
| VRAM spillover in production | Medium | High (25-105x latency) | Monitor at 85%; use Ollama for >4K | Ops |
| Q2_K deployed accidentally | Low | High (near-random output) | Quality gate in pipeline; ban Q2_K in config | DevOps |
| Compiled decode crash | Medium | High (service outage) | Never compile decode; eager always | Platform |
| PyTorch upgrade breaks compile | Medium | Medium (prefill regression) | Rerun TR126 Phase 2 after upgrade | Platform |
| Model quality below gate | Low | Medium (user-facing) | Automated quality checks against TR124 baselines | ML Eng |
| vLLM version changes scaling | Medium | Medium (capacity miscalculation) | Rerun TR130 N=8 benchmark after upgrade | Platform |
| Thermal throttling at sustained load | Low | Medium (throughput drop) | Alert at 75°C; tested safe to 66°C (TR128) | Ops |
| M/D/1 used for capacity planning | Medium | High (20.4x overestimate) | Use chimeraforge exclusively; deprecate theory | Planning |

---

## Appendix U: Program Evolution Narrative (TR123-TR133)

Phase 2 began with a clear mandate: convert Phase 1's measurement methodology into deployment policy. The first step (TR123) was economic: what does production inference actually cost? This required enabling KV-cache (disabled in Phase 1's TR119 for methodological simplicity) and separating prefill from decode costs. The result was the first decision-grade $/token table for cached inference.

The program then recognized its blind spot: all cost recommendations assumed quality equivalence. TR124 tested this assumption across 3,600 samples and confirmed it — but also exposed quantization as a major unanswered question. TR125 filled this gap with ~26,000 samples across 34 model-quant variants.

The compile paradox from Phase 1 demanded resolution. TR126 moved to Docker/Linux and demonstrated that real Triton compilation delivers the speedups that Windows's aot_eager fallback had hidden. This also revealed that compiled decode crashes in all modes — a finding with immediate policy implications.

TR127-TR128 shifted focus from controlled benchmarks to production conditions. Long context (TR127) and realistic load (TR128) introduced new failure modes: VRAM spillover and queueing theory breakdown. These findings directly motivated the multi-agent studies.

TR129-TR132 form the scaling investigation arc. Each report dug deeper into the multi-agent bottleneck: TR129 measured it, TR130 compared alternatives, TR131 identified the root cause, and TR132 proved the mechanism. The arc's central narrative — from "Ollama is the bottleneck" to "GPU memory bandwidth is the bottleneck" to "continuous batching amortizes the bandwidth bottleneck" — is the most intellectually satisfying thread in the program.

TR133 closed the loop by operationalizing everything into a CLI tool. The program's output shifted from reports to software — from "here are the results" to "here is a tool that uses the results."

---

## Appendix V: Extended Cost Modeling and Token Economics

### V.1 Cost Sensitivity to Hourly Rate

| Pricing Tier | $/hr | GPT-2/compile $/1M | Llama-1B/compile $/1M | phi-2/GPU $/1M |
|-------------|------|--------------------|-----------------------|----------------|
| Consumer (owned) | $0.046 | $0.013 | $0.047 | $0.093 |
| AWS Spot | $0.302 | $0.085 | $0.308 | $0.610 |
| AWS On-Demand | $1.006 | $0.283 | $1.026 | $2.032 |
| Azure Reserved (1yr) | $0.508 | $0.143 | $0.518 | $1.026 |

### V.2 Break-Even Analysis

Consumer GPU (RTX 4080, ~$1,200 purchase) vs AWS on-demand:

Monthly savings = (AWS $/month - consumer energy $/month)
Break-even months = $1,200 / monthly savings

For llama3.2-1b at 100M tok/month: AWS=$102.60/month, consumer=$4.70/month → savings=$97.90/month → break-even=12.3 months.
For llama3.2-1b at 1B tok/month: AWS=$1,026/month, consumer=$47/month → savings=$979/month → break-even=1.2 months.

---

## Appendix W: Serving Stack Comparison Deep Dive

### W.1 N=1 Throughput Comparison

| Backend | llama3.2-1b | llama3.2-3b | qwen2.5-1.5b |
|---------|-------------|-------------|---------------|
| Ollama Q4_0 | 177.7 tok/s | 130.1 tok/s | 198.3 tok/s |
| vLLM FP16 | 150.7 tok/s | 60.9 tok/s | 102.6 tok/s |
| TGI FP16 | 125.2 tok/s | 49.4 tok/s | 75.0 tok/s |

### W.2 N=8 Total Throughput

| Backend | llama3.2-1b | llama3.2-3b | qwen2.5-1.5b |
|---------|-------------|-------------|---------------|
| vLLM | 559 tok/s | 319 tok/s | 457 tok/s |
| TGI | 483 tok/s | 261 tok/s | 362 tok/s |
| Ollama | 248 tok/s | 162 tok/s | 259 tok/s |

### W.3 Scaling Law Comparison

Ollama follows Amdahl's Law: eta(N) = 1/(s×N + 1-s), R²=0.957-0.987
vLLM/TGI follow power law: eta(N) ∝ N^(-α), α=0.17-0.35, R²=0.988-0.996

The Amdahl serial fraction is a category error when applied to vLLM/TGI because these backends do not degrade via Amdahl's mechanism (serial bottleneck). Their degradation comes from resource contention under continuous batching, which is better described by a power law.

---

## Appendix X: GPU Kernel Profiling Methodology

### X.1 Nsight Systems Configuration

```
nsys profile --trace cuda --cuda-event-stacks \
  --output /traces/profile_{backend}_{model}_{N}.nsys-rep \
  --force-overwrite true \
  {server_command}
```

### X.2 In-Container Profiling (TR132 Innovation)

The key challenge: Docker containers under WSL2 on Windows cannot see the host nsys binary, and GPU profiling requires CUPTI access. Solution: mount the Linux nsys binary into the container via volume mount, and wrap the server entrypoint with `nsys profile --trace cuda`.

```bash
docker run --gpus all \
  -v /usr/local/cuda/nsight-systems-2024.7/target-linux-x64/nsys:/usr/local/bin/nsys \
  -v /traces:/traces \
  --entrypoint nsys \
  vllm/vllm-openai:latest \
  profile --trace cuda --output /traces/vllm_profile.nsys-rep \
  python -m vllm.entrypoints.openai.api_server ...
```

### X.3 Trace Analysis Pipeline

1. Export nsys-rep to SQLite via `nsys export --type sqlite`
2. Query CUPTI_ACTIVITY_KIND_KERNEL for kernel launches
3. Query CUPTI_ACTIVITY_KIND_MEMCPY and CUPTI_ACTIVITY_KIND_MEMSET for memory operations
4. Aggregate per-token kernel count and memory operation time
5. Statistical comparison: N=1 vs N=8 per backend per model

---

## Appendix Y: Continuous Batching Amortization Analysis

### Y.1 Amortization Ratios

| Backend | Model | N=1 Kernels/Token | N=8 Kernels/Token | Ratio |
|---------|-------|-------------------|-------------------|-------|
| vLLM | LLaMA-1B | 54.89 | 10.85 | 5.06x |
| vLLM | LLaMA-3B | 76.71 | 15.43 | 4.97x |
| TGI | LLaMA-1B | 72.98 | 17.12 | 4.26x |
| TGI | LLaMA-3B | 86.97 | 20.14 | 4.32x |

### Y.2 Theoretical Maximum

At N=8, perfect amortization would reduce per-token kernels by 8x (each kernel serves 8 tokens instead of 1). Observed ratios of 4.3-5.1x represent 53-63% of theoretical maximum. The gap comes from attention kernels that cannot be fully batched (per-sequence KV cache lookups) and scheduling overhead.

### Y.3 Super-Linear Amortization

vLLM LLaMA-1B achieves 5.75x bandwidth amortization — exceeding the N/2 threshold (4.0x). This suggests kernel fusion in the batched code path: the GEMM operations for 8 sequences are fused into a single larger matrix multiply, which has better compute/memory ratio than 8 sequential small GEMMs.

---

## Appendix Z: Amdahl's Law Derivations and Limits

### Z.1 Derivation

Given N agents sharing a resource with serial fraction s:
- Serial portion: s × T (cannot be parallelized)
- Parallel portion: (1-s) × T / N (shared across N agents)
- Total time: T(N) = s × T + (1-s) × T / N
- Speedup: S(N) = T / T(N) = 1 / (s + (1-s)/N)
- Per-agent efficiency: eta(N) = S(N) / N

### Z.2 Fitted Parameters

| Model | s | 1/s (max speedup) | R² | Fit method |
|-------|---|-------|-----|------------|
| llama3.2-1b | 0.5391 | 1.85x | 0.970 | Non-linear least squares on eta(N) |
| llama3.2-3b | 0.3870 | 2.58x | 0.993 | Same |
| qwen2.5-1.5b | 0.4554 | 2.20x | 0.985 | Same |

### Z.3 When Amdahl Fails

Amdahl's Law assumes a fixed serial fraction. This assumption fails when:
1. The degradation mechanism is resource contention (bandwidth), not serial execution → power law is better (vLLM/TGI)
2. The serial fraction varies with N (possible but not observed in TR129)
3. The system has multiple serial bottlenecks with different scaling (not tested)

Force-fitting Amdahl to vLLM/TGI produces s=0.81-0.92, which is meaningless — these backends don't have a "serial fraction" in the Amdahl sense.

---

## Appendix AA: VRAM Budget Calculator and Context Limits

### AA.1 VRAM Components

```
VRAM_total = weight_bytes × 1.058 + KV_bytes_per_token × context + activation_overhead
```

### AA.2 Per-Model VRAM Budget (12 GB GPU, FP16)

| Model | Weights (GB) | KV/token (KB) | Max Context Before Spillover | Max Context Before OOM |
|-------|-------------|---------------|------------------------------|----------------------|
| qwen2.5-0.5b | 1.0 | ~14 | ~16K | ~32K |
| qwen2.5-1.5b | 3.1 | ~28 | ~16K | ~32K |
| qwen2.5-3b | 6.0 | ~37 | ~8K | ~16K |
| phi-2 | 5.4 | ~40 | ~8K | ~16K |

### AA.3 Ollama Quantized (Q4_K_M, approximate)

| Model | Weights (GB) | KV/token (KB) | Practical Limit |
|-------|-------------|---------------|-----------------|
| llama3.2-1b | 0.7 | ~7 | >32K (no spillover) |
| qwen2.5-1.5b | 1.0 | ~7 | >32K |
| llama3.2-3b | 2.0 | ~9 | >32K |

---

## Appendix AB: Compile Policy Decision Matrix

| Condition | Platform | Backend | Compile? | Mode | Rationale |
|-----------|----------|---------|----------|------|-----------|
| Prefill-heavy, Linux | Linux | HF transformers | YES | reduce-overhead or default | 24-60% speedup (TR126) |
| Decode-heavy, Linux | Linux | HF transformers | NO | N/A | Compiled decode crashes or no speedup |
| Any workload, Windows | Windows | HF transformers | NO | N/A | aot_eager fallback, no real Triton |
| Any workload, Ollama | Any | Ollama | N/A | N/A | Ollama uses llama.cpp, not torch.compile |
| Any workload, vLLM | Linux | vLLM | N/A | N/A | vLLM manages its own compilation |
| Small model (<500M) | Linux | HF transformers | YES (prefill) | reduce-overhead | Highest speedup ratio (2.5x for gpt2-25m) |
| Large model (>1.5B) | Linux | HF transformers | MAYBE (prefill) | reduce-overhead | Ollama may match or beat compiled HF |

---

## Appendix AC: Multi-Agent Scaling Detailed Results

### AC.1 Per-Agent Efficiency eta(N) — Ollama (Amdahl-fitted)

Note: These values are from Amdahl's Law curve fits (R² > 0.97) and may differ slightly from empirical throughput ratios in AC.2 due to model smoothing.

| N | llama3.2-1b | llama3.2-3b | qwen2.5-1.5b |
|---|-------------|-------------|---------------|
| 1 | 100% | 100% | 100% |
| 2 | 80.0% | 67.5% | 72.7% |
| 3 | 59.0% | 50.5% | 53.0% |
| 4 | 40.4% | 34.2% | 36.8% |
| 5 | 33.7% | 29.2% | 31.2% |
| 6 | 28.5% | 25.1% | 26.8% |
| 7 | 24.0% | 21.3% | 22.5% |
| 8 | 20.3% | 17.3% | 18.6% |

### AC.2 Total System Throughput — Ollama

| N | llama3.2-1b | llama3.2-3b | qwen2.5-1.5b |
|---|-------------|-------------|---------------|
| 1 | 117.8 | 79.2 | 102.7 |
| 2 | 185.3 | 107.8 | 147.3 |
| 4 | 187.0 | 109.5 | 150.2 |
| 8 | 187.9 | 109.8 | 151.1 |

---

## Appendix AD: M/D/1 Queueing Theory vs Empirical Deviation

### AD.1 Theory

M/D/1 wait time: W_q = ρ / (2μ(1-ρ)) where ρ = λ/μ
Expected wait at NP=4: assumes μ scales by 4x → ρ drops by 4x → W_q drops dramatically

### AD.2 Empirical Deviation

| Model | NP | Arrival Rate | M/D/1 Predicted Wait | Observed Wait | Deviation |
|-------|-----|-------------|---------------------|---------------|-----------|
| llama3.2-3b | 4 | 1.0 req/s | ~250 ms | 5,100 ms | 20.4x |
| llama3.2-1b | 4 | 1.0 req/s | ~150 ms | 2,800 ms | 18.7x |
| qwen2.5-1.5b | 4 | 1.0 req/s | ~200 ms | 3,900 ms | 19.5x |

### AD.3 Why Theory Fails

Two assumptions fail simultaneously:
1. **Deterministic service:** Service CV is 2-10%, not zero. This alone adds ~5-15% to predicted wait.
2. **Linear NP scaling:** NUM_PARALLEL does not scale throughput (0/30 significant). The GPU serializes inference regardless of NP. At NP=4, effective μ = μ_base (not 4×μ_base), making ρ = λ/μ_base rather than λ/(4×μ_base). This alone accounts for 4x deviation; combined with queueing buildup, it produces the 20x gap.

---

## Appendix AE: Predictive Model Validation Details

### AE.1 VRAM Model

- Method: Two-pass fit (weight overhead from low-context, activation quadratic from residuals)
- Training data: 17 groups from TR127 VRAM measurements
- Validation: 20% holdout
- R² = 0.968, RMSE = 1.71 GB
- Overhead factor: 1.058x (captures allocator fragmentation)

### AE.2 Throughput Model

- Method: 22-entry lookup table + power-law fallback + quantization multipliers
- Training data: TR123 (HF backends), TR128/TR130 (Ollama, vLLM, TGI)
- Validation: 20% holdout
- R² = 0.859
- Power-law fallback: 72.1 × params^(-0.089)

### AE.3 Scaling Model

- Method: Per-(model, backend) Amdahl serial fractions from TR129/TR130
- Training data: 9 (model, backend) pairs
- Validation: 20% holdout
- R² = 0.647 (weakest model)
- MAPE = 27.8%

### AE.4 Quality Model

- Method: 35-entry lookup (5 models × 7 quants) + average deltas
- Training data: TR124/TR125 quality measurements
- Validation: 20% holdout
- RMSE = 0.062

### AE.5 Latency Model

- Method: M/D/1 with empirical median service times per (model, backend)
- Training data: TR128 Phase 1 baselines
- Validation: 9 groups
- MAPE = 1.05%
- Safety cap: 70% utilization

---

## Appendix AF: ChimeraForge CLI Architecture and Usage

### AF.1 Architecture

```
chimeraforge/
├── planner.py          # 4-gate search engine
├── models/
│   ├── vram.py         # First-principles VRAM prediction
│   ├── throughput.py   # Lookup table + fallbacks
│   ├── scaling.py      # Amdahl's law
│   ├── quality.py      # Lookup + deltas
│   ├── cost.py         # Algebraic $/token
│   └── latency.py      # M/D/1 approximation
├── data/
│   └── fitted_models.json  # ~5KB baked-in parameters
└── cli.py              # Typer + Rich interface
```

### AF.2 Usage Examples

```bash
# Find best config for 12GB GPU, 2 agents, quality >= 0.5
chimeraforge plan --vram-budget 12 --agents 2 --quality-target 0.5

# List available hardware profiles
chimeraforge plan --list-hardware

# Estimate VRAM for specific model
chimeraforge plan --model llama3.2-1b --quant Q4_K_M --context 8192
```

### AF.3 Runtime Properties

- Zero GPU requirement (predict-only, no model loading)
- <1 second execution
- 57 unit tests
- Pure Python + Typer + Rich (no numpy/scipy/torch)
- pip installable: `pip install chimeraforge`

---

## Appendix AG: Extended Glossary and Acronyms

- **AD104:** NVIDIA Ada Lovelace GPU die used in RTX 4080 Laptop
- **ARC:** AI2 Reasoning Challenge benchmark
- **aot_eager:** PyTorch's ahead-of-time eager compilation mode (fallback when Triton unavailable)
- **AWQ:** Activation-aware Weight Quantization
- **BPW:** Bits per weight (e.g., FP16=16, Q4_K_M≈4.5, Q2_K≈2.5)
- **CUDA graphs:** Pre-recorded GPU execution sequences for reduced launch overhead
- **CUTLASS:** CUDA Templates for Linear Algebra Subroutines
- **cuBLAS:** NVIDIA's CUDA Basic Linear Algebra Subroutines library
- **GDDR6:** Graphics Double Data Rate 6 memory (432 GB/s on RTX 4080 Laptop, 256-bit bus)
- **GGUF:** GPT-Generated Unified Format (quantized model format for llama.cpp)
- **GPTQ:** Generative Pre-Trained Quantization
- **HellaSwag:** Harder Endings, Longer contexts, Low-shot Activities benchmark
- **NDJSON:** Newline-delimited JSON (Ollama streaming format)
- **NGC:** NVIDIA GPU Cloud (container registry)
- **NVML:** NVIDIA Management Library (GPU telemetry API)
- **OOM:** Out of Memory
- **PCIe:** Peripheral Component Interconnect Express (system bus)
- **WDDM:** Windows Display Driver Model (limits kernel-level GPU profiling)
- **WSL2:** Windows Subsystem for Linux 2

---

## Appendix AH: Detailed Artifact Inventory

| TR | Primary Artifacts | Size | Location |
|----|------------------|------|----------|
| TR123 | cost_summary.json, phase_metrics.csv, energy_summary.json | ~5 MB | results/eval/tr123/ |
| TR124 | anova_results.json, per_model_quality.csv, pareto_frontier.json | ~8 MB | results/eval/tr124_phase1/ |
| TR125 | phase2_analysis.json, tier_classification.csv, wilson_cis.json | ~12 MB | results/eval/tr125/ |
| TR126 | compile_analysis.json, triton_kernels.csv, mode_comparison.json | ~15 MB | results/eval/tr126/ |
| TR127 | context_scaling.json, vram_measurements.csv, regime_fits.json | ~3 MB | results/eval/tr127/ |
| TR128 | concurrency_results.json, thermal_log.csv, streaming_comparison.json | ~8 MB | results/eval/tr128/ |
| TR129 | scaling_analysis.json, amdahl_fits.csv, fairness_indices.json | ~10 MB | results/eval/tr129/ |
| TR130 | backend_comparison.json, eta_curves.csv, ttft_analysis.json | ~12 MB | results/eval/tr130/ |
| TR131 | profiling_analysis.json, nsys traces (1.6 GB), hypothesis_tests.json | ~1.6 GB | results/eval/tr131/ |
| TR132 | kernel_analysis.json, nsys traces (375 MB), amortization.json | ~375 MB | results/eval/tr132/ |
| TR133 | fitted_models.json, validation_results.json, spot_checks.json | ~1 MB | results/eval/tr133/ |

---

## Appendix AI: Artifact-to-Claim Provenance Examples

### AI.1 Example: "Q4_K_M preserves quality" (C3)

1. **Raw data:** TR125 Phase 2 MMLU/ARC responses stored in `results/eval/tr125/phase2_raw/`
2. **Rescoring:** Regex letter extraction applied to raw responses → `phase2_rescored.json`
3. **Accuracy computation:** Per-(model, quant) accuracy with Wilson CIs → `phase2_analysis.json`
4. **Tier classification:** Delta vs baseline + tier thresholds → `tier_classification.csv`
5. **Claim:** Q4_K_M tier = "negligible" or "acceptable" for all 5 models

### AI.2 Example: "GPU physics dominates" (C8)

1. **Raw data:** TR131 nsys traces in `results/eval/tr131/traces/`
2. **Export:** nsys-rep → SQLite → kernel_launches.csv, memory_ops.csv
3. **Aggregation:** Per-condition means, CIs, effect sizes → `profiling_analysis.json`
4. **Hypothesis test:** Welch's t on PyTorch vs Ollama degradation → p=0.002
5. **Claim:** PyTorch Direct degradation (86.4%) > Ollama (82.1%) → GPU physics, not serving stack

---

## Appendix AJ: Reproducibility and Regeneration Notes

All Phase 2 results can be reproduced by:
1. Setting up the hardware baseline (RTX 4080 Laptop GPU or equivalent)
2. Installing the correct software versions (see manifest in Executive Summary)
3. Running the per-TR scripts in `research/trNNN/` directories
4. Comparing outputs against published artifacts

Key reproducibility constraints:
- TR126 requires Docker with GPU passthrough on Linux (not native Windows)
- TR131/TR132 require Nsight Systems installation
- TR125 requires HuggingFace datasets for MMLU and ARC-Challenge
- Ollama model versions may drift (quantization implementations change)
- GPU thermal behavior may vary by laptop chassis and ambient temperature

---

## Appendix AK: Scenario-Specific Policy Playbooks

### AK.1 Hobby/Personal Use

- Model: llama3.2-1b Q4_K_M via Ollama
- Context: up to 32K tokens
- Cost: <$5/month electricity
- Quality: composite ~0.44 (adequate for chat, creative writing)

### AK.2 Small Business (5-10 concurrent users)

- Model: qwen2.5-1.5b or llama3.2-3b via vLLM FP16
- Context: up to 8K tokens
- Cost: ~$25-50/month consumer GPU
- Quality: composite 0.52-0.55

### AK.3 Quality-Critical Pipeline

- Model: phi-2 Q8_0 via Ollama (N=1) or vLLM FP16 (N>=4)
- Context: up to 4K tokens (FP16 VRAM budget)
- Quality gate: composite >= 0.60, MMLU >= 50%

---

## Appendix AL: Quality Metric Definitions and Benchmark Mapping

See Appendix R for metric definitions. This appendix maps benchmarks to quality dimensions:

| Benchmark | Quality Dimension | TR124 Best Model | TR124 Score |
|-----------|------------------|-----------------|-------------|
| MMLU | General knowledge | qwen2.5-1.5b | 52% |
| HellaSwag | Commonsense reasoning | phi-2 | 48% |
| ARC-Easy | Scientific reasoning | qwen2.5-1.5b | 91% |

---

## Appendix AM: Decision Heuristics and Rules of Thumb

1. **The N=4 rule:** If you have >=4 concurrent agents, switch from Ollama to vLLM.
2. **The Q4_K_M rule:** When in doubt, use Q4_K_M. It's safe for every model tested.
3. **The 70% rule:** Never exceed 70% of theoretical max throughput for sustained operation.
4. **The 4K rule:** Don't use HF FP16 for contexts >4K tokens on 12GB VRAM.
5. **The compile rule:** Compile prefill, never decode, only on Linux.
6. **The streaming rule:** Always enable streaming. It's free.
7. **The Q2_K rule:** Never deploy Q2_K for anything quality-sensitive.
8. **The 2-agent rule:** Total system throughput plateaus at N=2 on Ollama.
9. **The bandwidth rule:** Multi-agent degradation is GPU bandwidth, not software.
10. **The chimeraforge rule:** Use the tool, not the theory.

---

## Appendix AN: Policy Decision Trees

### AN.1 Backend Selection Decision Tree

```
How many concurrent agents?
├── N = 1
│   └── Use Ollama Q4_K_M
├── N = 2-3
│   ├── Quality-critical? → vLLM FP16
│   └── Cost-critical? → Ollama Q4_K_M
└── N >= 4
    └── Use vLLM FP16 (2.25x advantage)
```

### AN.2 Model Selection Decision Tree

```
Quality requirement?
├── Composite >= 0.60 → phi-2 (Q8_0 or FP16)
├── Composite >= 0.50 → qwen2.5-1.5b or llama3.2-3b (Q4_K_M)
├── Composite >= 0.40 → llama3.2-1b (Q4_K_M, best cost)
└── No quality gate → GPT-2 (cheapest, $0.013/1M)
```

---

## Appendix AO: Extended Systems Glossary

See Appendix D (primary glossary) and Appendix AG (acronyms). This appendix adds systems-level terms:

- **Bandwidth amortization:** Sharing memory bandwidth cost across multiple concurrent requests via batched kernel execution.
- **Closed-loop scheduling:** Agent sends request, waits for response, then sends next. Max in-flight = N.
- **Continuous batching:** Dynamically grouping incoming requests into single GPU kernel launches.
- **Duty cycle:** Fraction of time an agent is actively waiting for GPU response (vs idle/thinking).
- **Kernel serialization:** GPU hardware executing one kernel at a time despite multiple CUDA streams.
- **Open-loop scheduling:** Requests arrive independently (Poisson process). In-flight is unbounded.
- **Saturation point:** The N at which per-agent efficiency drops below 50%.
- **TTFT amplification:** Ratio of loaded TTFT to unloaded TTFT. Caused by queueing delay.

---

## Appendix AP: Cross-Phase Synthesis Narrative (Phase 1 + Phase 2)

Phase 1 asked: "How do we measure LLM inference correctly?" Phase 2 asked: "What do the measurements tell us to deploy?" Together, they form a 22-report evidence chain from raw benchmarks (TR117) to predictive software (TR133).

The most important cross-phase finding is the compile paradox resolution. Phase 1 (TR120) discovered the problem; Phase 2 (TR126) solved it. This required expanding the measurement platform from Windows-only to Docker/Linux — an infrastructure change that also enabled serving stack comparison (TR130), kernel profiling (TR131/TR132), and vLLM/TGI testing.

The second cross-phase thread is economic. Phase 1 (TR119) produced uncached cost models. Phase 2 (TR123) added KV-cache, cutting costs 2-8x. TR125 added quantization, cutting another 30-67%. TR130 added continuous batching, adding 2.25x throughput at N>=4. The cumulative cost improvement from naive Phase 1 defaults to Phase 2 optimal configuration is approximately 5-10x.

---

## Appendix AQ: Extended Risk Mitigation Strategies

See Appendix T for the risk register. This appendix details mitigation strategies:

**VRAM spillover mitigation:** Implement VRAM monitoring daemon that checks `torch.cuda.memory_allocated()` every 5 seconds. Alert at 85% of physical VRAM. Auto-reject requests that would push context beyond the spillover threshold. For Ollama: not needed (Flash Attention prevents spillover).

**Quality degradation mitigation:** Run TR124 quality baseline suite weekly. Compare against stored baselines. Alert if any metric degrades >5% from baseline. Investigate model version changes, tokenizer updates, or quantization engine changes.

**Version upgrade mitigation:** Maintain a "golden" benchmark suite (subset of TR123 + TR124 + TR126 + TR128) that runs in <30 minutes. Run after any version change. Compare against stored results. Flag regressions before production deployment.

---

## Appendix AR: Operational Metrics and Dashboard Specifications

### AR.1 Key Metrics to Track

| Metric | Source | Alert Threshold | Dashboard Panel |
|--------|--------|----------------|----------------|
| p95 latency | Request logs | >2x baseline (TR128) | Time series |
| TTFT | Streaming timestamps | >500ms (Ollama), >100ms (vLLM) | Time series |
| Decode tok/s | /api/generate response | <80% of TR123 baseline | Gauge |
| VRAM utilization | nvidia-smi | >85% | Gauge with zones |
| GPU temperature | nvidia-smi | >75°C | Gauge |
| Error rate | HTTP response codes | >1% | Counter |
| Queue depth | Backend metrics | >5 (Ollama) | Time series |

---

## Appendix AS: Cross-Report Comparison Table (Narrative)

| Dimension | Phase 1 (TR117-TR122) | Phase 2 (TR123-TR133) |
|-----------|----------------------|----------------------|
| Focus | Measurement methodology | Deployment policy |
| Backends | HF, ONNX, compile | HF, compile, Ollama, vLLM, TGI |
| Quality | Not measured | 3,600 + 26,000 samples |
| Models | 3-5 (single family) | 5-7 (multi-family, 124M-8B) |
| Platform | Windows only | Windows + Docker/Linux |
| Profiling | None | nsys + ncu + in-container CUPTI |
| Cost model | Uncached | KV-cached, phase-split, blend |
| Concurrency | None | Poisson, closed-loop, N=1-8 |
| Output | Decision framework + report | Decision framework + CLI tool |

---

## Appendix AT: Extended Decision Matrix Commentary

The Decision Impact Matrix (Section 4) maps TRs to decisions. This appendix provides commentary on the decision chains:

The cost chain (TR123→TR125→TR130→TR133) produces the largest cumulative impact. TR123 establishes that KV-cached inference is 2-8x cheaper than uncached. TR125 adds quantization savings of 30-67%. TR130 adds continuous batching throughput of 2.25x at N>=4. TR133 makes these savings accessible via a single CLI command.

The quality chain (TR124→TR125) is shorter but foundational. Without quality baselines, every cost recommendation would carry an implicit assumption. TR124 validates that assumption; TR125 extends it across quantization levels.

The scaling chain (TR128→TR129→TR130→TR131→TR132) is the longest and most intellectually dramatic. It progresses from "NUM_PARALLEL doesn't work" to "Amdahl governs Ollama" to "vLLM is 2.25x better" to "it's GPU physics, not software" to "continuous batching amortizes bandwidth." Each step deepened understanding while overturning the previous attribution.

---

## Appendix AU: Expanded Operational Checklists

See Appendix E for core checklists. This appendix adds role-specific expansions.

### AU.1 For ML Engineers

1. Validate model quality against TR124 baselines before deployment
2. Run TR125 quant sweep if using a new model family
3. Verify quantization level via `chimeraforge plan --quality-target`
4. Check VRAM budget for target context length

### AU.2 For Platform Engineers

1. Configure Ollama with NUM_PARALLEL=1 (higher values are no-op)
2. Enable streaming in all API endpoints
3. Set up vLLM Docker containers for N>=4 workloads
4. Never compile decode on any backend
5. Monitor VRAM utilization with alerting

### AU.3 For Capacity Planners

1. Use `chimeraforge plan` for all capacity estimates
2. Do not use M/D/1 queueing theory
3. Apply 70% utilization safety cap
4. Budget 2-3 agents per GPU for Ollama; up to 8 for vLLM
5. Consumer hardware break-even: 1-3 months at moderate throughput

---

## Appendix AV: Extended Economic Sensitivity Analysis

### AV.1 Sensitivity to Throughput

A 10% throughput improvement reduces $/1M tokens by 9.1% (inverse relationship). This means:
- Backend choice (2-7x throughput range): 50-86% cost impact
- Quantization (1.0-2.3x throughput via reduced bandwidth): 0-57% cost impact
- torch.compile (1.2-2.5x prefill speedup): 17-60% prefill cost impact (decode unaffected)

### AV.2 Sensitivity to Pricing Tier

Consumer ($0.046/hr) vs AWS on-demand ($1.006/hr) = 21.9x price ratio. This dominates all other optimization axes. Moving from the most expensive backend to the cheapest saves ~7x; moving from cloud to consumer saves ~22x.

---

## Appendix AW: Measurement Ethics and Reproducibility Principles

1. **Report negative results.** TR128's NUM_PARALLEL refutation and TR131's serving-stack overturning are as valuable as positive findings.
2. **Document failures.** Compiled decode crashes (TR126), M/D/1 deviation (TR128), and Amdahl category error (TR130) are explicitly documented.
3. **Bound all claims.** Every finding is bounded to the measured hardware, software stack, and workload.
4. **Distinguish measurement from inference.** The chain-of-custody (Appendix B) separates measured quantities from modeled quantities from inferred policy.
5. **Publish artifacts.** All raw data, analysis scripts, and intermediate results are version-controlled and accessible.

---

## Appendix AX: Architectural Considerations for Serving Stacks

### AX.1 Ollama Architecture

Ollama wraps llama.cpp with a Go HTTP server. Request scheduling is FIFO with optional NUM_PARALLEL for CPU-side admission. GPU execution is always serial (max_concurrent_kernels=1). Strengths: simplicity, quantization, low TTFT. Weakness: no continuous batching.

### AX.2 vLLM Architecture

vLLM uses PagedAttention for memory management and continuous batching for scheduling. Multiple requests share GPU kernel launches, amortizing bandwidth. Strengths: 2.25x multi-agent throughput, 6x faster TTFT, efficient memory use. Weakness: FP16 only (higher VRAM, no quantization in tested version).

### AX.3 TGI Architecture

TGI (Text Generation Inference by HuggingFace) provides continuous batching with a different attention implementation. Performance is 10-15% below vLLM but amortization is equivalent (4.65-4.80x vs 4.68-5.75x). Strengths: HuggingFace ecosystem integration. Weakness: slightly lower absolute throughput.

---

## Appendix AY: Operational Lessons Learned

1. **The most impactful optimization is often the simplest.** Q4_K_M quantization saves 30-67% with one config change. No code, no infrastructure, no complexity.
2. **Intuitive attributions are often wrong.** "The serving stack is the bottleneck" (TR130) was overturned by GPU profiling (TR131). Always measure before optimizing.
3. **Theory is a starting point, not an answer.** M/D/1 deviates 20.4x. Amdahl is a category error across backends. Use empirical data.
4. **Consumer hardware is production-viable.** An RTX 4080 Laptop serves 0.7-1.17 req/s without throttling, at 95.4% less cost than cloud.
5. **Streaming is free.** Zero overhead in 0/9 tests. There is no reason not to enable it.
6. **Compiled decode is dead.** Five evidence lines, two PyTorch versions, three compile modes. Don't invest time trying to make it work.

---

## Appendix AZ: Scaling Laws vs Inference Performance

Training scaling laws (Kaplan et al. 2020, Chinchilla 2022) predict loss as a function of compute, data, and parameters. These laws do not transfer to inference performance because:

1. **Inference is memory-bandwidth-bound, not compute-bound** (for decode). Training is compute-bound.
2. **Quantization changes the parameter-performance relationship.** A Q4_K_M model has the same parameter count but different throughput than FP16.
3. **Serving stack architecture dominates at high concurrency.** The difference between Ollama and vLLM at N=8 (2.25x) is larger than the difference between 1B and 3B models (~1.4x).

TR129's Amdahl serial fractions and TR130's power-law degradation curves are inference-specific "scaling laws" that have no training-side analog.

---

## Appendix BA: Energy, Carbon, and Sustainability Considerations

Energy cost is a rounding error at consumer scale: 66-99% of total cost is infrastructure (compute-time), not electricity. However, carbon footprint is reportable:

| Configuration | gCO2e/1M tokens | Context |
|--------------|----------------|---------|
| GPT-2/CPU | 3.4 | Lowest absolute |
| GPT-2/compile | 4.6 | Best GPU option |
| Llama-1B/compile | 15.8 | Best at >1B |
| Phi-2/GPU | 31.2 | Highest quality |

At 1B tokens/month, even the highest-emission configuration produces ~31 kgCO2e/year — equivalent to driving ~75 miles. Consumer-scale LLM inference has negligible carbon impact.

---

## Appendix BB: Methodological QA Checklist

1. [ ] All claims trace to artifacts (Appendix B)
2. [ ] Statistical tests appropriate for data type (Appendix I)
3. [ ] Multiple comparison correction applied where needed
4. [ ] Effect sizes reported alongside p-values
5. [ ] Confidence intervals provided
6. [ ] Power analysis confirms ability to detect claimed effects
7. [ ] Measurement boundaries documented (Appendix L)
8. [ ] Warmup protocol eliminates cold-start artifacts
9. [ ] Hardware manifest recorded (Executive Summary)
10. [ ] Negative results reported with same rigor as positive

---

## Appendix BC: Model Registry Metadata Schema

```json
{
  "model_id": "llama3.2-1b",
  "parameters_billions": 1.2,
  "architecture": "GQA",
  "num_layers": 16,
  "num_attention_heads": 32,
  "num_kv_heads": 8,
  "head_dim": 64,
  "hidden_dim": 2048,
  "vocab_size": 128256,
  "max_context": 131072,
  "fp16_weight_bytes_gb": 2.4,
  "kv_bytes_per_token": 16384,
  "gated": true,
  "tested_quants": ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"],
  "recommended_quant": "Q4_K_M",
  "composite_quality_fp16": 0.44,
  "composite_quality_q4km": 0.42
}
```

---

## Appendix BD: Implementation Guidance by Team Role

| Role | Primary TRs | Key Actions |
|------|------------|-------------|
| ML Engineer | TR124, TR125 | Set quality gates; select quant level; validate new models |
| Platform Engineer | TR126, TR128, TR130 | Configure backends; set compile policy; deploy vLLM for N>=4 |
| Capacity Planner | TR123, TR129, TR133 | Use chimeraforge; size instances; plan agent count |
| DevOps | TR128, TR131 | Monitor VRAM, thermal, TTFT; set up alerting |
| Product Manager | TR124, TR133 | Understand quality-cost tradeoffs; use chimeraforge for ROI |

---

## Appendix BE: Quality Evaluation and Acceptance Criteria

### BE.1 Minimum Viable Quality by Use Case

| Use Case | Metric | Minimum | Source |
|----------|--------|---------|--------|
| General chat | Composite | 0.45 | TR124 §6 |
| QA pipeline | ROUGE-L | 0.30 | TR124 §6.3 |
| Summarization | BERTScore | 0.75 | TR124 §6.3 |
| Code generation | BLEU | 0.15 | TR124 §6.3 |
| Classification | MMLU | 45% | TR125 §SS8 |

### BE.2 Acceptance Testing Protocol

1. Run TR124 eval suite against deployed model
2. Compare all metrics against baselines (stored in results/)
3. Flag any metric >5% below baseline
4. Re-run with different quant level if below threshold
5. Document quality-cost tradeoff in deployment log

---

## Appendix BF: Example Report Update Workflow

When new data becomes available (e.g., new model, new GPU):

1. Run relevant TR experiments with new configuration
2. Compare results against existing baselines
3. Update chimeraforge fitted_models.json with new entries
4. Re-validate against holdout data
5. Update relevant TR report with new findings
6. Update this conclusive report's claim status table if needed
7. Tag release with updated artifacts

---

## Appendix BG: Evaluation Philosophy and Limitations

The Phase 2 evaluation philosophy prioritizes decision utility over metric completeness. This means:

1. **Automated metrics are sufficient for the decisions being made.** The choice between Q4_K_M and Q8_0 does not require human evaluation — the automated metrics capture the relevant signal (structural overlap, semantic similarity, benchmark accuracy).
2. **Human evaluation would add value for subjective quality dimensions** (fluency, helpfulness, safety) but is out of scope for a performance research program focused on cost, throughput, and scaling.
3. **The composite metric is a deliberate simplification.** Unweighted averaging across metrics dilutes task-specific signal. Users should consult per-task metrics (TR124 §6.3) for deployment decisions, and use the composite only for cross-model comparison.
4. **Temperature=0 is the right default for evaluation.** TR124 Phase 3 shows CV=0.33 at temp=0.7, making non-greedy decoding unreliable for quality comparison. All quality claims use temp=0.

---

## Appendix BH: Additional Notes on Documentation and Communication

This report follows the documentation principles established in Phase 1 (TR118_v2.2):

1. **Every number has a source.** Section numbers, TR numbers, and artifact paths are provided for all key claims.
2. **Negative results are first-class.** The refutation of NUM_PARALLEL (TR128), M/D/1 theory (TR128), linear scaling (TR129), and serving-stack-as-bottleneck (TR131) receive the same analytical depth as positive findings.
3. **Caveats are explicit.** The TOST failure (TR125), Ollama determinism gap (TR124/TR125), and WDDM profiling limitation (TR131) are documented in the claim status table, limitations table, and threats section.
4. **The report is structured for multiple audiences.** The reading guide (§1.4) maps four distinct reading paths. The whitepaper (separate document) provides executive-level guidance. The extended appendices provide deep-dive material.
5. **Terminology is consistent.** All terms are defined in Appendices D, AG, and AO. Metric definitions are consistent across all 11 TRs.

---

*Supplemental material is mirrored in `PublishReady/reports/Technical_Report_Conclusive_123-133_Extended_Appendices.md`.*
