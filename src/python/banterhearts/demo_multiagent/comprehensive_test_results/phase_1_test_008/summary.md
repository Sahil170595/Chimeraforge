# Multi-Agent Demo Summary

Generated: 2025-10-09T23:26:14.649636
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 43.25 tok/s |
| Chimera Throughput (avg) | 57.68 tok/s |
| Throughput Delta (avg) | +14.42 tok/s |
| TTFT Delta (avg) | -32671.04 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.45x |
| Average Wall Time | 108.02s |
| Average Efficiency | 72.7% |
| Runs with Contention | 5/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

