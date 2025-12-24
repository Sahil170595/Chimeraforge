# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 61.22s
**Sequential Estimated Time:** 121.83s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 60.89s

```
Throughput: 39.15 tok/s
TTFT: 453.69 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 60.95s

```
Throughput: 38.94 tok/s
TTFT: 482.04 ms
```

## Performance Delta
- Throughput Δ: -0.21 tok/s
- TTFT Δ: -28.36 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.5% (speedup / ideal 2x speedup)
- **Contention:** Low
