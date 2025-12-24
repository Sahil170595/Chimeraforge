# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 76.51s
**Sequential Estimated Time:** 145.29s
**Concurrency Speedup:** 1.90x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 76.51s

```
Throughput: 55.25 tok/s
TTFT: 17620.65 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 140, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 68.78s

```
Throughput: 41.41 tok/s
TTFT: 8159.83 ms
```

## Performance Delta
- Throughput Δ: -13.84 tok/s
- TTFT Δ: +9460.82 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.90x (sequential time / concurrent time)
- **Efficiency:** 95.0% (speedup / ideal 2x speedup)
- **Contention:** Low
