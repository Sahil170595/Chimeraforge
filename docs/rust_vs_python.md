# Rust vs Python Agent Performance Comparison

Comprehensive cross-language performance analysis based on Technical Reports 112_v2 and 114_v2.

## Executive Summary

| Metric | Python | Rust | Winner |
|--------|--------|------|--------|
| **Single-Agent Throughput** | 99.34 tok/s | 114.54 tok/s | **Rust** (+15.2%) |
| **Single-Agent TTFT (cold)** | 1437 ms | 603 ms | **Rust** (-58%) |
| **Single-Agent Memory** | ~250 MB | ~75 MB | **Rust** (-67%) |
| **Single-Agent Startup** | 1.5s | 0.2s | **Rust** (-83%) |
| **Single-Agent Consistency** | 4.8% CV | 2.6% CV | **Rust** (-46%) |
| **Multi-Agent Peak Config** | 99.25% | 99.396% | **Rust** (+0.15pp) |
| **Multi-Agent Mean Efficiency** | 95.8% | 98.281% | **Rust** (+2.48pp) |
| **Multi-Agent Consistency** | 7.4pp StdDev | 4.9pp StdDev | **Rust** (-34%) |
| **Contention Rate** | 10-15% | 0.74% | **Rust** (-93%) |
| **Optimization Success** | 38.9% | 72.2% | **Rust** (+85%) |

**Verdict**: Rust **dominates** across all metrics - single-agent and multi-agent. Winner: **Rust for production workloads**.

## Single-Agent Comparison (TR112_v2)

### Throughput Analysis

**Python (TR109)**:
- Baseline: 99.34 tok/s
- Range: 95.1 - 103.8 tok/s
- CV: 4.8%

**Rust (TR111_v2)**:
- Baseline: 114.54 tok/s
- Range: 113.99 - 114.97 tok/s
- CV: 2.6%

**Analysis**:
- Throughput difference: **+15.2%** (Rust faster)
- Rust shows **46% better consistency** (2.6% vs 4.8% CV)
- Rust's tighter range indicates more predictable performance

### Optimization Success Rate

**Python (TR109)**:
- 39% of configurations showed improvement over baseline
- Optimal config: GPU=60-80, CTX=512-1024, TEMP=0.6-0.8

**Rust (TR111)**:
- 72% of configurations showed improvement over baseline
- Optimal config: GPU=60, CTX=1024, TEMP=0.8

**Analysis**:
- Rust achieves **85% higher optimization success rate**
- Suggests Rust's async runtime is more tolerant of configuration variations
- Python requires more precise tuning to achieve optimal performance

### Time to First Token (TTFT)

**Python (TR109)**:
- Baseline (cold): 1437ms
- Optimized: ~450ms (GPU=80, CTX=2048, TEMP=0.8)

**Rust (TR111_v2)**:
- Baseline (cold): 603ms
- Optimized: ~487ms (GPU=60, CTX=256, TEMP=0.6)

**Analysis**:
- Rust **58% faster** TTFT on cold start (603ms vs 1437ms)
- Rust's async runtime provides superior I/O performance
- Both achieve <500ms TTFT with optimization

## Multi-Agent Comparison (TR110 vs TR114_v2)

### Peak Efficiency

**Python (TR110)**:
- Peak config avg: 99.25% efficiency (1.985x speedup)
- Config: GPU=80, CTX=2048, TEMP=1.0, homogeneous

**Rust (TR114_v2)**:
- Peak config avg: 99.396% efficiency (1.988x speedup)
- Peak single run: 99.992% efficiency
- Config: GPU=120/140, CTX=512/1024, TEMP=0.8, heterogeneous (test011)

**Analysis**:
- **+0.15pp efficiency advantage** for Rust (99.396% vs 99.25%)
- Rust achieves near-perfect single-run efficiency (99.992%)
- Both achieve >99% efficiency with optimal configurations
- Rust's work-stealing scheduler handles heterogeneous workloads effectively

### Mean Efficiency

**Python (TR110)**:
- Mean: 95.8% (all 150 runs)
- Range: 73.1% - 99.25%

**Rust (TR114_v2)**:
- Mean: 98.281% (all 135 runs)
- Range: 61.7% - 99.992%

