# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 59.35s
**Sequential Estimated Time:** 115.87s
**Concurrency Speedup:** 1.95x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 59.35s

```
Throughput: 41.78 tok/s
TTFT: 311.56 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.52s

```
Throughput: 38.76 tok/s
TTFT: 486.12 ms
```

## Performance Delta
- Throughput Δ: -3.02 tok/s
- TTFT Δ: -174.56 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.95x (sequential time / concurrent time)
- **Efficiency:** 97.6% (speedup / ideal 2x speedup)
- **Contention:** Low
