# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 108.43s
**Sequential Estimated Time:** 193.07s
**Concurrency Speedup:** 1.78x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 108.43s

```
Throughput: 44.14 tok/s
TTFT: 27598.43 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 84.64s

```
Throughput: 43.92 tok/s
TTFT: 17278.63 ms
```

## Performance Delta
- Throughput Δ: -0.22 tok/s
- TTFT Δ: +10319.80 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.78x (sequential time / concurrent time)
- **Efficiency:** 89.0% (speedup / ideal 2x speedup)
- **Contention:** Low
