# Banterhearts Technical Reports
## Comprehensive LLM Performance Research & Cross-Language Analysis

This directory contains the complete research journey documenting LLM performance analysis, optimization strategies, multi-agent orchestration, and cross-language (Rust vs Python) performance evaluation in the Chimera Heart project.

---

## 📊 Research Journey Overview

### Phase 1: Single-Agent Foundation (TR108-TR109)
**Objective:** Establish baseline LLM performance and agent workflow optimization

- **TR108:** Single-agent LLM performance analysis (Python)
- **TR109:** Agent workflow optimization (Python)

### Phase 2: Multi-Agent Python Baseline (TR110)
**Objective:** Establish Python multi-agent performance baseline

- **TR110:** Concurrent multi-agent performance analysis (Python)

### Phase 3: Rust Single-Agent Implementation (TR111)
**Objective:** Port Python agents to Rust and validate single-agent performance

- **TR111:** Initial Rust agent (micro-benchmark) - **SUPERSEDED**
- **TR111_v2:** ✅ **Production-grade Rust single-agent** (full workflow parity)

### Phase 4: Cross-Language Single-Agent Comparison (TR112)
**Objective:** Direct Rust vs Python single-agent performance comparison

- **TR112:** Initial comparison (flawed - used micro-benchmark) - **SUPERSEDED**
- **TR112_v2:** ✅ **Comprehensive Rust vs Python comparison** (production-grade)

### Phase 5: Rust Multi-Agent Implementation (TR113-TR114)
**Objective:** Port multi-agent orchestration to Rust and compare to Python

- **TR113:** Rust multi-agent (single Ollama) - identified server contention issue
- **TR114:** Rust multi-agent (dual Ollama) - initial analysis - **SUPERSEDED**
- **TR114_v2:** ✅ **Comprehensive Rust multi-agent** (dual Ollama, corrected statistics)

### Phase 6: Runtime Optimization (TR115)
**Objective:** Optimize Rust async runtime for multi-agent workloads

- **TR115:** Initial runtime analysis - **SUPERSEDED**
- **TR115_v2:** ✅ **Definitive runtime optimization** (5 runtimes, 150 runs)

---

## 📋 Technical Reports Index

### ✅ **Current Production-Ready Reports (v2)**

| Report | Title | Status | Key Finding |
|--------|-------|--------|-------------|
| **TR108** | Single-Agent LLM Performance Analysis | ✅ Complete | Optimal configs for single-agent inference |
| **TR109** | Agent Workflow Optimization | ✅ Complete | GPU=60, CTX=512, TEMP=0.8 optimal for workflows |
| **TR110** | Concurrent Multi-Agent Performance (Python) | ✅ Complete | 99.25% parallel efficiency achieved |
| **TR111_v2** | Rust Single-Agent Performance | ✅ Complete | 114.54 tok/s baseline, 15.2% faster than Python |
| **TR112_v2** | Rust vs Python Comparison | ✅ Complete | Rust: +15.2% throughput, -58% TTFT, -67% memory |
| **TR114_v2** | Rust Multi-Agent Performance | ✅ Complete | 98.281% mean efficiency, 99.992% peak run |
| **TR115_v2** | Rust Runtime Optimization | ✅ Complete | Tokio-default recommended (98.72% mean, 1.21pp σ) |
| **TR116** | Cross-Model Multi-Agent Benchmarks | ✅ Complete | Rust + Gemma 3 is king (99.2%). Qwen shows imbalance. |
| **TR117** | Root Cause Analysis of Efficiency Anomalies | ✅ Complete | Python ceiling (86%) caused by Event Loop Lag (16ms spikes). |
| **TR117_multi_agent** | Multi-Agent Root Cause Analysis | ✅ Complete | Python event loop saturation (5.33ms mean lag, 15.22ms max). |
| **TR118_v2.2** | ONNX Runtime + TensorRT Deep Dive | ✅ Complete | TensorRT-fp16 best prefill (2.48ms, -87% vs baseline). |
| **TR119** | Cost & Energy Analysis | ✅ Complete | onnxruntime-gpu best cost ($0.1279/1M tok on-demand). |
| **TR120** | The "Compile Paradox" Root-Cause Audit | ✅ Complete | TR117 compile label misattributed; shape stability critical. |
| **TR121v1** | Model Scaling Study | ✅ Complete | Scaling pipeline from 5M to 20B parameters established. |

