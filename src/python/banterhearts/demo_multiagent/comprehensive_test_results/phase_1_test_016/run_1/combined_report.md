# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.39s
**Sequential Estimated Time:** 112.43s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.31s

```
Throughput: 38.47 tok/s
TTFT: 263.95 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.12s

```
Throughput: 38.57 tok/s
TTFT: 482.57 ms
```

## Performance Delta
- Throughput Δ: +0.10 tok/s
- TTFT Δ: -218.62 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.7% (speedup / ideal 2x speedup)
- **Contention:** Low
