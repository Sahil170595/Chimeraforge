# Banterhearts Technical Reports

This directory contains comprehensive technical reports documenting LLM performance analysis, optimization strategies, and multi-agent orchestration capabilities in the Chimera Heart project.

## 📊 Technical Reports Overview

### TR108: Single-Agent LLM Performance Analysis
**File:** `Technical_Report_108.md`

- **Focus:** Comprehensive LLM performance benchmarking and optimization
- **Models:** gemma3:latest, llama3.1:8b-instruct variants
- **Hardware:** NVIDIA RTX 4080 (12GB VRAM), i9-13980HX
- **Key Findings:** Optimal configurations for single-agent inference
- **Test Matrix:** 150+ benchmark runs across parameter sweeps
- **Status:** ✅ Complete (Publication-ready)

### TR109: Agent Workflow Optimization
**File:** `Technical_Report_109.md`

- **Focus:** Agent workflow performance vs single-inference optimization
- **Methodology:** Process isolation, forced cold starts, statistical validation
- **Key Findings:** Agent tasks require different optimization than single-inference
- **Optimal Config:** GPU=60, CTX=512, TEMP=0.8 for agent workflows
- **Quality Analysis:** Automated scoring methodology for report quality
- **Status:** ✅ Complete (Publication-ready)

### TR110: Concurrent Multi-Agent Performance Analysis
**File:** `banterhearts/demo_multiagent/reports/Technical_Report_110.md`

- **Focus:** Parallel agent execution with resource coordination
- **Test Matrix:** 30 configurations × 5 runs = 150 benchmark runs
- **Key Findings:** 99.25% parallel efficiency achieved with homogeneous Chimera agents
- **Scenarios:** Baseline vs Chimera, Heterogeneous, Homogeneous configurations
- **Resource Analysis:** VRAM utilization, memory bandwidth saturation, contention patterns
- **Status:** ✅ Complete (Publication-ready)

---

## 🔬 Model Benchmarks

### Gemma3 (Google)
**Location:** `reports/gemma3/`

- **Model:** gemma3:latest (4.3B parameters, Q4_K_M quantization, 3.3GB)
- **Test Date:** 2025-10-08
- **GPU:** NVIDIA GeForce RTX 4080 (12GB VRAM, 9,728 CUDA cores)
- **CPU:** Intel Core i9-13980HX (24 cores, 32 threads)

**Key Results:**
- ⚡ **102.85 tokens/s** average throughput
- 🚀 **0.165s** mean TTFT (warm)
- 💾 **5.3 GB** GPU memory usage
- 🏆 **34% faster** than Llama3.1 q4_0

**Files:**
- `Gemma3_Benchmark_Report.md` - Full detailed report
- `gemma3_baseline.json` - Baseline performance data
- `gemma3_param_tuning.csv` - Parameter sweep results
- `gemma3_param_tuning_summary.csv` - Top configurations

**Also see:** `docs/Gemma3_Benchmark_Report.md` for documentation

---

### Llama3.1 (Meta)
**Location:** `reports/llama3/`

- **Models:** llama3.1:8b-instruct (q4_0, q5_K_M, q8_0)
- **Test Date:** 2025-09-30
- **GPU:** NVIDIA GeForce RTX 4080 (12GB VRAM, 9,728 CUDA cores)
- **CPU:** Intel Core i9-13980HX (24 cores, 32 threads)

**Key Results (q4_0):**
- ⚡ **76.59 tokens/s** average throughput  
- 🚀 **0.097s** mean TTFT (warm)
- 📦 **4.7 GB** model size

**Files:**
- `ollama_benchmark_summary.md` - Concise summary
- `ollama_quant_bench.csv` - Quantization comparison data
- `ollama_param_tuning.csv` - Parameter sweep results
- `baseline_system_metrics.json` - System telemetry
- `baseline_ml_report.txt` - ML metrics report
- `artifacts/` - Performance visualizations (PNG charts)

**Also see:** `docs/Ollama_Benchmark_Report.md` for full documentation

---

## 🔬 Comparative Analysis

| Metric | Gemma3:latest | Llama3.1:8b-q4_0 | Winner |
|--------|---------------|------------------|--------|
| **Model Size** | 3.3 GB | 4.7 GB | Gemma3 ✅ (-30%) |
| **Parameters** | 4.3B | 8B | Gemma3 ✅ (smaller) |
| **Throughput** | 102.85 tok/s | 76.59 tok/s | Gemma3 ✅ (+34%) |
| **TTFT (warm)** | 0.165 s | 0.097 s | Llama3.1 ✅ (faster) |
| **GPU Memory** | 5.3 GB | ~6-7 GB | Gemma3 ✅ (lower) |
| **Best Config** | 102.31 tok/s | 78.42 tok/s | Gemma3 ✅ (+30%) |

