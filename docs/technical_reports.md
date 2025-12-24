# Technical Reports Index

Complete index of all technical reports documenting LLM performance optimization research.

## Report Overview

| Report | Title | Focus | Key Finding |
|--------|-------|-------|-------------|
| **TR108** | Single-Inference Optimization | GPU/context/temperature tuning | GPU=80, CTX=512 optimal |
| **TR109** | Python Agent Workflows | Agent-specific optimization | Different configs needed for agents |
| **TR110** | Python Multi-Agent Concurrent | Concurrent execution | 99.25% efficiency with dual Ollama |
| **TR111_v2** | Rust Single-Agent | Rust agent performance | 114.54 tok/s baseline, 15.2% faster than Python |
| **TR112_v2** | Rust vs Python Single-Agent | Cross-language comparison | Rust: +15.2% throughput, -58% TTFT, -67% memory |
| **TR113** | Rust Multi-Agent (Single Ollama) | Architectural analysis | 82.2% peak, identifies bottleneck |
| **TR114_v2** | Rust Multi-Agent (Dual Ollama) | True concurrency validation | 98.281% mean, 99.396% peak, exceeds Python |
| **TR115_v2** | Rust Runtime Optimization | Runtime scheduler investigation | Tokio-default: 98.72% mean, 1.21pp  (recommended) |
| **TR116** | Cross-Model Benchmarks | Multi-model scaling analysis | Gemma 3 (99.2%) > Llama 3.1 (98.5%) > Qwen 2.5 (90.0%) |
| **TR117** | Cross-Backend Inference Benchmark | Backend matrix + degradation | Compile-paradox discovery (inference track) |
| **TR117 (Multi-Agent)** | Root Cause Analysis of Efficiency Anomalies | Event loop + streaming bottlenecks | Python ceiling explained (agent track) |

## Detailed Reports

### TR108: Single-Inference LLM Performance Analysis

**File**: [Technical_Report_108.md](../outputs/publish_ready/reports/Technical_Report_108.md)

**Objective**: Comprehensive analysis of single-inference LLM performance optimization.

**Key Findings**:
- Optimal configuration: GPU=80, CTX=512, TEMP=0.8
- GPU layer allocation: 60-80 layers optimal for RTX 4080
- Context window: 512-1024 tokens optimal for most tasks
- Temperature: 0.6-0.8 optimal for quality/performance balance

**Methodology**:
- Parameter sweep: GPU (60-120), CTX (256-2048), TEMP (0.6-1.0)
- Model: gemma3:latest (4.3B parameters)
- Hardware: RTX 4080 (12GB VRAM)

**Use Cases**:
- Single-request optimization
- Baseline for agent workflow comparison
- Understanding GPU/context trade-offs

---

### TR109: Python Agent Workflow Optimization

**File**: [Technical_Report_109.md](../outputs/publish_ready/reports/Technical_Report_109.md)

**Objective**: Evaluate Chimera optimization strategies for multi-step agent workflows.

**Key Findings**:
- Agent workflows need different configs than single-inference
- Optimal: GPU=60-80, CTX=512-1024, TEMP=0.6-0.8
- 39% optimization success rate (vs 72% for Rust in TR111)
- Context size 512-1024 optimal (vs 2048 for single-inference)

**Methodology**:
- 18 configuration parameter sweep
- 5 runs per configuration
- Agent task: Technical report generation (800-1000 words)

**Comparison to TR108**:
- Single-inference optimal configs don't transfer to agents
- Agents benefit from smaller context windows
- Temperature sensitivity higher in agent workflows

---

### TR110: Python Concurrent Multi-Agent Performance

**File**: [Technical_Report_110.md](../outputs/publish_ready/reports/Technical_Report_110.md)

**Objective**: Systematic evaluation of concurrent multi-agent LLM execution.

**Key Findings**:
- Peak efficiency: 99.25% (1.985x speedup) with homogeneous Chimera
- Best config: GPU=80, CTX=2048, TEMP=1.0
- Dual Ollama instances required for true concurrency
- 33% contention rate (mostly at GPU=60)

