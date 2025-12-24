# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.99s
**Sequential Estimated Time:** 109.55s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.79s

```
Throughput: 39.12 tok/s
TTFT: 450.20 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.76s

```
Throughput: 41.21 tok/s
TTFT: 492.28 ms
```

## Performance Delta
- Throughput Δ: +2.09 tok/s
- TTFT Δ: -42.08 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 97.8% (speedup / ideal 2x speedup)
- **Contention:** Low
