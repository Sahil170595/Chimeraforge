# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 108.93s
**Sequential Estimated Time:** 197.57s
**Concurrency Speedup:** 1.81x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 108.93s

```
Throughput: 43.63 tok/s
TTFT: 28997.29 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 88.64s

```
Throughput: 43.97 tok/s
TTFT: 19742.86 ms
```

## Performance Delta
- Throughput Δ: +0.34 tok/s
- TTFT Δ: +9254.42 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.81x (sequential time / concurrent time)
- **Efficiency:** 90.7% (speedup / ideal 2x speedup)
- **Contention:** Low
