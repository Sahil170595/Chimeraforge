# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 108.40s
**Sequential Estimated Time:** 192.76s
**Concurrency Speedup:** 1.78x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 108.40s

```
Throughput: 44.06 tok/s
TTFT: 28521.44 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 84.35s

```
Throughput: 43.48 tok/s
TTFT: 17048.59 ms
```

## Performance Delta
- Throughput Δ: -0.57 tok/s
- TTFT Δ: +11472.84 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.78x (sequential time / concurrent time)
- **Efficiency:** 88.9% (speedup / ideal 2x speedup)
- **Contention:** Low
