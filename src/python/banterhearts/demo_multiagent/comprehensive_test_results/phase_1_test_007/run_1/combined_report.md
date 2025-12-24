# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 107.86s
**Sequential Estimated Time:** 197.09s
**Concurrency Speedup:** 1.83x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 107.86s

```
Throughput: 43.53 tok/s
TTFT: 1075.90 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 89.23s

```
Throughput: 37.95 tok/s
TTFT: 16589.28 ms
```

## Performance Delta
- Throughput Δ: -5.57 tok/s
- TTFT Δ: -15513.38 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.83x (sequential time / concurrent time)
- **Efficiency:** 91.4% (speedup / ideal 2x speedup)
- **Contention:** Low
