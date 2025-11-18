# Multi-Agent Demo Summary

Generated: 2025-10-09T22:39:45.425724
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 42.71 tok/s |
| Chimera Throughput (avg) | 43.00 tok/s |
| Throughput Delta (avg) | +0.29 tok/s |
| TTFT Delta (avg) | +13649.18 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.71x |
| Average Wall Time | 113.96s |
| Average Efficiency | 85.4% |
| Runs with Contention | 1/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

