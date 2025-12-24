# Multi-Agent Demo Summary

Generated: 2025-10-09T19:37:23.578269
Scenario: baseline_vs_chimera
Runs: 2

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 420.95 tok/s |
| Chimera Throughput (avg) | 682.43 tok/s |
| Throughput Delta (avg) | +261.48 tok/s |
| TTFT Delta (avg) | +250.00 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.71x |
| Average Wall Time | 0.95s |
| Average Efficiency | 85.7% |
| Runs with Contention | 0/2 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 1 Ollama URL:** http://127.0.0.1:18034
**Agent 2 Ollama URL:** http://127.0.0.1:18035

