# Multi-Agent Demo Summary

Generated: 2025-10-10T01:26:51.801239
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 41.13 tok/s |
| Chimera Throughput (avg) | 39.82 tok/s |
| Throughput Delta (avg) | -1.31 tok/s |
| TTFT Delta (avg) | +223.43 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.96x |
| Average Wall Time | 59.04s |
| Average Efficiency | 97.9% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

