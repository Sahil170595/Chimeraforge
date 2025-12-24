# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 60.93s
**Sequential Estimated Time:** 119.57s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 60.93s

```
Throughput: 40.21 tok/s
TTFT: 878.19 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 58.64s

```
Throughput: 38.07 tok/s
TTFT: 883.09 ms
```

## Performance Delta
- Throughput Δ: -2.14 tok/s
- TTFT Δ: -4.90 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.1% (speedup / ideal 2x speedup)
- **Contention:** Low
