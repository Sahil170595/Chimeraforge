# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 59.37s
**Sequential Estimated Time:** 116.65s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.49s

```
Throughput: 39.09 tok/s
TTFT: 454.45 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 59.16s

```
Throughput: 41.01 tok/s
TTFT: 488.39 ms
```

## Performance Delta
- Throughput Δ: +1.92 tok/s
- TTFT Δ: -33.94 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.2% (speedup / ideal 2x speedup)
- **Contention:** Low
