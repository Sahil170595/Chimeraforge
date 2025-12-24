# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.83s
**Sequential Estimated Time:** 110.01s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.83s

```
Throughput: 39.98 tok/s
TTFT: 281.10 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 54.17s

```
Throughput: 38.34 tok/s
TTFT: 487.00 ms
```

## Performance Delta
- Throughput Δ: -1.64 tok/s
- TTFT Δ: -205.89 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.5% (speedup / ideal 2x speedup)
- **Contention:** Low
