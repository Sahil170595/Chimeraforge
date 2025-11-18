# Multi-Agent Demo Summary

Generated: 2025-10-10T00:30:16.698147
Scenario: chimera_homo
Runs: 5

## Performance Metrics

| Metric | Value |
|--------|-------|
| Baseline Throughput (avg) | 38.75 tok/s |
| Chimera Throughput (avg) | 39.45 tok/s |
| Throughput Delta (avg) | +0.69 tok/s |
| TTFT Delta (avg) | -110.78 ms |

## Concurrent Execution Analysis

| Metric | Value |
|--------|-------|
| Average Concurrency Speedup | 1.98x |
| Average Wall Time | 57.42s |
| Average Efficiency | 99.1% |
| Runs with Contention | 0/5 |

## Configuration

**Agent 1 Config:** {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
**Agent 2 Config:** {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
**Agent 1 Ollama URL:** http://localhost:11434
**Agent 2 Ollama URL:** http://localhost:11435

