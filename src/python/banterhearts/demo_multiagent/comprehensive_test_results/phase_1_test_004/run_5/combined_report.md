# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 110.13s
**Sequential Estimated Time:** 199.20s
**Concurrency Speedup:** 1.81x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 110.13s

```
Throughput: 42.60 tok/s
TTFT: 29249.67 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 89.07s

```
Throughput: 42.48 tok/s
TTFT: 18356.01 ms
```

## Performance Delta
- Throughput Δ: -0.12 tok/s
- TTFT Δ: +10893.65 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.81x (sequential time / concurrent time)
- **Efficiency:** 90.4% (speedup / ideal 2x speedup)
- **Contention:** Low
