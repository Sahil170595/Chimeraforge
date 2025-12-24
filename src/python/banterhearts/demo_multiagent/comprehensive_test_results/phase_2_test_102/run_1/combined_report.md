# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.24s
**Sequential Estimated Time:** 109.86s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 54.90s

```
Throughput: 38.71 tok/s
TTFT: 494.61 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 54.96s

```
Throughput: 38.54 tok/s
TTFT: 529.45 ms
```

## Performance Delta
- Throughput Δ: -0.16 tok/s
- TTFT Δ: -34.83 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
