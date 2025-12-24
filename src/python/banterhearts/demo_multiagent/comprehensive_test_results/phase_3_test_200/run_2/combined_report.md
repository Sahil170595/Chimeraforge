# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.69s
**Sequential Estimated Time:** 113.01s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.69s

```
Throughput: 41.46 tok/s
TTFT: 459.86 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.32s

```
Throughput: 38.48 tok/s
TTFT: 482.61 ms
```

## Performance Delta
- Throughput Δ: -2.99 tok/s
- TTFT Δ: -22.75 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 97.9% (speedup / ideal 2x speedup)
- **Contention:** Low
