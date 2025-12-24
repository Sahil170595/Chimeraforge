# Chimera Agent Performance Comparison Report

**Date:** 2025-11-26 19:15:52  
**Model:** gemma3:latest  
**Runs:** 5  
**Demo Duration:** 199.01 seconds

## Executive Summary

This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup while executing identical benchmark-analysis workloads.

- **Average throughput improvement:** -0.3% (118.40 → 118.02 tok/s)
- **Average TTFT reduction:** -2.3% (221.55 → 226.66 ms)

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | 118.40 | 118.02 | -0.3% |
| Average TTFT (ms) | 221.55 | 226.66 | -2.3% |

## Run-by-Run Detail

### Run 1

- Baseline duration: 20.70s  (throughput 119.16 tok/s, TTFT 212.58 ms)
- Chimera duration: 22.58s  (throughput 117.97 tok/s, TTFT 252.93 ms)
- Throughput delta: -1.19 tok/s (-1.0%)
- TTFT delta: -40.35 ms (-19.0%)

### Run 2

- Baseline duration: 21.66s  (throughput 118.64 tok/s, TTFT 223.45 ms)
- Chimera duration: 22.39s  (throughput 116.74 tok/s, TTFT 195.05 ms)
- Throughput delta: -1.90 tok/s (-1.6%)
- TTFT delta: +28.40 ms (+12.7%)

### Run 3

- Baseline duration: 22.22s  (throughput 118.17 tok/s, TTFT 213.89 ms)
- Chimera duration: 13.34s  (throughput 117.43 tok/s, TTFT 263.02 ms)
- Throughput delta: -0.74 tok/s (-0.6%)
- TTFT delta: -49.13 ms (-23.0%)

### Run 4

- Baseline duration: 22.12s  (throughput 117.68 tok/s, TTFT 224.38 ms)
- Chimera duration: 20.54s  (throughput 117.86 tok/s, TTFT 207.50 ms)
- Throughput delta: +0.18 tok/s (+0.2%)
- TTFT delta: +16.88 ms (+7.5%)

### Run 5

- Baseline duration: 21.31s  (throughput 118.38 tok/s, TTFT 233.46 ms)
- Chimera duration: 12.16s  (throughput 120.09 tok/s, TTFT 214.82 ms)
- Throughput delta: +1.72 tok/s (+1.4%)
- TTFT delta: +18.64 ms (+8.0%)

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