# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 118.88s
**Sequential Estimated Time:** 181.60s
**Concurrency Speedup:** 1.53x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 118.88s

```
Throughput: 41.17 tok/s
TTFT: 33177.05 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 62.72s

```
Throughput: 40.75 tok/s
TTFT: 4726.53 ms
```

## Performance Delta
- Throughput Δ: -0.42 tok/s
- TTFT Δ: +28450.53 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.53x (sequential time / concurrent time)
- **Efficiency:** 76.4% (speedup / ideal 2x speedup)
- **Contention:** Low
