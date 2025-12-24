# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.77s
**Sequential Estimated Time:** 115.42s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 58.77s

```
Throughput: 40.83 tok/s
TTFT: 855.59 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.65s

```
Throughput: 38.29 tok/s
TTFT: 779.96 ms
```

## Performance Delta
- Throughput Δ: -2.55 tok/s
- TTFT Δ: +75.63 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.2% (speedup / ideal 2x speedup)
- **Contention:** Low
