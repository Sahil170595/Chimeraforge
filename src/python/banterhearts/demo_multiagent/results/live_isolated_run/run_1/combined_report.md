# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 67.84s
**Sequential Estimated Time:** 130.68s
**Concurrency Speedup:** 1.93x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://127.0.0.1:11434
Execution Time: 67.84s

```
Throughput: 41.79 tok/s
TTFT: 1781.40 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://127.0.0.1:11435
Execution Time: 62.83s

```
Throughput: 37.35 tok/s
TTFT: 1863.88 ms
```

## Performance Delta
- Throughput Δ: -4.44 tok/s
- TTFT Δ: -82.48 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.93x (sequential time / concurrent time)
- **Efficiency:** 96.3% (speedup / ideal 2x speedup)
- **Contention:** Low
