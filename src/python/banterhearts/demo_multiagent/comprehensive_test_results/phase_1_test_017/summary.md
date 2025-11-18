# Multi-Agent Demo Summary

Generated: 2025-10-10T00:25:29.286638
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 39.06 tok/s |
| Chimera Throughput (avg) | 39.39 tok/s |
| Throughput Delta (avg) | +0.33 tok/s |
| TTFT Delta (avg) | -22.65 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 56.73s |
| Average Efficiency | 99.1% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