**Methodology**:
- 30 configurations, 5 runs each = 150 benchmarks
- Three scenarios: baseline_vs_chimera, chimera_hetero, chimera_homo
- Dual Ollama instances (ports 11434/11435)

**Scenarios**:
1. **Baseline vs Chimera**: 97.9% peak efficiency
2. **Heterogeneous**: 99.0% peak efficiency
3. **Homogeneous**: 99.25% peak efficiency

**Production Impact**:
- Near-perfect parallel efficiency enables 2x capacity with <1% overhead
- GPU=80 optimal for multi-agent (avoids memory bandwidth saturation)

---

### TR111_v2: Rust Single-Agent Performance Analysis

**File**: [Technical_Report_111_v2.md](../outputs/publish_ready/reports/Technical_Report_111_v2.md)

**Objective**: Comprehensive Rust agent performance evaluation with full workflow parity.

**Key Findings**:
- Baseline throughput: 114.54 tok/s (vs Python 99.34 tok/s) - **+15.2% faster**
- Peak throughput: 115.94 tok/s (GPU=60, CTX=256, TEMP=0.6)
- 72.2% optimization success rate (vs Python 38.9%)
- 2.6% throughput CV (exceptional consistency)
- Best config: GPU=60, CTX=256, TEMP=0.6

**Methodology**:
- 19 configurations (1 baseline + 18 parameter variations)
- 3 runs per configuration = 57 total runs
- Full workflow parity: file I/O, multi-stage LLM calls, comprehensive metrics

**Comparison to TR109 (Python)**:
- Throughput: Rust **15.2% faster** (114.54 vs 99.34 tok/s)
- Consistency: Rust 46% better (2.6% vs 4.8% CV)
- Optimization success: Rust 85% better (72.2% vs 38.9%)

**Production Implications**:
- Rust **dominates** single-agent deployments
- Superior performance, consistency, and resource efficiency
- 67% less memory, 83% faster startup

---

### TR112_v2: Rust vs Python Single-Agent Comparison

**File**: [Technical_Report_112_v2.md](../outputs/publish_ready/reports/Technical_Report_112_v2.md)

**Objective**: Direct cross-language comparison with full workflow parity.

**Key Findings**:
- Throughput: Rust **15.2% faster** (114.54 vs 99.34 tok/s)
- TTFT (cold): Rust **58% faster** (603ms vs 1437ms)
- Memory: Rust **67% less** (~75 MB vs ~250 MB)
- Startup: Rust **83% faster** (0.2s vs 1.5s)
- Consistency: Rust **46% better** (2.6% vs 4.8% CV)

**Methodology**:
- 37 configurations (19 Rust + 18 Python), 111 total runs
- Identical hardware, model, and full workflow complexity
- Statistical validation with confidence intervals

**Production Decision Framework**:
- **Choose Rust**: Production reliability, resource efficiency, deployment simplicity
- **Choose Python**: Rapid prototyping, development velocity, ecosystem richness

**Verdict**: Rust **dominates** single-agent performance across all metrics. Winner: Rust for production workloads.

---

### TR113: Rust Multi-Agent (Single Ollama)

**File**: [Technical_Report_113.md](../outputs/publish_ready/reports/Technical_Report_113.md)

**Objective**: Rust multi-agent performance with single Ollama instance.

**Key Findings**:
- Peak efficiency: 82.2% (vs Python 99.25% in TR110)
- Mean efficiency: 72.0% (vs Python 92.7%)
- 74% contention rate (vs Python 33%)
- Identifies single Ollama instance as bottleneck

**Methodology**:
- 19 configurations (13 baseline_vs_chimera, 2 hetero, 4 homo)
- Single Ollama instance (port 11434)
- Direct comparison to TR110 Python results

**Root Cause Analysis**:
- Single Ollama forces sequential model loading
- VRAM allocation contention
- Tokio work-stealing overhead
- Reqwest buffering behavior

**Hypothesis**: Dual Ollama architecture would recover 15-18pp efficiency.

---

### TR114_v2: Rust Multi-Agent (Dual Ollama)

**File**: [Technical_Report_114_v2.md](../outputs/publish_ready/reports/Technical_Report_114_v2.md)

