# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.75s
**Sequential Estimated Time:** 112.16s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.67s

```
Throughput: 39.14 tok/s
TTFT: 447.25 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.49s

```
Throughput: 39.90 tok/s
TTFT: 490.58 ms
```

## Performance Delta
- Throughput Δ: +0.76 tok/s
- TTFT Δ: -43.32 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.8% (speedup / ideal 2x speedup)
- **Contention:** Low
