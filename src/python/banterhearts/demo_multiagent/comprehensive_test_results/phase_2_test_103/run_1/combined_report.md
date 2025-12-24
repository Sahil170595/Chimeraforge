# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.20s
**Sequential Estimated Time:** 110.78s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 54.87s

```
Throughput: 38.85 tok/s
TTFT: 491.16 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 55.90s

```
Throughput: 40.13 tok/s
TTFT: 496.21 ms
```

## Performance Delta
- Throughput Δ: +1.28 tok/s
- TTFT Δ: -5.04 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.5% (speedup / ideal 2x speedup)
- **Contention:** Low
