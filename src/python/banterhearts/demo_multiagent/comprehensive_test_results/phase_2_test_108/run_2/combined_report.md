# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 59.28s
**Sequential Estimated Time:** 118.23s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 59.19s

```
Throughput: 38.21 tok/s
TTFT: 259.78 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 59.04s

```
Throughput: 38.16 tok/s
TTFT: 484.28 ms
```

## Performance Delta
- Throughput Δ: -0.06 tok/s
- TTFT Δ: -224.49 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.7% (speedup / ideal 2x speedup)
- **Contention:** Low
