# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.60s
**Sequential Estimated Time:** 209.71s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 103.42s

```
Throughput: 44.02 tok/s
TTFT: 27322.15 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 106.29s

```
Throughput: 43.83 tok/s
TTFT: 28140.98 ms
```

## Performance Delta
- Throughput Δ: -0.19 tok/s
- TTFT Δ: -818.82 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.4% (speedup / ideal 2x speedup)
- **Contention:** Low
