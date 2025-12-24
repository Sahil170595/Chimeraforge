# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 50.25s
**Sequential Estimated Time:** 84.13s
**Concurrency Speedup:** 1.67x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Execution Time: 50.25s

```
Throughput: 105.19 tok/s
TTFT: 13030.14 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Execution Time: 33.88s

```
Throughput: 106.27 tok/s
TTFT: 6672.04 ms
```

## Performance Delta
- Throughput Δ: +1.08 tok/s
- TTFT Δ: +6358.09 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.67x (sequential time / concurrent time)
- **Efficiency:** 83.7% (speedup / ideal 2x speedup)
- **Contention:** Low
