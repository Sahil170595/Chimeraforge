# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 104.20s
**Sequential Estimated Time:** 202.86s
**Concurrency Speedup:** 1.95x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 98.99s

```
Throughput: 43.67 tok/s
TTFT: 24159.24 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 103.87s

```
Throughput: 44.13 tok/s
TTFT: 28162.92 ms
```

## Performance Delta
- Throughput Δ: +0.46 tok/s
- TTFT Δ: -4003.68 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.95x (sequential time / concurrent time)
- **Efficiency:** 97.3% (speedup / ideal 2x speedup)
- **Contention:** Low
