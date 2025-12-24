# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 37.98s
**Sequential Estimated Time:** 64.94s
**Concurrency Speedup:** 1.71x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 27.16s

```
Throughput: 75.09 tok/s
TTFT: 316.91 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 37.78s

```
Throughput: 72.54 tok/s
TTFT: 319.07 ms
```

## Performance Delta
- Throughput Δ: -2.55 tok/s
- TTFT Δ: -2.16 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.71x (sequential time / concurrent time)
- **Efficiency:** 85.5% (speedup / ideal 2x speedup)
- **Contention:** Low
