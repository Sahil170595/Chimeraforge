# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 113.39s
**Sequential Estimated Time:** 199.84s
**Concurrency Speedup:** 1.76x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 113.39s

```
Throughput: 42.47 tok/s
TTFT: 29848.16 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 86.45s

```
Throughput: 42.30 tok/s
TTFT: 16722.22 ms
```

## Performance Delta
- Throughput Δ: -0.17 tok/s
- TTFT Δ: +13125.95 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.76x (sequential time / concurrent time)
- **Efficiency:** 88.1% (speedup / ideal 2x speedup)
- **Contention:** Low
