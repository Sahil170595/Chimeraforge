# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.43s
**Sequential Estimated Time:** 115.50s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.31s

```
Throughput: 38.42 tok/s
TTFT: 290.59 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 58.19s

```
Throughput: 39.40 tok/s
TTFT: 481.26 ms
```

## Performance Delta
- Throughput Δ: +0.98 tok/s
- TTFT Δ: -190.67 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.8% (speedup / ideal 2x speedup)
- **Contention:** Low
