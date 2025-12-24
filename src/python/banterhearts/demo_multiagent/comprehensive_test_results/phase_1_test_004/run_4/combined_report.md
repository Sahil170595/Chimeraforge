# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 110.55s
**Sequential Estimated Time:** 167.78s
**Concurrency Speedup:** 1.52x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 110.55s

```
Throughput: 38.76 tok/s
TTFT: 26236.08 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.23s

```
Throughput: 40.96 tok/s
TTFT: 1637.44 ms
```

## Performance Delta
- Throughput Δ: +2.20 tok/s
- TTFT Δ: +24598.64 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.52x (sequential time / concurrent time)
- **Efficiency:** 75.9% (speedup / ideal 2x speedup)
- **Contention:** Low
