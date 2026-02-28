# Conclusive Report 117-122: Extended Appendices
## Supplemental material extracted from the main conclusive report

This file mirrors the extended appendices for convenience. The main conclusive report is the canonical
deep-dive document; the content here is supplemental and should be treated as supporting material.

## Appendix F: Workload Taxonomy and Routing Examples

This appendix summarizes workload classes and example routing decisions. It is intended as a practical complement to the decision matrix.

- Interactive chat: decode-dominant; route to best decode throughput backend.
- Batch prefill pipelines: prefill-dominant; route to best batched prefill cost backend.
- Tool-augmented agents: short prompts with high concurrency; prioritize overhead and warmup stability.

## Appendix H: Operational Playbooks and Templates

This appendix lists templates for common operational actions, such as warmup procedures, routing changes, and regression response. The detailed playbooks appear later in Appendix Y.

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
