# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 103.26s
**Sequential Estimated Time:** 192.25s
**Concurrency Speedup:** 1.86x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 103.26s

```
Throughput: 44.17 tok/s
TTFT: 26499.32 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 88.99s

```
Throughput: 43.75 tok/s
TTFT: 18250.04 ms
```

## Performance Delta
- Throughput Δ: -0.42 tok/s
- TTFT Δ: +8249.28 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.86x (sequential time / concurrent time)
- **Efficiency:** 93.1% (speedup / ideal 2x speedup)
- **Contention:** Low
