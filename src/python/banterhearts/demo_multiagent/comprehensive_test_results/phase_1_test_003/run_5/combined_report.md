# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 115.28s
**Sequential Estimated Time:** 203.25s
**Concurrency Speedup:** 1.76x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 115.28s

```
Throughput: 43.85 tok/s
TTFT: 29821.65 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 87.96s

```
Throughput: 44.17 tok/s
TTFT: 19906.54 ms
```

## Performance Delta
- Throughput Δ: +0.32 tok/s
- TTFT Δ: +9915.11 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.76x (sequential time / concurrent time)
- **Efficiency:** 88.1% (speedup / ideal 2x speedup)
- **Contention:** Low
