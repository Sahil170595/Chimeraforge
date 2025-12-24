# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 63.32s
**Sequential Estimated Time:** 125.93s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://127.0.0.1:11434
Execution Time: 63.32s

```
Throughput: 37.42 tok/s
TTFT: 356.14 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://127.0.0.1:11435
Execution Time: 62.61s

```
Throughput: 37.07 tok/s
TTFT: 509.79 ms
```

## Performance Delta
- Throughput Δ: -0.35 tok/s
- TTFT Δ: -153.65 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
