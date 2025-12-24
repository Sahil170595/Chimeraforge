# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.64s
**Sequential Estimated Time:** 116.99s
**Concurrency Speedup:** 2.00x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 58.64s

```
Throughput: 38.31 tok/s
TTFT: 260.95 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 58.35s

```
Throughput: 38.31 tok/s
TTFT: 485.45 ms
```

## Performance Delta
- Throughput Δ: -0.00 tok/s
- TTFT Δ: -224.50 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 2.00x (sequential time / concurrent time)
- **Efficiency:** 99.8% (speedup / ideal 2x speedup)
- **Contention:** Low
