# Multi-Agent Demo Summary

Generated: 2025-10-09T23:07:58.708407
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 43.91 tok/s |
| Chimera Throughput (avg) | 42.76 tok/s |
| Throughput Delta (avg) | -1.15 tok/s |
| TTFT Delta (avg) | +15520.80 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.69x |
| Average Wall Time | 115.13s |
| Average Efficiency | 84.7% |
| Runs with Contention | 1/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

