# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 54.34s
**Sequential Estimated Time:** 108.15s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 54.08s

```
Throughput: 39.00 tok/s
TTFT: 453.73 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 54.06s

```
Throughput: 38.79 tok/s
TTFT: 469.43 ms
```

## Performance Delta
- Throughput Δ: -0.21 tok/s
- TTFT Δ: -15.70 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.5% (speedup / ideal 2x speedup)
- **Contention:** Low