**Objective**: Comprehensive Rust multi-agent analysis with corrected statistics.

**Key Findings**:
-  **Dual Ollama Confirmed**: Contention reduction 63%  0.74% (85x improvement)
- Peak single run: 99.992% (test108)
- Best config average: 99.396% (test011: chimera-hetero)
- Mean efficiency: **98.281%** (vs Python 95.8%) - **+2.48pp advantage**
- Contention rate: 0.74% (vs Python 10-15%)

**Methodology**:
- 27 configurations, 5 runs each = 135 benchmarks
- Three scenarios: baseline-vs-chimera, chimera-hetero, chimera-homo
- Dual Ollama instances (ports 11434/11435)

**Comparison to TR110 (Python)**:
- Peak config avg: +0.15pp (99.396% vs 99.25%)
- Mean efficiency: **+2.48pp** (98.281% vs 95.8%)
- Consistency: Rust better (4.9pp vs 7.4pp StdDev)
- Contention: Rust dramatically better (0.74% vs 10-15%)

**Production Verdict**:
- Dual Ollama **mandatory** for Rust multi-agent
- Rust **exceeds** Python in multi-agent scenarios (+2.48pp mean)
- No "paradox" - Rust's advantages carry over to multi-agent

---

### TR115_v2: Rust Runtime Optimization

**File**: [Technical_Report_115_v2.md](../outputs/publish_ready/reports/Technical_Report_115_v2.md)

**Objective**: Definitive Rust async runtime analysis for multi-agent workloads.

**Key Findings**:
- All 4 working runtimes achieve **~100% peak** (99.87-99.99%, only 0.12pp spread)
- **Consistency matters more than peak**: Tokio-default (1.21pp ) recommended
- **Tokio-default**: 98.72% mean, 1.21pp , 94.80% min - **MOST RELIABLE**
- **Smol-1KB**: 98.61% mean, 1.32pp  - **Alternative for smaller binaries**
- **Async-std unusable** (50% efficiency) due to Tokio HTTP bridge conflict
- **Smol has pathological failures** (72.80% min efficiency) - avoid

**Methodology**:
- 5 runtime variants: tokio-default, tokio-localset, async-std, smol, smol-1kb
- 6 configurations  5 runs = 30 benchmarks per runtime (150 total)
- Comprehensive statistical analysis with percentiles and variance

**Runtime Performance Ranking (By Consistency)**:
1. **Tokio-default**: 98.72% mean, 1.21pp   **RECOMMENDED**
2. **Smol-1KB**: 98.61% mean, 1.32pp   **Alternative**
3. **Tokio-localset**: 97.95% mean, 4.03pp   **Unstable**
4. **Smol**: 97.72% mean, 4.87pp   **Pathological failures**
5. **Async-std**: 50.00%  **Catastrophic**

**Production Verdict**:
- **Use standard Tokio** (`#[tokio::main]`) - no custom configuration needed
- **Peak performance irrelevant** - all runtimes achieve ~100% peak
- **Consistency is key** - Tokio-default provides best reliability (1.21pp )
- **Architecture > Runtime** - dual-Ollama is the key, not scheduler optimization

---

### TR116: Cross-Model Benchmarks (Qwen 2.5 vs Gemma 3 vs Llama 3.1)

**File**: [Technical_Report_116.md](../outputs/publish_ready/reports/Technical_Report_116.md)

**Objective**: Determine if model choice impacts multi-agent coordination efficiency and if Rust's advantages hold across different architectures.

**Key Findings**:
- **Rust Dominates**: +12-17pp higher efficiency than Python across ALL models.
- **Gemma 3 Champion**: 99.2% efficiency in Rust (near-perfect scaling).
- **Qwen 2.5 Issues**: Throughput imbalance (+12 tok/s delta) hurts efficiency (90.0%).
- **Python Ceiling**: Python never exceeds 86% efficiency, regardless of model.

**Methodology**:
- 60+ multi-agent runs across 3 models (Gemma 3, Llama 3.1, Qwen 2.5).
- Dual Ollama architecture (ports 11434/11435).
- Scenarios: `baseline_vs_chimera` and `chimera_homo`.

