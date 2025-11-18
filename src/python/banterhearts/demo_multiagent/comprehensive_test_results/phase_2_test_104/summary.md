# Multi-Agent Demo Summary

Generated: 2025-10-10T00:53:52.380149
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 38.71 tok/s |
| Chimera Throughput (avg) | 39.68 tok/s |
| Throughput Delta (avg) | +0.97 tok/s |
| TTFT Delta (avg) | -111.30 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 57.19s |
| Average Efficiency | 98.8% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

