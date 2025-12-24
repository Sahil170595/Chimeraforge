# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.23s
**Sequential Estimated Time:** 114.85s
**Concurrency Speedup:** 1.97x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.84s

```
Throughput: 38.88 tok/s
TTFT: 456.86 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 58.00s

```
Throughput: 40.08 tok/s
TTFT: 484.22 ms
```

## Performance Delta
- Throughput Δ: +1.20 tok/s
- TTFT Δ: -27.36 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.97x (sequential time / concurrent time)
- **Efficiency:** 98.6% (speedup / ideal 2x speedup)
- **Contention:** Low
