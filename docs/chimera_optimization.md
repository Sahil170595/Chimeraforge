# Chimera Optimization Guide

Complete guide to optimizing LLM performance using Chimera configuration parameters.

## Overview

Chimera optimization is a set of strategies for maximizing LLM inference performance through systematic tuning of GPU layer allocation, context window size, and sampling parameters. Based on comprehensive benchmarking (Technical Reports 108-114), Chimera can achieve 30-40% throughput improvements over baseline configurations.

## Key Parameters

### GPU Layer Allocation (`num_gpu`)

**What it does**: Controls how many transformer layers are offloaded to GPU.

**Impact**:
- **Critical parameter** - Single most important for performance
- More layers = higher GPU utilization, lower CPU overhead
- Too many layers = VRAM exhaustion
- Too few layers = CPU bottleneck

**Optimal Values** (RTX 4080, 12GB VRAM):
- **Single-agent**: 60-80 layers
- **Multi-agent**: 80 layers (minimum for contention-free)
- **Maximum**: 120 layers (model-dependent)

**Recommendations**:
```python
# Single-agent (gemma3:latest)
num_gpu = 80  # Optimal balance

# Multi-agent (gemma3:latest)
num_gpu = 80  # Prevents contention

# Memory-constrained
num_gpu = 60  # Safer for 8GB VRAM
```

### Context Window Size (`num_ctx`)

**What it does**: Maximum number of tokens the model can consider in context.

**Impact**:
- Larger context = better coherence, higher memory usage
- Smaller context = faster inference, lower memory
- Affects KV cache size (quadratic scaling)

**Optimal Values**:
- **Single-agent**: 512-1024 tokens
- **Multi-agent (Python)**: 2048 tokens
- **Multi-agent (Rust)**: 512 tokens (cache thrashing at larger sizes)

**Recommendations**:
```python
# Single-agent
num_ctx = 512   # Fast, efficient
num_ctx = 1024  # Better quality, slightly slower

# Multi-agent (Python)
num_ctx = 2048  # Optimal for concurrent execution

# Multi-agent (Rust)
num_ctx = 512   # Avoids tokio cache thrashing
```

### Temperature (`temperature`)

**What it does**: Controls randomness in token sampling.

**Impact**:
- Lower (0.6-0.8) = more deterministic, faster TTFT
- Higher (0.8-1.0) = more creative, slightly slower
- Minimal impact on throughput (<3%)

**Optimal Values**:
- **Single-agent**: 0.6-0.8
- **Multi-agent**: 0.8-1.0
- **Quality-critical**: 0.6-0.7
- **Creative tasks**: 0.8-1.0

**Recommendations**:
```python
# Balanced
temperature = 0.8

# Quality-focused
temperature = 0.6

# Creative tasks
temperature = 1.0
```

### Additional Parameters

**Top-p (Nucleus Sampling)**:
- Default: 0.9
- Range: 0.8-0.95
- Impact: Minimal on performance, affects quality

**Top-k**:
- Default: 40
- Range: 20-50
- Impact: Minimal on performance, affects diversity

**Repeat Penalty**:
- Default: 1.1
- Range: 1.0-1.2
- Impact: Prevents repetition, minimal performance cost

## Optimization Strategies

### Strategy 1: Single-Agent Optimization

**Goal**: Maximize throughput for single-agent workloads.

**Optimal Configuration**:
```python
{
    "num_gpu": 80,
    "num_ctx": 512,
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1
}
```

**Expected Performance**:
- Throughput: 98-103 tok/s (gemma3:latest)
- TTFT: <500ms
- VRAM: ~6-8GB

**Trade-offs**:
- Lower context (512) = faster, less coherence
- Higher context (1024) = slower, better quality

### Strategy 2: Multi-Agent Optimization (Python)

**Goal**: Maximize concurrent throughput.

**Optimal Configuration**:
```python
{
    "num_gpu": 80,
    "num_ctx": 2048,
    "temperature": 1.0,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1
}
```

**Expected Performance**:
- Efficiency: 99.25% (1.985x speedup)
- Throughput: ~99 tok/s per agent
- VRAM: ~10-12GB total

**Requirements**:
- **Dual Ollama instances** (mandatory)
- Ports 11434 and 11435
- 12GB+ VRAM

### Strategy 3: Multi-Agent Optimization (Rust)

**Goal**: Maximize concurrent throughput with Rust.

**Optimal Configuration**:
```python
{
    "num_gpu": 80,
    "num_ctx": 512,  # Smaller due to tokio cache thrashing
    "temperature": 1.0,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1
}
```

**Expected Performance**:
- Efficiency: 95.7% (1.914x speedup)
- Throughput: ~99 tok/s per agent
- VRAM: ~8-10GB total

