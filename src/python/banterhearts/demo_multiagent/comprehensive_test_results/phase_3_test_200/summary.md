# Multi-Agent Demo Summary

Generated: 2025-10-10T01:17:12.058627
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.17 tok/s |
| Chimera Throughput (avg) | 39.95 tok/s |
| Throughput Delta (avg) | +0.79 tok/s |
| TTFT Delta (avg) | -123.95 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.97x |
| Average Wall Time | 55.89s |
| Average Efficiency | 98.3% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

