# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 114.19s
**Sequential Estimated Time:** 196.84s
**Concurrency Speedup:** 1.72x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 114.19s

```
Throughput: 42.64 tok/s
TTFT: 30476.39 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 82.65s

```
Throughput: 42.90 tok/s
TTFT: 15656.31 ms
```

## Performance Delta
- Throughput Δ: +0.26 tok/s
- TTFT Δ: +14820.08 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.72x (sequential time / concurrent time)
- **Efficiency:** 86.2% (speedup / ideal 2x speedup)
- **Contention:** Low
