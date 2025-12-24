# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 1.04s
**Sequential Estimated Time:** 1.75s
**Concurrency Speedup:** 1.68x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://127.0.0.1:18034
Execution Time: 1.04s

```
Throughput: 420.95 tok/s
TTFT: 630.00 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://127.0.0.1:18035
Execution Time: 0.70s

```
Throughput: 682.43 tok/s
TTFT: 380.00 ms
```

## Performance Delta
- Throughput Δ: +261.48 tok/s
- TTFT Δ: +250.00 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.68x (sequential time / concurrent time)
- **Efficiency:** 83.8% (speedup / ideal 2x speedup)
- **Contention:** Low