**Analysis**:
- **+2.48pp mean efficiency advantage** for Rust (98.281% vs 95.8%)
- Rust shows superior average performance across all configurations
- Rust's higher mean demonstrates better consistency and fewer outliers
- Both achieve excellent efficiency with dual Ollama architecture

### Consistency (Standard Deviation)

**Python (TR110)**:
- Efficiency StdDev: 7.4pp
- Speedup StdDev: ~0.15x

**Rust (TR114)**:
- Efficiency StdDev: 5.5pp
- Speedup StdDev: 0.109x

**Analysis**:
- Rust shows **26% lower variance** (5.5pp vs 7.4pp)
- More predictable performance for SLA-driven workloads
- Lower speedup variance (0.109x vs 0.15x) indicates more stable concurrency

### Resource Contention

**Python (TR110)**:
- Contention rate: 10-15% (across all runs)
- Mostly at GPU=60 configurations
- Zero contention at GPU80 in homogeneous scenarios

**Rust (TR114_v2)**:
- Contention rate: 0.74% (1/135 runs)
- Single contention event at test005 (GPU=120, CTX=512)
- Zero contention in optimal configurations

**Analysis**:
- Rust shows **93% lower contention rate** (0.74% vs 10-15%)
- Dual Ollama architecture eliminates server-level contention
- Rust's work-stealing scheduler prevents resource starvation
- Both achieve near-zero contention with optimal configurations

### Configuration Sensitivity

**Python (TR110)**:
- GPU layer selection: Critical (60 vs 80 vs 120 = 15pp variance)
- Temperature selection: Moderate (0.6 vs 0.8 vs 1.0 = 3pp variance)
- Context size: Important (512 vs 1024 vs 2048 = 5-8pp variance)

**Rust (TR114)**:
- GPU layer selection: Negligible (60 vs 80 vs 120 = 0.6pp variance in homogeneous)
- Temperature selection: Negligible (0.6 vs 0.8 vs 1.0 = 0.4pp variance)
- Context size: Moderate (512 vs 1024 vs 2048 = 1.3pp variance)

**Analysis**:
- Rust is **operationally simpler** - configuration choices have minimal impact
- Python requires precise tuning for optimal performance
- Rust's flat performance curve enables "deploy-and-forget" configurations

## Architectural Comparison

### Single Ollama Instance

**Python (TR110 methodology, not tested)**:
- Expected: Would show similar degradation to Rust
- Asyncio's single-threaded model might handle it better

**Rust (TR113)**:
- Peak efficiency: 82.2% (vs 95.7% with dual Ollama)
- Mean efficiency: 72.0% (vs 89.3% with dual Ollama)
- Contention rate: 74% (vs 6% with dual Ollama)

**Analysis**:
- Single Ollama is **unacceptable for Rust** (-17.3pp efficiency loss)
- Dual Ollama mandatory for production Rust multi-agent deployments

### Dual Ollama Instances

**Python (TR110)**:
- Peak efficiency: 99.25%
- Mean efficiency: ~92.7%
- Contention rate: 33%

**Rust (TR114_v2)**:
- Peak config avg: 99.396%
- Mean efficiency: 98.281%
- Contention rate: 0.74%

**Analysis**:
- Both languages benefit significantly from dual Ollama
- Rust achieves higher peak config avg (+0.15pp) and mean (+2.48pp)
- Rust's work-stealing scheduler provides superior load balancing
- No performance gap - Rust exceeds Python in multi-agent scenarios

## Root Cause Analysis

### Why Rust Wins on Performance

1. **Superior Async Runtime**:
   - Tokio's work-stealing scheduler provides optimal load balancing
   - Better handling of heterogeneous I/O-bound workloads
   - Lower overhead for concurrent HTTP requests

2. **Dual Ollama Architecture**:
   - Eliminates server-level serialization bottlenecks
   - Reduces contention from 63% (single Ollama) to 0.74% (dual Ollama)
   - Enables true parallel execution

3. **Resource Efficiency**:
   - 67% less memory usage enables higher concurrency
   - 83% faster startup reduces cold-start latency
   - Predictable resource usage prevents contention

### Why Rust Wins on Consistency