### Recommendation 🏆
**Choose Gemma3 for production gaming banter:**
- 34% faster token generation (critical for real-time applications)
- 30% smaller model (easier deployment)
- Better GPU efficiency
- Trade-off: +0.07s TTFT (negligible for gaming)

---

## 📁 Repository Structure

```
reports/
├── README.md (this file)
├── Technical_Report_108.md - Single-agent LLM performance analysis
├── Technical_Report_109.md - Agent workflow optimization
├── gemma3/
│   ├── Gemma3_Benchmark_Report.md
│   ├── gemma3_baseline.json
│   ├── gemma3_baseline.csv
│   ├── gemma3_param_tuning.csv
│   └── gemma3_param_tuning_summary.csv
├── llama3/
│   ├── ollama_benchmark_summary.md
│   ├── ollama_quant_bench.csv
│   ├── ollama_param_tuning.csv
│   ├── baseline_system_metrics.json
│   ├── baseline_ml_report.txt
│   └── artifacts/
│       ├── quant_tokens_per_sec.png
│       ├── quant_ttft.png
│       ├── param_ttft_vs_tokens.png
│       └── param_heatmap_temp_*.png
├── compilation/
│   └── (model compilation benchmarks)
├── quantization/
│   └── (quantization strategy reports)
└── ollama/
    └── (historical Ollama benchmark data)
```

**Demo Frameworks:**
```
banterhearts/
├── demo_agent/ - Single-agent optimization demo
│   ├── run_demo.py
│   ├── agents/
│   ├── config/
│   └── reports/
└── demo_multiagent/ - Concurrent multi-agent demo
    ├── run_multiagent_demo.py
    ├── orchestrator.py
    ├── coordinator.py
    ├── agents/
    └── reports/
        └── Technical_Report_110.md
```

---

## 🚀 Quick Start

### Run Technical Report Demos
```bash
# Single-agent optimization demo (TR109)
python banterhearts/demo_agent/run_demo.py

# Multi-agent concurrent execution demo (TR110)
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 3 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0
```

### Run Gemma3 Benchmark
```bash
# Pull model
ollama pull gemma3:latest

# Run comprehensive benchmark
python scripts/ollama/gemma3_comprehensive_benchmark.py

# Results saved to reports/gemma3/
```

### Run Llama3 Benchmark  
```bash
# Pull models
ollama pull llama3.1:8b-instruct-q4_0
ollama pull llama3.1:8b-instruct-q5_K_M
ollama pull llama3.1:8b-instruct-q8_0

# Run quantization sweep (see docs/Ollama_Benchmark_Report.md)
```

---

## 📖 Documentation

### Full Reports
- **Gemma3:** `docs/Gemma3_Benchmark_Report.md`
- **Llama3.1:** `docs/Ollama_Benchmark_Report.md`

### Additional Resources
- **Quantization Guide:** `docs/quantization_system.md`
- **Compilation Benchmarks:** `docs/model_compilation.md`
- **Performance Deep Dive:** `docs/Performance_Deep_Dive.md`

---

## ⚙️ Recommended Production Settings

### Gemma3 (Optimal for Gaming)
```yaml
model: gemma3:latest
options:
  num_gpu: 999      # Full GPU offload
  num_ctx: 4096     # Large context window
  temperature: 0.4  # Balanced creativity
  top_p: 0.9

Expected: 102.31 tokens/s @ 0.128s TTFT
```

### Llama3.1 (Lower Latency Start)
```yaml
model: llama3.1:8b-instruct-q4_0
options:
  num_gpu: 40       # Optimized layers
  num_ctx: 1024     # Fast context
  temperature: 0.4
  top_p: 0.9

Expected: 78.42 tokens/s @ 0.088s TTFT
```

---

## 📊 Benchmark Methodology

All benchmarks follow standardized methodology:

1. **Hardware:** NVIDIA RTX 4080 (12GB VRAM, 9,728 CUDA cores), Intel Core i9-13980HX (24 cores, 32 threads)
2. **Prompts:** 5 gaming banter scenarios from `prompts/banter_prompts.txt`
3. **Metrics:** TTFT, tokens/second, GPU utilization, memory usage
4. **Parameters:** Sweep across num_gpu, num_ctx, temperature
5. **Validation:** GPU usage confirmed via `ollama ps` and `nvidia-smi`

---

**Last Updated:** 2025-10-10  
**Maintainer:** Chimera Heart Development Team

