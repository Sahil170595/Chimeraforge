# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.75s
**Sequential Estimated Time:** 109.80s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 54.30s

```
Throughput: 38.46 tok/s
TTFT: 264.42 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.50s

```
Throughput: 40.01 tok/s
TTFT: 480.71 ms
```

## Performance Delta
- Throughput Δ: +1.54 tok/s
- TTFT Δ: -216.28 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.5% (speedup / ideal 2x speedup)
- **Contention:** Low
