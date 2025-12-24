# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 113.28s
**Sequential Estimated Time:** 211.47s
**Concurrency Speedup:** 1.87x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 98.46s

```
Throughput: 43.51 tok/s
TTFT: 24176.18 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 113.01s

```
Throughput: 42.82 tok/s
TTFT: 30445.08 ms
```

## Performance Delta
- Throughput Δ: -0.69 tok/s
- TTFT Δ: -6268.90 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.87x (sequential time / concurrent time)
- **Efficiency:** 93.3% (speedup / ideal 2x speedup)
- **Contention:** Low
