# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.77s
**Sequential Estimated Time:** 112.88s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.43s

```
Throughput: 38.50 tok/s
TTFT: 283.02 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.45s

```
Throughput: 38.91 tok/s
TTFT: 486.56 ms
```

## Performance Delta
- Throughput Δ: +0.41 tok/s
- TTFT Δ: -203.54 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
