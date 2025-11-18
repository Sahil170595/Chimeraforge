# Multi-Agent Demo Summary

Generated: 2025-10-09T23:44:20.318524
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 43.18 tok/s |
| Chimera Throughput (avg) | 43.02 tok/s |
| Throughput Delta (avg) | -0.16 tok/s |
| TTFT Delta (avg) | +29.65 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.95x |
| Average Wall Time | 109.81s |
| Average Efficiency | 97.3% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 100, "num_ctx": 2048, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

