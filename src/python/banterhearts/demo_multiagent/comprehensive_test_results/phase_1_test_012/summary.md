# Multi-Agent Demo Summary

Generated: 2025-10-10T00:02:02.097519
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 47.29 tok/s |
| Chimera Throughput (avg) | 42.19 tok/s |
| Throughput Delta (avg) | -5.10 tok/s |
| TTFT Delta (avg) | +12893.92 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.81x |
| Average Wall Time | 104.18s |
| Average Efficiency | 90.6% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 140, "num_ctx": 2048, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

