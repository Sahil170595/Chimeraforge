# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 39.50s
**Sequential Estimated Time:** 68.43s
**Concurrency Speedup:** 1.73x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 39.50s

```
Throughput: 72.84 tok/s
TTFT: 282.46 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 28.93s

```
Throughput: 88.05 tok/s
TTFT: 307.43 ms
```

## Performance Delta
- Throughput Δ: +15.21 tok/s
- TTFT Δ: -24.98 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.73x (sequential time / concurrent time)
- **Efficiency:** 86.6% (speedup / ideal 2x speedup)
- **Contention:** Low
