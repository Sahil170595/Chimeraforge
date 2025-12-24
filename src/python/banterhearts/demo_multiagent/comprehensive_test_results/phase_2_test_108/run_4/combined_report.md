# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.50s
**Sequential Estimated Time:** 114.19s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.91s

```
Throughput: 38.58 tok/s
TTFT: 517.12 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 57.28s

```
Throughput: 38.69 tok/s
TTFT: 526.38 ms
```

## Performance Delta
- Throughput Δ: +0.11 tok/s
- TTFT Δ: -9.26 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.3% (speedup / ideal 2x speedup)
- **Contention:** Low
