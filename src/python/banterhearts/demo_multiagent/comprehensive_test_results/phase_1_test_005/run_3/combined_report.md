# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 113.49s
**Sequential Estimated Time:** 197.17s
**Concurrency Speedup:** 1.74x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 113.49s

```
Throughput: 43.40 tok/s
TTFT: 27999.17 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 83.68s

```
Throughput: 43.85 tok/s
TTFT: 17410.94 ms
```

## Performance Delta
- Throughput Δ: +0.45 tok/s
- TTFT Δ: +10588.23 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.74x (sequential time / concurrent time)
- **Efficiency:** 86.9% (speedup / ideal 2x speedup)
- **Contention:** Low
