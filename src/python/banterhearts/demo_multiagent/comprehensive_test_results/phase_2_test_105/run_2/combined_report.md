# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.42s
**Sequential Estimated Time:** 113.74s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.42s

```
Throughput: 39.61 tok/s
TTFT: 508.85 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 56.32s

```
Throughput: 38.18 tok/s
TTFT: 540.69 ms
```

## Performance Delta
- Throughput Δ: -1.44 tok/s
- TTFT Δ: -31.84 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.0% (speedup / ideal 2x speedup)
- **Contention:** Low
