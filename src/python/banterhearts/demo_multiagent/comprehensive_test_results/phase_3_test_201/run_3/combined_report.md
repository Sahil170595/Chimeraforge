# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 57.67s
**Sequential Estimated Time:** 113.71s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.67s

```
Throughput: 39.84 tok/s
TTFT: 256.80 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.04s

```
Throughput: 38.06 tok/s
TTFT: 494.51 ms
```

## Performance Delta
- Throughput Δ: -1.78 tok/s
- TTFT Δ: -237.71 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.6% (speedup / ideal 2x speedup)
- **Contention:** Low
