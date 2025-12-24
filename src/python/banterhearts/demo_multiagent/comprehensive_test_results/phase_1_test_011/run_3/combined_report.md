# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 110.99s
**Sequential Estimated Time:** 196.86s
**Concurrency Speedup:** 1.77x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 110.99s

```
Throughput: 43.54 tok/s
TTFT: 29536.60 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 85.87s

```
Throughput: 43.90 tok/s
TTFT: 18312.04 ms
```

## Performance Delta
- Throughput Δ: +0.35 tok/s
- TTFT Δ: +11224.56 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.77x (sequential time / concurrent time)
- **Efficiency:** 88.7% (speedup / ideal 2x speedup)
- **Contention:** Low
