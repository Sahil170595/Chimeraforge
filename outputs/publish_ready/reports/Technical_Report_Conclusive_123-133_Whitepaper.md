# TR123-TR133 Decision Whitepaper
## Executive guidance for deployment leaders

Project: Banterhearts LLM Performance Research
Date: 2026-02-28
Version: 1.0
Audience: Decision makers, product leaders, ops leaders
Scope: TR123, TR124, TR125, TR126, TR127, TR128, TR129, TR130, TR131, TR132, TR133
Primary source: `PublishReady/reports/Technical_Report_Conclusive_123-133.md`

---

## Abstract

This whitepaper distills eleven technical reports (TR123-TR133) and approximately 70,000 measurements into deployment policy for local-first LLM inference on consumer hardware. The central question: given 70,000+ measurements on a consumer GPU, what model, quantization level, backend, and serving stack should we run -- and when does each choice break? Outcome: six shippable decisions that cover the full deployment space from single-agent chat to eight-agent orchestration, backed by artifact-level provenance and tested against their own falsification criteria.

---

## Boundary conditions (do not skip)

This guidance is valid only under the measured boundary:

- Fixed hardware class: NVIDIA RTX 4080 Laptop GPU, 12 GB VRAM, 432 GB/s bandwidth, AD104
- Same inference stack versions: PyTorch 2.x, CUDA 12.x, Ollama 0.6.x, vLLM 0.7.x, TGI
- Same measurement definitions: phase-split (prefill vs decode), end-to-end, kernel-level
- Models at or below 8B parameters (GPT-2 124M through LLaMA-3.1-8B)

If any of these change, re-run the core measurement matrix and re-validate artifacts before applying these decisions.

---

## Six decisions you can ship now

1. **Default backend (single-agent):** Ollama with Q4_K_M quantization. Highest throughput per dollar at negligible quality loss (within -4.1pp of FP16 on benchmark accuracy). Compile overhead, ONNX export complexity, and raw transformers startup costs are not justified for N=1.

2. **Default backend (multi-agent, N >= 4):** vLLM with FP16 weights. Continuous batching amortizes GPU memory bandwidth by 4.7-5.8x, yielding a 2.25x throughput advantage over Ollama at N=8. TGI provides equivalent amortization but lower absolute throughput.

3. **Compile policy:** torch.compile prefill only, on Linux, with Inductor+Triton backend. Never compile decode -- it crashes in all tested modes and provides no speedup even when it works (+2.2%, not significant). On Windows, torch.compile is a no-op (aot_eager fallback). Eager decode always.

4. **Quantization policy:** Q4_K_M is the universal default across all tested models (llama3.2-1b, qwen2.5-1.5b, phi-2, llama3.2-3b, llama3.1-8b). Use Q8_0 for quality-critical workloads requiring accuracy within 2pp of baseline. Never deploy Q2_K -- it produces near-random accuracy across all models. Q3_K_S is acceptable only for phi-2 and llama3.1-8b.

5. **Context budget:** Ollama for contexts exceeding 4K tokens on 12 GB VRAM. HuggingFace FP16 is limited to 4-8K tokens before VRAM spillover causes 25-105x latency cliffs. Monitor VRAM utilization; alert at 85%, hard-stop at 90%.

6. **Capacity planning tool:** Use `chimeraforge plan` for configuration search across the (model, quantization, backend, N-agents) space. Empirical lookup tables validated at R-squared >= 0.859 for throughput, 0.968 for VRAM. Do not use M/D/1 queueing theory -- it deviates up to 20.4x from reality.

---

## Decision matrix (one-glance policy)

| Condition | Backend | Quantization | Compile | Streaming |
| --- | --- | --- | --- | --- |
| N=1, decode-heavy | Ollama | Q4_K_M | N/A | Always on |
| N=1, prefill-heavy (Linux) | Compiled HF | FP16 | Prefill only | N/A |
| N=2-3, any workload | Ollama or vLLM (benchmark your mix) | Q4_K_M or FP16 | Per backend default | Always on |
| N >= 4, any workload | vLLM FP16 | FP16 | N/A (vLLM manages internally) | Always on |
| Quality-critical | phi-2 or llama3.1-8b | Q8_0 | No | Always on |
| VRAM-constrained (12 GB) | Ollama | Q4_K_M; Q3_K_S for phi-2 only | No | Always on |