1. **Compile-Time Guarantees**:
   - Memory safety prevents runtime errors
   - No garbage collection pauses
   - Predictable resource usage

2. **Tokio's Work-Stealing**:
   - Load balancing prevents thread starvation
   - More uniform performance across runs
   - Better handling of asymmetric workloads

3. **Type System**:
   - Prevents configuration errors at compile time
   - Reduces runtime variability from type coercion
   - More deterministic execution

## Production Decision Matrix

### Single-Agent Deployments

| Priority | Recommended Language | Rationale |
|----------|---------------------|-----------|
| **Peak Throughput** | **Rust** | 114.54 vs 99.34 tok/s (+15.2%) |
| **TTFT (Cold Start)** | **Rust** | 603ms vs 1437ms (-58%) |
| **Memory Efficiency** | **Rust** | 75 MB vs 250 MB (-67%) |
| **Startup Speed** | **Rust** | 0.2s vs 1.5s (-83%) |
| **Consistency** | **Rust** | 2.6% vs 4.8% CV (46% better) |
| **Memory Safety** | **Rust** | Compile-time guarantees |
| **Development Velocity** | **Python** | Easier debugging, richer ecosystem |

**Verdict**: **Rust dominates** single-agent performance. Choose Rust for production workloads.

### Multi-Agent Deployments

| Priority | Recommended Language | Rationale |
|----------|---------------------|-----------|
| **Peak Config Avg** | **Rust** | 99.396% vs 99.25% (+0.15pp) |
| **Mean Efficiency** | **Rust** | 98.281% vs 95.8% (+2.48pp) |
| **Consistency** | **Rust** | 4.9pp vs 7.4pp StdDev (34% better) |
| **Contention Avoidance** | **Rust** | 0.74% vs 10-15% (93% better) |
| **Configuration Simplicity** | **Rust** | Flat performance curve |
| **Memory Safety** | **Rust** | Compile-time guarantees |
| **P95/P99 Latency** | **Rust** | Lower variance, predictable SLA |

**Verdict**: **Rust exceeds Python** in multi-agent scenarios. Winner: Rust for production.

## Recommendations by Use Case

### High-Throughput Batch Processing
- **Language**: **Rust**
- **Config**: GPU=120/140, CTX=512/1024, TEMP=0.8 (test011)
- **Rationale**: 99.396% peak config efficiency, 98.281% mean efficiency

### Real-Time API with SLA Requirements
- **Language**: **Rust**
- **Config**: GPU=80, CTX=1024, TEMP=0.8 (test004)
- **Rationale**: 98.984% efficiency, 4.9pp StdDev ensures predictable P95/P99 latency

### Regulated Industries (Finance, Healthcare)
- **Language**: **Rust**
- **Config**: GPU=80, CTX=512, TEMP=0.8
- **Rationale**: Memory safety guarantees, consistent performance, 0.74% contention

### Rapid Prototyping
- **Language**: Python
- **Config**: GPU=80, CTX=1024, TEMP=0.8
- **Rationale**: Faster development, easier debugging

### Production Multi-Agent System
- **Language**: **Rust** (recommended for production)
- **Architecture**: **Dual Ollama mandatory**
- **Config (Rust)**: GPU=120/140, CTX=512/1024, TEMP=0.8 (test011)  99.396% efficiency
- **Runtime (Rust)**: Tokio-default (98.72% mean, 1.21pp ) - recommended
- **Config (Python)**: GPU=80, CTX=2048, TEMP=1.0  99.25% efficiency

## Related Documentation

- [TR112_v2: Rust vs Python Single-Agent](../outputs/publish_ready/reports/Technical_Report_112_v2.md)
- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)
- [TR114_v2: Rust Multi-Agent](../outputs/publish_ready/reports/Technical_Report_114_v2.md)
- [TR115_v2: Rust Runtime Optimization](../outputs/publish_ready/reports/Technical_Report_115_v2.md)
- [Production Deployment Guide](production_deployment.md)
- [Chimera Optimization Guide](chimera_optimization.md)

---

**Last Updated**: November 2025  
**Based on**: Technical Reports 109, 110, 111_v2, 112_v2, 114_v2, 115_v2

