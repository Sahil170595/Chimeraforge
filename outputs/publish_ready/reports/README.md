# Banterhearts Technical Reports
## LLM Inference Research & Optimization — 70,000+ Measurements, 26 Technical Reports

This directory contains the complete research program documenting LLM inference performance, optimization, multi-agent orchestration, cross-language analysis, and deployment policy — all on a single NVIDIA RTX 4080 Laptop GPU (12 GB VRAM).

---

## Research Program Overview

### Phase 1: Foundation (TR108-TR122)
**15 technical reports. ~8,000 benchmark runs.**

Single-agent and multi-agent performance analysis, Rust vs Python cross-language evaluation, ONNX/TensorRT backend exploration, cost/energy analysis, the compile paradox root-cause audit, model scaling study, and resource profiling.

### Phase 2: Deployment Framework (TR123-TR133)
**11 technical reports. ~62,000+ measurements.**

KV-cache economics, quality baselines, quantization decision matrix, Linux/Triton compile validation, long-context characterization, production workload analysis, N-agent scaling laws, serving stack comparison, GPU kernel profiling (host + in-container), and a predictive capacity planner shipped as the `chimeraforge plan` CLI.

### Conclusive Reports
**9 synthesis documents spanning both phases.**

Three dissertation-style conclusive reports (TR108-TR116, TR117-TR122, TR123-TR133), three extended appendices volumes, and three executive whitepapers — providing audit-ready decision guidance with full artifact provenance.

---

## Technical Reports Index

### Phase 1: Foundation (TR108-TR122)

| Report | Title | Status | Key Finding |
|--------|-------|--------|-------------|
| **TR108** | Single-Agent LLM Performance Analysis | Complete | Optimal configs for single-agent inference |
| **TR109** | Agent Workflow Optimization | Complete | GPU=60, CTX=512, TEMP=0.8 optimal for workflows |
| **TR110** | Concurrent Multi-Agent Performance (Python) | Complete | 99.25% parallel efficiency achieved |
| **TR111_v2** | Rust Single-Agent Performance | Complete | 114.54 tok/s baseline, 15.2% faster than Python |
| **TR112_v2** | Rust vs Python Comparison | Complete | Rust: +15.2% throughput, -58% TTFT, -67% memory |
| **TR113** | Rust Multi-Agent (Single Ollama) | Complete | 82.2% peak; server contention identified |
| **TR114_v2** | Rust Multi-Agent (Dual Ollama) | Complete | 98.281% mean efficiency, 0.74% contention |
| **TR115_v2** | Rust Runtime Optimization | Complete | Tokio-default recommended (98.72% mean, 1.21pp sigma) |
| **TR116** | Cross-Model Multi-Agent Benchmarks | Complete | Rust + Gemma 3 is king (99.2%); Qwen shows imbalance |
| **TR117** | Cross-Backend Inference Benchmark | Complete | GPU-compile best mean; ONNX/TRT failures documented |
| **TR117_multi** | Multi-Agent Root Cause Analysis | Complete | Python event loop saturation (5.33ms mean lag) |
| **TR118_v2.2** | ONNX Runtime + TensorRT Deep Dive | Complete | TensorRT-fp16 best prefill (2.48ms, -87% vs baseline) |
| **TR119** | Cost & Energy Analysis | Complete | onnxruntime-gpu best cost ($0.1279/1M tok on-demand) |
| **TR120** | The "Compile Paradox" Root-Cause Audit | Complete | TR117 compile label misattributed; shape stability critical |
| **TR121v1** | Model Scaling Study | Complete | Scaling pipeline from 5M to 20B parameters established |
| **TR122** | Resource Profiling Deep Dive | Complete | Baseline power (20.71W), poller scheduling, thermal equilibrium |

### Phase 2: Deployment Framework (TR123-TR133)

