# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 54.44s
**Sequential Estimated Time:** 107.34s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.12s

```
Throughput: 39.03 tok/s
TTFT: 451.52 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 54.22s

```
Throughput: 40.20 tok/s
TTFT: 484.55 ms
```

## Performance Delta
- Throughput Δ: +1.17 tok/s
- TTFT Δ: -33.02 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.6% (speedup / ideal 2x speedup)
- **Contention:** Low
