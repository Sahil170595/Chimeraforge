# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 55.68s
**Sequential Estimated Time:** 97.08s
**Concurrency Speedup:** 1.74x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Execution Time: 41.66s

```
Throughput: 105.94 tok/s
TTFT: 9082.97 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Execution Time: 55.42s

```
Throughput: 102.54 tok/s
TTFT: 16138.57 ms
```

## Performance Delta
- Throughput Δ: -3.40 tok/s
- TTFT Δ: -7055.60 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.74x (sequential time / concurrent time)
- **Efficiency:** 87.2% (speedup / ideal 2x speedup)
- **Contention:** Low