| Report | Title | Status | Key Finding |
|--------|-------|--------|-------------|
| **TR123** | KV-Cache Production Economics | Complete | Best cost $0.013/1M tokens; cached decode 2-8x cheaper |
| **TR124** | Quality & Accuracy Baseline | Complete | Backend choice does not affect quality (0/7 ANOVA significant) |
| **TR125** | Quantization Decision Matrix | Complete | Q4_K_M universal sweet spot (-4.1pp max); Q2_K universally unacceptable |
| **TR126** | Docker/Linux + Triton Validation | Complete | Compile paradox resolved: 24-60% prefill speedup on Linux; crashes decode |
| **TR127** | Long-Context Characterization | Complete | VRAM spillover (25-105x cliffs), not quadratic attention, is the bottleneck |
| **TR128** | Production Workloads | Complete | NUM_PARALLEL is a no-op (0/30 significant); M/D/1 deviates 20.4x |
| **TR129** | N-Agent Scaling Laws | Complete | Amdahl s=0.39-0.54; throughput plateaus at N=2 |
| **TR130** | Serving Stack Comparison | Complete | vLLM 2.25x advantage at N=8 via continuous batching |
| **TR131** | GPU Kernel Profiling | Complete | Overturns TR130: GPU memory bandwidth, not serving stack, is the bottleneck |
| **TR132** | In-Container GPU Profiling | Complete | Continuous batching amortizes kernels 77-80%, bandwidth 79-83% |
| **TR133** | Predictive Capacity Planner | Complete | 4/4 validation targets met; `chimeraforge plan` CLI shipped |

### Conclusive Reports

| Report | Scope | Size |
|--------|-------|------|
| **Conclusive 108-116** | Phase 1 Synthesis (Python→Rust Migration) | 2,826 lines |
| **Conclusive 108-116 Extended Appendices** | Phase 1 Deep-Dive Appendices (108-116) | 1,171 lines |
| **Conclusive 108-116 Whitepaper** | Phase 1 Executive Guidance (108-116) | 214 lines |
| **Conclusive 117-122** | Phase 1 Synthesis (Benchmarking→Decision-Grade) | 208KB |
| **Conclusive 117-122 Extended Appendices** | Phase 1 Deep-Dive Appendices | 89KB |
| **Conclusive 117-122 Whitepaper** | Phase 1 Executive Guidance | 8KB |
| **Conclusive 123-133** | Phase 2 Synthesis | 433KB, 3,327 lines, 60 appendices |
| **Conclusive 123-133 Extended Appendices** | Phase 2 Deep-Dive Appendices | 62KB |
| **Conclusive 123-133 Whitepaper** | Phase 2 Executive Guidance | 15KB |

### Historical Reports (Superseded)

| Report | Superseded By | Reason |
|--------|---------------|--------|
| TR111 | TR111_v2 | Micro-benchmark replaced with full workflow |
| TR112 | TR112_v2 | Flawed comparison methodology |
| TR114 | TR114_v2 | Incorrect statistics (97.5% -> 98.281%) |
| TR115 | TR115_v2 | Incomplete data analysis (30 -> 150 runs) |
| TR118 | TR118_v2.2 | Multiple revisions; v2.2 is latest |
| TR119v1 | TR119 | Early draft superseded |
| TR121 | TR121v1 | Early draft superseded |

---

## Phase 2 Deployment Decisions

Six shippable decisions backed by ~62,000 measurements:

1. **Single-agent:** Ollama Q4_K_M (highest throughput per dollar)
2. **Multi-agent (N>=4):** vLLM FP16 (2.25x advantage from continuous batching)
3. **Compile:** Prefill only, Linux only, Inductor+Triton; never compile decode
4. **Quantization:** Q4_K_M default; Q8_0 for quality-critical; never Q2_K
5. **Context budget:** Ollama for >4K tokens on 12 GB; HF FP16 spills at 8-16K
6. **Capacity planning:** `chimeraforge plan` (empirical lookup tables, R-squared >= 0.859)

### Decision Matrix

| Condition | Backend | Quantization | Compile | Streaming |
|-----------|---------|-------------|---------|-----------|
| N=1, decode-heavy | Ollama | Q4_K_M | N/A | Always on |
| N=1, prefill-heavy (Linux) | Compiled HF | FP16 | Prefill only | N/A |
| N=2-3, any workload | Ollama or vLLM (benchmark your mix) | Q4_K_M or FP16 | Per backend default | Always on |
| N>=4, any workload | vLLM FP16 | FP16 | N/A (vLLM manages internally) | Always on |
| Quality-critical | phi-2 or llama3.1-8b | Q8_0 | No | Always on |
| VRAM-constrained (12 GB) | Ollama | Q4_K_M; Q3_K_S for phi-2 only | No | Always on |

