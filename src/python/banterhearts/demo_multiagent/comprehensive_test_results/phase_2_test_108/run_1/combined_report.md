# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 54.59s
**Sequential Estimated Time:** 107.87s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.55s

```
Throughput: 38.90 tok/s
TTFT: 363.02 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 54.32s

```
Throughput: 39.83 tok/s
TTFT: 499.03 ms
```

## Performance Delta
- Throughput Δ: +0.93 tok/s
- TTFT Δ: -136.02 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.8% (speedup / ideal 2x speedup)
- **Contention:** Low
