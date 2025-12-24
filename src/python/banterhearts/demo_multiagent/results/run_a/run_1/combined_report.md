# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 51.99s
**Sequential Estimated Time:** 90.18s
**Concurrency Speedup:** 1.73x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Execution Time: 38.47s

```
Throughput: 106.61 tok/s
TTFT: 7822.50 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Execution Time: 51.71s

```
Throughput: 106.63 tok/s
TTFT: 15366.84 ms
```

## Performance Delta
- Throughput Δ: +0.02 tok/s
- TTFT Δ: -7544.34 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.73x (sequential time / concurrent time)
- **Efficiency:** 86.7% (speedup / ideal 2x speedup)
- **Contention:** Low
