# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 111.55s
**Sequential Estimated Time:** 195.85s
**Concurrency Speedup:** 1.76x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 111.55s

```
Throughput: 43.56 tok/s
TTFT: 25612.63 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 84.30s

```
Throughput: 44.02 tok/s
TTFT: 17533.84 ms
```

## Performance Delta
- Throughput Δ: +0.46 tok/s
- TTFT Δ: +8078.78 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.76x (sequential time / concurrent time)
- **Efficiency:** 87.8% (speedup / ideal 2x speedup)
- **Contention:** Low
