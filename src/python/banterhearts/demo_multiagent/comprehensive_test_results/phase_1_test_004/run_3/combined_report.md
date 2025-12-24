# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 116.54s
**Sequential Estimated Time:** 203.41s
**Concurrency Speedup:** 1.75x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 116.54s

```
Throughput: 42.56 tok/s
TTFT: 30261.14 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 86.87s

```
Throughput: 42.55 tok/s
TTFT: 16650.37 ms
```

## Performance Delta
- Throughput Δ: -0.01 tok/s
- TTFT Δ: +13610.77 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.75x (sequential time / concurrent time)
- **Efficiency:** 87.3% (speedup / ideal 2x speedup)
- **Contention:** Low
