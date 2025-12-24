# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.10s
**Sequential Estimated Time:** 111.07s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.27s

```
Throughput: 38.94 tok/s
TTFT: 460.84 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 55.80s

```
Throughput: 39.51 tok/s
TTFT: 492.80 ms
```

## Performance Delta
- Throughput Δ: +0.56 tok/s
- TTFT Δ: -31.96 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.0% (speedup / ideal 2x speedup)
- **Contention:** Low
