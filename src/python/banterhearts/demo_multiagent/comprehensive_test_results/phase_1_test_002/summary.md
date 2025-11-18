# Multi-Agent Demo Summary

Generated: 2025-10-09T22:30:15.337462
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 53.19 tok/s |
| Chimera Throughput (avg) | 42.26 tok/s |
| Throughput Delta (avg) | -10.93 tok/s |
| TTFT Delta (avg) | +31726.60 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.46x |
| Average Wall Time | 111.81s |
| Average Efficiency | 73.1% |
| Runs with Contention | 5/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