### 📚 **Historical Reports (Superseded)**

| Report | Status | Superseded By | Reason |
|--------|--------|---------------|--------|
| TR111 | ❌ Superseded | TR111_v2 | Micro-benchmark → Full workflow |
| TR112 | ❌ Superseded | TR112_v2 | Flawed comparison methodology |
| TR114 | ❌ Superseded | TR114_v2 | Incorrect statistics (97.5% → 98.281%) |
| TR115 | ❌ Superseded | TR115_v2 | Incomplete data analysis (30 → 150 runs) |

---

## 🎯 Key Research Findings

### **Single-Agent Performance (TR111_v2, TR112_v2)**

**Rust Advantages:**
- **Throughput:** 114.54 tok/s vs Python 99.34 tok/s (**+15.2%**)
- **TTFT (cold):** 603ms vs Python 1437ms (**-58%**)
- **Memory:** ~75 MB vs Python ~250 MB (**-67%**)
- **Startup:** 0.2s vs Python 1.5s (**-83%**)
- **Consistency:** 2.6% CV vs Python 4.8% CV (**46% more consistent**)

**Verdict:** Rust dominates single-agent performance across all metrics.

### **Multi-Agent Performance (TR110, TR114_v2)**

**Python Baseline (TR110):**
- **Peak Config Efficiency:** 99.25% (homogeneous Chimera)
- **Mean Efficiency:** 95.8% (all 150 runs)
- **Contention Rate:** 10-15%

**Rust Performance (TR114_v2):**
- **Peak Config Efficiency:** 99.396% (chimera-hetero test011)
- **Peak Single Run:** 99.992% (chimera-homo test108)
- **Mean Efficiency:** 98.281% (all 135 runs) - **+2.48pp vs Python**
- **Contention Rate:** 0.74% - **-10-14pp vs Python**

**Verdict:** Rust **exceeds** Python in multi-agent scenarios (+2.48pp mean, +0.15pp peak config).

### **Runtime Optimization (TR115_v2)**

**Runtime Ranking (By Consistency):**
1. **Tokio-default:** 98.72% mean, 1.21pp σ 🏆 **RECOMMENDED**
2. **Smol-1KB:** 98.61% mean, 1.32pp σ ✅ **Alternative (smaller binary)**
3. **Tokio-localset:** 97.95% mean, 4.03pp σ ⚠️ **Unstable (18.96pp range)**
4. **Smol:** 97.72% mean, 4.87pp σ ❌ **Pathological failures (72.80% min)**
5. **Async-std:** 50.00% ❌ **Catastrophic (Tokio bridge conflict)**

**Verdict:** Use **standard Tokio** (`#[tokio::main]`) - no custom configuration needed.

---

## 📈 Performance Summary Matrix

### **Single-Agent Comparison (TR112_v2)**

| Metric | Python | Rust | Rust Advantage |
|--------|--------|------|----------------|
| **Throughput** | 99.34 tok/s | 114.54 tok/s | **+15.2%** |
| **TTFT (cold)** | 1437 ms | 603 ms | **-58.0%** |
| **Memory** | ~250 MB | ~75 MB | **-67%** |
| **Startup** | 1.5s | 0.2s | **-83%** |
| **CV (throughput)** | 4.8% | 2.6% | **-46% (more consistent)** |

### **Multi-Agent Comparison (TR110 vs TR114_v2)**

| Metric | Python (TR110) | Rust (TR114_v2) | Rust Advantage |
|--------|---------------|-----------------|----------------|
| **Peak Config Avg** | 99.25% | 99.396% | **+0.15pp** |
| **Peak Single Run** | 99.25% | 99.992% | **+0.74pp** |
| **Mean Efficiency** | 95.8% | 98.281% | **+2.48pp** |
| **Median Efficiency** | ~96.5% | 98.6% | **+2.1pp** |
| **StdDev** | 7.4pp | 4.9pp | **-2.5pp (more stable)** |
| **Contention Rate** | 10-15% | 0.74% | **-10-14pp** |

