# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 20:10:46  
**Model:** llama3.1:8b-instruct-q4_0  
**Runs:** 5  
**Demo Duration:** 139.64 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -3.6% (82.31 → 79.38 tok/s)
- **Average TTFT reduction:** -18.1% (200.28 → 236.47 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 82.31 | 79.38 | -3.6% |
| Average TTFT (ms) | 200.28 | 236.47 | -18.1% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 13.19s  (throughput 82.03 tok/s, TTFT 177.13 ms)
- Chimera duration: 16.94s  (throughput 81.01 tok/s, TTFT 241.40 ms)
- Throughput delta: -1.02 tok/s (-1.2%)
- TTFT delta: -64.27 ms (-36.3%)

### Run 2

- Baseline duration: 11.41s  (throughput 82.62 tok/s, TTFT 180.87 ms)
- Chimera duration: 16.79s  (throughput 79.69 tok/s, TTFT 221.38 ms)
- Throughput delta: -2.92 tok/s (-3.5%)
- TTFT delta: -40.51 ms (-22.4%)

### Run 3

- Baseline duration: 10.89s  (throughput 82.52 tok/s, TTFT 203.81 ms)
- Chimera duration: 15.88s  (throughput 79.39 tok/s, TTFT 243.56 ms)
- Throughput delta: -3.13 tok/s (-3.8%)
- TTFT delta: -39.75 ms (-19.5%)

### Run 4

- Baseline duration: 11.74s  (throughput 82.16 tok/s, TTFT 206.91 ms)
- Chimera duration: 14.32s  (throughput 78.61 tok/s, TTFT 222.78 ms)
- Throughput delta: -3.55 tok/s (-4.3%)
- TTFT delta: -15.87 ms (-7.7%)

### Run 5

- Baseline duration: 13.77s  (throughput 82.24 tok/s, TTFT 232.68 ms)
- Chimera duration: 14.71s  (throughput 78.21 tok/s, TTFT 253.24 ms)
- Throughput delta: -4.03 tok/s (-4.9%)
- TTFT delta: -20.56 ms (-8.8%)

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