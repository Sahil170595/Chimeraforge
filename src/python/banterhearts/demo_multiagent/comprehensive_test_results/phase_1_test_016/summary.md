# Multi-Agent Demo Summary

Generated: 2025-10-10T00:20:45.259390
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 38.77 tok/s |
| Chimera Throughput (avg) | 45.31 tok/s |
| Throughput Delta (avg) | +6.55 tok/s |
| TTFT Delta (avg) | -109.44 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.93x |
| Average Wall Time | 54.41s |
| Average Efficiency | 96.5% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