### **Runtime Performance (TR115_v2)**

| Runtime | Peak (%) | Mean (%) | StdDev (pp) | Min (%) | Recommendation |
|---------|----------|----------|-------------|---------|----------------|
| **Tokio-default** | 99.89 | **98.72** | **1.21** | 94.80 | ✅ **Production** |
| **Smol-1KB** | 99.94 | 98.61 | 1.32 | 94.98 | ✅ **Small binary** |
| **Tokio-localset** | 99.99 | 97.95 | 4.03 | 81.03 | ⚠️ **Unstable** |
| **Smol** | 99.87 | 97.72 | 4.87 | 72.80 | ❌ **Avoid** |
| **Async-std** | 50.00 | 50.00 | 0.00 | 50.00 | ❌ **Unusable** |

---

## 🔬 Report Details

### **TR108: Single-Agent LLM Performance Analysis**
**File:** `Technical_Report_108.md`

- **Focus:** Comprehensive LLM performance benchmarking and optimization
- **Models:** gemma3:latest, llama3.1:8b-instruct variants
- **Hardware:** NVIDIA RTX 4080 (12GB VRAM), i9-13980HX
- **Test Matrix:** 150+ benchmark runs across parameter sweeps
- **Key Findings:** Optimal configurations for single-agent inference
- **Status:** ✅ Complete (Publication-ready)

### **TR109: Agent Workflow Optimization**
**File:** `Technical_Report_109.md`

- **Focus:** Agent workflow performance vs single-inference optimization
- **Methodology:** Process isolation, forced cold starts, statistical validation
- **Key Findings:** Agent tasks require different optimization than single-inference
- **Optimal Config:** GPU=60, CTX=512, TEMP=0.8 for agent workflows
- **Quality Analysis:** Automated scoring methodology for report quality
- **Status:** ✅ Complete (Publication-ready)

### **TR110: Concurrent Multi-Agent Performance Analysis (Python)**
**File:** `Technical_Report_110.md`

- **Focus:** Parallel agent execution with resource coordination
- **Test Matrix:** 30 configurations × 5 runs = 150 benchmark runs
- **Key Findings:** 99.25% parallel efficiency achieved with homogeneous Chimera agents
- **Scenarios:** Baseline vs Chimera, Heterogeneous, Homogeneous configurations
- **Resource Analysis:** VRAM utilization, memory bandwidth saturation, contention patterns
- **Status:** ✅ Complete (Publication-ready)

### **TR111_v2: Rust Single-Agent Performance Analysis**
**File:** `Technical_Report_111_v2.md`

- **Focus:** Comprehensive Rust agent workflow performance with full Python parity
- **Test Matrix:** 19 configurations × 3 runs = 57 benchmark runs
- **Key Findings:**
  - Baseline: 114.54 tok/s (15.2% faster than Python)
  - TTFT: 547-1354ms range (high variance, context-dependent)
  - Optimal: `gpu60_ctx256_temp0p6` (115.94 tok/s)
- **Critical Discovery:** TTFT shows 150× more variation than throughput
- **Status:** ✅ Complete (Supersedes TR111)

### **TR112_v2: Rust vs Python Agent Performance Comparison**
**File:** `Technical_Report_112_v2.md`

- **Focus:** Cross-language comprehensive comparison with workflow parity
- **Test Matrix:** 37 configurations (19 Rust + 18 Python), 111 total runs
- **Key Findings:**
  - Rust: +15.2% throughput, -58% TTFT, -67% memory, -83% startup
  - Rust: 46% more consistent (2.6% vs 4.8% CV)
  - Business Impact: ~$3,040/year savings, 20-month break-even
- **Status:** ✅ Complete (Supersedes TR112)

### **TR113: Rust Multi-Agent Initial Analysis**
**File:** `Technical_Report_113.md`

- **Focus:** First Rust multi-agent implementation (single Ollama instance)
- **Key Finding:** 82.2% peak efficiency, 63% contention rate
- **Critical Discovery:** Server-level serialization bottleneck identified
- **Recommendation:** Dual Ollama architecture required
- **Status:** ✅ Complete (Historical - led to TR114)

