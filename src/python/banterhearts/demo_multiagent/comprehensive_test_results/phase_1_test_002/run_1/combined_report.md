# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 107.43s
**Sequential Estimated Time:** 155.01s
**Concurrency Speedup:** 1.44x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 107.42s

```
Throughput: 55.94 tok/s
TTFT: 32232.09 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 47.58s

```
Throughput: 42.71 tok/s
TTFT: 517.00 ms
```

## Performance Delta
- Throughput Δ: -13.23 tok/s
- TTFT Δ: +31715.09 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.44x (sequential time / concurrent time)
- **Efficiency:** 72.1% (speedup / ideal 2x speedup)
- **Contention:** High
