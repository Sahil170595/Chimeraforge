# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 108.42s
**Sequential Estimated Time:** 196.81s
**Concurrency Speedup:** 1.82x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 108.42s

```
Throughput: 43.73 tok/s
TTFT: 29325.99 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 88.39s

```
Throughput: 44.08 tok/s
TTFT: 19268.13 ms
```

## Performance Delta
- Throughput Δ: +0.35 tok/s
- TTFT Δ: +10057.85 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.82x (sequential time / concurrent time)
- **Efficiency:** 90.8% (speedup / ideal 2x speedup)
- **Contention:** Low
