# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.77s
**Sequential Estimated Time:** 112.47s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.00s

```
Throughput: 39.20 tok/s
TTFT: 449.71 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.46s

```
Throughput: 39.59 tok/s
TTFT: 483.39 ms
```

## Performance Delta
- Throughput Δ: +0.39 tok/s
- TTFT Δ: -33.68 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.1% (speedup / ideal 2x speedup)
- **Contention:** Low
