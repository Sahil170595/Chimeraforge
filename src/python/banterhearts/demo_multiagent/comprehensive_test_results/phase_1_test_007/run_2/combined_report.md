# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.16s
**Sequential Estimated Time:** 208.44s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 103.20s

```
Throughput: 42.04 tok/s
TTFT: 548.80 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 105.23s

```
Throughput: 38.11 tok/s
TTFT: 22857.25 ms
```

## Performance Delta
- Throughput Δ: -3.93 tok/s
- TTFT Δ: -22308.46 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.2% (speedup / ideal 2x speedup)
- **Contention:** Low
