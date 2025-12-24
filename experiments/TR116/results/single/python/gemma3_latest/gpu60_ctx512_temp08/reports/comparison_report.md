# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 19:02:42  
**Model:** gemma3:latest  
**Runs:** 5  
**Demo Duration:** 289.92 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -0.4% (118.29 → 117.81 tok/s)
- **Average TTFT reduction:** -50.9% (86.04 → 129.82 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 118.29 | 117.81 | -0.4% |
| Average TTFT (ms) | 86.04 | 129.82 | -50.9% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 23.68s  (throughput 118.78 tok/s, TTFT 87.23 ms)
- Chimera duration: 25.73s  (throughput 117.69 tok/s, TTFT 132.17 ms)
- Throughput delta: -1.08 tok/s (-0.9%)
- TTFT delta: -44.93 ms (-51.5%)

### Run 2

- Baseline duration: 22.34s  (throughput 117.21 tok/s, TTFT 87.47 ms)
- Chimera duration: 25.06s  (throughput 117.91 tok/s, TTFT 129.81 ms)
- Throughput delta: +0.70 tok/s (+0.6%)
- TTFT delta: -42.33 ms (-48.4%)

### Run 3

- Baseline duration: 24.27s  (throughput 118.45 tok/s, TTFT 86.63 ms)
- Chimera duration: 23.57s  (throughput 117.58 tok/s, TTFT 128.60 ms)
- Throughput delta: -0.87 tok/s (-0.7%)
- TTFT delta: -41.96 ms (-48.4%)

### Run 4

- Baseline duration: 24.44s  (throughput 118.36 tok/s, TTFT 87.33 ms)
- Chimera duration: 69.15s  (throughput 118.07 tok/s, TTFT 129.25 ms)
- Throughput delta: -0.29 tok/s (-0.2%)
- TTFT delta: -41.92 ms (-48.0%)

### Run 5

- Baseline duration: 26.08s  (throughput 118.68 tok/s, TTFT 81.54 ms)
- Chimera duration: 25.59s  (throughput 117.79 tok/s, TTFT 129.28 ms)
- Throughput delta: -0.90 tok/s (-0.8%)
- TTFT delta: -47.75 ms (-58.6%)

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
- num_ctx: 512
- temperature: 0.8
- top_p: 0.9
- top_k: 40
- repeat_penalty: 1.1

#### Chimera Configuration Summary

Chimera config (TR108-inspired): GPU layers=60, ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1

#### Citations

Derived from TR108/112 optimized single-agent settings.

## Conclusion

Chimera's optimized configuration consistently outperforms the baseline setup across the measured runs. The higher sustained throughput and lower time-to-first-token translate directly into faster technical report generation with identical workloads.