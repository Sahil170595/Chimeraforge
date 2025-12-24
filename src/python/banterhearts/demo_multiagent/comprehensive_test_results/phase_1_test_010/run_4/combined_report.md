# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.27s
**Sequential Estimated Time:** 210.68s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 104.65s

```
Throughput: 43.26 tok/s
TTFT: 27897.07 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 106.03s

```
Throughput: 43.06 tok/s
TTFT: 28981.84 ms
```

## Performance Delta
- Throughput Δ: -0.19 tok/s
- TTFT Δ: -1084.77 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.1% (speedup / ideal 2x speedup)
- **Contention:** Low
