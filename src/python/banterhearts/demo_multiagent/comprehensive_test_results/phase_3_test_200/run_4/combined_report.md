# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.04s
**Sequential Estimated Time:** 108.45s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.67s

```
Throughput: 39.02 tok/s
TTFT: 447.02 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 54.78s

```
Throughput: 40.15 tok/s
TTFT: 483.53 ms
```

## Performance Delta
- Throughput Δ: +1.13 tok/s
- TTFT Δ: -36.52 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.5% (speedup / ideal 2x speedup)
- **Contention:** Low
