# Multi-Agent Demo Summary

Generated: 2025-10-09T22:58:22.649045
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 43.64 tok/s |
| Chimera Throughput (avg) | 43.94 tok/s |
| Throughput Delta (avg) | +0.30 tok/s |
| TTFT Delta (avg) | +9317.15 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.78x |
| Average Wall Time | 111.50s |
| Average Efficiency | 89.1% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

