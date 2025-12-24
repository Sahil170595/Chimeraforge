# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.94s
**Sequential Estimated Time:** 110.27s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.94s

```
Throughput: 40.71 tok/s
TTFT: 469.86 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 54.33s

```
Throughput: 38.13 tok/s
TTFT: 319.47 ms
```

## Performance Delta
- Throughput Δ: -2.58 tok/s
- TTFT Δ: +150.40 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.6% (speedup / ideal 2x speedup)
- **Contention:** Low
