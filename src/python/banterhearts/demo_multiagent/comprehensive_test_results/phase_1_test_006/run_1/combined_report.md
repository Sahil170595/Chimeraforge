# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 110.34s
**Sequential Estimated Time:** 197.13s
**Concurrency Speedup:** 1.79x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 110.34s

```
Throughput: 43.81 tok/s
TTFT: 29021.78 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 86.79s

```
Throughput: 43.40 tok/s
TTFT: 16509.75 ms
```

## Performance Delta
- Throughput Δ: -0.41 tok/s
- TTFT Δ: +12512.03 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.79x (sequential time / concurrent time)
- **Efficiency:** 89.3% (speedup / ideal 2x speedup)
- **Contention:** Low
