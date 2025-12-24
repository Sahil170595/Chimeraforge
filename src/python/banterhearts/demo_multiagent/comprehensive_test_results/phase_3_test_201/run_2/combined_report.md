# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 56.52s
**Sequential Estimated Time:** 111.76s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.45s

```
Throughput: 38.67 tok/s
TTFT: 328.60 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.31s

```
Throughput: 39.72 tok/s
TTFT: 501.10 ms
```

## Performance Delta
- Throughput Δ: +1.05 tok/s
- TTFT Δ: -172.50 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.9% (speedup / ideal 2x speedup)
- **Contention:** Low
