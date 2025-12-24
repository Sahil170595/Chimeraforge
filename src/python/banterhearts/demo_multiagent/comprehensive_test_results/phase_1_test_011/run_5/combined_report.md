# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 100.39s
**Sequential Estimated Time:** 182.00s
**Concurrency Speedup:** 1.81x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 100.39s

```
Throughput: 44.46 tok/s
TTFT: 27755.80 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 81.61s

```
Throughput: 44.42 tok/s
TTFT: 18014.99 ms
```

## Performance Delta
- Throughput Δ: -0.04 tok/s
- TTFT Δ: +9740.81 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.81x (sequential time / concurrent time)
- **Efficiency:** 90.6% (speedup / ideal 2x speedup)
- **Contention:** Low
