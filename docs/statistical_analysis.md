# Statistical Analysis Guide

Complete guide to understanding and interpreting benchmark results.

## Overview

This guide explains how to interpret benchmark results, understand statistical metrics, and make data-driven decisions based on performance data.

## Key Metrics

### Throughput

**Definition**: Tokens generated per second

**Calculation**:
```
throughput = tokens_generated / generation_time
```

**Interpretation**:
- Higher is better
- Typical range: 95-105 tok/s (gemma3:latest)
- >100 tok/s: Excellent
- 95-100 tok/s: Good
- <95 tok/s: Needs optimization

### Time to First Token (TTFT)

**Definition**: Latency from request to first token

**Calculation**:
```
ttft = first_token_time - request_time
```

**Interpretation**:
- Lower is better
- Baseline: ~1400ms
- Optimized: <500ms
- Excellent: <450ms

### Coefficient of Variation (CV)

**Definition**: Relative standard deviation

**Calculation**:
```
CV = (stddev / mean) * 100%
```

**Interpretation**:
- Lower is better (more consistent)
- <1%: Excellent consistency
- 1-5%: Good consistency
- 5-10%: Acceptable
- >10%: High variance (investigate)

## Statistical Measures

### Mean (Average)

**Definition**: Sum of values divided by count

**Calculation**:
```
mean = (1/n) * (x_i)
```

**Use Case**: Central tendency, expected value

### Standard Deviation

**Definition**: Measure of spread

**Calculation**:
```
stddev = sqrt((1/n) * (x_i - mean)2)
```

**Use Case**: Variability, consistency

### Confidence Interval

**Definition**: Range containing true mean with probability

**Calculation**:
```
CI = mean  (z * stddev / sqrt(n))
```

**95% Confidence Interval**:
```
CI = mean  (1.96 * stddev / sqrt(n))
```

**Interpretation**: 95% probability true mean lies within interval

## Analysis Techniques

### Outlier Detection

#### IQR Method

**Calculation**:
```
Q1 = 25th percentile
Q3 = 75th percentile
IQR = Q3 - Q1
Outlier if: x < Q1 - 1.5*IQR or x > Q3 + 1.5*IQR
```

**Example**:
```python
import numpy as np

def detect_outliers_iqr(data):
    Q1 = np.percentile(data, 25)
    Q3 = np.percentile(data, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return [x for x in data if x < lower_bound or x > upper_bound]
```

#### Z-Score Method

**Calculation**:
```
z = (x - mean) / stddev
Outlier if: |z| > 3
```

**Example**:
```python
def detect_outliers_zscore(data):
    mean = np.mean(data)
    stddev = np.std(data)
    z_scores = [(x - mean) / stddev for x in data]
    return [data[i] for i, z in enumerate(z_scores) if abs(z) > 3]
```

### Trend Analysis

#### Linear Regression

**Use Case**: Identify trends over time or configuration

**Example**:
```python
from scipy import stats

# Throughput vs GPU layers
gpu_layers = [60, 80, 100, 120]
throughput = [95, 99, 101, 102]

slope, intercept, r_value, p_value, std_err = stats.linregress(gpu_layers, throughput)
print(f"Slope: {slope:.2f}, R2: {r_value**2:.3f}")
```

### Comparison Analysis

#### T-Test

**Use Case**: Compare two configurations

**Example**:
```python
from scipy import stats

# Baseline vs Chimera
baseline = [95, 96, 97, 95, 96]
chimera = [99, 100, 101, 99, 100]

t_stat, p_value = stats.ttest_ind(baseline, chimera)
print(f"T-statistic: {t_stat:.3f}, P-value: {p_value:.3f}")

if p_value < 0.05:
    print("Significant difference (p < 0.05)")
```

#### ANOVA

**Use Case**: Compare multiple configurations

**Example**:
```python
from scipy import stats

# Multiple configurations
config1 = [95, 96, 97]
config2 = [99, 100, 101]
config3 = [98, 99, 100]

f_stat, p_value = stats.f_oneway(config1, config2, config3)
print(f"F-statistic: {f_stat:.3f}, P-value: {p_value:.3f}")
```

## Multi-Agent Metrics

### Concurrency Speedup

**Definition**: Ratio of sequential to concurrent time

**Calculation**:
```
speedup = sequential_time / concurrent_time
```

**Interpretation**:
- Higher is better
- Ideal: 2.0x (perfect parallelism)
- >1.9x: Excellent
- 1.8-1.9x: Good
- <1.6x: Needs optimization

### Parallel Efficiency

**Definition**: Speedup relative to ideal

**Calculation**:
```
efficiency = (speedup / num_agents) * 100%
```

**Interpretation**:
- Higher is better
- Ideal: 100%
- >95%: Excellent
- 90-95%: Good
- <85%: Needs optimization

### Contention Rate

**Definition**: Percentage of runs with resource contention

**Calculation**:
```
contention_rate = (contention_events / total_runs) * 100%
```

**Interpretation**:
- Lower is better
- <5%: Excellent
- 5-10%: Good
- 10-20%: Acceptable
- >30%: Problematic

## Decision Making

### Configuration Selection

**Criteria**:
1. **Throughput**: Maximize
2. **TTFT**: Minimize
3. **Consistency**: Minimize CV
4. **Efficiency**: Maximize (multi-agent)

**Example**:
```python
def select_best_config(configs: List[Dict]) -> Dict:
    best = None
    best_score = -1
    
    for config in configs:
        # Weighted score
        score = (
            config['throughput'] * 0.4 +
            (1000 - config['ttft']) * 0.2 +
            (100 - config['cv']) * 0.2 +
            config['efficiency'] * 0.2
        )
        
        if score > best_score:
            best_score = score
            best = config
    
    return best
```

### Statistical Significance

**Rule of Thumb**:
- **p < 0.05**: Significant difference
- **p < 0.01**: Highly significant
- **p > 0.05**: No significant difference

**Example**:
```python
from scipy import stats

baseline = [95, 96, 97, 95, 96]
optimized = [99, 100, 101, 99, 100]

t_stat, p_value = stats.ttest_ind(baseline, optimized)

if p_value < 0.05:
    print(f"Optimization is significant (p={p_value:.3f})")
else:
    print(f"No significant difference (p={p_value:.3f})")
```

## References

- [Methodology Guide](methodology.md)
- [Benchmarking Guide](benchmarking.md)
- [TR108: Single-Inference Optimization](../outputs/publish_ready/reports/Technical_Report_108.md)
- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)

---

**Last Updated**: November 2025

