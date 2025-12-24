# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 60.51s
**Sequential Estimated Time:** 120.20s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 59.98s

```
Throughput: 39.05 tok/s
TTFT: 1736.82 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 60.21s

```
Throughput: 39.04 tok/s
TTFT: 1527.36 ms
```

## Performance Delta
- Throughput Δ: -0.00 tok/s
- TTFT Δ: +209.47 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.3% (speedup / ideal 2x speedup)
- **Contention:** Low
