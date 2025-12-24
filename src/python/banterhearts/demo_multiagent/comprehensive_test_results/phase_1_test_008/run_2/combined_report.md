# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.90s
**Sequential Estimated Time:** 154.85s
**Concurrency Speedup:** 1.45x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 48.20s

```
Throughput: 43.48 tok/s
TTFT: 470.51 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 106.65s

```
Throughput: 61.30 tok/s
TTFT: 33550.14 ms
```

## Performance Delta
- Throughput Δ: +17.82 tok/s
- TTFT Δ: -33079.63 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.45x (sequential time / concurrent time)
- **Efficiency:** 72.4% (speedup / ideal 2x speedup)
- **Contention:** High