### **TR114_v2: Rust Concurrent Multi-Agent Performance**
**File:** `Technical_Report_114_v2.md`

- **Focus:** Comprehensive Rust multi-agent with dual Ollama architecture
- **Test Matrix:** 27 configurations × 5 runs = 135 benchmark runs
- **Key Findings:**
  - Peak single run: 99.992% (test108)
  - Best config avg: 99.396% (test011 chimera-hetero)
  - Mean efficiency: 98.281% (+2.48pp vs Python)
  - Contention rate: 0.74% (-10-14pp vs Python)
- **Critical Discovery:** Rust **exceeds** Python in multi-agent scenarios
- **Status:** ✅ Complete (Supersedes TR114)

### **TR115_v2: Rust Async Runtime Performance Deep Dive**
**File:** `Technical_Report_115_v2.md`

- **Focus:** Comprehensive multi-runtime analysis for multi-agent workloads
- **Test Matrix:** 5 runtimes × 6 configs × 5 runs = 150 benchmark runs
- **Key Findings:**
  - All 4 working runtimes achieve ~100% peak (99.87-99.99%)
  - Consistency matters more: Tokio-default (1.21pp σ) recommended
  - Async-std unusable (50% efficiency, Tokio bridge conflict)
  - Smol has pathological failures (72.80% min efficiency)
- **Production Recommendation:** Use standard `#[tokio::main]` - no custom config needed
- **Status:** ✅ Complete (Supersedes TR115)

### **TR116: Cross-Model Multi-Agent Performance**
**File:** `Technical_Report_116.md`

- **Focus:** Impact of model choice (Qwen, Gemma, Llama) on multi-agent efficiency
- **Test Matrix:** 3 models × 2 runtimes × 2 scenarios × 5 runs = 60 benchmark runs
- **Key Findings:**
  - Rust dominates across all models (+12-17pp efficiency vs Python)
  - Gemma 3 is the scaling king (99.2% efficiency in Rust)
  - Qwen 2.5 shows significant throughput imbalance (+12 tok/s delta)
- **Production Recommendation:** Rust + Gemma 3 for max performance, Rust + Llama 3.1 for reasoning.
- **Status:** ✅ Complete (Publication-ready)

### **TR117: Root Cause Analysis of Efficiency Anomalies**
**File:** `Technical_Report_117.md`

- **Focus:** Investigate why Python multi-agent efficiency never exceeds 86% despite optimal configurations
- **Key Findings:**
  - Python ceiling identified: Event loop lag (16ms spikes) prevents >86% efficiency
  - Root cause: Single-threaded event loop cannot handle concurrent I/O without blocking
  - Rust advantage confirmed: Multi-threaded runtime avoids this bottleneck entirely
- **Production Verdict:** Python limitation is structural; Rust required for >86% efficiency
- **Status:** ✅ Complete (Publication-ready)

### **TR117_multi_agent: Multi-Agent Root Cause Analysis**
**File:** `Technical_Report_117_multi_agent.md`

- **Focus:** Definitive root cause analysis of Python Ceiling, Qwen Mystery, and Ranking Flip
- **Methodology:** Three invasive research phases (Event Loop Instrumentation, Hardware Forensics, Flow Dynamics)
- **Key Findings:**
  - Python event loop saturation: Mean lag 5.33ms, p99 12.13ms, max 15.22ms
  - CPU-bound serialization: Each chunk triggers JSON parsing, monopolizing event loop
  - Efficiency correlation: Loop lag + chunk gaps = 40ms cycle time → caps efficiency at ~91%
- **Production Verdict:** For >100 tok/s multi-agent systems, Rust is mandatory
- **Status:** ✅ Complete (Publication-ready)

### **TR118_v2.2: ONNX Runtime + TensorRT Deep Dive**
**File:** `Technical_Report_118_v2.2.md`

- **Focus:** ONNX Runtime and TensorRT for local-first LLM inference with explicit degraded reasons and accuracy gates
- **Test Matrix:** 360 run-level records across prefill and generate modes
- **Key Findings:**
  - Best prefill latency: TensorRT-fp16 (2.48ms, -87.08% vs baseline)
  - Best generate latency: ONNX Runtime-CPU (43.3ms, -73.34% vs baseline)
  - Degraded rate: 25.0% (90/360 runs)
  - Accuracy gate passed: Perplexity validation successful
