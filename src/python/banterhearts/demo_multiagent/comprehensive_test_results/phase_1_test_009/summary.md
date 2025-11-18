# Multi-Agent Demo Summary

Generated: 2025-10-09T23:35:10.916568
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 43.66 tok/s |
| Chimera Throughput (avg) | 43.40 tok/s |
| Throughput Delta (avg) | -0.26 tok/s |
| TTFT Delta (avg) | -7190.16 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.87x |
| Average Wall Time | 107.19s |
| Average Efficiency | 93.4% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 100, "num_ctx": 1024, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

