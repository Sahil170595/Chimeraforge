# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 60.51s
**Sequential Estimated Time:** 120.65s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 60.42s

```
Throughput: 38.54 tok/s
TTFT: 428.09 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 60.22s

```
Throughput: 38.28 tok/s
TTFT: 525.74 ms
```

## Performance Delta
- Throughput Δ: -0.26 tok/s
- TTFT Δ: -97.65 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.7% (speedup / ideal 2x speedup)
- **Contention:** Low
