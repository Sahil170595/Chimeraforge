# Multi-Agent Demo Summary

Generated: 2025-10-09T23:53:20.874079
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 43.67 tok/s |
| Chimera Throughput (avg) | 43.72 tok/s |
| Throughput Delta (avg) | +0.05 tok/s |
| TTFT Delta (avg) | +11097.68 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.80x |
| Average Wall Time | 108.03s |
| Average Efficiency | 89.9% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 140, "num_ctx": 1024, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

