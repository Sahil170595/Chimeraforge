# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.36s
**Sequential Estimated Time:** 110.10s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.36s

```
Throughput: 39.44 tok/s
TTFT: 454.95 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 54.74s

```
Throughput: 38.64 tok/s
TTFT: 483.75 ms
```

## Performance Delta
- Throughput Δ: -0.80 tok/s
- TTFT Δ: -28.79 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
