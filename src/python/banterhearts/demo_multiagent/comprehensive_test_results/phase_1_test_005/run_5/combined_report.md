# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 116.62s
**Sequential Estimated Time:** 207.29s
**Concurrency Speedup:** 1.78x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 116.62s

```
Throughput: 43.30 tok/s
TTFT: 29131.96 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 90.67s

```
Throughput: 44.43 tok/s
TTFT: 22980.54 ms
```

## Performance Delta
- Throughput Δ: +1.13 tok/s
- TTFT Δ: +6151.42 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.78x (sequential time / concurrent time)
- **Efficiency:** 88.9% (speedup / ideal 2x speedup)
- **Contention:** Low
