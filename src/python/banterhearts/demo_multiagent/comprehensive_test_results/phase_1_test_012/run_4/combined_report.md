# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 118.24s
**Sequential Estimated Time:** 222.32s
**Concurrency Speedup:** 1.88x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 118.24s

```
Throughput: 43.23 tok/s
TTFT: 33013.79 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 104.08s

```
Throughput: 43.35 tok/s
TTFT: 25787.87 ms
```

## Performance Delta
- Throughput Δ: +0.12 tok/s
- TTFT Δ: +7225.93 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.88x (sequential time / concurrent time)
- **Efficiency:** 94.0% (speedup / ideal 2x speedup)
- **Contention:** Low