**Production Verdict**:
- **Use Rust + Gemma 3** for maximum performance (99.2% efficiency).
- **Avoid Qwen 2.5** for high-concurrency multi-agent (imbalance issues).
- **Rust is superior** regardless of model choice.

---

### TR117: Root Cause Analysis of Efficiency Anomalies

**File**: [Technical_Report_117.md](../outputs/publish_ready/reports/Technical_Report_117.md)

**Objective**: Investigate why Python multi-agent efficiency never exceeds 86% despite optimal configurations.

**Key Findings**:
- **Python Ceiling Identified**: Event loop lag (16ms spikes) prevents Python from achieving >86% efficiency.
- **Root Cause**: Single-threaded event loop cannot handle concurrent I/O without blocking.
- **Rust Advantage Confirmed**: Rust's multi-threaded runtime avoids this bottleneck entirely.

**Methodology**:
- Detailed profiling of Python event loop behavior.
- Comparison of I/O blocking patterns between Python and Rust.
- Analysis of scheduler starvation in Python async runtime.

**Production Verdict**:
- **Python limitation is structural**, not configuration-related.
- **Rust's advantage is fundamental** - multi-threaded runtime eliminates event loop lag.
- **For >86% efficiency, Rust is required** - no Python optimization can overcome this ceiling.

---

### TR117_multi_agent: Multi-Agent Root Cause Analysis

**File**: [Technical_Report_117_multi_agent.md](../outputs/publish_ready/reports/Technical_Report_117_multi_agent.md)

**Objective**: Definitive root cause analysis of Python Ceiling, Qwen Mystery, and Ranking Flip through invasive instrumentation.

**Key Findings**:
- **Python Event Loop Saturation**: Mean lag 5.33ms, p99 12.13ms, max 15.22ms (Gemma, default buffer).
- **CPU-Bound Serialization**: Each chunk triggers JSON parsing, monopolizing single-threaded event loop.
- **Efficiency Correlation**: Loop lag + chunk gaps = 40ms cycle time → caps efficiency at ~91%.
- **Qwen Mystery**: BPE tokenizer overhead + chunk amplification explains lower efficiency.
- **Ranking Flip**: Slower models provide "breathing room" for event loop, improving efficiency.

**Methodology**:
- Phase 1: Python MRI (Event Loop Instrumentation) - invasive loop lag measurement.
- Phase 2: Hardware Forensics (GPU/PCIe Profiling) - hardware bottleneck analysis.
- Phase 3: Flow Dynamics (Artificial Throttling) - controlled rate limiting experiments.

**Production Verdict**:
- **For >100 tok/s multi-agent systems, Rust is mandatory**.
- Python mitigation: Token bucket throttling, batched HTTP processing, uvloop.
- **Rust immunity**: Tokio's multi-threaded work-stealing scheduler eliminates loop lag.

---

### TR118_v2.2: ONNX Runtime + TensorRT Deep Dive

**File**: [Technical_Report_118_v2.2.md](../outputs/publish_ready/reports/Technical_Report_118_v2.2.md)

**Objective**: Make ONNX export + TRT engine builds real and measurable with explicit degraded reasons and accuracy gates.

**Key Findings**:
- **Best Prefill**: TensorRT-fp16 (2.48ms, -87.08% vs baseline transformers-gpu-compile).
- **Best Generate**: ONNX Runtime-CPU (43.3ms, -73.34% vs baseline).
- **Degraded Rate**: 25.0% (90/360 runs) with explicit reasons.
- **Accuracy Gate**: Perplexity validation passed.

**Methodology**:
- 360 run-level records across prefill and generate modes.
- Explicit degraded reasons and accuracy gates.
- Artifact-driven reproducibility (JSONL + CSV + manifests).

**Production Verdict**:
- **TensorRT-fp16 for prefill** (fastest latency).
- **ONNX Runtime for generate** (best throughput).
- Shape stability and quantization strategy critical.

---

### TR119: Cost & Energy Analysis

**File**: [Technical_Report_119.md](../outputs/publish_ready/reports/Technical_Report_119.md)

