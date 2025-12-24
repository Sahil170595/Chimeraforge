# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.04s
**Sequential Estimated Time:** 110.12s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.04s

```
Throughput: 40.50 tok/s
TTFT: 259.51 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 54.08s

```
Throughput: 38.16 tok/s
TTFT: 491.63 ms
```

## Performance Delta
- Throughput Δ: -2.34 tok/s
- TTFT Δ: -232.11 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.2% (speedup / ideal 2x speedup)
- **Contention:** Low