- **Production Recommendation:** TensorRT-fp16 for prefill, ONNX Runtime for generate
- **Status:** ✅ Complete (Publication-ready)

### **TR119: Cost & Energy Analysis**
**File:** `Technical_Report_119.md`

- **Focus:** Convert benchmark latency/throughput into dollars, kWh, and carbon per 1M tokens
- **Test Matrix:** 5 backends × 5 scenarios × 7 repetitions × 2 modes = 350 runs
- **Key Findings:**
  - Best-cost backend: onnxruntime-gpu at ~$0.1279 per 1M tokens (on-demand)
  - Best spot pricing: onnxruntime-gpu at ~$0.03868 per 1M tokens (69.8% savings)
  - Lowest carbon: onnxruntime-gpu at ~1.0 gCO2e per 1M tokens
  - Best energy efficiency: onnxruntime-gpu at ~503M tokens/kWh
- **Production Recommendation:** onnxruntime-gpu for GPU-available systems
- **Status:** ✅ Complete (Publication-ready)

### **TR120: The "Compile Paradox" Root-Cause Audit**
**File:** `Technical_Report_120.md`

- **Focus:** Root-cause audit of why "-compile" backend wins mean while losing median
- **Key Findings:**
  - TR117's "compile paradox" is real but misattributed (label-only, no actual torch.compile)
  - When torch.compile is actually enabled: prefill becomes fast at p50 but develops heavy tail
  - Shape stability fix: Padding/bucketing collapses compiled tail (p99 drops to sub-millisecond)
  - KV-cached decode: Inductor improves prefill but regresses KV decode
- **Production Guidance:** Do not rely on backend labels; wire compilation explicitly; stabilize shapes
- **Status:** ✅ Complete (Publication-ready)

### **TR121v1: Model Scaling Study**
**File:** `Technical_Report_121v1.md`

- **Focus:** How inference behavior changes from ~5M to ~20B parameters (HF + Ollama)
- **Scope:** Two-family scaling study (HF local models 5M-124M, Ollama models 270M-20B)
- **Methodology:** Consistent phase definitions (prefill vs decode), artifact-backed measurements
- **Status:** ✅ Pipeline complete (scaling harness established, ready for full sweep)
- **Note:** This is the pipeline draft; full matrix run pending for publish-ready report

### **TR122: Resource Profiling Deep Dive**
**File:** Planned (see `experiments/tr122/README.md`)

- **Status:** 🔬 Planned (Target: Week of 2026-01-06)
- **Research Question:** Where do resources (GPU VRAM, CPU RAM, power, thermal) bottleneck?
- **Scope:** Full instrumentation, per-layer profiling, KV cache analysis, thermal throttling detection
- **Expected Deliverables:** Resource telemetry, bottleneck identification, optimization strategies

### **TR123: Multi-Hardware Generalization**
**File:** Planned (see `experiments/tr123/README.md`)

- **Status:** 🔬 Planned (Target: Week of 2026-01-13)
- **Research Question:** Do TR117 findings generalize across GPU types, CPU architectures, and cloud providers?
- **Scope:** Hardware matrix (NVIDIA RTX 4080, A100, H100), CPU comparison, cloud validation
- **Expected Deliverables:** Multi-hardware validation, cloud provider replication, deployment guide

---

## 🎓 Research Evolution & Key Insights

### **The Journey: From Python Baseline to Rust Excellence**