---

## Phase 1 Key Findings

### Single-Agent (TR111_v2, TR112_v2)

| Metric | Python | Rust | Rust Advantage |
|--------|--------|------|----------------|
| Throughput | 99.34 tok/s | 114.54 tok/s | +15.2% |
| TTFT (cold) | 1437 ms | 603 ms | -58.0% |
| Memory | ~250 MB | ~75 MB | -67% |
| Startup | 1.5s | 0.2s | -83% |
| CV (throughput) | 4.8% | 2.6% | -46% (more consistent) |

### Multi-Agent (TR110, TR114_v2)

| Metric | Python (TR110) | Rust (TR114_v2) | Rust Advantage |
|--------|---------------|-----------------|----------------|
| Peak Config Avg | 99.25% | 99.396% | +0.15pp |
| Peak Single Run | 99.25% | 99.992% | +0.74pp |
| Mean Efficiency | 95.8% | 98.281% | +2.48pp |
| Contention Rate | 10-15% | 0.74% | -10-14pp |

### Runtime Optimization (TR115_v2)

| Runtime | Mean (%) | StdDev (pp) | Recommendation |
|---------|----------|-------------|----------------|
| Tokio-default | 98.72 | 1.21 | Production |
| Smol-1KB | 98.61 | 1.32 | Small binary alternative |
| Tokio-localset | 97.95 | 4.03 | Unstable |
| Smol | 97.72 | 4.87 | Avoid |
| Async-std | 50.00 | 0.00 | Unusable |

---

## Phase 2 Key Findings

- **Quantization is the dominant lever.** Q4_K_M saves 30-67% cost versus FP16 while losing at most -4.1pp accuracy. Q2_K is universally unacceptable (all models >11pp loss; qwen2.5-1.5b collapses -40.6pp).

- **Backend choice does not affect quality.** 7 quality metrics across 5 models and 2 backends at temp=0; none showed statistically significant differences (TR124).

- **The GPU, not the serving stack, is the scaling bottleneck.** PyTorch Direct (no serving stack) degrades 86.4% at N=8, worse than Ollama's 82.1%. Memory bandwidth stress increases +74% at N=8 (TR131).

- **Continuous batching amortizes the bandwidth bottleneck.** 77-80% kernel count reduction and 79-83% bandwidth-per-token reduction at N=8. Amortization ratio is 4.7-5.8x (TR132).

- **VRAM spillover, not quadratic attention, is the practical long-context bottleneck.** 25-105x latency cliffs when KV-cache pushes VRAM past capacity. Below spillover, Ollama prefill scaling is sub-linear (b = 0.083-0.158). GQA models sustain 3-11x longer contexts than MHA models (TR127).

- **NUM_PARALLEL is a no-op.** 0/30 pairwise comparisons significant (mean absolute change 4.0%). M/D/1 queueing theory deviates up to 20.4x from observed latency (TR128).

- **Multi-agent throughput plateaus at N=2.** Amdahl's Law with serial fractions s = 0.39-0.54 (R-squared > 0.97). Per-agent throughput at N=8 is 17-20% of solo throughput (TR129).

- **Consumer hardware is 95.4% cheaper than cloud.** TCO at 1B tokens/month: $153/yr consumer versus $2,880/yr AWS on-demand. Break-even for an RTX 4080 occurs at 0.3-2.7 months at 10M requests/month (TR123).

---

## Report Details

### Phase 1

#### TR108: Single-Agent LLM Performance Analysis
**File:** `Technical_Report_108.md`
- Models: gemma3:latest, llama3.1:8b-instruct variants
- Hardware: NVIDIA RTX 4080 (12GB VRAM), i9-13980HX
- Test Matrix: 150+ benchmark runs across parameter sweeps

#### TR109: Agent Workflow Optimization
**File:** `Technical_Report_109.md`
- Optimal Config: GPU=60, CTX=512, TEMP=0.8 for agent workflows
- Methodology: Process isolation, forced cold starts, statistical validation

