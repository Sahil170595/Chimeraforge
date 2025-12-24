# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 57.20s
**Sequential Estimated Time:** 113.61s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.20s

```
Throughput: 39.64 tok/s
TTFT: 449.70 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.41s

```
Throughput: 38.45 tok/s
TTFT: 483.84 ms
```

## Performance Delta
- Throughput Δ: -1.19 tok/s
- TTFT Δ: -34.14 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.3% (speedup / ideal 2x speedup)
- **Contention:** Low
