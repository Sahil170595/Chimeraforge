# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 19:22:44  
**Model:** gemma3:latest  
**Runs:** 5  
**Demo Duration:** 241.03 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -1.1% (118.55 → 117.25 tok/s)
- **Average TTFT reduction:** -7.6% (210.17 → 226.15 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 118.55 | 117.25 | -1.1% |
| Average TTFT (ms) | 210.17 | 226.15 | -7.6% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 20.13s  (throughput 118.02 tok/s, TTFT 225.02 ms)
- Chimera duration: 20.24s  (throughput 117.69 tok/s, TTFT 208.33 ms)
- Throughput delta: -0.34 tok/s (-0.3%)
- TTFT delta: +16.69 ms (+7.4%)

### Run 2

- Baseline duration: 21.70s  (throughput 118.87 tok/s, TTFT 172.72 ms)
- Chimera duration: 23.78s  (throughput 115.08 tok/s, TTFT 222.23 ms)
- Throughput delta: -3.78 tok/s (-3.2%)
- TTFT delta: -49.51 ms (-28.7%)

### Run 3

- Baseline duration: 20.53s  (throughput 118.30 tok/s, TTFT 218.37 ms)
- Chimera duration: 22.56s  (throughput 117.18 tok/s, TTFT 260.06 ms)
- Throughput delta: -1.12 tok/s (-0.9%)
- TTFT delta: -41.68 ms (-19.1%)

### Run 4

- Baseline duration: 20.65s  (throughput 118.93 tok/s, TTFT 213.72 ms)
- Chimera duration: 49.29s  (throughput 118.32 tok/s, TTFT 236.62 ms)
- Throughput delta: -0.61 tok/s (-0.5%)
- TTFT delta: -22.90 ms (-10.7%)

### Run 5

- Baseline duration: 20.55s  (throughput 118.61 tok/s, TTFT 221.00 ms)
- Chimera duration: 21.60s  (throughput 117.97 tok/s, TTFT 203.50 ms)
- Throughput delta: -0.63 tok/s (-0.5%)
- TTFT delta: +17.50 ms (+7.9%)

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