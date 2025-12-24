# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 56.94s
**Sequential Estimated Time:** 113.02s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.35s

```
Throughput: 39.02 tok/s
TTFT: 448.31 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.67s

```
Throughput: 39.27 tok/s
TTFT: 490.76 ms
```

## Performance Delta
- Throughput Δ: +0.25 tok/s
- TTFT Δ: -42.45 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.2% (speedup / ideal 2x speedup)
- **Contention:** Low
