# Multi-Agent Demo Summary

Generated: 2025-10-10T01:02:57.830874
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 38.96 tok/s |
| Chimera Throughput (avg) | 39.41 tok/s |
| Throughput Delta (avg) | +0.44 tok/s |
| TTFT Delta (avg) | -34.29 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 56.76s |
| Average Efficiency | 98.9% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