**Objective**: Convert benchmark latency/throughput into dollars, kWh, and carbon per 1M tokens.

**Key Findings**:
- **Best-Cost Backend**: onnxruntime-gpu at ~$0.1279 per 1M tokens (on-demand).
- **Best Spot Pricing**: onnxruntime-gpu at ~$0.03868 per 1M tokens (69.8% savings).
- **Lowest Carbon**: onnxruntime-gpu at ~1.0 gCO2e per 1M tokens.
- **Best Energy Efficiency**: onnxruntime-gpu at ~503M tokens/kWh.
- **Runs**: 350 total, 0 degraded (0.0%).

**Methodology**:
- 5 backends × 5 scenarios × 7 repetitions × 2 modes = 350 runs.
- On-device telemetry (power, energy, carbon).
- Multiple pricing tiers (on-demand, spot, reserved).

**Production Verdict**:
- **onnxruntime-gpu is the default recommendation** for GPU-available systems.
- **onnxruntime-cpu preferred over transformers-cpu** for CPU-only systems.
- Pricing tier lever (spot vs on-demand) provides 69.8% cost savings.

---

### TR120: The "Compile Paradox" Root-Cause Audit

**File**: [Technical_Report_120.md](../outputs/publish_ready/reports/Technical_Report_120.md)

**Objective**: Root-cause audit of why "-compile" backend wins mean while losing median.

**Key Findings**:
- **TR117's "compile paradox" is real but misattributed**: Label-only, no actual torch.compile() call path.
- **When torch.compile is actually enabled**: Prefill becomes fast at p50 but develops heavy tail.
- **Shape stability fix**: Padding/bucketing collapses compiled tail (p99 drops to sub-millisecond).
- **KV-cached decode**: Inductor improves prefill but regresses KV decode.

**Methodology**:
- Backend label audit (TR117 codebase review).
- Controlled reproduction with explicit compile attempts (TR120 runner).
- Shape stability experiments (padding/bucketing).

**Production Verdict**:
- **Do not rely on backend labels** - wire compilation explicitly and record compile metadata.
- **Treat prefill and decode as separate optimization targets**.
- **Stabilize shapes** (padding/bucketing) or use dynamic strategy for shape polymorphism.
- **Gate compile availability** on Triton (Windows/Python combos cannot run Inductor on GPU).

---

### TR121v1: Model Scaling Study

**File**: [Technical_Report_121v1.md](../outputs/publish_ready/reports/Technical_Report_121v1.md)

**Objective**: How inference behavior changes from ~5M to ~20B parameters (HF + Ollama).

**Key Findings**:
- **Scaling pipeline established**: Consistent phase definitions (prefill vs decode).
- **Two-family study**: HF local models (5M-124M) + Ollama models (270M-20B).
- **Artifact-backed measurements**: Ready for full matrix sweep.

**Methodology**:
- Consistent phase definitions (prefill vs KV decode).
- Fixed decode token budget (gen_tokens).
- Artifact-backed measurements for extension.

**Status**: ✅ Pipeline complete (scaling harness established, ready for full sweep).

**Note**: This is the pipeline draft; full matrix run pending for publish-ready report.

---

### TR122: Resource Profiling Deep Dive

**File**: Planned (see [experiments/tr122/README.md](../../experiments/tr122/README.md))

**Status**: 🔬 Planned (Target: Week of 2026-01-06)

**Research Question**: Where do resources (GPU VRAM, CPU RAM, power, thermal) bottleneck?

**Scope**:
- Full instrumentation (GPU memory, CPU memory, swap, power, temp).
- Per-layer profiling (attention vs MLP vs sampling).
- KV cache analysis (memory growth, eviction).
- Thermal throttling detection.
- Optimization experiments (cache offloading, mixed precision).

**Expected Deliverables**:
1. Resource telemetry with <1% overhead.
2. Bottleneck identification (e.g., "VRAM at 89% causes 2x slowdown").
3. 3+ validated optimization strategies.
4. Technical report with production tuning guide.

---

### TR123: Multi-Hardware Generalization

**File**: Planned (see [experiments/tr123/README.md](../../experiments/tr123/README.md))

**Status**: 🔬 Planned (Target: Week of 2026-01-13)