---

## Key findings (decision-grade)

- **Quantization is the dominant lever.** Q4_K_M saves 30-67% cost versus FP16 while losing at most -4.1pp accuracy. The effect compounds across cost, VRAM budget, and concurrency ceiling simultaneously. Q2_K is universally unacceptable (all models >11pp loss; qwen2.5-1.5b collapses -40.6pp).

- **Backend choice does not affect quality.** TR124 tested 7 quality metrics across 5 models and 2 backends at temp=0; none showed statistically significant differences. The cheapest backend is the best backend for a given quality level.

- **The GPU, not the serving stack, is the scaling bottleneck.** TR131 overturned TR130: PyTorch Direct (no serving stack) degrades 86.4% at N=8, worse than Ollama's 82.1%. Memory bandwidth stress increases +74% at N=8, statistically confirmed with very high confidence (sole Holm-surviving test).

- **Continuous batching amortizes the bandwidth bottleneck.** TR132 proved the mechanism: 77-80% kernel count reduction and 79-83% bandwidth-per-token reduction at N=8. Amortization ratio is 4.7-5.8x (59-72% of the theoretical 8:1 maximum). vLLM and TGI use the identical mechanism.

- **VRAM spillover, not quadratic attention, is the practical bottleneck for long context.** TR127 observed 25-105x latency cliffs when KV-cache pushes VRAM past capacity. Below spillover, Ollama prefill scaling is clean and sub-linear (b = 0.083-0.158). GQA models sustain 3-11x longer contexts than MHA models.

- **NUM_PARALLEL is a no-op.** TR128 tested 30 pairwise comparisons; 0/30 significant (mean absolute change 4.0%). M/D/1 queueing theory deviates up to 20.4x from observed latency. Streaming adds zero overhead (0/9 tests significant).

- **Multi-agent throughput plateaus at N=2.** TR129 fits Amdahl's Law with serial fractions s = 0.39-0.54 (R-squared > 0.97). Per-agent throughput at N=8 is 17-20% of solo throughput. Fairness remains excellent (Jain's index >= 0.997).

- **Consumer hardware is 95.4% cheaper than cloud.** TR123 TCO at 1B tokens/month: $153/yr consumer versus $2,880/yr AWS on-demand (GPT-2/compile). Break-even for an RTX 4080 occurs at 0.3-2.7 months at 10M requests/month.

---

## Operational recommendations (policy statements)

### Backend selection

- **Policy:** Default to Ollama Q4_K_M for single-agent serving (N=1).
- **Policy:** Switch to vLLM FP16 at N >= 4 agents. N=2-3 is the crossover zone; benchmark your workload mix.
- **Policy:** Use TTFT as the tiebreaker in the crossover zone -- vLLM/TGI deliver 6-8x faster time-to-first-token (22-35ms versus 163-194ms).

### Quantization

- **Policy:** Q4_K_M is the universal default for all models tested.
- **Policy gate:** Use Q8_0 only when composite quality >= 0.60 is required and Q4_K_M falls below the threshold.
- **Policy ban:** Never deploy Q2_K in any quality-sensitive context. Q3_K_S is banned for llama3.2-1b, llama3.2-3b, and qwen2.5-1.5b (9.5-12.2pp loss).

### Compile

- **Policy:** Compile prefill only, on Linux, with Inductor+Triton. Speedup range: 1.3x (qwen2.5-3b) to 2.5x (gpt2-25m).
- **Policy gate:** Never compile decode -- 100% crash rate in all tested modes. Eager decode always.
- **Policy:** All Windows torch.compile results are invalid (aot_eager fallback). Do not trust them.

### Context budget

