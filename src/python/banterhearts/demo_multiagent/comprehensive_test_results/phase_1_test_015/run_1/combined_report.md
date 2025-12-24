# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 61.02s
**Sequential Estimated Time:** 121.05s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 61.02s

```
Throughput: 39.88 tok/s
TTFT: 1771.23 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 60.03s

```
Throughput: 38.46 tok/s
TTFT: 1443.95 ms
```

## Performance Delta
- Throughput Δ: -1.42 tok/s
- TTFT Δ: +327.28 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.2% (speedup / ideal 2x speedup)
- **Contention:** Low
