# Conclusive Report 123-133: Extended Appendices
## Supplemental material extracted from the main conclusive report

This file mirrors and expands the extended appendices from the main conclusive report (TR123-TR133) for convenience. The main conclusive report is the canonical deep-dive document; the content here is supplemental and should be treated as supporting material. Each appendix is numbered to match the main report's appendix scheme. Where the main report provides a compact table or summary, this document provides the expanded narrative, worked examples, and operational depth.

---

## Appendix F: Workload Taxonomy and Routing Examples

This appendix expands the workload taxonomy from a routing table into a full characterization of six production workload types. Each entry describes the workload's computational profile, backend recommendations by concurrency level, quality considerations, and context budget implications. The goal is to provide enough detail for an engineering team to route traffic without consulting the individual technical reports.

### F.1 RAG-Heavy Workloads

**Input/output ratio:** 95/5. The prompt consists of retrieved documents (typically 2K-8K tokens) with a short generated answer (50-200 tokens).

**Dominant phase:** Prefill. The vast majority of GPU time is spent encoding the retrieved context. Decode is negligible in wall-clock terms because output length is short.

**Backend recommendation by N:**
- N=1: Ollama Q4_K_M. Prefill throughput is adequate for single-user RAG, and quantization reduces VRAM consumption enough to accommodate large contexts on 12 GB. Compiled HF on Linux is viable for prefill-heavy workloads but introduces deployment complexity without meaningful throughput advantage over Ollama at N=1.
- N=2-3: Ollama Q4_K_M remains viable. Amdahl serial fraction (s=0.39-0.54) means eta(2) is 0.67-0.80, which is acceptable for moderate concurrency.
- N>=4: vLLM FP16. Continuous batching amortizes the prefill kernel launches across concurrent requests (TR132: 77-80% kernel reduction), and PagedAttention manages KV-cache memory efficiently across users.

**Quality considerations:** RAG quality is dominated by retrieval quality, not generation quality. BERTScore and ROUGE-L are appropriate metrics for answer faithfulness. Q4_K_M is within -4.1pp of FP16 on benchmark accuracy (TR125), which is negligible for short-answer extraction from retrieved context.

**Context budget implications:** At 8K tokens with qwen2.5-1.5b FP16, VRAM usage is approximately 4.9 GB (TR127 worked example). Ollama with Q4_K_M reduces this proportionally, enabling contexts well beyond 8K on 12 GB hardware. The critical constraint is VRAM spillover: HF FP16 inference must stay below the model-specific spillover threshold (TR127) or redirect to Ollama.

### F.2 Summarization Workloads

**Input/output ratio:** 85/15. Long input documents (2K-16K tokens) with moderate-length summaries (200-500 tokens).

**Dominant phase:** Prefill, but decode is no longer negligible. A 500-token summary at 280 tok/s takes approximately 1.8 seconds of decode time, which can approach or exceed prefill time for shorter documents.

**Backend recommendation by N:**
- N=1: Ollama Q4_K_M. The decode component is long enough that Ollama's optimized GGUF kernels provide throughput advantages over raw HF.
- N>=4: vLLM FP16. The longer decode phase makes continuous batching even more valuable because decode tokens are generated sequentially and benefit from bandwidth amortization across concurrent requests.

**Quality considerations:** Summarization is sensitive to coherence and factual consistency. BERTScore > 0.80 and ROUGE-L > 0.45 are recommended baselines (TR124). Q4_K_M is acceptable; Q3_K_S introduces coherence degradation for some models (TR125: llama3.2-1b loses 12.2pp).

**Context budget implications:** Documents exceeding 4K tokens on HF FP16 risk VRAM spillover (TR127: 25-105x latency cliffs). Ollama with Flash Attention eliminates this risk via paged KV caches. For summarization pipelines processing documents of variable length, Ollama is the safer default regardless of concurrency.

### F.3 Chat Workloads

**Input/output ratio:** 67/33. Conversational exchanges with moderate context (1K-4K tokens including history) and moderate generation (100-300 tokens).

**Dominant phase:** Decode. The conversational pattern means each turn generates enough tokens that decode throughput determines perceived responsiveness. TTFT matters for user experience but decode dominates wall-clock time.

**Backend recommendation by N:**
- N=1: Ollama Q4_K_M. Optimized for single-agent decode throughput. At 280 tok/s native decode (llama3.2-1b), a 200-token response completes in under 1 second.
- N>=4: vLLM FP16. Chat workloads at scale (multiple concurrent conversations) benefit most from continuous batching because the decode-heavy nature means many sequential kernel launches are amortized simultaneously.

**Quality considerations:** Chat quality is multi-dimensional: coherence, factual accuracy, tone, and safety. The composite quality gate of >= 0.50 (TR124/TR125) is the minimum. For customer-facing chat, Q8_0 provides a safer margin.

**Context budget implications:** Multi-turn chat accumulates context across turns. A 10-turn conversation with 200 tokens per turn consumes 2K tokens of context. This is well within VRAM budgets for all backends. The risk is unbounded conversation length; implement a sliding window or summarization of older turns.

### F.4 Balanced Workloads

**Input/output ratio:** 50/50. Equal weight on prompt processing and generation. Examples include question-answering with detailed explanations, or structured data extraction with formatted output.

**Dominant phase:** Mixed. Neither prefill nor decode dominates, which makes this workload the hardest to optimize with a single strategy.

**Backend recommendation by N:**
- N=1: Ollama Q4_K_M. The balanced profile means no single optimization lever dominates. Ollama provides the best general-purpose throughput at N=1.
- N>=4: vLLM FP16. Even at 50/50, the decode component benefits from continuous batching, and the prefill component benefits from PagedAttention.

**Quality considerations:** Same as chat. The balanced profile means quality degradation from quantization affects both the understanding (prefill) and generation (decode) components.

**Context budget implications:** Similar to chat. Monitor total token count (input + output) against VRAM budget.

### F.5 Code Generation Workloads

**Input/output ratio:** 25/75. Short prompts (function signature, docstring, or test case) with long generated output (200-1000+ tokens of code).

**Dominant phase:** Decode. This is the most decode-heavy workload type. A 500-token code generation at 280 tok/s takes approximately 1.8 seconds. At 1000 tokens, decode time approaches 3.6 seconds.

**Backend recommendation by N:**
- N=1: Ollama Q4_K_M. Decode throughput is the primary lever. Ollama's optimized GGUF decode kernels outperform raw HF for this workload shape.
- N>=4: vLLM FP16. The long decode sequences make bandwidth amortization from continuous batching extremely effective. TR132 shows 79-83% bandwidth reduction per token at N=8.

**Quality considerations:** Code generation is sensitive to exact token sequences (syntax, variable names, indentation). BLEU and exact match are primary metrics. Q4_K_M is acceptable for general code generation; Q8_0 is recommended for safety-critical code (medical devices, financial systems) where a single syntax error is unacceptable.

**Context budget implications:** Short prompts mean minimal VRAM pressure from prefill. The constraint is decode memory: long generations grow the KV cache linearly. On 12 GB with Q4_K_M, generation length is effectively unconstrained for models up to 3B parameters.

### F.6 Classification Workloads

**Input/output ratio:** 99/1. Long input (document to classify) with minimal output (a label or short structured response, typically 1-10 tokens).

**Dominant phase:** Prefill. Decode is essentially free. This is the only workload type where compiled HF on Linux is recommended at N=1.

