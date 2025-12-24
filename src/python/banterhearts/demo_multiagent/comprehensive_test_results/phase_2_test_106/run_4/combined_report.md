# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.80s
**Sequential Estimated Time:** 112.92s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.35s

```
Throughput: 38.84 tok/s
TTFT: 500.01 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.57s

```
Throughput: 38.66 tok/s
TTFT: 538.65 ms
```

## Performance Delta
- Throughput Δ: -0.18 tok/s
- TTFT Δ: -38.65 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
