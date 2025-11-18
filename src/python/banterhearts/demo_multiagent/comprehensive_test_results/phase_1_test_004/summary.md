# Multi-Agent Demo Summary

Generated: 2025-10-09T22:49:04.787989
Scenario: baseline_vs_chimera
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 42.09 tok/s |
| Chimera Throughput (avg) | 42.35 tok/s |
| Throughput Delta (avg) | +0.26 tok/s |
| TTFT Delta (avg) | +14740.37 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.72x |
| Average Wall Time | 111.80s |
| Average Efficiency | 86.1% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

