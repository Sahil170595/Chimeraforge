# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.89s
**Sequential Estimated Time:** 113.09s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.46s

```
Throughput: 38.84 tok/s
TTFT: 404.33 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.63s

```
Throughput: 38.92 tok/s
TTFT: 484.10 ms
```

## Performance Delta
- Throughput Δ: +0.08 tok/s
- TTFT Δ: -79.76 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
