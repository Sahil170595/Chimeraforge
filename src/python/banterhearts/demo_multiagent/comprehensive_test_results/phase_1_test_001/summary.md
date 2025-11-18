# Multi-Agent Demo Summary

Generated: 2025-10-09T22:20:55.974790
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 44.09 tok/s |
| Chimera Throughput (avg) | 42.45 tok/s |
| Throughput Delta (avg) | -1.64 tok/s |
| TTFT Delta (avg) | +29658.75 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.60x |
| Average Wall Time | 113.30s |
| Average Efficiency | 79.9% |
| Runs with Contention | 3/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