1. **TR108-TR109 (Python Foundation):** Established optimal single-agent and workflow configurations
2. **TR110 (Python Multi-Agent):** Achieved 99.25% parallel efficiency baseline
3. **TR111_v2 (Rust Single-Agent):** Discovered Rust's 15.2% throughput advantage
4. **TR112_v2 (Cross-Language):** Quantified Rust's comprehensive advantages (performance, memory, startup)
5. **TR113 (Rust Multi-Agent v1):** Identified server contention bottleneck (single Ollama)
6. **TR114_v2 (Rust Multi-Agent v2):** Proved Rust **exceeds** Python in multi-agent (+2.48pp mean)
7. **TR115_v2 (Runtime Optimization):** Established Tokio-default as optimal runtime
8. **TR116 (Cross-Model):** Proved Rust dominance holds across architectures
9. **TR117 (Root Cause):** Identified Python event loop lag as structural bottleneck
10. **TR117_multi_agent (Multi-Agent Root Cause):** Quantified event loop saturation (5.33ms mean lag)
11. **TR118_v2.2 (ONNX/TRT):** Established TensorRT-fp16 as optimal prefill backend
12. **TR119 (Cost/Energy):** Quantified $/token and kWh/token economics
13. **TR120 (Compile Paradox):** Root-caused TR117 compile label misattribution
14. **TR121v1 (Scaling):** Established scaling pipeline from 5M to 20B parameters

### **Critical Discoveries**

1. **Single-Agent:** Rust is **15.2% faster** than Python (TR112_v2)
2. **Multi-Agent:** Rust **exceeds** Python by +2.48pp mean efficiency (TR114_v2)
3. **Runtime:** Standard Tokio achieves 98.72% mean with 1.21pp σ (TR115_v2)
4. **Architecture:** Dual Ollama **mandatory** for multi-agent (reduces contention 63% → 0.74%)
5. **Consistency:** Rust's lower variance (4.9pp vs 7.4pp) provides production reliability
6. **Backend Selection:** TensorRT-fp16 optimal for prefill, ONNX Runtime-gpu for cost efficiency (TR118, TR119)
7. **Compilation:** Shape stability critical; compile labels must be verified (TR120)
8. **Economics:** onnxruntime-gpu achieves $0.1279/1M tokens on-demand (TR119)

### **The "Paradox" That Wasn't**

**Initial Hypothesis (TR113/TR114):** Rust's single-agent advantage would disappear in multi-agent scenarios due to coordination overhead.

**Actual Reality (TR114_v2):** Rust's advantages **carry over** to multi-agent:
- Single-agent: +15.2% throughput
- Multi-agent: +2.48pp mean efficiency, +0.15pp peak config
- **Conclusion:** No paradox - Rust maintains and extends advantages

---

## 🚀 Production Recommendations

### **Single-Agent Deployment**

**Choose Rust if:**
- ✅ Production reliability required
- ✅ Resource efficiency critical (67% less memory)
- ✅ Fast startup needed (83% faster)
- ✅ Consistent performance valued (46% lower variance)

**Choose Python if:**
- ✅ Rapid prototyping needed
- ✅ Development velocity prioritized
- ✅ Ecosystem richness required

**Verdict:** **Rust for production** (15% faster, 67% less memory, 83% faster startup)

### **Multi-Agent Deployment**

**Architecture:**
- ✅ **Dual Ollama instances** (mandatory - eliminates server contention)
- ✅ **Heterogeneous configs** optimal (asymmetric GPU allocation)
- ✅ **Tokio-default runtime** (best consistency: 1.21pp σ)

**Configuration:**
- **Best Config (TR114_v2):** GPU=120/140, CTX=512/1024 (test011) → 99.396% efficiency
- **Balanced Config:** GPU=80, CTX=1024 (test004) → 98.984% efficiency
- **Avoid:** GPU=120 in baseline-vs-chimera (test005: 91.60% with contention)

**Verdict:** **Rust multi-agent** (98.281% mean vs Python 95.8%, 0.74% contention vs 10-15%)

### **Runtime Selection (TR115_v2)**

**Production:**
```rust
// Use standard Tokio - no custom configuration needed
#[tokio::main]
async fn main() {
    let (r1, r2) = tokio::join!(agent_a(), agent_b());
}
```

**Why:**
- ✅ Highest consistency: 1.21pp σ (vs 4.03pp for localset)
- ✅ Best mean efficiency: 98.72% (vs 97.95% for localset)
- ✅ Simplest deployment: No custom runtime configuration
- ✅ Best ecosystem: Native reqwest, no bridges

**Alternatives:**
- **Smol-1KB:** If binary size <5MB critical (98.61% mean, 1.32pp σ, -0.11pp loss acceptable)
- **Never use:** Async-std (50% efficiency), Smol (pathological failures)