**Backend recommendation by N:**
- N=1: Compiled HF (Linux) with Inductor+Triton backend. TR126 shows 24-60% prefill latency reduction from torch.compile. Since decode is negligible, the compile crash on decode (TR126) is irrelevant. On Windows, fall back to Ollama Q4_K_M.
- N>=4: vLLM FP16. Classification at scale (batch classification of documents) benefits from vLLM's continuous batching of prefill operations.

**Quality considerations:** Classification accuracy is the only metric. MMLU-style benchmark accuracy is directly relevant. Q4_K_M maintains accuracy within -4.1pp of FP16 (TR125), which is acceptable for most classification tasks. For high-stakes classification (medical diagnosis, regulatory compliance), use Q8_0 or FP16.

**Context budget implications:** Long documents can push VRAM utilization. The routing rule applies: if context > 4K tokens and backend is HF FP16, redirect to Ollama to avoid VRAM spillover (TR127).

---

## Appendix H: Operational Playbooks and Templates

This appendix provides five operational playbooks that translate the Phase 2 research findings into step-by-step procedures. Each playbook is designed to be executed by an operations or engineering team without requiring familiarity with the underlying technical reports.

### H.1 Playbook: Upgrading from Ollama to vLLM

**When to execute:** Your workload has grown to N >= 4 concurrent agents and Ollama throughput has plateaued (TR129: eta(4) = 0.38 with s = 0.54).

**Prerequisites:** Docker installed. vLLM image pulled. Same model available in FP16 format (HuggingFace Hub or local weights).

**Step 1: Establish Ollama baseline.** Run your production workload at N=1 on Ollama with the current model and quantization. Record total throughput (tok/s), per-request latency (p50, p95), and VRAM utilization. This is your regression detection baseline.

**Step 2: Deploy vLLM in staging.** Launch vLLM with the same model in FP16 via Docker. Use the default tensor parallelism (tp=1 for single GPU). Set max-model-len to match your context budget. Enable continuous batching (default in vLLM >= 0.4).

**Step 3: Run N=1 baseline on vLLM.** Expect 20-40% lower absolute tok/s compared to Ollama Q4_K_M, because vLLM uses FP16 weights (2x larger than Q4_K_M). This is expected and not a regression. Record the same metrics as Step 1.

**Step 4: Run N=4 comparison.** Launch 4 concurrent agents against both Ollama and vLLM. Record total system throughput. Expect vLLM to match or exceed Ollama total throughput at N=4 (TR130: crossover at N=3-4). At N=8, expect vLLM to achieve 2.25x Ollama's total throughput.

**Step 5: Validate quality equivalence.** Run the TR124 quality evaluation suite (BERTScore, ROUGE-L, exact_match, coherence) on vLLM FP16 output. Compare against the Ollama Q4_K_M baseline. Backend choice does not affect quality (TR124: 0/7 metrics significant), but FP16 vs Q4_K_M may show small differences (TR125: within 4.1pp).

**Step 6: Monitor TTFT improvement.** vLLM with continuous batching provides 6-8x faster time-to-first-token under concurrency because requests are batched rather than queued. Verify this improvement matches your latency SLO.

**Step 7: Production cutover.** Route N >= 4 traffic to vLLM. Keep Ollama running for N=1 fallback and for workloads where quantized inference is preferred (VRAM-constrained contexts). Monitor for 48 hours before decommissioning the Ollama path for high-concurrency workloads.

### H.2 Playbook: Responding to VRAM Spillover

**When to execute:** You observe unexplained latency spikes (25-105x normal), VRAM utilization alerts at > 85%, or user reports of intermittent slowdowns on long-context requests.

**Step 1: Diagnose.** Check `nvidia-smi` or `torch.cuda.max_memory_allocated()`. If VRAM utilization exceeds 85% during the spike, VRAM spillover is the likely cause (TR127). PyTorch silently pages KV-cache to system RAM via PCIe, causing catastrophic throughput degradation without raising an error.

**Step 2: Identify the trigger.** Determine which model and context length caused the spillover. Common triggers: HF FP16 with > 4K context on 12 GB (TR127: qwen2.5-3b hits VRAM wall at 8K tokens; smaller models at 16K). Check whether the request was an outlier (unusually long document) or part of a trend (context accumulation in multi-turn chat).

**Step 3: Immediate remediation.** If using HF FP16: reduce context to below the model-specific spillover threshold. Thresholds by HF FP16 model on 12 GB (from TR127): gpt2 ~32K, qwen2.5-0.5b ~16K, qwen2.5-1.5b ~16K, phi-2 ~8K, qwen2.5-3b ~8K. Note: llama3.2 models were tested under Ollama only and do not spill due to Flash Attention. If using Ollama: spillover should not occur because Flash Attention and paged KV caches prevent it. If it does occur, the model is too large for the GPU at any context length.

**Step 4: Structural remediation.** Migrate long-context workloads from HF FP16 to Ollama or vLLM. Both use memory-efficient attention that prevents spillover. Implement a context length check in your request routing: reject or truncate requests that would exceed 90% VRAM capacity.

**Step 5: Monitoring.** Set VRAM utilization alerts at 85% (warning) and 90% (hard-stop). Log `torch.cuda.max_memory_allocated()` per request. Any request that pushes utilization above 90% should be flagged for review.

### H.3 Playbook: Quality Regression Investigation

**When to execute:** Automated quality checks detect a drop in composite score below the production gate (0.50 for general workloads, 0.60 for quality-critical), or user feedback indicates degraded output quality.

**Step 1: Establish the regression magnitude.** Run the TR124 quality evaluation suite on the current production configuration. Compare against the most recent quality baseline (stored in `results/eval/tr124_phase1/` or equivalent). Compute per-metric deltas: BERTScore, ROUGE-L, exact_match, coherence, MMLU accuracy, ARC accuracy.

**Step 2: Isolate the variable.** Quality regressions have four common root causes:
- Model change (different checkpoint, different quantization level)
- Backend change (Ollama version upgrade, vLLM scheduler change)
- Prompt template change (system prompt, formatting)
- Temperature or sampling parameter change

Run a controlled comparison: fix all variables except the suspected cause. TR124 establishes that backend choice at temp=0 does not affect quality (0/7 metrics significant), so if you see a backend-correlated regression, the root cause is likely elsewhere.

**Step 3: Check quantization.** If the model was recently re-quantized or a different quantization variant was deployed, compare quality against the TR125 tier table. Q4_K_M should be within -4.1pp of FP16. Q3_K_S is acceptable only for phi-2 and llama3.1-8b. Q2_K is never acceptable (near-random accuracy). If an incorrect quantization was deployed, this is the root cause.

**Step 4: Root-cause confirmation.** Once isolated, reproduce the regression in a controlled environment. Run the same prompts through both the regressed and baseline configurations. Compute effect sizes (Cohen's d) and statistical significance (Welch's t-test). A regression is confirmed when d > 0.2 and p < 0.05 on at least one primary metric.

**Step 5: Remediation.** Roll back to the last known good configuration. Document the root cause and update the quality gate checks to catch this class of regression automatically.

### H.4 Playbook: Adding a New Model to the Planner

**When to execute:** A new model (e.g., a new release from Meta, Mistral, or Qwen) needs to be incorporated into the `chimeraforge plan` capacity planner (TR133).

