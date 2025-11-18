# Multi-Agent Demo Summary

Generated: 2025-10-10T00:49:06.113512
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.07 tok/s |
| Chimera Throughput (avg) | 39.11 tok/s |
| Throughput Delta (avg) | +0.04 tok/s |
| TTFT Delta (avg) | -103.97 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 56.30s |
| Average Efficiency | 98.9% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