- **Policy:** VRAM budget = model_weights + KV_cost_per_token x context_length. GQA models get 3-11x more context per GB.
- **Policy:** Use Ollama for contexts exceeding 4K tokens on 12 GB VRAM. HF FP16 collapses (95% throughput loss) at the spillover boundary.
- **Policy gate:** Alert at 85% VRAM utilization; hard-stop at 90% to avoid 25-105x latency cliffs.

### Capacity planning

- **Policy:** Use `chimeraforge plan` for all configuration search and sizing decisions. Runtime < 1 second, zero GPU required.
- **Policy ban:** Do not use M/D/1 queueing theory for latency prediction (20.4x deviation from reality).
- **Policy:** Cap utilization at 70% of measured peak throughput to absorb burst traffic (TTFT amplifies 29.9x at saturation).

---

## Economic impact

### Cost levers (ranked by magnitude)

1. **Infrastructure choice:** Consumer GPU versus cloud on-demand saves 95.4%. This is the single largest cost lever and dwarfs all other optimizations combined.
2. **Quantization:** Q4_K_M saves 30-67% versus FP16. Cost range spans 10x across the quantization-model matrix ($0.020 to $0.198 per 1M tokens).
3. **Serving stack at scale:** vLLM delivers 2.25x throughput at N=8, halving the per-request cost for multi-agent workloads.
4. **Compile (prefill-heavy, Linux only):** 1.3-2.5x prefill speedup for small models. Diminishes at larger sizes.

### Dollar figures

- Best cost: $0.013/1M tokens (GPT-2/compile, chat blend)
- Best cost above 1B parameters: $0.047/1M tokens (LLaMA-3.2-1B/compile)
- Consumer TCO at 1B tokens/month: $153/yr (GPT-2/compile) to $561/yr (LLaMA-3.2-1B/compile)
- AWS TCO at 1B tokens/month: $2,880/yr (GPT-2) to $8,584/yr (LLaMA-3.2-1B); consumer hardware saves 95.4%
- Break-even: RTX 4080 ($1,200) pays for itself in 0.3 months at 10M requests/month (llama3.2-1b/Ollama), 2.7 months at 1M requests/month

### Production throughput ceiling

- Single-agent peak: 1.17 req/s (Ollama, llama3.2-1b)
- Multi-agent peak: 559 tok/s total (vLLM, llama3.2-1b, N=8)
- Per-agent at N=8: 17-20% of solo throughput (Ollama); 56% efficiency retained (vLLM)

---

## Implementation plan (30-day view)

**Days 1-7: reproduce and validate**

- Re-run the core scenario matrix on your hardware and workload mix.
- Validate artifacts against the chain-of-custody (Appendix B of the conclusive report).
- Capture full manifests: GPU model, driver, CUDA, PyTorch, Ollama/vLLM versions, OS.

**Days 8-14: translate into your planning numbers**

- Recompute $/token and capacity with your electricity rate and hardware amortization schedule.
- Run `chimeraforge plan` with your specific (model, quantization, N-agents, SLA, quality floor, budget ceiling) inputs.
- If compiling on Linux: verify Triton kernel generation (check `torch._inductor` logs for generated kernels, not aot_eager fallback).

**Days 15-30: enforce policies**

- Ship backend routing rules: Ollama for N <= 2, vLLM for N >= 4. Benchmark your workload at N=3.
- Deploy Q4_K_M as the default quantization; require explicit approval for Q8_0 or Q3_K_S exceptions.
- Set VRAM monitoring with 85%/90% alert/hard-stop thresholds.
- Cap utilization at 70% of measured peak; set TTFT alarms at your SLA boundary.
- Add re-run-required triggers to change management for any hardware, driver, or stack version change.

---

## Risks, limitations, invalidation triggers

### Limitations

- Single hardware baseline (RTX 4080 Laptop, 12 GB VRAM). Not portable across GPU classes without re-run.
- Models tested at or below 8B parameters. Larger models may exhibit different scaling, quantization tolerance, and VRAM behavior.
- $/token values are planning proxies (shadow prices), not exact TCO. Apply your own rates.
- Quality metrics are automated (BERTScore, ROUGE-L, MMLU, ARC). No human evaluation performed.
- Formal equivalence testing could not confirm with full statistical power at a tight +/-3pp margin, so quality tiers are based on observed accuracy differences rather than formal equivalence proof.
- Consumer WDDM driver blocks direct kernel-level metrics (ncu null); bandwidth attribution relies on back-of-envelope calculation.
- Scaling model is the weakest predictor (R-squared = 0.647); Amdahl captures the trend but misses backend interaction effects.

