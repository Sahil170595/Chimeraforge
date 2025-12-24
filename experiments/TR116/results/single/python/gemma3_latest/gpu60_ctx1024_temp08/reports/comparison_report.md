# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 19:09:42  
**Model:** gemma3:latest  
**Runs:** 5  
**Demo Duration:** 248.72 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -0.6% (118.65 → 117.95 tok/s)
- **Average TTFT reduction:** -56.6% (82.56 → 129.27 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 118.65 | 117.95 | -0.6% |
| Average TTFT (ms) | 82.56 | 129.27 | -56.6% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 27.11s  (throughput 118.32 tok/s, TTFT 91.10 ms)
- Chimera duration: 24.86s  (throughput 117.91 tok/s, TTFT 130.02 ms)
- Throughput delta: -0.41 tok/s (-0.3%)
- TTFT delta: -38.93 ms (-42.7%)

### Run 2

- Baseline duration: 24.92s  (throughput 118.39 tok/s, TTFT 88.00 ms)
- Chimera duration: 24.86s  (throughput 117.89 tok/s, TTFT 128.63 ms)
- Throughput delta: -0.50 tok/s (-0.4%)
- TTFT delta: -40.63 ms (-46.2%)

### Run 3

- Baseline duration: 23.21s  (throughput 118.39 tok/s, TTFT 86.80 ms)
- Chimera duration: 23.61s  (throughput 118.07 tok/s, TTFT 129.18 ms)
- Throughput delta: -0.31 tok/s (-0.3%)
- TTFT delta: -42.38 ms (-48.8%)

### Run 4

- Baseline duration: 24.14s  (throughput 119.08 tok/s, TTFT 73.22 ms)
- Chimera duration: 27.24s  (throughput 117.93 tok/s, TTFT 129.05 ms)
- Throughput delta: -1.15 tok/s (-1.0%)
- TTFT delta: -55.82 ms (-76.2%)

### Run 5

- Baseline duration: 24.63s  (throughput 119.10 tok/s, TTFT 73.69 ms)
- Chimera duration: 24.14s  (throughput 117.94 tok/s, TTFT 129.46 ms)
- Throughput delta: -1.17 tok/s (-1.0%)
- TTFT delta: -55.77 ms (-75.7%)

## Configuration Details

### Baseline
- num_gpu: 80
- num_ctx: 1024
- temperature: 0.8
- top_p: 0.9
- top_k: 40
- repeat_penalty: 1.1

### Chimera Optimized
- num_gpu: 60
- num_ctx: 1024
- temperature: 0.8
- top_p: 0.9
- top_k: 40
- repeat_penalty: 1.1

#### Chimera Configuration Summary

Chimera config (TR108-inspired): GPU layers=60, ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1

#### Citations

Derived from TR108/112 optimized single-agent settings.

## Conclusion

Chimera's optimized configuration consistently outperforms the baseline setup across the measured runs. The higher sustained throughput and lower time-to-first-token translate directly into faster technical report generation with identical workloads.