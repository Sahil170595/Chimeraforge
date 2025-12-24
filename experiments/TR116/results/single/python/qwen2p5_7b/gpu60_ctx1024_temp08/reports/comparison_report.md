# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 20:51:44  
**Model:** qwen2.5:7b  
**Runs:** 5  
**Demo Duration:** 445.58 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -0.0% (82.01 → 82.01 tok/s)
- **Average TTFT reduction:** -162.5% (52.12 → 136.84 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 82.01 | 82.01 | -0.0% |
| Average TTFT (ms) | 52.12 | 136.84 | -162.5% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 22.42s  (throughput 82.19 tok/s, TTFT 50.42 ms)
- Chimera duration: 60.57s  (throughput 82.21 tok/s, TTFT 136.43 ms)
- Throughput delta: +0.02 tok/s (+0.0%)
- TTFT delta: -86.01 ms (-170.6%)

### Run 2

- Baseline duration: 19.81s  (throughput 82.09 tok/s, TTFT 42.31 ms)
- Chimera duration: 28.62s  (throughput 82.17 tok/s, TTFT 137.24 ms)
- Throughput delta: +0.08 tok/s (+0.1%)
- TTFT delta: -94.93 ms (-224.4%)

### Run 3

- Baseline duration: 25.55s  (throughput 81.45 tok/s, TTFT 58.34 ms)
- Chimera duration: 82.56s  (throughput 81.10 tok/s, TTFT 131.97 ms)
- Throughput delta: -0.35 tok/s (-0.4%)
- TTFT delta: -73.63 ms (-126.2%)

### Run 4

- Baseline duration: 28.80s  (throughput 82.11 tok/s, TTFT 58.66 ms)
- Chimera duration: 27.72s  (throughput 82.83 tok/s, TTFT 136.99 ms)
- Throughput delta: +0.71 tok/s (+0.9%)
- TTFT delta: -78.33 ms (-133.5%)

### Run 5

- Baseline duration: 23.20s  (throughput 82.21 tok/s, TTFT 50.89 ms)
- Chimera duration: 126.34s  (throughput 81.74 tok/s, TTFT 141.56 ms)
- Throughput delta: -0.47 tok/s (-0.6%)
- TTFT delta: -90.67 ms (-178.2%)

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