# Benchmarking Guide

Complete guide to running benchmarks for single-agent and multi-agent LLM performance evaluation.

## Overview

Chimeraforge (the Banterhearts benchmarking breakout) provides comprehensive
benchmarking tools for:
- **Single-agent performance**: Throughput, TTFT, resource usage
- **Multi-agent concurrent execution**: Speedup, efficiency, contention analysis
- **Cross-language comparison**: Python vs Rust performance evaluation

## Prerequisites

### Required Software
- **Python 3.11+** (for Python agents)
- **Rust 1.70+** (for Rust agents)
- **Ollama** (model serving)
- **NVIDIA GPU** (12GB+ VRAM recommended)
- **CUDA 11.8+** (for GPU acceleration)

### Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Build Rust agents (optional)
cd src/rust/demo_agent && cargo build --release
cd ../demo_multiagent && cargo build --release
cd ../../..

# Pull model
ollama pull gemma3:latest
```

## Quick Start

### Python Single-Agent Benchmark

```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

**Output**: `src/python/banterhearts/demo_agent/demo_agent_*/` with reports and metrics.

### Python Multi-Agent Benchmark

```bash
# Setup dual Ollama instances (required for true concurrency)
.\scripts\windows\ollama\setup_dual_ollama.ps1  # Windows
# or manually start two Ollama instances on ports 11434/11435

python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0
```

**Output**: `src/python/banterhearts/demo_multiagent/comprehensive_test_results/` with per-run metrics.

### Rust Single-Agent Benchmark

```bash
cd src/rust/demo_agent
cargo run --release -- \
  --model gemma3:latest \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8 \
  --output-dir rust_results/test_80_512_08
```

**Output**: `rust_results/test_80_512_08/` with reports and metrics.json.

### Rust Multi-Agent Benchmark

```bash
# Setup dual Ollama instances
.\scripts\windows\ollama\setup_dual_ollama.ps1

# Run comprehensive benchmark (30 configs, 150 runs)
python run_rust_multiagent_dual_ollama_sweep.py
```

**Output**: `src/rust/demo_multiagent/Demo_rust_multiagent_results_tr110_dual/` with phase-organized results.

### Rust Runtime Optimization Benchmark (TR115)

```bash
# Setup dual Ollama instances
.\scripts\windows\ollama\setup_dual_ollama.ps1

# Run TR115 runtime optimization sweep (5 runtimes, 750 total runs)
cd experiments/TR115_runtime_optimization/scripts
python run_tr115_sweep.py
cd ../../..
```

**Output**: `experiments/TR115_runtime_optimization/results/` with per-runtime results.

**Runtime Variants**:
- `runtime-tokio-default`: Standard Tokio runtime
- `runtime-tokio-localset`: Tokio LocalSet (single-threaded)
- `runtime-async-std`: Async-std runtime ( 50% efficiency - not recommended)
- `runtime-smol`: Smol runtime
- `runtime-smol-1kb`: Smol with custom 1KB HTTP buffering

## Benchmark Types

### 1. Single-Agent Benchmarks

**Purpose**: Evaluate individual agent performance with various configurations.

**Metrics Collected**:
- Throughput (tokens/second)
- Time to First Token (TTFT)
- Prompt evaluation duration
- Generation evaluation duration
- Model load duration
- Memory usage
- CPU usage

**Use Cases**:
- Configuration optimization
- Baseline performance measurement
- Language comparison

### 2. Multi-Agent Concurrent Benchmarks

**Purpose**: Evaluate concurrent execution of multiple agents.

**Metrics Collected**:
- Concurrency speedup (sequential_time / concurrent_time)
- Parallel efficiency (speedup / ideal_speedup)
- TTFT delta between agents
- Throughput delta between agents
- Resource contention events
- Wall-clock time vs sequential time

**Scenarios**:
- **Baseline vs Chimera**: Mixed deployment (one baseline, one optimized)
- **Heterogeneous**: Both optimized, different configurations
- **Homogeneous**: Both optimized, identical configuration

**Use Cases**:
- Multi-agent system design
- Resource allocation optimization
- Concurrency bottleneck identification

## Configuration Options

### Chimera Optimization Parameters

| Parameter | Description | Typical Range | Default |
|-----------|-------------|---------------|---------|
| `num_gpu` | GPU layers to offload | 60-120 | Ollama default |
| `num_ctx` | Context window size | 512-2048 | Ollama default |
| `temperature` | Sampling temperature | 0.6-1.0 | Ollama default |
| `top_p` | Top-p sampling | 0.9-0.95 | Ollama default |
| `top_k` | Top-k sampling | 40 | Ollama default |
| `repeat_penalty` | Repeat penalty | 1.1 | Ollama default |

### Benchmark Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--runs` | Number of runs per configuration | 3-5 |
| `--model` | Ollama model to benchmark | gemma3:latest |
| `--output-dir` | Output directory for results | auto-generated |
| `--scenario` | Multi-agent scenario (multi-agent only) | baseline_vs_chimera |

## Running Parameter Sweeps

### Python Single-Agent Sweep

```bash
# Manual sweep
for gpu in 60 80 120; do
  for ctx in 512 1024 2048; do
    python src/python/banterhearts/demo_agent/run_demo.py \
      --runs 5 \
      --chimera-num-gpu $gpu \
      --chimera-num-ctx $ctx \
      --chimera-temperature 0.8
  done
done
```

### Rust Single-Agent Sweep