**Research Question**: Do TR117 findings generalize across GPU types, CPU architectures, and cloud providers?

**Scope**:
- Hardware matrix: NVIDIA (RTX 4080, A100, H100), AMD, Apple M-series.
- CPU comparison: Intel Xeon vs AMD EPYC vs ARM Graviton.
- Cloud validation: AWS g5 vs Azure NC vs GCP A2.
- Real workload traces (1M production requests).
- Cross-platform reproducibility (Linux, macOS, Windows).

**Expected Deliverables**:
1. 3+ GPU types, 2+ CPU architectures tested.
2. Findings replicated on 2+ cloud providers.
3. Hardware-specific decision matrix.
4. Technical report with deployment guide.

---

### TR117: Root Cause Analysis of Efficiency Anomalies (Inference Track)

**File**: [Technical_Report_117.md](../outputs/publish_ready/reports/Technical_Report_117.md)

**Objective**: Benchmark local-first inference backends (CPU vs GPU, eager vs compile paths, and serving runtimes) and quantify performance + degradation.

**Key Findings**:
- **Cross-Backend Baseline**: Established performance matrix across multiple inference backends.
- **Compile Paradox**: Surfaces mean-vs-median inversion that requires attribution-correct follow-up (see TR120).
- **Degradation Tracking**: Explicit degraded reasons and accuracy gates.

**Methodology**:
- Matrix sweep across backends (torch CPU/compile, ONNX Runtime, Ollama).
- Quant modes (fp32/fp16/int8 labels).
- Capability detection and graceful degradation.

**Production Verdict**:
- Backend selection depends on workload (prefill vs generate).
- Compile labels must be verified (see TR120 for root cause).
- Accuracy gates prevent deployment of degraded backends.

---

### TR117_multi_agent: Multi-Agent Root Cause Analysis

**File**: [Technical_Report_117_multi_agent.md](../outputs/publish_ready/reports/Technical_Report_117_multi_agent.md)

**Objective**: Definitive root cause analysis of Python Ceiling, Qwen Mystery, and Ranking Flip through invasive instrumentation.

**Key Findings**:
- **Python Event Loop Saturation**: Mean lag 5.33ms, p99 12.13ms, max 15.22ms (Gemma, default buffer).
- **CPU-Bound Serialization**: Each chunk triggers JSON parsing, monopolizing single-threaded event loop.
- **Efficiency Correlation**: Loop lag + chunk gaps = 40ms cycle time → caps efficiency at ~91%.
- **Qwen Mystery**: BPE tokenizer overhead + chunk amplification explains lower efficiency.
- **Ranking Flip**: Slower models provide "breathing room" for event loop, improving efficiency.
- **Root Cause**: Single-threaded event loop cannot handle concurrent I/O without blocking.
- **Rust Advantage Confirmed**: Rust's multi-threaded runtime avoids this bottleneck entirely.

**Methodology**:
- Detailed profiling of Python event loop behavior.
- Comparison of I/O blocking patterns between Python and Rust.
- Analysis of scheduler starvation in Python async runtime.

**Production Verdict**:
- **Python limitation is structural**, not configuration-related.
- **Rust's advantage is fundamental** - multi-threaded runtime eliminates event loop lag.
- **For >86% efficiency, Rust is required** - no Python optimization can overcome this ceiling.

---

## Cross-Report Relationships

```
TR108 (Single-Inference)
    
TR109 (Python Agents)  TR110 (Python Multi-Agent)
    
TR111 (Rust Agents)  TR112 (Rust vs Python)
    
TR113 (Rust Multi-Agent Single)  TR114 (Rust Multi-Agent Dual)  TR115 (Runtime Optimization)
                                                                 |
                                                               TR116 (Cross-Model)
                                                                 |
                                                               TR117 (Multi-Agent Root Cause)
```

