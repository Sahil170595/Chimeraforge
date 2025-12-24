# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.49s
**Sequential Estimated Time:** 110.14s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 54.94s

```
Throughput: 39.14 tok/s
TTFT: 453.24 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.20s

```
Throughput: 39.23 tok/s
TTFT: 489.27 ms
```

## Performance Delta
- Throughput Δ: +0.09 tok/s
- TTFT Δ: -36.04 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.2% (speedup / ideal 2x speedup)
- **Contention:** Low
