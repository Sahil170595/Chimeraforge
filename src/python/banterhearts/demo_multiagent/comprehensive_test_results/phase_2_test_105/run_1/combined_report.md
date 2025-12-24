# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 55.54s
**Sequential Estimated Time:** 109.41s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.54s

```
Throughput: 40.42 tok/s
TTFT: 502.63 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 53.87s

```
Throughput: 38.07 tok/s
TTFT: 527.69 ms
```

## Performance Delta
- Throughput Δ: -2.35 tok/s
- TTFT Δ: -25.06 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.5% (speedup / ideal 2x speedup)
- **Contention:** Low
