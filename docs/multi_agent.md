# Multi-Agent Architecture Guide

Complete guide to concurrent multi-agent LLM execution patterns and best practices.

## Overview

Multi-agent systems enable parallel execution of multiple LLM agents, achieving near-linear speedup (1.9-2.0x) with proper architecture. This guide covers deployment patterns, resource coordination, and optimization strategies.

## Architecture Patterns

### Pattern 1: Dual Ollama Instances (Recommended)

**Architecture**:
```
Agent 1 (DataCollector)  Ollama Instance 1 (port 11434)
Agent 2 (Insight)         Ollama Instance 2 (port 11435)
```

**Benefits**:
- True concurrent execution
- No server-level resource contention
- 95-99% parallel efficiency

**Requirements**:
- Two separate Ollama processes
- Different ports (11434, 11435)
- Separate model directories (optional)

**Setup**:
```bash
# Windows
.\scripts\windows\ollama\setup_dual_ollama.ps1

# Manual
# Terminal 1
OLLAMA_HOST=127.0.0.1:11434 ollama serve

# Terminal 2
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

### Pattern 2: Single Ollama Instance (Not Recommended)

**Architecture**:
```
Agent 1 (DataCollector) 
                           Ollama Instance (port 11434)
Agent 2 (Insight)        
```

**Drawbacks**:
- Sequential model loading
- Resource contention (74% contention rate)
- Reduced efficiency (72-82% vs 95-99%)

**When to Use**:
- Development/testing only
- Resource-constrained environments
- Single-agent workloads

## Deployment Scenarios

### Scenario 1: Baseline vs Chimera

**Configuration**:
- Agent 1: Baseline (Ollama defaults)
- Agent 2: Chimera-optimized

**Use Case**: Mixed deployment, gradual migration

**Performance**:
- Peak efficiency: 97.9% (Python)
- Mean efficiency: ~85-90%
- Contention: Moderate (33% in Python)

**Example**:
```python
# Python
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario baseline_vs_chimera \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0
```

### Scenario 2: Heterogeneous Chimera

**Configuration**:
- Agent 1: Chimera (GPU=80, CTX=512, TEMP=0.8)
- Agent 2: Chimera (GPU=100, CTX=1024, TEMP=1.0)

**Use Case**: Asymmetric workloads, different optimization targets

**Performance**:
- Peak efficiency: 99.0% (Python), 95.7% (Rust)
- Mean efficiency: ~90-95%
- Contention: Low (<10%)

**Example**:
```python
# Python
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_hetero \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

### Scenario 3: Homogeneous Chimera (Recommended)

**Configuration**:
- Agent 1: Chimera (GPU=80, CTX=2048, TEMP=1.0)
- Agent 2: Chimera (GPU=80, CTX=2048, TEMP=1.0)

**Use Case**: Production deployment, maximum throughput

**Performance**:
- Peak efficiency: 99.25% (Python), 95.7% (Rust)
- Mean efficiency: ~92-95%
- Contention: Minimal (<6%)

**Example**:
```python
# Python
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0

# Rust
cargo run --release -- \
  --scenario chimera_homo \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 1.0 \
  --collector-ollama-url http://localhost:11434 \
  --insight-ollama-url http://localhost:11435
```

## Implementation Details

### Python Implementation

**Concurrency Model**: `asyncio.gather()`

```python
import asyncio

async def run_multiagent():
    # Concurrent execution
    results = await asyncio.gather(
        agent1.run(),
        agent2.run()
    )
    return results
```

**Resource Coordination**: Semaphore-based

```python
from asyncio import Semaphore

coordinator = Semaphore(max_concurrent=2)

async def agent_with_coordination(agent):
    async with coordinator:
        return await agent.run()
```

**Metrics Collection**:
- Wall-clock time (concurrent execution)
- Sequential estimated time (sum of individual)
- Speedup = sequential / concurrent
- Efficiency = (speedup / 2) * 100%

### Rust Implementation

**Concurrency Model**: `tokio::try_join!`

```rust
use tokio::try_join;

async fn run_multiagent() -> Result<()> {
    let (result1, result2) = try_join!(
        agent1.run(),
        agent2.run()
    )?;
    Ok((result1, result2))
}
```

**Resource Coordination**: Semaphore-based

```rust
use tokio::sync::Semaphore;

let coordinator = Arc::new(Semaphore::new(2));

async fn agent_with_coordination(agent: Agent) -> Result<()> {
    let permit = coordinator.acquire().await?;
    let result = agent.run().await;
    drop(permit);
    Ok(result)
}
```

**Metrics Collection**:
- Same as Python
- Additional tokio runtime metrics

## Performance Characteristics

### Python Multi-Agent (TR110)

**Peak Performance**:
- Efficiency: 99.25%
- Speedup: 1.985x
- Config: GPU=80, CTX=2048, TEMP=1.0

**Mean Performance**:
- Efficiency: ~92.7%
- Speedup: ~1.85x
- Contention: 33% (mostly at GPU=60)

**Consistency**:
- StdDev: 7.4pp
- CV: ~8%

### Rust Multi-Agent (TR115 - Optimized)

**Peak Performance**:
- Efficiency: 96.3% (smol-1KB runtime)
- Speedup: 1.93x
- Config: GPU=80, CTX=512, TEMP=1.0, homogeneous

