# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 109.35s
**Sequential Estimated Time:** 198.10s
**Concurrency Speedup:** 1.81x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 109.35s

```
Throughput: 43.97 tok/s
TTFT: 28298.72 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 88.74s

```
Throughput: 43.75 tok/s
TTFT: 18842.50 ms
```

## Performance Delta
- Throughput Δ: -0.22 tok/s
- TTFT Δ: +9456.22 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.81x (sequential time / concurrent time)
- **Efficiency:** 90.6% (speedup / ideal 2x speedup)
- **Contention:** Low
