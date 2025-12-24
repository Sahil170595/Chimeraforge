# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.36s
**Sequential Estimated Time:** 111.14s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.07s

```
Throughput: 39.02 tok/s
TTFT: 449.45 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.07s

```
Throughput: 40.06 tok/s
TTFT: 481.52 ms
```

## Performance Delta
- Throughput Δ: +1.04 tok/s
- TTFT Δ: -32.07 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.6% (speedup / ideal 2x speedup)
- **Contention:** Low
