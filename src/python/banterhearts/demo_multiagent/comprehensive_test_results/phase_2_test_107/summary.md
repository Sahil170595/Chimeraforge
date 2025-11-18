# Multi-Agent Demo Summary

Generated: 2025-10-10T01:07:47.461981
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 38.63 tok/s |
| Chimera Throughput (avg) | 38.96 tok/s |
| Throughput Delta (avg) | +0.33 tok/s |
| TTFT Delta (avg) | -135.51 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 57.86s |
| Average Efficiency | 99.2% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