---

## 💰 Business Impact Summary

### **Infrastructure Savings (TR112_v2)**

**Single-Agent:**
- Memory: 67% reduction (75 MB vs 250 MB)
- Startup: 83% faster (0.2s vs 1.5s)
- **Cost:** ~$3,040/year savings at 1M requests/month
- **Break-even:** 20 months ($5k dev overhead)

### **Multi-Agent Advantages (TR114_v2)**

**Performance:**
- Mean efficiency: +2.48pp (98.281% vs 95.8%)
- Contention rate: -10-14pp (0.74% vs 10-15%)
- Consistency: -2.5pp StdDev (4.9pp vs 7.4pp)

**Cost:**
- 50% lower infrastructure cost (67% less memory per agent)
- 3× concurrent capacity (lower memory footprint)
- Reduced contention = fewer failed requests

### **Runtime Optimization (TR115_v2)**

**Impact:**
- Runtime choice: Marginal (<1% between best options)
- **Async-std cost:** 50% efficiency = **2× infrastructure cost** (avoid!)
- **Tokio-default cost:** Same as Python (both ~99% efficiency)

**Strategic Insight:** Standard Tokio requires zero custom configuration, achieving Python parity with Rust's resource advantages.

---

## 📁 Repository Structure

```
PublishReady/reports/
├── README.md (this file)
│
├── ✅ Production-Ready Reports (v2)
│   ├── Technical_Report_108.md - Single-agent LLM performance (Python)
│   ├── Technical_Report_109.md - Agent workflow optimization (Python)
│   ├── Technical_Report_110.md - Multi-agent performance (Python)
│   ├── Technical_Report_111_v2.md - Rust single-agent performance
│   ├── Technical_Report_112_v2.md - Rust vs Python comparison
│   ├── Technical_Report_114_v2.md - Rust multi-agent performance
│   ├── Technical_Report_115_v2.md - Rust runtime optimization
│   ├── Technical_Report_116.md - Cross-model multi-agent benchmarks
│   ├── Technical_Report_117.md - Root cause analysis (inference track)
│   ├── Technical_Report_117_multi_agent.md - Multi-agent root cause analysis
│   ├── Technical_Report_118_v2.2.md - ONNX Runtime + TensorRT deep dive
│   ├── Technical_Report_119.md - Cost & energy analysis
│   ├── Technical_Report_120.md - The "Compile Paradox" root-cause audit
│   └── Technical_Report_121v1.md - Model scaling study (pipeline)
│
├── 📚 Historical Reports (Superseded)
│   ├── Technical_Report_111.md - Initial Rust (micro-benchmark)
│   ├── Technical_Report_112.md - Flawed comparison
│   ├── Technical_Report_113.md - Rust multi-agent (single Ollama)
│   ├── Technical_Report_114.md - Rust multi-agent (incorrect stats)
│   └── Technical_Report_115.md - Incomplete runtime analysis
│
└── 📊 Model Benchmarks
    └── gemma3/
        └── Gemma3_Benchmark_Report.md
```

---

## 🔗 Report Relationships

```
TR108 (Python Single-Agent)
    ↓
TR109 (Python Workflow Optimization)
    ↓
TR110 (Python Multi-Agent Baseline)
    ↓
TR111_v2 (Rust Single-Agent) ──→ TR112_v2 (Rust vs Python)
    ↓                                    ↓
TR113 (Rust Multi-Agent v1)      TR114_v2 (Rust Multi-Agent v2)
    ↓                                    ↓
TR114_v2 (Dual Ollama)            TR115_v2 (Runtime Optimization)
```

**Key Dependencies:**
- TR111_v2 → TR112_v2 (single-agent comparison)
- TR110 → TR114_v2 (multi-agent comparison)
- TR111_v2/TR112_v2/TR114_v2 → TR115_v2 (baseline references)
- TR113 → TR114_v2 (identified dual Ollama requirement)

---

## 📖 Quick Reference

### **Best Configurations**

**Single-Agent (TR111_v2):**
- **Optimal:** `gpu60_ctx256_temp0p6` (115.94 tok/s)
- **Baseline:** Ollama defaults (114.54 tok/s)

