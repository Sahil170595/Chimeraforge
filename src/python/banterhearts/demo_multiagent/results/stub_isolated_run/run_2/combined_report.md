# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 0.86s
**Sequential Estimated Time:** 1.51s
**Concurrency Speedup:** 1.75x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://127.0.0.1:18034
Execution Time: 0.86s

```
Throughput: 420.95 tok/s
TTFT: 630.00 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://127.0.0.1:18035
Execution Time: 0.65s

```
Throughput: 682.43 tok/s
TTFT: 380.00 ms
```

## Performance Delta
- Throughput Δ: +261.48 tok/s
- TTFT Δ: +250.00 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.75x (sequential time / concurrent time)
- **Efficiency:** 87.7% (speedup / ideal 2x speedup)
- **Contention:** Low