**Research Progression**:
1. **TR108**: Establishes baseline single-inference optimization
2. **TR109**: Extends to Python agent workflows
3. **TR110**: Multi-agent concurrent execution (Python)
4. **TR111**: Rust single-agent baseline
5. **TR112**: Cross-language single-agent comparison
6. **TR113**: Rust multi-agent (identifies bottleneck)
7. **TR114**: Rust multi-agent (validates fix)
8. **TR115**: Rust runtime optimization (closes gap to 2.9pp, validates architecture > runtime)
9. **TR116**: Cross-model validation (proves Rust dominance holds across architectures)
10. **TR117**: Root cause analysis (identifies Python event loop lag as structural bottleneck)
11. **TR117_multi_agent**: Multi-agent root cause (quantifies event loop saturation)
12. **TR118_v2.2**: ONNX/TRT deep dive (establishes TensorRT-fp16 as optimal prefill)
13. **TR119**: Cost/energy analysis (quantifies $/token and kWh/token economics)
14. **TR120**: Compile paradox audit (root-causes TR117 compile label misattribution)
15. **TR121v1**: Model scaling study (establishes scaling pipeline from 5M to 20B)
10. **TR117**: Cross-backend inference benchmark (inference track)
11. **TR117 (Multi-Agent)**: Root cause analysis of Python efficiency ceiling (agent track)

## Key Insights Across Reports

### Single-Agent Performance
- **Python**: 99.2 tok/s (TR109)
- **Rust**: 98.9 tok/s (TR111)
- **Verdict**: Equivalent throughput, Rust superior consistency

### Multi-Agent Performance
- **Python (dual Ollama)**: 99.25% efficiency (TR110)
- **Rust (dual Ollama, optimized)**: 96.3% peak efficiency (TR115)
- **Rust (dual Ollama, baseline)**: 95.7% efficiency (TR114)
- **Rust (single Ollama)**: 82.2% efficiency (TR113)
- **Verdict**: Dual Ollama mandatory for Rust (-17.3pp without it). Runtime optimization provides marginal gains (+0.6pp)

### Configuration Optimization
- **Single-inference**: GPU=80, CTX=512, TEMP=0.8 (TR108)
- **Python agents**: GPU=60-80, CTX=512-1024, TEMP=0.6-0.8 (TR109)
- **Rust agents**: GPU=60, CTX=1024, TEMP=0.8 (TR111)
- **Python multi-agent**: GPU=80, CTX=2048, TEMP=1.0 (TR110)
- **Rust multi-agent**: GPU=80/100, CTX=512/1024, TEMP=0.8-1.0 (TR114)
- **Rust multi-agent (optimized)**: Any runtime (tokio/smol), GPU=80, CTX=512, TEMP=1.0 (TR115)

## Production Recommendations

### Single-Agent Deployments
- **Language**: Either Python or Rust (equivalent performance)
- **Config**: GPU=60-80, CTX=512-1024, TEMP=0.6-0.8
- **Choose Rust if**: Consistency critical, memory safety required
- **Choose Python if**: Peak throughput priority, existing infrastructure

### Multi-Agent Deployments
- **Language**: Python for peak throughput (99.25%), Rust for consistency (5.5pp StdDev)
- **Architecture**: **Dual Ollama mandatory** for both languages
- **Config (Python)**: GPU=80, CTX=2048, TEMP=1.0
- **Config (Rust)**: GPU=80, CTX=512, TEMP=1.0, any runtime (tokio-default/localset/smol)
- **Runtime choice**: <1pp impact - use tokio-default for simplicity
- **Choose Rust if**: Consistency > peak, memory safety, operational simplicity, 2.9pp gap acceptable
- **Choose Python if**: Absolute peak throughput required (99.25% vs 96.3%)

## Reading Guide

### For Performance Engineers
1. Start with **TR108** (single-inference baseline)
2. Read **TR109** (agent workflows)
3. Read **TR110** (multi-agent Python)
4. Read **TR114** (multi-agent Rust)

### For Language Comparison
1. Read **TR112** (single-agent comparison)
2. Compare **TR110** vs **TR114** (multi-agent comparison)

### For Production Deployment
1. Read **TR115** (latest multi-agent findings with runtime optimization)
2. Review production recommendations in each report
3. Check [Production Deployment Guide](production_deployment.md)

---

**All reports available in**: [outputs/publish_ready/reports/](../outputs/publish_ready/reports/)
