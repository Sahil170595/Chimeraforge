# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 109.93s
**Sequential Estimated Time:** 201.55s
**Concurrency Speedup:** 1.83x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 109.93s

```
Throughput: 38.20 tok/s
TTFT: 25105.99 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 91.61s

```
Throughput: 44.12 tok/s
TTFT: 544.13 ms
```

## Performance Delta
- Throughput Δ: +5.91 tok/s
- TTFT Δ: +24561.86 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.83x (sequential time / concurrent time)
- **Efficiency:** 91.7% (speedup / ideal 2x speedup)
- **Contention:** Low
