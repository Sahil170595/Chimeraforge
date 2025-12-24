# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.64s
**Sequential Estimated Time:** 108.74s
**Concurrency Speedup:** 1.95x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.33s

```
Throughput: 39.01 tok/s
TTFT: 448.19 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 55.41s

```
Throughput: 41.32 tok/s
TTFT: 482.27 ms
```

## Performance Delta
- Throughput Δ: +2.31 tok/s
- TTFT Δ: -34.08 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.95x (sequential time / concurrent time)
- **Efficiency:** 97.7% (speedup / ideal 2x speedup)
- **Contention:** Low
