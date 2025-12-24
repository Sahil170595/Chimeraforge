# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 107.77s
**Sequential Estimated Time:** 193.23s
**Concurrency Speedup:** 1.79x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 107.77s

```
Throughput: 43.65 tok/s
TTFT: 29044.27 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 85.45s

```
Throughput: 43.60 tok/s
TTFT: 17065.32 ms
```

## Performance Delta
- Throughput Δ: -0.05 tok/s
- TTFT Δ: +11978.96 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.79x (sequential time / concurrent time)
- **Efficiency:** 89.6% (speedup / ideal 2x speedup)
- **Contention:** Low
