# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 55.53s
**Sequential Estimated Time:** 110.13s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 54.83s

```
Throughput: 39.01 tok/s
TTFT: 445.79 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 55.31s

```
Throughput: 19.60 tok/s
TTFT: 114.12 ms
```

## Performance Delta
- Throughput Δ: -19.42 tok/s
- TTFT Δ: +331.66 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.2% (speedup / ideal 2x speedup)
- **Contention:** Low
