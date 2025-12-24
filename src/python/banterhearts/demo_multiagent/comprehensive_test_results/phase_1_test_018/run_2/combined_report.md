# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.59s
**Sequential Estimated Time:** 111.97s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.60s

```
Throughput: 38.36 tok/s
TTFT: 283.98 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.37s

```
Throughput: 39.44 tok/s
TTFT: 491.61 ms
```

## Performance Delta
- Throughput Δ: +1.08 tok/s
- TTFT Δ: -207.63 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 98.9% (speedup / ideal 2x speedup)
- **Contention:** Low
