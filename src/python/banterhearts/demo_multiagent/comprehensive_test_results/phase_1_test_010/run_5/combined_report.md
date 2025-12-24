# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 119.98s
**Sequential Estimated Time:** 224.28s
**Concurrency Speedup:** 1.87x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 119.98s

```
Throughput: 41.56 tok/s
TTFT: 34080.79 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 104.30s

```
Throughput: 40.80 tok/s
TTFT: 27569.06 ms
```

## Performance Delta
- Throughput Δ: -0.77 tok/s
- TTFT Δ: +6511.73 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.87x (sequential time / concurrent time)
- **Efficiency:** 93.5% (speedup / ideal 2x speedup)
- **Contention:** Low
