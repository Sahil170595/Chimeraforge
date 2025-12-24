# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 118.25s
**Sequential Estimated Time:** 204.24s
**Concurrency Speedup:** 1.73x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 118.24s

```
Throughput: 43.46 tok/s
TTFT: 32299.43 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 86.00s

```
Throughput: 41.66 tok/s
TTFT: 334.85 ms
```

## Performance Delta
- Throughput Δ: -1.80 tok/s
- TTFT Δ: +31964.58 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.73x (sequential time / concurrent time)
- **Efficiency:** 86.4% (speedup / ideal 2x speedup)
- **Contention:** Low
