# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.59s
**Sequential Estimated Time:** 115.83s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 58.58s

```
Throughput: 39.72 tok/s
TTFT: 874.91 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.25s

```
Throughput: 38.17 tok/s
TTFT: 867.07 ms
```

## Performance Delta
- Throughput Δ: -1.56 tok/s
- TTFT Δ: +7.85 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.9% (speedup / ideal 2x speedup)
- **Contention:** Low
