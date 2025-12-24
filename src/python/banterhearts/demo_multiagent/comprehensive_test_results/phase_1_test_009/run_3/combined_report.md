# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 107.43s
**Sequential Estimated Time:** 197.45s
**Concurrency Speedup:** 1.84x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 90.27s

```
Throughput: 43.62 tok/s
TTFT: 20683.68 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 107.17s

```
Throughput: 42.98 tok/s
TTFT: 28220.44 ms
```

## Performance Delta
- Throughput Δ: -0.63 tok/s
- TTFT Δ: -7536.76 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.84x (sequential time / concurrent time)
- **Efficiency:** 91.9% (speedup / ideal 2x speedup)
- **Contention:** Low
