# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 114.44s
**Sequential Estimated Time:** 198.38s
**Concurrency Speedup:** 1.73x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 114.44s

```
Throughput: 42.35 tok/s
TTFT: 26382.86 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 83.94s

```
Throughput: 43.04 tok/s
TTFT: 16847.75 ms
```

## Performance Delta
- Throughput Δ: +0.68 tok/s
- TTFT Δ: +9535.11 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.73x (sequential time / concurrent time)
- **Efficiency:** 86.7% (speedup / ideal 2x speedup)
- **Contention:** Low
