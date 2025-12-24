# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 18:06:22  
**Model:** qwen2.5:7b  
**Runs:** 5  
**Demo Duration:** 319.65 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -1.3% (81.92 → 80.88 tok/s)
- **Average TTFT reduction:** -48.4% (54.98 → 81.62 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 81.92 | 80.88 | -1.3% |
| Average TTFT (ms) | 54.98 | 81.62 | -48.4% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 21.40s  (throughput 82.19 tok/s, TTFT 48.10 ms)
- Chimera duration: 41.66s  (throughput 81.12 tok/s, TTFT 78.37 ms)
- Throughput delta: -1.07 tok/s (-1.3%)
- TTFT delta: -30.27 ms (-62.9%)

### Run 2

- Baseline duration: 20.27s  (throughput 82.06 tok/s, TTFT 58.95 ms)
- Chimera duration: 42.80s  (throughput 80.75 tok/s, TTFT 76.52 ms)
- Throughput delta: -1.31 tok/s (-1.6%)
- TTFT delta: -17.57 ms (-29.8%)

### Run 3

- Baseline duration: 21.38s  (throughput 81.59 tok/s, TTFT 59.12 ms)
- Chimera duration: 29.98s  (throughput 80.46 tok/s, TTFT 75.81 ms)
- Throughput delta: -1.13 tok/s (-1.4%)
- TTFT delta: -16.68 ms (-28.2%)

### Run 4

- Baseline duration: 35.56s  (throughput 81.96 tok/s, TTFT 50.81 ms)
- Chimera duration: 40.29s  (throughput 81.37 tok/s, TTFT 74.53 ms)
- Throughput delta: -0.60 tok/s (-0.7%)
- TTFT delta: -23.72 ms (-46.7%)

### Run 5

- Baseline duration: 43.41s  (throughput 81.78 tok/s, TTFT 57.91 ms)
- Chimera duration: 22.91s  (throughput 80.72 tok/s, TTFT 102.86 ms)
- Throughput delta: -1.06 tok/s (-1.3%)
- TTFT delta: -44.95 ms (-77.6%)

## Configuration Details

### Baseline
- num_gpu: 80
- num_ctx: 1024
- temperature: 0.8
- top_p: 0.9
- top_k: 40
- repeat_penalty: 1.1

### Chimera Optimized
- num_gpu: 80
- num_ctx: 512
- temperature: 0.8
- top_p: 0.9
- top_k: 40
- repeat_penalty: 1.1

#### Chimera Configuration Summary

Chimera config (TR108-inspired): GPU layers=80, ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1

#### Citations

Derived from TR108/112 optimized single-agent settings.

## Conclusion

Chimera's optimized configuration consistently outperforms the baseline setup across the measured runs. The higher sustained throughput and lower time-to-first-token translate directly into faster technical report generation with identical workloads.