# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.44s
**Sequential Estimated Time:** 113.74s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.53s

```
Throughput: 38.85 tok/s
TTFT: 327.08 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.21s

```
Throughput: 39.66 tok/s
TTFT: 491.55 ms
```

## Performance Delta
- Throughput Δ: +0.81 tok/s
- TTFT Δ: -164.48 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.0% (speedup / ideal 2x speedup)
- **Contention:** Low