**Step 1: Collect VRAM measurements.** Load the model in FP16 on the target GPU. Measure VRAM consumption at context lengths 512, 1K, 2K, 4K, 8K using `torch.cuda.max_memory_allocated()`. Record model weights size (parameter_count x 2 bytes for FP16). This provides the VRAM model inputs.

**Step 2: Collect throughput baselines.** Run the TR123 scenario matrix (5 workload types) at the standard configuration: Ollama Q4_K_M, N=1, 7 repetitions. Record native eval_duration from Ollama's API response (not wall-clock). This provides the throughput model inputs.

**Step 3: Collect quality baselines.** Run the TR124 Phase 1 evaluation: 5 tasks x 50 samples at temp=0, plus MMLU (285 questions) and ARC-Challenge (200 questions). Record composite score, per-metric scores, and benchmark accuracy with Wilson confidence intervals.

**Step 4: Validate against existing models.** Compare the new model's profile against the closest existing model in the planner's lookup tables. Verify that VRAM scaling follows the expected linear-in-context pattern (TR127). Verify that throughput falls within the expected range for the parameter count and architecture (GQA vs MHA).

**Step 5: Integrate into the planner.** Add the new model's data to the planner's empirical lookup tables. Refit the VRAM and throughput models. Rerun the 4-target validation (VRAM R^2 >= 0.95, throughput R^2 >= 0.85, quality RMSE < 0.10, latency MAPE < 25%) on the updated dataset. Run the 10 spot checks. If all targets pass, the model is production-ready in the planner.

### H.5 Playbook: Scaling from 1 to 8 Agents

**When to execute:** Your application needs to scale from single-agent to multi-agent inference on a single GPU.

**Step 1: Benchmark N=1 baseline.** Record per-agent throughput, total system throughput, and VRAM utilization. This is the ceiling for per-agent performance.

**Step 2: Predict scaling with Amdahl's Law.** Using TR129 serial fractions (s = 0.39 for llama3.2-3b, s = 0.54 for llama3.2-1b), compute expected per-agent throughput: eta(N) = 1 / (s*N + (1-s)). At N=2, expect eta = 0.67-0.80. At N=4, expect eta = 0.32-0.50. At N=8, expect eta = 0.17-0.28.

