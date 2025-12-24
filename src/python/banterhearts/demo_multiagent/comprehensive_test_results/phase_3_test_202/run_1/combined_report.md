# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 59.84s
**Sequential Estimated Time:** 116.57s
**Concurrency Speedup:** 1.95x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 59.84s

```
Throughput: 41.92 tok/s
TTFT: 2299.72 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.73s

```
Throughput: 43.94 tok/s
TTFT: 460.98 ms
```

## Performance Delta
- Throughput Δ: +2.01 tok/s
- TTFT Δ: +1838.74 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.95x (sequential time / concurrent time)
- **Efficiency:** 97.4% (speedup / ideal 2x speedup)
- **Contention:** Low
