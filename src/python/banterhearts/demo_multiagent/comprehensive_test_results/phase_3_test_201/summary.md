# Multi-Agent Demo Summary

Generated: 2025-10-10T01:21:56.212363
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.24 tok/s |
| Chimera Throughput (avg) | 35.02 tok/s |
| Throughput Delta (avg) | -4.22 tok/s |
| TTFT Delta (avg) | -31.03 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 56.77s |
| Average Efficiency | 99.0% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

