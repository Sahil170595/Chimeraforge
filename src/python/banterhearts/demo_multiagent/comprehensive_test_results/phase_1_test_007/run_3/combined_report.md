# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 121.39s
**Sequential Estimated Time:** 214.28s
**Concurrency Speedup:** 1.77x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 93.12s

```
Throughput: 43.29 tok/s
TTFT: 508.17 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 121.16s

```
Throughput: 38.06 tok/s
TTFT: 32036.19 ms
```

## Performance Delta
- Throughput Δ: -5.23 tok/s
- TTFT Δ: -31528.02 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.77x (sequential time / concurrent time)
- **Efficiency:** 88.3% (speedup / ideal 2x speedup)
- **Contention:** Low
