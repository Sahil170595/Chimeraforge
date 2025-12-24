# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 115.70s
**Sequential Estimated Time:** 202.44s
**Concurrency Speedup:** 1.75x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 115.70s

```
Throughput: 43.21 tok/s
TTFT: 28992.22 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 86.74s

```
Throughput: 43.76 tok/s
TTFT: 17715.17 ms
```

## Performance Delta
- Throughput Δ: +0.55 tok/s
- TTFT Δ: +11277.04 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.75x (sequential time / concurrent time)
- **Efficiency:** 87.5% (speedup / ideal 2x speedup)
- **Contention:** Low
