# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.51s
**Sequential Estimated Time:** 113.62s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.35s

```
Throughput: 39.13 tok/s
TTFT: 443.95 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.27s

```
Throughput: 40.02 tok/s
TTFT: 485.54 ms
```

## Performance Delta
- Throughput Δ: +0.89 tok/s
- TTFT Δ: -41.59 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.8% (speedup / ideal 2x speedup)
- **Contention:** Low
