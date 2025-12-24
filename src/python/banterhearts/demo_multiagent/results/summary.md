# Multi-Agent Demo Summary

Generated: 2025-10-09T20:28:10.229204
Scenario: chimera_homo
Runs: 3

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 51.56 tok/s |
| Chimera Throughput (avg) | 49.70 tok/s |
| Throughput Delta (avg) | -1.85 tok/s |
| TTFT Delta (avg) | -436.83 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.87x |
| Average Wall Time | 52.96s |
| Average Efficiency | 93.4% |
| Runs with Contention | 0/3 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