**Requirements**:
- **Dual Ollama instances** (mandatory)
- Ports 11434 and 11435
- 12GB+ VRAM

### Strategy 4: Memory-Constrained Optimization

**Goal**: Optimize for limited VRAM (8GB).

**Optimal Configuration**:
```python
{
    "num_gpu": 60,
    "num_ctx": 512,
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1
}
```

**Expected Performance**:
- Throughput: 95-98 tok/s
- TTFT: <600ms
- VRAM: ~5-6GB

**Trade-offs**:
- Lower GPU layers = more CPU usage
- Acceptable for single-agent workloads

## Performance Tuning Workflow

### Step 1: Baseline Measurement

```bash
# Run baseline (no Chimera)
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 3
```

**Record**:
- Baseline throughput
- Baseline TTFT
- VRAM usage

### Step 2: GPU Layer Sweep

```bash
# Test different GPU layer allocations
for gpu in 60 80 100 120; do
  python src/python/banterhearts/demo_agent/run_demo.py \
    --runs 3 \
    --chimera-num-gpu $gpu \
    --chimera-num-ctx 512 \
    --chimera-temperature 0.8
done
```

**Find**:
- Maximum GPU layers before VRAM exhaustion
- Optimal balance point (usually 80)

### Step 3: Context Size Optimization

```bash
# Test different context sizes
for ctx in 256 512 1024 2048; do
  python src/python/banterhearts/demo_agent/run_demo.py \
    --runs 3 \
    --chimera-num-gpu 80 \
    --chimera-num-ctx $ctx \
    --chimera-temperature 0.8
done
```

**Find**:
- Context size with best throughput/quality trade-off
- Memory constraints

### Step 4: Temperature Tuning

```bash
# Test different temperatures
for temp in 0.6 0.8 1.0; do
  python src/python/banterhearts/demo_agent/run_demo.py \
    --runs 3 \
    --chimera-num-gpu 80 \
    --chimera-num-ctx 512 \
    --chimera-temperature $temp
done
```

**Find**:
- Temperature for desired quality/creativity balance
- Minimal impact on throughput

### Step 5: Validate Configuration

```bash
# Run comprehensive test
python src/python/banterhearts/demo_agent/run_demo.py \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

**Verify**:
- Consistent performance across runs
- No VRAM exhaustion
- Acceptable TTFT

## Configuration Presets

### Preset 1: Maximum Throughput

```python
{
    "num_gpu": 80,
    "num_ctx": 512,
    "temperature": 0.8
}
```

**Use case**: High-throughput batch processing

### Preset 2: Quality Focused

```python
{
    "num_gpu": 80,
    "num_ctx": 1024,
    "temperature": 0.6
}
```

**Use case**: Quality-critical applications

### Preset 3: Multi-Agent (Python)

```python
{
    "num_gpu": 80,
    "num_ctx": 2048,
    "temperature": 1.0
}
```

**Use case**: Concurrent multi-agent execution

### Preset 4: Multi-Agent (Rust)

```python
{
    "num_gpu": 80,
    "num_ctx": 512,
    "temperature": 1.0
}
```

**Use case**: Rust-based concurrent execution

### Preset 5: Memory Efficient

```python
{
    "num_gpu": 60,
    "num_ctx": 512,
    "temperature": 0.8
}
```

**Use case**: Limited VRAM (8GB)

## Troubleshooting

### Low Throughput

**Symptoms**: Throughput <90 tok/s

**Solutions**:
1. Increase `num_gpu` (if VRAM allows)
2. Reduce `num_ctx` (512 is optimal)
3. Check GPU utilization: `nvidia-smi`
4. Ensure no background processes

### High TTFT

**Symptoms**: TTFT >1000ms

**Solutions**:
1. Reduce `num_ctx` (smaller KV cache)
2. Lower `temperature` (faster sampling)
3. Check model loading time
4. Verify streaming is working

### VRAM Exhaustion

**Symptoms**: OOM errors, model fails to load

**Solutions**:
1. Reduce `num_gpu` (try 60)
2. Reduce `num_ctx` (try 256)
3. Close other GPU applications
4. Use smaller model variant

### Inconsistent Performance

**Symptoms**: High variance across runs

**Solutions**:
1. Increase number of runs (5+)
2. Ensure no background processes
3. Check for thermal throttling
4. Verify stable power supply

## References

- [TR108: Single-Inference Optimization](../outputs/publish_ready/reports/Technical_Report_108.md)
- [TR109: Python Agent Workflows](../outputs/publish_ready/reports/Technical_Report_109.md)
- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)
- [TR111: Rust Single-Agent](../outputs/publish_ready/reports/Technical_Report_111.md)
- [TR114: Rust Multi-Agent](../outputs/publish_ready/reports/Technical_Report_114.md)

---

**Last Updated**: November 2025

