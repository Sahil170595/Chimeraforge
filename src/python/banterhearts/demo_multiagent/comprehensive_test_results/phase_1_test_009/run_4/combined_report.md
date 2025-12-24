# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 108.05s
**Sequential Estimated Time:** 201.21s
**Concurrency Speedup:** 1.86x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 93.43s

```
Throughput: 44.17 tok/s
TTFT: 22081.90 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 107.77s

```
Throughput: 43.55 tok/s
TTFT: 29180.13 ms
```

## Performance Delta
- Throughput Δ: -0.62 tok/s
- TTFT Δ: -7098.24 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.86x (sequential time / concurrent time)
- **Efficiency:** 93.1% (speedup / ideal 2x speedup)
- **Contention:** Low
