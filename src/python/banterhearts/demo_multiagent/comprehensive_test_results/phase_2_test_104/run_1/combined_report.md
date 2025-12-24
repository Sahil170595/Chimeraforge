# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.06s
**Sequential Estimated Time:** 109.32s
**Concurrency Speedup:** 1.95x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.55s

```
Throughput: 39.03 tok/s
TTFT: 449.79 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.77s

```
Throughput: 41.52 tok/s
TTFT: 491.65 ms
```

## Performance Delta
- Throughput Δ: +2.48 tok/s
- TTFT Δ: -41.87 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.95x (sequential time / concurrent time)
- **Efficiency:** 97.5% (speedup / ideal 2x speedup)
- **Contention:** Low