#### TR110: Concurrent Multi-Agent Performance (Python)
**File:** `Technical_Report_110.md`
- Test Matrix: 30 configurations x 5 runs = 150 benchmark runs
- Key Finding: 99.25% parallel efficiency with homogeneous Chimera agents

#### TR111_v2: Rust Single-Agent Performance
**File:** `Technical_Report_111_v2.md`
- Test Matrix: 19 configurations x 3 runs = 57 benchmark runs
- Baseline: 114.54 tok/s (15.2% faster than Python)
- Supersedes: TR111 (micro-benchmark)

#### TR112_v2: Rust vs Python Comparison
**File:** `Technical_Report_112_v2.md`
- Test Matrix: 37 configurations (19 Rust + 18 Python), 111 total runs
- Rust: +15.2% throughput, -58% TTFT, -67% memory, -83% startup
- Supersedes: TR112

#### TR113: Rust Multi-Agent (Single Ollama)
**File:** `Technical_Report_113.md`
- 82.2% peak efficiency, 63% contention rate
- Critical Discovery: Server-level serialization bottleneck; dual Ollama required

#### TR114_v2: Rust Multi-Agent (Dual Ollama)
**File:** `Technical_Report_114_v2.md`
- Test Matrix: 27 configurations x 5 runs = 135 benchmark runs
- Peak single run: 99.992%; Mean: 98.281% (+2.48pp vs Python)
- Supersedes: TR114

#### TR115_v2: Rust Runtime Optimization
**File:** `Technical_Report_115_v2.md`
- Test Matrix: 5 runtimes x 6 configs x 5 runs = 150 benchmark runs
- Recommendation: Standard Tokio — no custom config needed
- Supersedes: TR115

#### TR116: Cross-Model Multi-Agent Benchmarks
**File:** `Technical_Report_116.md`
- Test Matrix: 3 models x 2 runtimes x 2 scenarios x 5 runs = 60 runs
- Rust dominates across all models (+12-17pp efficiency vs Python)
- Gemma 3 is the scaling king (99.2% efficiency in Rust)

#### TR117: Cross-Backend Inference Benchmark
**File:** `Technical_Report_117.md`
- Test Matrix: 3,017 runs, 2,471 successful (82%)
- GPU-compile wins on mean latency (389ms); plain GPU wins on median (323ms)

#### TR117_multi_agent: Multi-Agent Root Cause Analysis
**File:** `Technical_Report_117_multi_agent.md`
- Python event loop saturation: Mean lag 5.33ms, p99 12.13ms, max 15.22ms
- For >100 tok/s multi-agent systems, Rust is mandatory

#### TR118_v2.2: ONNX Runtime + TensorRT Deep Dive
**File:** `Technical_Report_118_v2.2.md`
- Test Matrix: 360 run-level records across prefill and generate modes
- Best prefill: TensorRT-fp16 (2.48ms, -87% vs baseline)
- Supersedes: TR118, TR118_v2.1

#### TR119: Cost & Energy Analysis
**File:** `Technical_Report_119.md`
- Test Matrix: 5 backends x 5 scenarios x 7 reps x 2 modes = 350 runs
- Best cost: onnxruntime-gpu at $0.1279/1M tokens (on-demand)
- Lowest carbon: ~1.0 gCO2e/1M tokens

#### TR120: The "Compile Paradox" Root-Cause Audit
**File:** `Technical_Report_120.md`
- TR117's "compile paradox" is real but misattributed (label-only, no actual torch.compile)
- Shape stability fix: Padding/bucketing collapses compiled tail

#### TR121v1: Model Scaling Study
**File:** `Technical_Report_121v1.md`
- Scaling pipeline from 5M to 20B parameters (HF + Ollama)
- Three distinct regimes identified (small GPU, CPU, large-model serving)

#### TR122: Resource Profiling Deep Dive
**File:** `Technical_Report_122.md`
- Baseline power: RTX 4080 Laptop GPU idles at 20.71W (sigma=9.97W)
- V2 strict poller scheduling achieves 100ms grid adherence
- Thermal equilibrium: Small models reach equilibrium at 48C

