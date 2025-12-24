# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.77s
**Sequential Estimated Time:** 114.99s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.77s

```
Throughput: 38.84 tok/s
TTFT: 256.35 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.22s

```
Throughput: 38.15 tok/s
TTFT: 505.89 ms
```

## Performance Delta
- Throughput Δ: -0.70 tok/s
- TTFT Δ: -249.54 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.5% (speedup / ideal 2x speedup)
- **Contention:** Low
