# Multi-Agent Demo Summary

Generated: 2025-10-10T00:07:00.705509
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.70 tok/s |
| Chimera Throughput (avg) | 38.82 tok/s |
| Throughput Delta (avg) | -0.88 tok/s |
| TTFT Delta (avg) | -12.43 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.97x |
| Average Wall Time | 59.66s |
| Average Efficiency | 98.6% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

