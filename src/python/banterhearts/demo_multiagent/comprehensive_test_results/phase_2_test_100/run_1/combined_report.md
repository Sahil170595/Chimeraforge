# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.90s
**Sequential Estimated Time:** 115.30s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.71s

```
Throughput: 38.83 tok/s
TTFT: 1788.53 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 58.58s

```
Throughput: 41.27 tok/s
TTFT: 1677.45 ms
```

## Performance Delta
- Throughput Δ: +2.43 tok/s
- TTFT Δ: +111.08 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 97.9% (speedup / ideal 2x speedup)
- **Contention:** Low
