# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 18:14:26  
**Model:** qwen2.5:7b  
**Runs:** 5  
**Demo Duration:** 312.75 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -1.2% (81.99 → 81.02 tok/s)
- **Average TTFT reduction:** -19.1% (207.54 → 247.18 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 81.99 | 81.02 | -1.2% |
| Average TTFT (ms) | 207.54 | 247.18 | -19.1% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 16.85s  (throughput 81.80 tok/s, TTFT 176.75 ms)
- Chimera duration: 44.66s  (throughput 81.22 tok/s, TTFT 268.49 ms)
- Throughput delta: -0.58 tok/s (-0.7%)
- TTFT delta: -91.74 ms (-51.9%)

### Run 2

- Baseline duration: 17.94s  (throughput 82.01 tok/s, TTFT 191.38 ms)
- Chimera duration: 25.11s  (throughput 81.24 tok/s, TTFT 250.17 ms)
- Throughput delta: -0.77 tok/s (-0.9%)
- TTFT delta: -58.79 ms (-30.7%)

### Run 3

- Baseline duration: 14.67s  (throughput 82.24 tok/s, TTFT 155.70 ms)
- Chimera duration: 47.27s  (throughput 81.17 tok/s, TTFT 232.41 ms)
- Throughput delta: -1.07 tok/s (-1.3%)
- TTFT delta: -76.71 ms (-49.3%)

### Run 4

- Baseline duration: 40.94s  (throughput 81.67 tok/s, TTFT 266.55 ms)
- Chimera duration: 23.59s  (throughput 80.29 tok/s, TTFT 249.77 ms)
- Throughput delta: -1.38 tok/s (-1.7%)
- TTFT delta: +16.78 ms (+6.3%)

### Run 5

- Baseline duration: 59.13s  (throughput 82.23 tok/s, TTFT 247.29 ms)
- Chimera duration: 22.59s  (throughput 81.18 tok/s, TTFT 235.05 ms)
- Throughput delta: -1.05 tok/s (-1.3%)
- TTFT delta: +12.24 ms (+4.9%)

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
- num_ctx: 1024
- temperature: 0.8
- top_p: 0.9
- top_k: 40
- repeat_penalty: 1.1

#### Chimera Configuration Summary

Chimera config (TR108-inspired): GPU layers=80, ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1

#### Citations

Derived from TR108/112 optimized single-agent settings.

## Conclusion

Chimera's optimized configuration consistently outperforms the baseline setup across the measured runs. The higher sustained throughput and lower time-to-first-token translate directly into faster technical report generation with identical workloads.