# Multi-Agent Demo Summary

Generated: 2025-10-10T00:44:24.301370
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.22 tok/s |
| Chimera Throughput (avg) | 38.89 tok/s |
| Throughput Delta (avg) | -0.33 tok/s |
| TTFT Delta (avg) | -84.88 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 56.63s |
| Average Efficiency | 99.1% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