```bash
# Use automated sweep script
python run_rust_benchmark_sweep.py
```

**Output**: `rust_benchmark_results/benchmark_results.json`

### Python Multi-Agent Sweep

```bash
# Comprehensive sweep (matches TR110 methodology)
python -m banterhearts.demo_multiagent.run_comprehensive_test \
  --phases all \
  --runs 5
```

### Rust Multi-Agent Sweep

```bash
# Full TR114 methodology (30 configs, 150 runs)
python run_rust_multiagent_dual_ollama_sweep.py
```

### Rust Runtime Optimization Sweep (TR115)

```bash
# Full TR115 methodology (5 runtimes  30 configs  5 runs = 750 benchmarks)
cd experiments/TR115_runtime_optimization/scripts
python run_tr115_sweep.py
cd ../../..
```

**Note**: This is a comprehensive study comparing async runtime performance. See [TR115](../outputs/publish_ready/reports/Technical_Report_115.md) for detailed analysis.

## Analyzing Results

### Python Results

**Location**: `src/python/banterhearts/demo_agent/demo_agent_*/` or `src/python/banterhearts/demo_multiagent/comprehensive_test_results/`

**Files**:
- `comparison_report.md`: Side-by-side baseline vs Chimera comparison
- `metrics.json`: Raw metrics for analysis

**Analysis**:
```bash
# Use analysis notebooks
jupyter notebook outputs/publish_ready/notebooks/TR109_Comprehensive.ipynb
```

### Rust Results

**Location**: `src/rust/demo_agent/rust_results/` or `src/rust/demo_multiagent/Demo_rust_multiagent_results_tr110_dual/`

**Files**:
- `reports/comparison_report.md`: Detailed comparison
- `data/metrics.json`: Raw metrics

**Analysis**:
```bash
# Analyze Rust single-agent results
python scripts/analyze_rust_results.py

# Analyze Rust multi-agent results (TR114)
python scripts/analyze_rust_multiagent_tr110.py

# Analyze Rust runtime optimization results (TR115)
cd experiments/TR115_runtime_optimization/scripts
python analyze_tr115_results.py
python compare_to_tr114.py
cd ../../..
```

## Benchmark Methodology

### Statistical Rigor

1. **Multiple Runs**: Minimum 3-5 runs per configuration
2. **Process Isolation**: Separate processes to avoid warm-cache bias
3. **Cold Starts**: Force model unloads between runs (Python) or natural eviction (Rust)
4. **Outlier Detection**: Identify and exclude anomalous runs
5. **Confidence Intervals**: Calculate mean  stddev for all metrics

### Fair Comparison

1. **Identical Hardware**: Same GPU, CPU, RAM
2. **Identical Model**: Same model version and quantization
3. **Identical Prompts**: Same prompt complexity and length
4. **Identical Configurations**: Same GPU/context/temperature settings
5. **Identical Methodology**: Same number of runs, same isolation strategy

### Multi-Agent Specific

1. **Dual Ollama Instances**: Separate instances on ports 11434/11435
2. **Simultaneous Start**: Both agents start at same time
3. **Resource Coordination**: Semaphore-based coordination
4. **Contention Detection**: TTFT anomalies >3s indicate contention

## Understanding Results

### Single-Agent Metrics

**Throughput**:
- Higher is better
- Typical range: 95-105 tok/s (gemma3:latest)
- Optimization target: >100 tok/s

**TTFT**:
- Lower is better
- Baseline: ~1400ms
- Optimized: <500ms
- Optimization target: <450ms

**Coefficient of Variation (CV)**:
- Lower is better (more consistent)
- Typical: 0.4-0.5%
- Excellent: <0.4%

### Multi-Agent Metrics

**Concurrency Speedup**:
- Higher is better
- Ideal: 2.0x (perfect parallelism)
- Typical: 1.6-2.0x
- Optimization target: >1.9x

**Parallel Efficiency**:
- Higher is better
- Ideal: 100%
- Typical: 85-99%
- Optimization target: >95%

**Contention Rate**:
- Lower is better
- Ideal: 0%
- Acceptable: <10%
- Problematic: >30%

## Troubleshooting

### Common Issues

**Low Throughput**:
- Check GPU utilization: `nvidia-smi`
- Verify model is loaded: `ollama list`
- Check VRAM usage: Reduce `num_gpu` or `num_ctx`
- Ensure no background processes

**High TTFT**:
- Check model loading: First run is slower
- Verify streaming is working
- Check Ollama logs for errors
- Ensure sufficient VRAM

**Inconsistent Results**:
- Increase number of runs (`--runs 5` or higher)
- Ensure no background GPU processes
- Check for thermal throttling
- Verify stable power supply

**Multi-Agent Contention**:
- Ensure dual Ollama instances are running
- Check ports 11434 and 11435 are both active
- Reduce context size or GPU layers
- Verify sufficient VRAM (12GB+ recommended)

### Debug Mode

**Python**:
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python src/python/banterhearts/demo_agent/run_demo.py ...
```

**Rust**:
```bash
# Enable trace logging
RUST_LOG=trace cargo run --release -- ...
```

## Related Documentation

- [Technical Reports](../outputs/publish_ready/reports/) - Detailed analysis
- [Chimera Optimization Guide](chimera_optimization.md) - Configuration tuning
- [Multi-Agent Architecture](multi_agent.md) - Concurrent execution
- [Rust vs Python Comparison](rust_vs_python.md) - Cross-language analysis

---

**Last Updated**: November 2025

