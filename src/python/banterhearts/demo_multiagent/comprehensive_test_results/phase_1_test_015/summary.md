# Multi-Agent Demo Summary

Generated: 2025-10-10T00:16:12.894993
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 46.16 tok/s |
| Chimera Throughput (avg) | 48.97 tok/s |
| Throughput Delta (avg) | +2.81 tok/s |
| TTFT Delta (avg) | -4.78 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.93x |
| Average Wall Time | 53.92s |
| Average Efficiency | 96.5% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

