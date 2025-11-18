# Multi-Agent Demo Summary

Generated: 2025-10-10T00:58:13.635319
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 46.38 tok/s |
| Chimera Throughput (avg) | 34.81 tok/s |
| Throughput Delta (avg) | -11.57 tok/s |
| TTFT Delta (avg) | -5.34 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.92x |
| Average Wall Time | 52.17s |
| Average Efficiency | 96.0% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
**Agent 2 Config:** {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

