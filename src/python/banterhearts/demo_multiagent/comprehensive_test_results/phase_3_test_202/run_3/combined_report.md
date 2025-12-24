# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 57.30s
**Sequential Estimated Time:** 112.16s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.30s

```
Throughput: 40.82 tok/s
TTFT: 239.33 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 54.86s

```
Throughput: 38.55 tok/s
TTFT: 481.86 ms
```

## Performance Delta
- Throughput Δ: -2.27 tok/s
- TTFT Δ: -242.53 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 97.9% (speedup / ideal 2x speedup)
- **Contention:** Low
