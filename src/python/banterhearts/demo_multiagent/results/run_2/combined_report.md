# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 41.09s
**Sequential Estimated Time:** 69.85s
**Concurrency Speedup:** 1.70x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 29.01s

```
Throughput: 75.85 tok/s
TTFT: 455.76 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 40.84s

```
Throughput: 68.86 tok/s
TTFT: 354.02 ms
```

## Performance Delta
- Throughput Δ: -6.99 tok/s
- TTFT Δ: +101.73 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.70x (sequential time / concurrent time)
- **Efficiency:** 85.0% (speedup / ideal 2x speedup)
- **Contention:** Low
