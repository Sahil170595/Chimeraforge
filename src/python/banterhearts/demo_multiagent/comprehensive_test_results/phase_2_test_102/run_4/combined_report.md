# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.88s
**Sequential Estimated Time:** 114.69s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.02s

```
Throughput: 38.99 tok/s
TTFT: 444.85 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 57.67s

```
Throughput: 39.54 tok/s
TTFT: 481.04 ms
```

## Performance Delta
- Throughput Δ: +0.55 tok/s
- TTFT Δ: -36.19 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.1% (speedup / ideal 2x speedup)
- **Contention:** Low
