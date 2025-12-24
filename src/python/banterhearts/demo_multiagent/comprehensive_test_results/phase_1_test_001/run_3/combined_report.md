# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 112.59s
**Sequential Estimated Time:** 167.90s
**Concurrency Speedup:** 1.49x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 112.59s

```
Throughput: 43.52 tok/s
TTFT: 30510.06 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.32s

```
Throughput: 42.35 tok/s
TTFT: 269.55 ms
```

## Performance Delta
- Throughput Δ: -1.17 tok/s
- TTFT Δ: +30240.51 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.49x (sequential time / concurrent time)
- **Efficiency:** 74.6% (speedup / ideal 2x speedup)
- **Contention:** High
