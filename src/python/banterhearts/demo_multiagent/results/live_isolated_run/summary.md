# Multi-Agent Demo Summary

Generated: 2025-10-09T20:06:47.639764
Scenario: baseline_vs_chimera
Runs: 3

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.50 tok/s |
| Chimera Throughput (avg) | 37.23 tok/s |
| Throughput Delta (avg) | -2.27 tok/s |
| TTFT Delta (avg) | -144.54 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.96x |
| Average Wall Time | 64.21s |
| Average Efficiency | 97.9% |
| Runs with Contention | 0/3 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://127.0.0.1:11434
**Agent 2 Ollama URL:** http://127.0.0.1:11435

