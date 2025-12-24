# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.78s
**Sequential Estimated Time:** 106.88s
**Concurrency Speedup:** 1.92x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 51.41s

```
Throughput: 41.10 tok/s
TTFT: 578.12 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.46s

```
Throughput: 42.72 tok/s
TTFT: 1945.98 ms
```

## Performance Delta
- Throughput Δ: +1.62 tok/s
- TTFT Δ: -1367.85 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.92x (sequential time / concurrent time)
- **Efficiency:** 95.8% (speedup / ideal 2x speedup)
- **Contention:** Low
