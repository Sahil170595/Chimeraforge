# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.72s
**Sequential Estimated Time:** 110.62s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.12s

```
Throughput: 39.11 tok/s
TTFT: 450.70 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 55.50s

```
Throughput: 39.23 tok/s
TTFT: 503.39 ms
```

## Performance Delta
- Throughput Δ: +0.11 tok/s
- TTFT Δ: -52.68 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.3% (speedup / ideal 2x speedup)
- **Contention:** Low
