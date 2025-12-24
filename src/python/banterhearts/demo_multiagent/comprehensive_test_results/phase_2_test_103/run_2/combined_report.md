# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.58s
**Sequential Estimated Time:** 111.84s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.51s

```
Throughput: 38.63 tok/s
TTFT: 274.87 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.33s

```
Throughput: 39.73 tok/s
TTFT: 492.63 ms
```

## Performance Delta
- Throughput Δ: +1.10 tok/s
- TTFT Δ: -217.77 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.8% (speedup / ideal 2x speedup)
- **Contention:** Low
