# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 112.00s
**Sequential Estimated Time:** 219.76s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 108.00s

```
Throughput: 43.39 tok/s
TTFT: 28965.41 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 100, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 111.76s

```
Throughput: 43.27 tok/s
TTFT: 29421.60 ms
```

## Performance Delta
- Throughput Δ: -0.11 tok/s
- TTFT Δ: -456.18 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.1% (speedup / ideal 2x speedup)
- **Contention:** Low
