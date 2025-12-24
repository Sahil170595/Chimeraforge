# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 56.74s
**Sequential Estimated Time:** 110.35s
**Concurrency Speedup:** 1.95x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 56.74s

```
Throughput: 42.00 tok/s
TTFT: 321.88 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 53.62s

```
Throughput: 38.78 tok/s
TTFT: 477.61 ms
```

## Performance Delta
- Throughput Δ: -3.21 tok/s
- TTFT Δ: -155.73 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.95x (sequential time / concurrent time)
- **Efficiency:** 97.3% (speedup / ideal 2x speedup)
- **Contention:** Low
