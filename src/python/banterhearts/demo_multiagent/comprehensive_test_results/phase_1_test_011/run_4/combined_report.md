# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 112.07s
**Sequential Estimated Time:** 200.93s
**Concurrency Speedup:** 1.79x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 112.07s

```
Throughput: 43.04 tok/s
TTFT: 30949.95 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 88.86s

```
Throughput: 42.71 tok/s
TTFT: 17660.32 ms
```

## Performance Delta
- Throughput Δ: -0.34 tok/s
- TTFT Δ: +13289.63 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.79x (sequential time / concurrent time)
- **Efficiency:** 89.6% (speedup / ideal 2x speedup)
- **Contention:** Low
