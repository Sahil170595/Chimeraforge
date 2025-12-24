# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.08s
**Sequential Estimated Time:** 113.11s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.25s

```
Throughput: 38.53 tok/s
TTFT: 274.52 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.85s

```
Throughput: 39.37 tok/s
TTFT: 486.95 ms
```

## Performance Delta
- Throughput Δ: +0.85 tok/s
- TTFT Δ: -212.43 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.1% (speedup / ideal 2x speedup)
- **Contention:** Low
