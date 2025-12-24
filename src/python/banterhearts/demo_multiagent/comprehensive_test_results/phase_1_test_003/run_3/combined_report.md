# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 114.34s
**Sequential Estimated Time:** 198.54s
**Concurrency Speedup:** 1.74x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 114.34s

```
Throughput: 43.37 tok/s
TTFT: 27876.46 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 84.20s

```
Throughput: 43.77 tok/s
TTFT: 17480.78 ms
```

## Performance Delta
- Throughput Δ: +0.40 tok/s
- TTFT Δ: +10395.68 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.74x (sequential time / concurrent time)
- **Efficiency:** 86.8% (speedup / ideal 2x speedup)
- **Contention:** Low
