# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.52s
**Sequential Estimated Time:** 115.81s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.50s

```
Throughput: 38.70 tok/s
TTFT: 263.77 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 58.31s

```
Throughput: 39.55 tok/s
TTFT: 485.30 ms
```

## Performance Delta
- Throughput Δ: +0.85 tok/s
- TTFT Δ: -221.53 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.9% (speedup / ideal 2x speedup)
- **Contention:** Low
