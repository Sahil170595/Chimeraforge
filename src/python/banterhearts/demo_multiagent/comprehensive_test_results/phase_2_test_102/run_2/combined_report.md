# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.29s
**Sequential Estimated Time:** 115.94s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.87s

```
Throughput: 38.79 tok/s
TTFT: 420.73 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 58.07s

```
Throughput: 38.96 tok/s
TTFT: 489.29 ms
```

## Performance Delta
- Throughput Δ: +0.17 tok/s
- TTFT Δ: -68.55 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.5% (speedup / ideal 2x speedup)
- **Contention:** Low
