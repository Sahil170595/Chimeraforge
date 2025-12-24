# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 59.00s
**Sequential Estimated Time:** 116.22s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.42s

```
Throughput: 39.20 tok/s
TTFT: 458.62 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 58.80s

```
Throughput: 40.42 tok/s
TTFT: 486.82 ms
```

## Performance Delta
- Throughput Δ: +1.23 tok/s
- TTFT Δ: -28.20 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.5% (speedup / ideal 2x speedup)
- **Contention:** Low
