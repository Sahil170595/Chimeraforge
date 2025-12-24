# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.95s
**Sequential Estimated Time:** 111.20s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.48s

```
Throughput: 38.95 tok/s
TTFT: 451.14 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 55.72s

```
Throughput: 39.06 tok/s
TTFT: 495.38 ms
```

## Performance Delta
- Throughput Δ: +0.11 tok/s
- TTFT Δ: -44.24 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
