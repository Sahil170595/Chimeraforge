# Benchmarking Methodology

Complete guide to research methodology, statistical rigor, and benchmark validation.

## Overview

This document outlines the rigorous methodology used in all Chimeraforge
technical reports (TR108-114), ensuring reproducible, statistically valid
benchmark results across the Banterhearts benchmarking breakout.

## Core Principles

### 1. Statistical Significance

**Multiple Runs**: Minimum 3-5 runs per configuration
- **Single-agent**: 3-5 runs
- **Multi-agent**: 5 runs (150 total benchmarks)
- **Research**: 10+ runs for publication

**Rationale**: 
- Accounts for variance in LLM inference
- Enables confidence intervals
- Detects outliers

### 2. Process Isolation

**Separate Processes**: Each run in isolated process
- Prevents warm-cache bias
- Ensures fair comparison
- Mimics production deployment

**Implementation**:
```python
# Python: Separate subprocess
subprocess.run([...], env=isolated_env)

# Rust: Separate process spawn
Command::new("cargo").spawn()
```

### 3. Cold Starts

**Model Unloading**: Force model eviction between runs
- Python: Explicit unload via API
- Rust: Natural eviction (Ollama LRU)

**Rationale**:
- Prevents warm-start bias
- Tests real-world deployment
- Measures true cold-start performance

### 4. Comprehensive Metrics

**Collected Metrics**:
- Throughput (tokens/second)
- Time to First Token (TTFT)
- Prompt evaluation duration
- Generation evaluation duration
- Model load duration
- Memory usage (VRAM, RAM)
- CPU usage

**Aggregation**:
- Mean  Standard Deviation
- Coefficient of Variation (CV%)
- Min/Max values
- Outlier detection

## Test Methodology

### Phase 1: Parameter Sweep

**Objective**: Identify optimal configuration ranges

**Process**:
1. Define parameter space (GPU, context, temperature)
2. Systematic grid search
3. 3-5 runs per configuration
4. Statistical analysis

**Example**:
```python
CONFIGS = [
    {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8},
    {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8},
    {"num_gpu": 100, "num_ctx": 512, "temperature": 0.8},
    # ... more configs
]
```

### Phase 2: Optimization Validation

**Objective**: Validate optimal configurations

**Process**:
1. Select top-performing configs from Phase 1
2. Extended runs (5-10 runs)
3. Cross-validation
4. Sensitivity analysis

### Phase 3: Production Validation

**Objective**: Test production scenarios

**Process**:
1. Real-world workloads
2. Extended duration tests
3. Resource contention analysis
4. Failure mode testing

## Statistical Analysis

### Descriptive Statistics

**Mean**:
```
 = (1/n) * (x_i)
```

**Standard Deviation**:
```
 = sqrt((1/n) * (x_i - )2)
```

**Coefficient of Variation**:
```
CV = ( / ) * 100%
```

### Confidence Intervals

**95% Confidence Interval**:
```
CI =   (1.96 *  / sqrt(n))
```

**Interpretation**: 95% probability true mean lies within interval

### Outlier Detection

**IQR Method**:
```
Q1 = 25th percentile
Q3 = 75th percentile
IQR = Q3 - Q1
Outlier if: x < Q1 - 1.5*IQR or x > Q3 + 1.5*IQR
```

**Z-Score Method**:
```
z = (x - ) / 
Outlier if: |z| > 3
```

## Multi-Agent Methodology

### Concurrent Execution

**Architecture**:
- Two agents run simultaneously
- Separate Ollama instances (ports 11434/11435)
- Asyncio/Tokio concurrent execution

**Metrics**:
- Wall-clock time (concurrent)
- Sequential estimated time (sum of individual)
- Speedup = sequential / concurrent
- Efficiency = (speedup / num_agents) * 100%

### Contention Detection

**TTFT Anomaly Detection**:
```python
if ttft_delta > 10000:  # 10 seconds
    contention_detected = True
```

**Throughput Degradation**:
```python
if throughput_drop > 0.20:  # 20% drop
    contention_detected = True
```

## Validation Criteria

### Single-Agent Validation

**Acceptable Variance**:
- CV < 1%: Excellent consistency
- CV < 5%: Good consistency
- CV > 10%: High variance (investigate)

**Performance Targets**:
- Throughput: >95 tok/s (gemma3:latest)
- TTFT: <500ms (optimized)
- Consistency: CV < 5%

### Multi-Agent Validation

**Efficiency Targets**:
- >95%: Excellent
- >90%: Good
- >85%: Acceptable
- <80%: Problematic (investigate)

**Contention Targets**:
- <5%: Excellent
- <10%: Good
- <20%: Acceptable
- >30%: Problematic

## Reporting Standards

### Required Sections

1. **Executive Summary**: Key findings
2. **Methodology**: Test framework
3. **Results**: Statistical analysis
4. **Discussion**: Interpretation
5. **Recommendations**: Actionable insights

### Required Metrics

**Per Configuration**:
- Mean throughput  stddev
- Mean TTFT  stddev
- Coefficient of variation
- Number of runs
- Outlier count

**Aggregate**:
- Best configuration
- Performance range
- Statistical significance
- Confidence intervals

## Common Pitfalls

### Pitfall 1: Insufficient Runs

**Problem**: 1-2 runs per configuration
**Solution**: Minimum 3-5 runs, 10+ for research

### Pitfall 2: Warm Cache Bias

**Problem**: Reusing same process
**Solution**: Separate processes, cold starts

### Pitfall 3: Background Processes

**Problem**: Other GPU processes running
**Solution**: Clean system, monitor `nvidia-smi`

### Pitfall 4: Thermal Throttling

**Problem**: GPU throttling after extended use
**Solution**: Monitor temperatures, allow cooldown

### Pitfall 5: Statistical Misinterpretation

**Problem**: Reporting single run as representative
**Solution**: Always report mean  stddev, multiple runs

## References

- [TR108: Single-Inference Optimization](../outputs/publish_ready/reports/Technical_Report_108.md)
- [TR109: Python Agent Workflows](../outputs/publish_ready/reports/Technical_Report_109.md)
- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)
- [TR111: Rust Single-Agent](../outputs/publish_ready/reports/Technical_Report_111.md)
- [TR112: Rust vs Python Single-Agent](../outputs/publish_ready/reports/Technical_Report_112.md)
- [TR113: Rust Multi-Agent (Single Ollama)](../outputs/publish_ready/reports/Technical_Report_113.md)
- [TR114: Rust Multi-Agent (Dual Ollama)](../outputs/publish_ready/reports/Technical_Report_114.md)

---

**Last Updated**: November 2025

