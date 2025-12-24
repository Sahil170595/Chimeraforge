# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.59s
**Sequential Estimated Time:** 114.90s
**Concurrency Speedup:** 2.00x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.59s

```
Throughput: 38.43 tok/s
TTFT: 487.98 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.31s

```
Throughput: 38.21 tok/s
TTFT: 506.91 ms
```

## Performance Delta
- Throughput Δ: -0.22 tok/s
- TTFT Δ: -18.93 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 2.00x (sequential time / concurrent time)
- **Efficiency:** 99.8% (speedup / ideal 2x speedup)
- **Contention:** Low
