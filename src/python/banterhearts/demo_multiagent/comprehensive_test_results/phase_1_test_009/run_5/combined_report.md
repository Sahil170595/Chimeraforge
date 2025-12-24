# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 109.60s
**Sequential Estimated Time:** 205.01s
**Concurrency Speedup:** 1.87x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 95.67s

```
Throughput: 43.64 tok/s
TTFT: 22362.61 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 109.34s

```
Throughput: 43.83 tok/s
TTFT: 29894.69 ms
```

## Performance Delta
- Throughput Δ: +0.19 tok/s
- TTFT Δ: -7532.07 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.87x (sequential time / concurrent time)
- **Efficiency:** 93.5% (speedup / ideal 2x speedup)
- **Contention:** Low