### What invalidates this guidance

- GPU, driver, or CUDA version change without re-run
- PyTorch major version upgrade (kernel paths, compile behavior, CUDA graph handling)
- Ollama or vLLM version upgrade (serving stack behavior, scheduler, quantization engine)
- Workload mix shift (prompt/decode ratio, model families, context lengths) without revalidation
- Moving to multi-GPU without extending the measurement matrix

---

## Evidence anchors (audit-ready)

| Decision | Artifact | Validation |
| --- | --- | --- |
| KV-cached decode cheaper than uncached | `results/eval/tr123/processed/cost_summary.json` | Phase-split $/token tables, 30/30 KV formula matches |
| Backend quality equivalence | `results/eval/tr124_phase1/anova_results.json` | 7-metric ANOVA + Holm-Bonferroni |
| Q4_K_M preserves quality | `results/eval/tr125/phase2_analysis.json` | Wilson CIs + 4-tier classification |
| Compile prefill speedup on Linux | `results/eval/tr126/phase2_compile_analysis.json` | Welch's t + Cohen's d = -0.59 |
| VRAM spillover dominates context scaling | `results/eval/tr127/context_scaling_analysis.json` | Two-regime fit + cliff detection |
| NUM_PARALLEL is a no-op | `results/eval/tr128/phase2_concurrency.json` | 30 pairwise tests + Holm correction |
| Amdahl serial fractions s = 0.39-0.54 | `results/eval/tr129/scaling_analysis.json` | Amdahl fit R-squared > 0.97 |
| GPU bandwidth is the bottleneck | `results/eval/tr131/profiling_analysis.json` | PyTorch Direct control + Mann-Whitney |
| Continuous batching amortizes bandwidth | `results/eval/tr132/kernel_analysis.json` | Kernel count + Holm 8/8 significant |
| Lookup tables meet all validation targets | `results/eval/tr133/validation_results.json` | 4/4 targets + 10/10 spot checks |

---

## References

- Conclusive report: `PublishReady/reports/Technical_Report_Conclusive_123-133.md`
- TR123: `PublishReady/reports/Technical_Report_123.md` (KV-Cache Production Economics)
- TR124: `PublishReady/reports/Technical_Report_124.md` (Quality & Accuracy Baseline)
- TR125: `PublishReady/reports/Technical_Report_125.md` (Quantization Decision Matrix)
- TR126: `PublishReady/reports/Technical_Report_126.md` (Docker/Linux + Triton Validation)
- TR127: `PublishReady/reports/Technical_Report_127.md` (Long-Context Performance Characterization)
- TR128: `PublishReady/reports/Technical_Report_128.md` (Production Workload Characterization)
- TR129: `PublishReady/reports/Technical_Report_129.md` (N-Agent Scaling Laws)
- TR130: `PublishReady/reports/Technical_Report_130.md` (Serving Stack Benchmarking)
- TR131: `PublishReady/reports/Technical_Report_131.md` (GPU Kernel Profiling -- Root-Cause Analysis)
- TR132: `PublishReady/reports/Technical_Report_132.md` (In-Container GPU Kernel Profiling)
- TR133: `PublishReady/reports/Technical_Report_133.md` (Predictive Capacity Planner)

---

## Optional upgrades (board-ready polish)

- Add a 1-page Decision Card at the front: the six-row matrix + boundary conditions + three invalidation triggers.
- Add a single architecture diagram: request arrives, classify (N, workload shape), route to backend, apply quant/compile policy, monitor VRAM/TTFT, audit.
- Add a Change Control clause: any hardware/stack upgrade triggers re-run of the core scenario matrix and re-validation of the chimeraforge lookup tables.