### Phase 2

#### TR123: KV-Cache Production Economics
**File:** `Technical_Report_123.md`
- 5 models (124M-3.2B), 5 backends, 5 cost blends
- Best cost: $0.013/1M tokens (GPT-2/compile)
- Consumer vs cloud: 95.4% savings ($153/yr vs $2,880/yr at 1B tokens/month)

#### TR124: Quality & Accuracy Baseline
**File:** `Technical_Report_124.md`
- 5 models x 2 backends, temp=0, 7 quality metrics
- Backend choice does not affect quality: 0/7 ANOVA significant

#### TR125: Quantization Decision Matrix
**File:** `Technical_Report_125.md`
- 5 models x 7 quantization levels (Q2_K through FP16)
- Q4_K_M: universal sweet spot (-4.1pp max accuracy loss)
- Q2_K: universally unacceptable (>11pp loss all models; qwen2.5-1.5b -40.6pp)

#### TR126: Docker/Linux + Triton Validation
**File:** `Technical_Report_126.md`
- Compile paradox resolved: 24-60% prefill speedup on Linux with Inductor+Triton
- Decode compile crashes 100% of the time in all tested modes
- PyTorch bug discovered and reported upstream (pytorch/pytorch#175557, PR #175562)

#### TR127: Long-Context Performance Characterization
**File:** `Technical_Report_127.md`
- VRAM spillover causes 25-105x latency cliffs (not quadratic attention)
- Ollama prefill scaling is sub-linear below spillover (b = 0.083-0.158)
- GQA models sustain 3-11x longer contexts than MHA models

#### TR128: Production Workload Characterization
**File:** `Technical_Report_128.md`
- NUM_PARALLEL is a no-op: 0/30 pairwise comparisons significant
- M/D/1 queueing theory deviates up to 20.4x from reality
- Streaming adds zero overhead (0/9 tests significant)

#### TR129: N-Agent Scaling Laws
**File:** `Technical_Report_129.md`
- Amdahl's Law fit: serial fractions s = 0.39-0.54 (R-squared > 0.97)
- Per-agent throughput at N=8: 17-20% of solo throughput
- Fairness: Jain's index >= 0.997

#### TR130: Serving Stack Comparison
**File:** `Technical_Report_130.md`
- vLLM 2.25x throughput advantage at N=8 via continuous batching
- TGI provides equivalent amortization but lower absolute throughput
- vLLM/TGI deliver 6-8x faster TTFT (22-35ms vs 163-194ms)

#### TR131: GPU Kernel Profiling
**File:** `Technical_Report_131.md`
- Overturns TR130: GPU memory bandwidth, not serving stack, is the bottleneck
- PyTorch Direct degrades 86.4% at N=8 (worse than Ollama's 82.1%)
- Memory bandwidth stress increases +74% at N=8 (Holm-surviving test)

#### TR132: In-Container GPU Profiling
**File:** `Technical_Report_132.md`
- Continuous batching mechanism quantified: 77-80% kernel count reduction
- Bandwidth-per-token reduction: 79-83% at N=8
- Amortization ratio: 4.7-5.8x (59-72% of theoretical 8:1 maximum)

#### TR133: Predictive Capacity Planner
**File:** `Technical_Report_133.md`
- 19,676 empirical records feeding lookup tables
- 4-gate pipeline: VRAM feasibility, quality gate, latency gate, budget gate
- 4/4 validation targets met: VRAM R-squared=0.968, throughput R-squared=0.859
- `chimeraforge plan` CLI shipped

---

## Conclusive Report Details

### Phase 1a Synthesis: Technical_Report_Conclusive_108-116
**File:** `Technical_Report_Conclusive_108-116.md` (2,826 lines)
- Covers TR108 through TR116: Python-to-Rust migration, multi-agent architecture, runtime selection, cross-model validation
- Six shippable decisions: Rust for production, dual Ollama mandatory, Tokio-default runtime, Gemma 3 for scaling, Python ceiling at ~86%, config transfer failure
- Extended Appendices: `Technical_Report_Conclusive_108-116_Extended_Appendices.md` (1,171 lines)
- Executive Whitepaper: `Technical_Report_Conclusive_108-116_Whitepaper.md` (214 lines)

### Phase 1b Synthesis: Technical_Report_Conclusive_117-122
**File:** `Technical_Report_Conclusive_117-122.md` (208KB)
- Covers TR117 through TR122
- Extended Appendices: `Technical_Report_Conclusive_117-122_Extended_Appendices.md` (89KB)
- Executive Whitepaper: `Technical_Report_Conclusive_117-122_Whitepaper.md` (8KB)

### Phase 2 Synthesis: Technical_Report_Conclusive_123-133
**File:** `Technical_Report_Conclusive_123-133.md` (433KB, 3,327 lines, 60 appendices)
- Covers TR123 through TR133
- Three stable conclusions, six shippable decisions, full artifact provenance
- Extended Appendices: `Technical_Report_Conclusive_123-133_Extended_Appendices.md` (62KB)
- Executive Whitepaper: `Technical_Report_Conclusive_123-133_Whitepaper.md` (15KB)

---

## Economic Impact

### Phase 1 (TR119)
- Best cost: onnxruntime-gpu at $0.1279/1M tokens (on-demand)
- Spot pricing: $0.03868/1M tokens (69.8% savings)
- Lowest carbon: ~1.0 gCO2e/1M tokens

### Phase 2 (TR123)
- Best cost: $0.013/1M tokens (GPT-2/compile, chat blend)
- Best cost above 1B params: $0.047/1M tokens (LLaMA-3.2-1B/compile)
- Consumer TCO at 1B tokens/month: $153/yr to $561/yr
- AWS TCO at 1B tokens/month: $2,880/yr to $8,584/yr
- Consumer hardware saves 95.4% versus cloud on-demand
- Break-even: RTX 4080 ($1,200) pays for itself in 0.3-2.7 months at 10M requests/month

### Production Throughput Ceiling (Phase 2)
- Single-agent peak: 1.17 req/s (Ollama, llama3.2-1b)
- Multi-agent peak: 559 tok/s total (vLLM, llama3.2-1b, N=8)
- Per-agent at N=8: 17-20% of solo (Ollama); 56% efficiency retained (vLLM)

---

## Repository Structure

```
outputs/publish_ready/reports/
├── README.md (this file)
│
├── Phase 1: Foundation (TR108-TR122)
│   ├── Technical_Report_108.md
│   ├── Technical_Report_109.md
│   ├── Technical_Report_110.md
│   ├── Technical_Report_111_v2.md
│   ├── Technical_Report_112_v2.md
│   ├── Technical_Report_113.md
│   ├── Technical_Report_114_v2.md
│   ├── Technical_Report_115_v2.md
│   ├── Technical_Report_116.md
│   ├── Technical_Report_117.md
│   ├── Technical_Report_117_multi_agent.md
│   ├── Technical_Report_118_v2.2.md
│   ├── Technical_Report_119.md
│   ├── Technical_Report_120.md
│   ├── Technical_Report_121v1.md
│   └── Technical_Report_122.md
│
├── Phase 2: Deployment Framework (TR123-TR133)
│   ├── Technical_Report_123.md
│   ├── Technical_Report_124.md
│   ├── Technical_Report_125.md
│   ├── Technical_Report_126.md
│   ├── Technical_Report_127.md
│   ├── Technical_Report_128.md
│   ├── Technical_Report_129.md
│   ├── Technical_Report_130.md
│   ├── Technical_Report_131.md
│   ├── Technical_Report_132.md
│   └── Technical_Report_133.md
│
├── Conclusive Reports
│   ├── Technical_Report_Conclusive_108-116.md
│   ├── Technical_Report_Conclusive_108-116_Extended_Appendices.md
│   ├── Technical_Report_Conclusive_108-116_Whitepaper.md
│   ├── Technical_Report_Conclusive_117-122.md
│   ├── Technical_Report_Conclusive_117-122_Extended_Appendices.md
│   ├── Technical_Report_Conclusive_117-122_Whitepaper.md
│   ├── Technical_Report_Conclusive_123-133.md
│   ├── Technical_Report_Conclusive_123-133_Extended_Appendices.md
│   └── Technical_Report_Conclusive_123-133_Whitepaper.md
│
├── Historical (Superseded)
│   ├── Technical_Report_111.md
│   ├── Technical_Report_112.md
│   ├── Technical_Report_114.md
│   ├── Technical_Report_115.md
│   ├── Technical_Report_118.md (+ v2.1)
│   ├── Technical_Report_119v1.md
│   └── Technical_Report_121.md
│
├── Legacy (moved to legacy/)
│   ├── Technical_Report_118.md
│   └── Technical_Report_118_v2.1.md
│
└── Model Benchmarks
    └── gemma3/
        └── Gemma3_Benchmark_Report.md
```

---

## Hardware Baseline

All measurements on a single fixed baseline:
- **GPU:** NVIDIA RTX 4080 Laptop GPU (12 GB GDDR6, 256-bit, 432 GB/s, AD104)
- **CPU:** Intel Core i9-13980HX (24 cores, 32 threads)
- **RAM:** 64 GB DDR5-4800
- **OS:** Windows 11 + WSL2/Ubuntu 22.04 for Docker/Linux workloads

---

## Research Questions Answered

### Phase 1

1. **Is Rust faster than Python for LLM inference?**
   Yes — 15.2% faster throughput, 58% faster TTFT, 67% less memory (TR112_v2)

2. **Does Rust's single-agent advantage carry over to multi-agent?**
   Yes — Rust exceeds Python by +2.48pp mean efficiency (TR114_v2)

3. **Which Rust async runtime is optimal?**
   Tokio-default — 98.72% mean, 1.21pp sigma (TR115_v2)

4. **Is dual Ollama architecture necessary?**
   Yes — reduces contention from 63% to 0.74% (TR113 -> TR114_v2)

### Phase 2

5. **Does backend choice affect quality?**
   No — 0/7 ANOVA significant at temp=0 across 5 models (TR124)

6. **What quantization level should you default to?**
   Q4_K_M — universal sweet spot, at most -4.1pp accuracy loss, 30-67% cost savings (TR125)

7. **Does torch.compile help?**
   Prefill only, Linux only, 24-60% speedup; decode crashes 100% of the time (TR126)

8. **What limits long-context performance?**
   VRAM spillover, not quadratic attention — 25-105x latency cliffs at capacity (TR127)

9. **Is the serving stack or the GPU the bottleneck at scale?**
   The GPU — memory bandwidth, not serving stack logic, is the constraint. Continuous batching amortizes it 4.7-5.8x (TR131, TR132)

10. **Can you predict deployment configurations without running benchmarks?**
    Yes — `chimeraforge plan` uses empirical lookup tables with VRAM R-squared=0.968, throughput R-squared=0.859 (TR133)

---

## Reading Guide

### For Researchers
1. Start with **TR108-TR110** (Python baselines)
2. Study **TR112_v2** and **TR114_v2** (Rust vs Python)
3. Review Phase 2 starting with **TR123** (economics) through **TR133** (capacity planning)
4. Read the **Conclusive Reports** for synthesis and cross-TR analysis

### For Engineers
1. **Single-agent deployment:** TR112_v2 (language choice) + TR125 (quantization)
2. **Multi-agent deployment:** TR129 (scaling laws) + TR130 (serving stacks)
3. **Capacity planning:** TR133 + `chimeraforge plan` CLI
4. **Compilation:** TR126 (what works, what crashes)

### For Decision Makers
1. **Rust vs Python Decision:** `Technical_Report_Conclusive_108-116_Whitepaper.md` (language, architecture, runtime, model)
2. **Phase 2 Whitepaper:** `Technical_Report_Conclusive_123-133_Whitepaper.md` (15KB, 6 decisions)
3. **Decision Matrix:** See Phase 2 Deployment Decisions table above
4. **Cost Analysis:** TR123 ($/token) + TR119 (energy/carbon)

---

**Last Updated:** 2026-02-28
**Total Reports:** 41 files (26 production-ready TRs + 9 conclusive/whitepaper documents + 6 historical/superseded)
**Total Measurements:** 70,000+ across all reports
