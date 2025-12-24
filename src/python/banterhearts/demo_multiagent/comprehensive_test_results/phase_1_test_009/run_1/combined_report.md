# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 97.61s
**Sequential Estimated Time:** 186.12s
**Concurrency Speedup:** 1.91x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 88.78s

```
Throughput: 43.38 tok/s
TTFT: 17381.19 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 97.34s

```
Throughput: 43.83 tok/s
TTFT: 24896.02 ms
```

## Performance Delta
- Throughput Δ: +0.45 tok/s
- TTFT Δ: -7514.83 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.91x (sequential time / concurrent time)
- **Efficiency:** 95.3% (speedup / ideal 2x speedup)
- **Contention:** Low
