# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 98.83s
**Sequential Estimated Time:** 191.18s
**Concurrency Speedup:** 1.93x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 98.83s

```
Throughput: 53.09 tok/s
TTFT: 29844.58 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 92.35s

```
Throughput: 41.37 tok/s
TTFT: 20570.09 ms
```

## Performance Delta
- Throughput Δ: -11.72 tok/s
- TTFT Δ: +9274.49 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.93x (sequential time / concurrent time)
- **Efficiency:** 96.7% (speedup / ideal 2x speedup)
- **Contention:** Low
