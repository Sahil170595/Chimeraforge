# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 38.68s
**Sequential Estimated Time:** 66.71s
**Concurrency Speedup:** 1.72x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 28.29s

```
Throughput: 37.88 tok/s
TTFT: 261.23 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 38.42s

```
Throughput: 68.74 tok/s
TTFT: 489.93 ms
```

## Performance Delta
- Throughput Δ: +30.87 tok/s
- TTFT Δ: -228.70 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.72x (sequential time / concurrent time)
- **Efficiency:** 86.2% (speedup / ideal 2x speedup)
- **Contention:** Low
