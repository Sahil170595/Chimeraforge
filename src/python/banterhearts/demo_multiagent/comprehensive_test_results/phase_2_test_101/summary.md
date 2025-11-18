# Multi-Agent Demo Summary

Generated: 2025-10-10T00:39:40.828947
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 46.16 tok/s |
| Chimera Throughput (avg) | 45.14 tok/s |
| Throughput Delta (avg) | -1.02 tok/s |
| TTFT Delta (avg) | -74.51 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.93x |
| Average Wall Time | 54.17s |
| Average Efficiency | 96.7% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