**Step 3: Deploy N=2 and validate.** Launch 2 agents. Confirm that per-agent throughput matches the Amdahl prediction within 10%. Check VRAM utilization (should not change significantly; agents share the model). Check fairness (Jain's index should be >= 0.997 per TR129).

**Step 4: Evaluate the vLLM crossover.** At N=3, compare Ollama total throughput against vLLM total throughput. If vLLM exceeds Ollama (expected at N=3-4 per TR130), proceed with vLLM for higher agent counts. If not (possible for very small models where quantization advantage dominates), stay with Ollama.

**Step 5: Scale to N=4 with the chosen backend.** Validate throughput, latency, and fairness. For vLLM, expect power-law scaling (gentler degradation than Amdahl) due to continuous batching. Monitor VRAM: vLLM FP16 uses more VRAM than Ollama Q4_K_M, so headroom is smaller.

**Step 6: Scale to N=8 (vLLM only).** At N=8, Ollama degrades to 82.1% throughput loss (TR129). vLLM with continuous batching achieves 2.25x Ollama's total throughput (TR130). Monitor memory bandwidth stress: TR131 shows +74% memory operation time at N=8. This is the GPU physics floor and cannot be optimized further in software.

**Step 7: Production configuration.** Set VRAM alerts at 85%. Implement graceful degradation: if throughput per agent drops below the latency SLO, shed load to a queue rather than adding agents (diminishing returns beyond saturation). Document the scaling curve for capacity planning.

---

## Appendix J: Traceability Map (TR123-TR133 to Decisions)

This appendix provides an expanded traceability map from each operational decision to its contributing technical reports, primary evidence, and artifact paths. The map is organized by decision rather than by report, enabling a decision-maker to trace any policy choice back to its empirical foundation.

### J.1 Backend Selection (N=1)

**Decision:** Use Ollama Q4_K_M for single-agent workloads.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR123 | Phase-split cost tables: best-cost $0.013/1M tokens | `results/eval/tr123/` |
| TR124 | Backend choice does not affect quality (0/7 significant); enables cost-driven selection | `results/eval/tr124_phase1/` |
| TR126 | Compiled HF viable only on Linux, prefill only | `results/eval/tr126_phase2/` |
| TR128 | NUM_PARALLEL is a no-op; single-agent is the correct baseline | `results/eval/tr128/` |

### J.2 Backend Selection (N>=4)

**Decision:** Use vLLM FP16 for multi-agent workloads with N >= 4.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR129 | Amdahl serial fraction s=0.39-0.54 limits Ollama scaling | `results/eval/tr129/` |
| TR130 | vLLM 2.25x throughput advantage at N=8 | `results/eval/tr130/` |
| TR131 | GPU bandwidth is the bottleneck, not serving stack | `results/eval/tr131/` |
| TR132 | Continuous batching reduces kernel count 77-80% | `results/eval/tr132/` |

### J.3 Quantization Level

**Decision:** Q4_K_M universal default; Q8_0 for quality-critical; never Q2_K.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR124 | Quality baseline across 7 metrics, 5 models | `results/eval/tr124_phase1/` |
| TR125 | Tier table: Q4_K_M within -4.1pp of FP16; Q2_K near-random | `results/eval/tr125_phase2/` |

### J.4 Compile Policy

**Decision:** torch.compile prefill only, Linux only, eager decode always.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR126 | 24-60% prefill speedup; 916 Triton kernels; decode crash in all modes | `results/eval/tr126_phase2/`, `results/eval/tr126_phase3/` |

### J.5 Context Budget

**Decision:** Ollama for > 4K tokens; HF FP16 only for <= 4K on 12 GB.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR123 | KV-cache formula validation; GQA vs MHA memory comparison | `results/eval/tr123/` |
| TR127 | Two-regime discovery; 25-105x spillover cliffs | `results/eval/tr127/` |

### J.6 Agent Count and Scaling

**Decision:** 2-3 agents per GPU for Ollama; up to 8 for vLLM.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR129 | Amdahl fits with s=0.39-0.54; saturation at N=2 | `results/eval/tr129/` |
| TR130 | vLLM power-law scaling; crossover at N=3-4 | `results/eval/tr130/` |

### J.7 Capacity Planning Tool

**Decision:** Use `chimeraforge plan` for configuration search.

| Contributing TR | Evidence | Artifact Path |
|----------------|----------|---------------|
| TR133 | 4/4 validation targets met; 10/10 spot checks; 57 unit tests | `results/eval/tr133/` |
| TR123-TR130 | Input data (19,676 records) | All TR result directories |

---

## Appendix K: Extended Literature Review

This appendix expands the literature context for readers who want a deeper grounding beyond the core citations in the main report. The review is organized into six thematic clusters that correspond to the Phase 2 research arc.

### K.1 KV-Cache Mechanics and Grouped-Query Attention

The transformer attention mechanism (Vaswani et al., 2017) requires key and value tensors for every prior token during autoregressive decoding, making KV-cache the dominant memory consumer during generation. Multi-Head Attention (MHA) allocates independent key-value pairs per head, while Grouped-Query Attention (GQA, Ainslie et al., 2023) shares key-value heads across groups, reducing cache memory by a factor proportional to the grouping ratio. TR123 validates this distinction empirically: GQA models (llama3.2-1b, qwen2.5-1.5b, llama3.2-3b) use 3-11x less KV-cache memory than MHA models (gpt2, phi-2) at comparable context lengths. The practical consequence is that GQA enables longer context windows on fixed VRAM, which is the binding constraint for consumer GPUs.

### K.2 Quantization: GPTQ, AWQ, and GGUF/llama.cpp

Post-training quantization compresses model weights from FP16 (2 bytes) to lower bit-widths (4-bit, 3-bit, 2-bit), reducing memory footprint and increasing throughput at the cost of quality. Three major approaches dominate the literature: GPTQ (Frantar et al., 2022), which uses second-order information for optimal rounding; AWQ (Lin et al., 2023), which preserves salient weights based on activation distributions; and GGUF (llama.cpp project), which provides a family of k-quant variants (Q2_K through Q8_0) optimized for CPU and mixed-precision inference. TR125 provides the first systematic evaluation of k-quant quality across 5 models and 7 quantization levels using real benchmark data (MMLU, ARC-Challenge), establishing Q4_K_M as the universal sweet spot where quality loss is negligible (-4.1pp) but memory savings are substantial (30-67%).

### K.3 Serving Stacks: vLLM, TGI, and Continuous Batching

The PagedAttention paper (Kwon et al., 2023) established that paging KV-cache blocks enables serving multiple concurrent requests without proportional memory overhead. vLLM implements this as the core of its continuous batching scheduler, which dynamically batches prefill and decode operations across concurrent requests. Text Generation Inference (TGI, Hugging Face) implements a similar continuous batching strategy with a different scheduler. The Orca paper (Yu et al., 2022) introduced the concept of iteration-level scheduling for continuous batching. TR130 provides the first consumer-hardware comparison of these three approaches under identical conditions, and TR132 identifies the mechanism: continuous batching reduces per-token kernel launches by 77-80%, directly amortizing GPU memory bandwidth.

### K.4 GPU Profiling and Memory Bandwidth

Nsight Systems (NVIDIA) provides system-level tracing of CUDA kernel launches, memory operations, and API calls. Nsight Compute provides kernel-level metrics including memory throughput, occupancy, and instruction mix. The roofline model (Williams et al., 2009) provides a framework for understanding whether a workload is compute-bound or memory-bound. TR131 and TR132 apply these tools to LLM inference for the first time on consumer hardware, demonstrating that autoregressive decode is memory-bandwidth-bound (not compute-bound) and that multi-agent degradation is caused by memory bandwidth contention (+74% memory operation time at N=8), not serving stack overhead.

### K.5 Amdahl's Law in Modern Systems

Amdahl's Law (Amdahl, 1967) predicts that speedup from parallelism is limited by the serial fraction of a workload: S(N) = 1 / (s + (1-s)/N). While well-known in parallel computing, its application to LLM inference serving is novel. TR129 fits Amdahl's Law to multi-agent inference data with R^2 > 0.97, finding serial fractions of s = 0.39-0.54. This is unusually high compared to typical HPC workloads (s < 0.05), reflecting the fundamentally sequential nature of autoregressive decoding on a single GPU. The finding that s varies by model (0.39 for llama3.2-3b vs 0.54 for llama3.2-1b) suggests that the serial fraction is not purely hardware-determined but depends on the model's memory access pattern.

### K.6 Quality Evaluation: SemScore, BERTScore, and Benchmarks

Quality evaluation of language model outputs has evolved from simple n-gram metrics (BLEU, ROUGE) to embedding-based metrics (BERTScore, Zhang et al., 2019; SemScore) that capture semantic similarity. TR124 uses a 7-metric framework: BERTScore, ROUGE-L, BLEU, coherence (all-mpnet-base-v2 cosine similarity), exact match, output length, and repetition. For benchmark-based evaluation, MMLU (Hendrycks et al., 2020) and ARC-Challenge (Clark et al., 2018) provide standardized accuracy measurements. TR125 uses Wilson confidence intervals for benchmark accuracy and TOST (Two One-Sided Tests) for equivalence testing, providing a more rigorous statistical framework than simple point comparisons.

---

## Appendix L: Measurement Boundary Catalog

This appendix provides detailed per-TR measurement boundaries to prevent accidental cross-boundary comparisons. Each entry specifies what is included and excluded from the timed region, along with compatibility notes for cross-TR comparisons.

**TR123 (KV-Cache Economics):** Timed region includes model forward pass (prefill) and decode loop with KV cache enabled. Excludes tokenization, model loading, and warmup iterations (3 discarded). PhasePowerSampler with mark_phase() separates prefill and decode energy attribution. Compatible with TR119 (same formula, different cache setting) but not directly comparable to Ollama-based measurements (different timing boundary).

**TR124 (Quality Baseline):** Timed region includes full generation plus metric computation. Model loading and tokenization overhead are excluded. Timing is secondary to quality metrics; the primary output is metric scores, not latency. Cross-comparable only on quality metrics, not on throughput.

**TR125 (Quantization Matrix):** Two timing modes. Wall-clock: Ollama /api/generate total time including HTTP overhead. Native: Ollama eval_duration from API response, excluding model loading. Native timing is preferred; wall-clock has 190-920% overhead due to HTTP serialization. Native timing is comparable to TR128 and TR129 Ollama measurements.

**TR126 (Compile Validation):** Timed region includes forward pass (prefill) or decode loop, measured per compilation mode (eager, compiled, reduce-overhead). Compilation time itself is excluded and measured separately. Cross-platform comparable within TR126 (same prompts, same models, different OS). Not directly comparable to Ollama-based measurements.

**TR127 (Context Scaling):** Same as TR123 but measured across 7 context lengths (512-32K tokens). VRAM measured via `torch.cuda.max_memory_allocated()`. OOM samples are marked as failures, not excluded silently. Compatible with TR123 at matching context lengths.

**TR128 (Production Workloads):** Full /api/generate wall clock per request. Model is pre-warmed (loading excluded). Poisson inter-arrival sleep is excluded from timed region. Load generator is external; timing starts at request send. Compatible with TR125 wall-clock timing.

**TR129 (N-Agent Scaling):** Agent-observed wall clock per request. Think-time gaps between requests are excluded. Closed-loop measurement: agent sends, waits, measures, then sends again. Compatible with TR128 at N=1 but not at N > 1 (different load generation pattern).

**TR130 (Serving Stack Comparison):** Same as TR129 across 3 backends (Ollama, vLLM, TGI). Backend startup and Docker overhead are excluded. Warmup protocol eliminates cold-start effects. Cross-backend comparable within TR130.

**TR131 (GPU Kernel Profiling):** nsys-traced kernel execution and memory operations. Model loading, nsys startup, and trace export are excluded. Profiling overhead validated at < 1% TPS impact. Not directly comparable to wall-clock measurements (profiling adds systematic overhead, but it is bounded).

**TR132 (In-Container Profiling):** In-container nsys-traced kernels using a novel methodology: Linux nsys binary volume-mounted into Docker containers. Container startup, nsys mounting, and trace export are excluded. Traces are 11.6-17.4 MB each. Comparable to TR131 methodology but applied inside containers.

**TR133 (Predictive Planner):** No timed measurement; prediction only. All timing data is inherited from TR123-TR130. Validation is against held-out empirical data (20% holdout, 3,939 records), not against new measurements.

---

## Appendix N: Expanded Discussion and Implications

This appendix provides a narrative expansion of five themes that emerge from the Phase 2 research program. Each theme carries implications beyond the immediate deployment recommendations.

### N.1 The Serving Stack Abstraction Is Leaky

The most dramatic finding across Phase 2 is that "serving stack" is not a useful abstraction for understanding multi-agent scaling. TR130 attributed the scaling advantage of vLLM and TGI to "better scheduling," which is a software explanation. TR131 demolished this by showing that PyTorch Direct -- with no HTTP server, no Go runtime, no request queuing -- degrades worse than Ollama (86.4% vs 82.1% throughput loss at N=8). The degradation is in the GPU, not the software.

TR132 then identified the actual mechanism: continuous batching amortizes GPU memory bandwidth by combining multiple requests into fewer, larger kernel launches. The serving stack matters, but not for the reason TR130 suggested. It matters because some serving stacks implement continuous batching (vLLM, TGI) and others do not (Ollama). The performance advantage is a consequence of how the serving stack interacts with the GPU, not of how it manages HTTP connections or request queues.

The implication for systems research is that correlational evidence from application-level benchmarks can be right about the effect and wrong about the cause. TR130 correctly identified that vLLM scales better. It incorrectly attributed this to software scheduling efficiency. Only GPU kernel profiling (TR131) and in-container kernel analysis (TR132) revealed the true mechanism. This suggests that any serving stack comparison that does not include kernel-level evidence should be treated with caution.

### N.2 Quantization Is Under-Studied in Systems Literature

Most serving stack comparisons in the academic literature use FP16 throughout. This is a significant omission. TR131 found that Ollama's Q4_0 quantization actually helps under concurrency: Ollama's advantage over PyTorch Direct (FP16) grows from 3.0x at N=1 to 3.9x at N=8. The mechanism is straightforward: quantized weights consume less memory bandwidth per token, leaving more bandwidth headroom for concurrent requests. Under bandwidth contention, this headroom becomes a first-order performance advantage.

The implication is that the interaction between quantization and bandwidth contention is a rich and under-explored design space. Future work should compare vLLM with quantized weights (AWQ, GPTQ, or k-quant) against Ollama to isolate the continuous batching benefit from the quantization benefit. It is plausible that vLLM + Q4_K_M would outperform vLLM + FP16 at high concurrency, which would reshape the serving stack recommendation.

### N.3 Theoretical Models Need Empirical Calibration

Three theoretical frameworks were tested against empirical data in Phase 2, and each failed in specific ways:

- **M/D/1 queueing theory** (TR128): Predicts latency under load as a function of arrival rate and service time. Deviates up to 20.4x from observed latency when NUM_PARALLEL > 1. The failure mode is that M/D/1 assumes independent service, but GPU inference is serialized: the "parallel" slots do not actually execute in parallel.

- **Amdahl's Law** (TR129): Fits well within a single backend (R^2 > 0.97) but becomes a category error when applied across backends with fundamentally different degradation mechanisms. Ollama follows Amdahl (hardware serialization). vLLM follows a power law (continuous batching amortization). Comparing serial fractions across these two is meaningless.

- **O(n^2) attention scaling** (TR127): Theoretically correct but practically dominated by VRAM spillover on consumer hardware. Below VRAM capacity, Ollama prefill scaling is sub-linear (b = 0.083-0.158); HF FP16 scales between linear and quadratic (b = 1.58-1.78). Above capacity, the 25-105x cliff is caused by PCIe paging, not by attention compute.

The chimeraforge planner (TR133) succeeds precisely because it uses empirical lookup tables rather than theoretical models. The theoretical frameworks are useful for understanding mechanisms but unreliable for prediction on real hardware.

### N.4 Consumer Hardware Is Production-Viable

The entire Phase 2 research program runs on a single RTX 4080 Laptop GPU with 12 GB VRAM. The key findings:

- Single-agent inference at 280 tok/s native decode (llama3.2-1b Q4_K_M) is sufficient for interactive chat.
- Multi-agent inference at N=8 on vLLM serves 8 concurrent users with approximately 70 tok/s each (sufficient for RAG and chat workloads).
- Monthly cost for 100M tokens/month: approximately $1.70 in electricity.
- Quality is preserved: Q4_K_M is within -4.1pp of FP16 on benchmark accuracy.

The practical implication is that a team with a single consumer GPU and Ollama can serve a prototype or small-scale production workload without cloud infrastructure. The scaling limit is real (throughput plateaus at N=2 on Ollama, N=8 on vLLM), but for many applications -- internal tools, development assistants, low-traffic chatbots -- a consumer GPU is sufficient.

### N.5 From Reports to Tools: The Research-to-Product Pipeline

TR133 represents a deliberate transition from research output (reports, tables, findings) to product output (a CLI tool that makes decisions). The chimeraforge planner ingests 19,676 empirical records and exposes them through a sub-second query interface. A user who has never read a single technical report can run `chimeraforge plan` and receive a ranked list of deployment configurations.

This transition is non-trivial. The planner must validate its own predictions (4/4 targets met), handle edge cases (models not in the lookup table), and degrade gracefully when data is missing. The fact that simple models (lookup tables + Amdahl's Law + first-principles VRAM formulas) outperform complex ones (M/D/1 queueing) is itself a finding: the best predictive model is the one calibrated against empirical data, not the one with the most elegant theory. This has implications for tooling in the ML systems space: invest in data collection and empirical validation, not in theoretical model complexity.

---

## Appendix O: Extended Results Narratives

This appendix provides dissertation-style narratives for each of the eleven technical reports in Phase 2. Each narrative explains the report's contribution in the context of the overall research arc, highlights its key findings, and identifies how it reshapes the understanding that preceded it.

### O.1 TR123: The Economic Foundation

TR123 is the economic foundation of Phase 2. It answers the question that TR119 could not: what does production inference actually cost when KV-cache is enabled? The answer reframes every cost recommendation from Phase 1. With KV-cache, decode throughput doubles or more for memory-bandwidth-bound models, and the cost per million tokens drops proportionally. The phase-split cost model -- separating prefill economics from decode economics across five workload blend ratios -- provides the first decision-grade pricing for local-first inference. The GQA versus MHA comparison adds a structural dimension that was invisible in Phase 1: at comparable parameter counts, GQA models use 3-11x less KV-cache memory, enabling dramatically longer contexts on the same hardware. This is not a minor optimization; it determines whether a model can serve 4K or 40K token contexts on a consumer GPU. The best-cost configuration ($0.013/1M tokens for GPT-2 compiled at chat blend) establishes an economic floor that makes local inference competitive with cloud API pricing for moderate-volume workloads.

### O.2 TR124: The Quality Insurance Policy

TR124 is the quality insurance policy for the entire program. Without it, every cost recommendation from TR123 and every quantization recommendation from TR125 would carry an implicit and untested assumption: that cheaper backends and more aggressive quantization produce equivalent output. TR124 tests this assumption across three phases. Phase 1 (5 models, 2 backends, temp=0, 7 metrics with ANOVA and Holm-Bonferroni correction) confirms backend equivalence: 0/7 metrics show significant differences. This is the enabling result for cost-driven backend selection. Phase 2 maps the quality landscape across quantization levels. Phase 3 bounds sampling variance at temp=0.7, providing the noise floor for quality comparisons. The Pareto frontier finding -- that llama3.2-1b offers the best quality-per-dollar -- is not merely a data point; it is a deployment recommendation that has survived statistical scrutiny across 2,800 Phase 1 samples.

### O.3 TR125: Mapping the Decision Space

TR125 transforms quantization from a binary choice ("full precision or some compression") into a mapped decision space with 34 model-quant variants, 4 quality tiers, and specific per-model recommendations. The two-phase design (900 samples for rapid screening, then 24,990 samples for definitive evaluation including MMLU and ARC benchmarks) balances research velocity with statistical rigor. The Q4_K_M sweet spot is the single most impactful deployment recommendation in the Phase 2 program: it saves 30-67% on cost and VRAM with negligible quality loss across all 5 tested models. The Q2_K cliff (near-random accuracy across all models) is equally important as a prohibition. The Q3_K_S finding is nuanced: it is acceptable for phi-2 and llama3.1-8b but breaks llama3.2-1b (12.2pp loss), llama3.2-3b, and qwen2.5-1.5b. This model-dependent behavior means that Q3_K_S cannot be recommended as a universal policy, which is itself a valuable finding -- it prevents a plausible but dangerous generalization.

### O.4 TR126: Resolving the Mystery

TR126 is the most satisfying report in the program because it resolves a genuine mystery. The Phase 1 compile paradox (TR120 on Windows) appeared to show that torch.compile hurts performance -- or at best does nothing. This was deeply puzzling because torch.compile with Triton should, in theory, generate optimized GPU kernels. TR126 proves that the Windows result was an artifact: Windows uses aot_eager as its Triton fallback, which performs no real compilation. On Linux with genuine Triton, compilation delivers 24-60% prefill latency reduction across all 7 models with 916 generated Triton kernels and Cohen's d = -0.59. The report also reveals an important limitation that Windows had obscured: compiled decode crashes in all tested modes (reduce-overhead and mode="default"). Since compile never worked on Windows, this crash was never triggered. The five independent evidence lines (environment validation, Triton kernel generation, statistical significance, mode comparison, and PyTorch version rerun) make the conclusion exceptionally robust. The net policy is crisp: compile prefill on Linux, never compile decode, never compile on Windows.

### O.5 TR127: The Two-Regime Discovery

TR127 discovers the two-regime phenomenon that reshapes all context-length planning for consumer hardware. Below VRAM capacity, Ollama prefill scaling is clean, predictable, and sub-linear (power-law exponent b = 0.083-0.158). This is better than the theoretical O(n^2) prediction because Ollama's Flash Attention and optimized kernels reduce the effective scaling exponent. HF FP16 pre-spillover scaling remains between linear and quadratic (b = 1.58-1.78) since it does not benefit from Flash Attention on this hardware. Above VRAM capacity, performance degrades catastrophically: 25-105x latency cliffs when PyTorch silently pages KV-cache to system RAM via PCIe. The silence is the critical operational detail. PyTorch does not raise an error, does not log a warning, and does not visibly fail. It simply slows down by two orders of magnitude. The user sees unexplained latency spikes with no diagnostic signal. Ollama eliminates this entirely by using Flash Attention and paged KV caches that stay within VRAM. This finding makes Ollama the mandatory backend for any workload that might exceed 4K tokens on 12 GB hardware, regardless of any other performance consideration.

### O.6 TR128: The Production Reality Check

TR128 is the production reality check. It tests the knobs that practitioners actually turn and discovers that two of three are useless. NUM_PARALLEL, the Ollama setting that claims to enable concurrent GPU inference, is a no-op: 0/30 pairwise statistical tests are significant. M/D/1 queueing theory, the standard framework for predicting latency under load, deviates up to 20.4x from reality because it assumes independent parallel service when GPU inference is actually serialized. Streaming, the one knob that practitioners worry about, turns out to be free: zero wall-clock overhead confirmed by 0/9 significant tests. The 20.4x M/D/1 deviation is perhaps the most practically important negative result in the program. It means that any capacity planning based on standard queueing theory will be wildly optimistic for single-GPU inference, overestimating throughput capacity by up to an order of magnitude. This finding directly motivates the empirical approach used in TR133's capacity planner.

### O.7 TR129: Quantifying the Scaling Wall

TR129 quantifies the multi-agent problem that TR128 exposed. The Amdahl fits (R^2 > 0.97) provide a predictive formula -- eta(N) = 1/(s*N + 1-s) -- that is validated across 5,310 measurements and 3 models. With serial fractions of s = 0.39-0.54, the formula predicts that total system throughput plateaus at N=2 (approximately 1.4-1.6x single-agent) and per-agent efficiency drops to 17-20% at N=8. This has immediate design implications: deploying 8 agents on one GPU through Ollama wastes approximately 80% of each agent's potential throughput. The fairness result (Jain's index >= 0.997) is reassuring but strategically irrelevant: the agents share fairly, but they share a shrinking pie. The finding that serial fractions vary by model (0.39 for llama3.2-3b, 0.54 for llama3.2-1b) suggests that larger models, with their higher memory bandwidth demand, leave less room for parallelism.

### O.8 TR130: Identifying the Solution and the Misattribution

TR130 identifies the solution to TR129's scaling problem: continuous batching via vLLM. The 2.25x throughput advantage at N=8 is dramatic and practically significant. However, TR130 also commits the program's most instructive error: it attributes vLLM's advantage to "better serving stack scheduling" -- a software explanation. This attribution feels natural (vLLM has a sophisticated scheduler, Ollama does not) but is wrong. The serving stack is the vehicle for continuous batching, not the cause of the performance advantage. The cause is bandwidth amortization at the GPU level. This misattribution is not embarrassing; it is the evidence that the program's falsification machinery works. TR130's software hypothesis is precisely what TR131 was designed to test, and TR131 overturns it.

### O.9 TR131: The Causal Test

TR131 is the causal test that overturns the serving-stack hypothesis. The experimental design is elegant in its simplicity: remove the serving stack entirely (PyTorch Direct, no HTTP server, no Go runtime, no request queuing) and see whether the degradation persists. It does. PyTorch Direct degrades 86.4% at N=8, which is worse than Ollama's 82.1%. This is a definitive refutation: if the degradation is worse without the serving stack, the serving stack cannot be the cause. The mechanism is GPU memory bandwidth contention. Memory operation time increases +74% at N=8 (p = 6.4 x 10^-5, the sole Holm-surviving test in the full comparison). Maximum concurrent kernels equals 1 in all conditions -- hardware serialization, not software serialization. The GPU physics overturns the serving-stack hypothesis completely. The question shifts from "why is Ollama slow?" to "why is vLLM faster despite the same GPU physics?"

### O.10 TR132: Proving the Mechanism

TR132 completes the causal chain. If the bottleneck is GPU memory bandwidth (TR131), and vLLM scales better (TR130), then vLLM must be doing something to reduce bandwidth demand per token. TR132 proves exactly this with a novel in-container profiling methodology: Linux nsys binary volume-mounted into Docker containers running vLLM and TGI under WSL2/WDDM. Continuous batching reduces kernel launches by 77-80% at N=8 (all p < 10^-6, Cohen's d > 600, 4/4 Holm-significant tests). Memory bandwidth per token drops 79-83%. The amortization ratio is 4.7-5.8x, which is 59-72% of the theoretical 8:1 maximum. The fact that vLLM and TGI show identical amortization proves that the mechanism is continuous batching itself, not any implementation-specific optimization. This resolves the TR130/TR131 apparent contradiction: vLLM scales better not because Ollama's serving stack is bad, but because continuous batching amortizes the GPU memory bandwidth bottleneck that TR131 identified.

### O.11 TR133: The Capstone

TR133 is the capstone that operationalizes the entire corpus. It ingests 19,676 records from TR123-TR130, fits 6 predictive models (VRAM, throughput, scaling, quality, cost, latency), validates against a 20% holdout (3,939 records), and ships a CLI tool. All 4 validation targets are met: VRAM R^2 = 0.968 (target 0.95), throughput R^2 = 0.859 (target 0.85), quality RMSE = 0.062 (target < 0.10), latency MAPE = 1.05% (target < 25%). The 10/10 spot checks pass, and 57 unit tests confirm correctness. The key insight is that empirical lookup tables with first-principles interpolation outperform theoretical models. M/D/1 deviates 20.4x. Amdahl is a category error across backends. But lookup tables calibrated against real measurements, combined with physics-based VRAM formulas, produce predictions accurate enough for production capacity planning. No machine learning is needed. The simplest model that respects the empirical data wins. This is the methodological lesson of the entire program: invest in measurement, not in model complexity.

---

## Appendix P: Quantization Decision Trees and Quality Gates

This appendix expands the compact decision tree from the main report into a comprehensive set of decision paths for different deployment scenarios, along with per-application quality thresholds.

### P.1 Primary Decision Tree: Selecting Quantization Level

```
START: What is your application's risk tolerance?

[HIGH RISK] Medical, legal, financial, or safety-critical
  |
  +-- Is VRAM sufficient for FP16? (model_params_B x 2 < 0.8 x VRAM_GB)
  |     YES --> FP16 (maximum quality, no quantization artifacts)
  |     NO  --> Q8_0 (within -2pp of FP16 on all tested models)
  |             +-- Still too large? --> Use a smaller model. Do NOT use Q4_K_M
  |                                     for high-risk applications.

[MODERATE RISK] Customer-facing chat, QA pipelines, document processing
  |
  +-- Q4_K_M (universal default)
  |     Quality: within -4.1pp of FP16 across all 5 tested models (TR125)
  |     Composite: >= 0.50 (TR124)
  |     VRAM savings: 30-67% vs FP16
  |
  +-- Is quality gate failing (composite < 0.50)?
        YES --> Upgrade to Q8_0 or use a larger model at Q4_K_M
        NO  --> Ship Q4_K_M

[LOW RISK] Internal tools, development, prototyping
  |
  +-- Q4_K_M (still the default -- no reason to go lower)
  |
  +-- VRAM extremely constrained? (<2 GB available for model weights)
        +-- Model is phi-2 or llama3.1-8b? --> Q3_K_S is acceptable
        +-- Model is llama3.2-1b, llama3.2-3b, or qwen2.5-1.5b?
            --> Q3_K_S breaks these models (9.5-12.2pp loss). Use Q4_K_M minimum.
        +-- Still too large? --> Use a smaller model.

[NEVER] Q2_K
  Produces near-random accuracy across ALL tested models.
  Explicitly prohibited in all deployment scenarios.
```

### P.2 Quality Gates by Application Type

| Application | Min Composite | Min MMLU | Min ARC | Recommended Quant | Rationale |
|------------|--------------|---------|---------|-------------------|-----------|
| General chatbot | 0.50 | 40% | 35% | Q4_K_M | Balance of cost and quality |
| QA pipeline | 0.55 | 45% | 40% | Q4_K_M or Q8_0 | Factual accuracy matters |
| Summarization | 0.45 | -- | -- | Q4_K_M | Coherence > accuracy |
| Code generation | 0.40 | -- | -- | Q4_K_M | Syntax correctness; test coverage compensates |
| Medical/legal | 0.60 | 55% | 50% | Q8_0 or FP16 | Error cost is high |
| Classification | -- | 50% | 45% | Q4_K_M | Label accuracy is the only metric |
| Multi-agent coding | 0.45 | -- | -- | Q4_K_M | Cost efficiency across 4-8 agents |
| Batch analytics | 0.40 | -- | -- | Q4_K_M | Throughput > per-item quality |

### P.3 Model-Specific Quantization Compatibility

| Model | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_S | Q2_K |
|-------|------|------|--------|--------|--------|------|
| llama3.2-1b | PASS | PASS | PASS | PASS | FAIL (-12.2pp) | FAIL |
| qwen2.5-1.5b | PASS | PASS | PASS | PASS | FAIL (-9.5pp) | FAIL |
| phi-2 | PASS | PASS | PASS | PASS | PASS | FAIL |
| llama3.2-3b | PASS | PASS | PASS | PASS | FAIL | FAIL |
| llama3.1-8b | PASS | PASS | PASS | PASS | PASS | FAIL |

PASS = within the moderate-risk quality gate (composite >= 0.50 or MMLU within -5pp of Q8_0 baseline).
FAIL = below quality gate or > 9pp loss from Q8_0.

---

## Appendix Q: Extended Decision Case Studies

This appendix provides five case studies that illustrate how to apply the Phase 2 findings to realistic deployment scenarios. Each case study includes a scenario description, the decision path through the research findings, quantitative predictions, and a final recommendation.

### Q.1 Case Study: Small Startup with Single RTX 4080

**Scenario:** A 3-person startup is building an AI-powered customer support chatbot. They have a single RTX 4080 (desktop, 12 GB VRAM). Expected traffic: approximately 50 requests per hour during business hours. Quality matters (customer-facing), but the team has no budget for cloud GPU instances.

**Decision path:** 50 requests per hour is 0.014 requests per second, far below any GPU saturation threshold. This is definitively N=1 territory. No multi-agent scaling is needed. Backend: Ollama Q4_K_M (no vLLM overhead justified for single-agent). Model: llama3.2-1b for cost efficiency (best quality-per-dollar per TR124 Pareto frontier) or phi-2 for higher absolute quality (composite 0.63 vs 0.58). Quantization: Q4_K_M (within -4.1pp of FP16, well above the 0.50 quality gate for general chatbots).

**Quantitative prediction (from TR123/TR125/TR133):**
- Decode throughput: approximately 280 tok/s native (llama3.2-1b Q4_K_M)
- Average response (200 tokens): approximately 0.7 seconds decode + 0.1 seconds prefill = 0.8 seconds
- VRAM usage: approximately 1.2 GB (model) + 0.5 GB (overhead) = 1.7 GB. Massive headroom on 12 GB.
- Context budget: effectively unlimited within model limits (Ollama, quantized)
- Monthly electricity cost: approximately $1.70 for 100M tokens/month; at 50 req/hr with 300 tokens each, actual usage is approximately 10M tokens/month = $0.17/month

**Recommendation:** Deploy llama3.2-1b on Ollama Q4_K_M. No vLLM, no compiled HF, no FP16 needed. Context can extend to 32K tokens without VRAM concern. Quality gate check: run TR124 evaluation suite monthly. Scale to vLLM only if concurrent users exceed 3.

### Q.2 Case Study: RAG Pipeline with 8 Concurrent Users

**Scenario:** A mid-size company runs a knowledge base with 8 concurrent internal users. Each query retrieves 3-5 documents (total 6K-8K tokens of context) and generates a 128-token answer. Latency SLO: p95 under 5 seconds. Budget: consumer hardware preferred.

**Decision path:** N=8 concurrent users means vLLM is mandatory (TR129: Ollama at N=8 loses 82.1% throughput; TR130: vLLM achieves 2.25x advantage). Model: llama3.2-1b FP16 (fits in 12 GB at 8K context; VRAM approximately 4.9 GB per TR127 worked example). Backend: vLLM with continuous batching. The 8K context is within vLLM's comfortable range with PagedAttention.

**Quantitative prediction:**
- vLLM throughput at N=8: approximately 559 tok/s total system, approximately 70 tok/s per user (TR130 extrapolation)
- Per-request latency: 128 decode tokens / 70 tok/s = 1.83 seconds decode + approximately 100ms prefill = approximately 1.93 seconds
- p95 SLO check: 1.93 seconds is well within the 5-second SLO even at p95
- VRAM: llama3.2-1b FP16 at 8K context = approximately 4.9 GB. With 8 concurrent KV caches under PagedAttention: approximately 6-7 GB total. Fits in 12 GB with headroom.
- Monthly cost: approximately $25/month on consumer hardware electricity

**Recommendation:** Deploy llama3.2-1b FP16 on vLLM. Set max-model-len to 8192. Monitor VRAM at 85% alert threshold. If latency SLO is violated, reduce concurrent users to 6 or switch to Q4_K_M via vLLM (if supported) to reduce memory pressure.

### Q.3 Case Study: Quality-Sensitive Legal Document Processing

**Scenario:** A legal tech company processes contracts for compliance review. Accuracy is paramount: a missed clause or misidentified term could have legal consequences. Two lawyers use the system simultaneously. Documents are 2K-4K tokens. Output is structured analysis of 300-500 tokens.

**Decision path:** Quality-critical application (medical/legal tier). N=2 concurrent users means Ollama is still viable (TR129: eta(2) = 0.67-0.80). Quantization: Q8_0 minimum, FP16 preferred. Model: phi-2 (highest absolute quality at composite 0.63 per TR124) or llama3.1-8b for maximum accuracy (but requires quantization to fit in 12 GB).

**Quantitative prediction:**
- phi-2 Q8_0 on Ollama at N=2: approximately 110 tok/s per agent (solo approximately 140 tok/s x eta(2) = 0.80)
- Per-request latency: 400 decode tokens / 110 tok/s = 3.6 seconds decode + approximately 200ms prefill = approximately 3.8 seconds
- Quality: phi-2 Q8_0 composite = 0.63, MMLU approximately 55%, within -1.8pp of FP16. Exceeds the 0.60 quality gate for legal applications.
- VRAM: phi-2 Q8_0 at 4K context = approximately 4.5 GB (model) + 1.5 GB (KV + overhead) = approximately 6 GB. Fits in 12 GB.

**Recommendation:** Deploy phi-2 Q8_0 on Ollama. Quality gate: BERTScore > 0.80, ROUGE-L > 0.45, composite >= 0.60 per TR124 baselines. Run quality evaluation weekly. For documents exceeding 4K tokens, implement chunking with overlap rather than extending context (avoids approaching VRAM spillover). Escalation path: if quality gate fails on specific document types, upgrade to llama3.1-8b Q8_0 or switch to FP16 with vLLM.

### Q.4 Case Study: Multi-Agent Coding Assistant

**Scenario:** A development team of 6 runs an AI coding assistant integrated into their IDEs. Each developer generates multiple requests per minute (code completion, documentation, test generation). Effective concurrency: N=4-6 simultaneous requests. Code quality matters but is verified by test suites.

**Decision path:** N=4-6 means vLLM is the clear choice (TR130: vLLM overtakes Ollama at N=3-4). Code generation is decode-heavy (25/75 input/output ratio). Model: llama3.2-3b for code quality (larger model = better code generation) or llama3.2-1b for throughput. Quantization: vLLM runs FP16; if VRAM is tight with llama3.2-3b, fall back to llama3.2-1b FP16.

**Quantitative prediction:**
- llama3.2-1b FP16 on vLLM at N=6: approximately 420 tok/s total, approximately 70 tok/s per developer
- Per-request (code completion, 200 tokens): 200 / 70 = 2.9 seconds. Acceptable for code completion with IDE prefetching.
- Per-request (test generation, 500 tokens): 500 / 70 = 7.1 seconds. Acceptable as a background task.
- VRAM: llama3.2-1b FP16 with 6 concurrent 2K-context requests under PagedAttention: approximately 5 GB. Comfortable on 12 GB.

**Recommendation:** Deploy llama3.2-1b FP16 on vLLM with continuous batching. Quality gate: BLEU > 0.30 for code completion (verified against known-good completions). Since code is verified by test suites, the quality gate can be lower than for customer-facing applications. If code quality is insufficient, upgrade to llama3.2-3b FP16 (fits in 12 GB at 2K context) and accept slightly lower per-agent throughput. Monitor fairness (Jain's index, expect >= 0.997 per TR129) to ensure no developer is starved of GPU time.

### Q.5 Case Study: Cost-Optimized Batch Processing Pipeline

**Scenario:** A data analytics company processes 500K customer feedback documents nightly for sentiment classification and topic extraction. Documents average 800 tokens. Output is a JSON label (approximately 20 tokens). The pipeline must complete within an 8-hour overnight window. Budget: minimize cost.

**Decision path:** 500K documents x 820 tokens = 410M tokens per night. Time budget: 8 hours = 28,800 seconds. Required throughput: 410M / 28,800 = 14,236 tok/s. This exceeds single-GPU capacity by approximately 50x (single GPU at approximately 280 tok/s). Options: (a) multiple GPUs, (b) reduce model size, (c) optimize classification workload.

Classification is 99/1 input/output ratio. Compiled HF on Linux provides 24-60% prefill speedup (TR126). With compiled prefill: llama3.2-1b achieves approximately 5,000 tok/s prefill on a single GPU. At 820 tokens per document, this is approximately 6 documents/second. For 500K documents: approximately 83,333 seconds = 23.1 hours. Still too slow for one GPU.

With Ollama Q4_K_M (quantization reduces memory bandwidth demand): approximately 7,000 tok/s effective prefill. 500K documents in approximately 58,571 seconds = 16.3 hours. Still too slow.

**Revised approach:** Deploy 3 consumer GPUs with Ollama Q4_K_M. Each processes 167K documents. 167K x 820 / 7,000 = 19,523 seconds = 5.4 hours per GPU. Fits within the 8-hour window with margin.

**Cost analysis:**
- 3 x RTX 4080 at $0.046/hr x 5.4 hours = $0.75/night
- Monthly: $0.75 x 30 = $22.50/month for 15M documents
- Comparison: cloud API at $0.15/1M input tokens = 410M x 30 / 1M x $0.15 = $1,845/month
- Consumer hardware ROI: hardware cost recovered within 2 months

**Recommendation:** Deploy 3 consumer GPUs running Ollama Q4_K_M with llama3.2-1b. No vLLM needed (each GPU processes documents sequentially; no concurrent users per GPU). Quality gate: classification accuracy > 90% on a 500-sample validation set (run weekly). Q4_K_M is sufficient for classification (MMLU accuracy within -4.1pp of FP16). Use the `chimeraforge plan` tool to verify throughput predictions before hardware procurement.

---

*This document is supplemental to the main conclusive report (Technical_Report_Conclusive_123-133.md). For the canonical analysis, claim status table, and full appendix set (Appendix A through Appendix BH), consult the main report.*
