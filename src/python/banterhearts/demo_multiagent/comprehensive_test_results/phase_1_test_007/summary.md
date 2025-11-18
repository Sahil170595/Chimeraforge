# Multi-Agent Demo Summary

Generated: 2025-10-09T23:17:14.137404
Scenario: chimera_hetero
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 42.81 tok/s |
| Chimera Throughput (avg) | 44.37 tok/s |
| Throughput Delta (avg) | +1.56 tok/s |
| TTFT Delta (avg) | -26596.79 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.70x |
| Average Wall Time | 111.02s |
| Average Efficiency | 85.0% |
| Runs with Contention | 2/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

