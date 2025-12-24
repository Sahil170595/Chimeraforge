# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 61.47s
**Sequential Estimated Time:** 120.36s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://127.0.0.1:11434
Execution Time: 61.47s

```
Throughput: 39.27 tok/s
TTFT: 299.91 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://127.0.0.1:11435
Execution Time: 58.89s

```
Throughput: 37.27 tok/s
TTFT: 497.41 ms
```

## Performance Delta
- Throughput Δ: -2.01 tok/s
- TTFT Δ: -197.50 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 97.9% (speedup / ideal 2x speedup)
- **Contention:** Low
