# Multi-Agent Demo Summary

Generated: 2025-10-10T00:11:42.986624
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.10 tok/s |
| Chimera Throughput (avg) | 40.12 tok/s |
| Throughput Delta (avg) | +1.02 tok/s |
| TTFT Delta (avg) | -106.45 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.97x |
| Average Wall Time | 56.38s |
| Average Efficiency | 98.5% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

