# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 59.24s
**Sequential Estimated Time:** 117.65s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 58.64s

```
Throughput: 39.05 tok/s
TTFT: 463.30 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 59.01s

```
Throughput: 39.32 tok/s
TTFT: 486.39 ms
```

## Performance Delta
- Throughput Δ: +0.27 tok/s
- TTFT Δ: -23.08 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.3% (speedup / ideal 2x speedup)
- **Contention:** Low