**Mean Performance**:
- Efficiency: ~90% (across all successful runtimes)
- Speedup: ~1.80x
- Contention: 6% (all at CTX1024)

**Consistency**:
- StdDev: 5.5pp
- CV: ~6%

### Rust Multi-Agent (TR114 - Baseline)

**Peak Performance**:
- Efficiency: 95.7%
- Speedup: 1.914x
- Config: GPU=80/100 hetero, CTX=512/1024

**Mean Performance**:
- Efficiency: 89.3%
- Speedup: ~1.79x
- Contention: 6% (all at CTX1024)

**Consistency**:
- StdDev: 5.5pp
- CV: ~6%

### Comparison

| Metric | Python | Rust (TR115) | Rust (TR114) | Winner |
|--------|--------|--------------|--------------|--------|
| Peak Efficiency | 99.25% | 96.3% | 95.7% | **Python** |
| Mean Efficiency | ~92.7% | ~90% | 89.3% | **Python** |
| Consistency | 7.4pp | 5.5pp | 5.5pp | **Rust** |
| Contention | 33% | 6% | 6% | **Rust** |

## Optimization Strategies

### Strategy 1: Maximize Throughput (Python)

**Configuration**:
```python
{
    "scenario": "chimera_homo",
    "num_gpu": 80,
    "num_ctx": 2048,
    "temperature": 1.0
}
```

**Expected**:
- Efficiency: 99.25%
- Speedup: 1.985x

### Strategy 2: Maximize Consistency (Rust)

**Configuration**:
```python
{
    "scenario": "chimera_homo",
    "num_gpu": 80,
    "num_ctx": 512,  # Smaller for Rust
    "temperature": 1.0
}
```

**Expected**:
- Efficiency: 96.3% peak (95-96% typical)
- Speedup: 1.93x peak (1.80-1.90x typical)
- StdDev: 5.5pp (better consistency)
- **Runtime choice**: <1pp impact - use tokio-default for simplicity

### Strategy 3: Minimize Contention

**Configuration**:
```python
{
    "scenario": "chimera_homo",
    "num_gpu": 80,  # Minimum for contention-free
    "num_ctx": 512,  # Smaller = less contention
    "temperature": 1.0
}
```

**Expected**:
- Contention: <6%
- Efficiency: 95-99%

## Resource Contention

### Detection

**Symptoms**:
- TTFT anomalies (>10s baseline increase)
- Throughput degradation (>20% drop)
- Efficiency <80%

**Monitoring**:
```python
# Check for contention
if ttft_delta > 10000:  # 10 seconds
    print("Contention detected!")
```

### Prevention

1. **Dual Ollama Instances**: Mandatory for production
2. **GPU80**: Minimum for contention-free execution
3. **CTX512 (Rust)**: Prevents cache thrashing
4. **CTX2048 (Python)**: Optimal for Python

### Mitigation

1. **Reduce Context Size**: Smaller KV cache
2. **Increase GPU Layers**: Better resource allocation
3. **Stagger Agent Starts**: Avoid simultaneous loading
4. **Monitor VRAM**: Ensure sufficient headroom

## Metrics and Monitoring

### Key Metrics

**Concurrency Speedup**:
```
speedup = sequential_time / concurrent_time
```

**Parallel Efficiency**:
```
efficiency = (speedup / num_agents) * 100%
```

**TTFT Delta**:
```
ttft_delta = |agent1_ttft - agent2_ttft|
```

**Throughput Delta**:
```
throughput_delta = |agent1_throughput - agent2_throughput|
```

### Monitoring Dashboard

```python
# Example monitoring
metrics = {
    "speedup": 1.985,
    "efficiency": 99.25,
    "ttft_delta": 45,  # ms
    "throughput_delta": 0.3,  # tok/s
    "contention": False
}
```

## Production Deployment

### Checklist

- [ ] Dual Ollama instances running
- [ ] Ports 11434 and 11435 accessible
- [ ] GPU80 layers configured
- [ ] Context size optimized (2048 Python, 512 Rust)
- [ ] Resource monitoring enabled
- [ ] Contention detection configured
- [ ] Fallback to single-agent if needed

### Configuration

**Python**:
```python
# Production config
PRODUCTION_CONFIG = {
    "scenario": "chimera_homo",
    "num_gpu": 80,
    "num_ctx": 2048,
    "temperature": 1.0,
    "runs": 5,
    "collector_ollama_url": "http://localhost:11434",
    "insight_ollama_url": "http://localhost:11435"
}
```

**Rust**:
```rust
// Production config
let config = Config {
    scenario: "chimera_homo",
    num_gpu: 80,
    num_ctx: 512,
    temperature: 1.0,
    runs: 5,
    collector_ollama_url: "http://localhost:11434",
    insight_ollama_url: "http://localhost:11435",
};
```

## References

- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)
- [TR113: Rust Multi-Agent (Single Ollama)](../outputs/publish_ready/reports/Technical_Report_113.md)
- [TR114: Rust Multi-Agent (Dual Ollama)](../outputs/publish_ready/reports/Technical_Report_114.md)
- [TR115: Rust Runtime Optimization](../outputs/publish_ready/reports/Technical_Report_115.md)
- [Dual Ollama Setup](dual_ollama_setup.md)
- [Chimera Optimization](chimera_optimization.md)

---

**Last Updated**: November 2025  
**Based on**: Technical Reports 110, 113, 114, 115