**Multi-Agent (TR114_v2):**
- **Best Config:** GPU=120/140, CTX=512/1024 (test011) → 99.396% efficiency
- **Balanced:** GPU=80, CTX=1024 (test004) → 98.984% efficiency

**Runtime (TR115_v2):**
- **Production:** Tokio-default (`#[tokio::main]`)
- **Small Binary:** Smol-1KB (if size critical)

### **Performance Targets**

**Single-Agent:**
- Rust: 114.54 tok/s baseline, 115.94 tok/s optimal
- Python: 99.34 tok/s baseline

**Multi-Agent:**
- Rust: 98.281% mean, 99.396% peak config, 99.992% peak run
- Python: 95.8% mean, 99.25% peak config

**Runtime:**
- Tokio-default: 98.72% mean, 1.21pp σ (recommended)
- Smol-1KB: 98.61% mean, 1.32pp σ (alternative)

---

## 🎯 Research Questions Answered

1. **Q: Is Rust faster than Python for LLM inference?**  
   **A: Yes - 15.2% faster throughput, 58% faster TTFT, 67% less memory (TR112_v2)**

2. **Q: Does Rust's single-agent advantage carry over to multi-agent?**  
   **A: Yes - Rust exceeds Python by +2.48pp mean efficiency (TR114_v2)**

3. **Q: Which Rust async runtime is optimal for multi-agent workloads?**  
   **A: Tokio-default - 98.72% mean, 1.21pp σ (best consistency) (TR115_v2)**

4. **Q: Is dual Ollama architecture necessary?**  
   **A: Yes - Reduces contention from 63% to 0.74% (TR113 → TR114_v2)**

5. **Q: What is the optimal multi-agent configuration?**  
   **A: Heterogeneous GPU allocation (120/140) with asymmetric context (512/1024) → 99.396% efficiency (TR114_v2)**

---

## 📊 Statistical Validation

All reports include:
- ✅ **Statistical rigor:** Mean, median, stddev, percentiles, CV
- ✅ **Multiple runs:** 3-5 runs per configuration for confidence
- ✅ **Comprehensive coverage:** 19-37 configurations per report
- ✅ **Cross-validation:** Results validated across multiple reports
- ✅ **Reproducibility:** Full methodology and data sources documented

**Total Benchmark Runs:**
- TR108: 150+ runs
- TR109: 90 runs
- TR110: 150 runs
- TR111_v2: 57 runs
- TR112_v2: 111 runs
- TR114_v2: 135 runs
- TR115_v2: 150 runs
- TR116: 60 runs
- **Total: 903+ benchmark runs** across all reports

---

## 🚀 Getting Started

### **For Researchers**
1. Start with **TR108** (Python single-agent baseline)
2. Review **TR109** (workflow optimization methodology)
3. Study **TR110** (Python multi-agent baseline)
4. Compare **TR112_v2** (Rust vs Python single-agent)
5. Analyze **TR114_v2** (Rust multi-agent performance)
6. Reference **TR115_v2** (runtime optimization guidance)

### **For Engineers**
1. **Single-Agent:** Read **TR112_v2** for Rust vs Python comparison
2. **Multi-Agent:** Read **TR114_v2** for deployment guidance
3. **Runtime:** Read **TR115_v2** for production recommendations
4. **Configuration:** Use best configs from TR111_v2 (single) and TR114_v2 (multi)

### **For Decision Makers**
1. **Executive Summary:** Review "Key Findings" sections in each report
2. **Business Impact:** See "Business Impact" sections in TR112_v2, TR114_v2
3. **Recommendations:** See "Production Recommendations" in this README
4. **Cost Analysis:** Review break-even analysis in TR112_v2

---

## 📝 Report Status Legend

- ✅ **Complete (Publication-ready):** Fully validated, production-grade analysis
- 📚 **Historical (Superseded):** Replaced by v2 with corrected methodology/data
- 🔬 **In Progress:** Currently being developed

---

**Last Updated:** 2025-12-23  
**Maintainer:** Chimera Heart Development Team  
**Total Reports:** 20 (15 production-ready, 5 historical, 2 planned)  
**Total Benchmark Runs:** 2000+ across all reports
