# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 111.48s
**Sequential Estimated Time:** 164.18s
**Concurrency Speedup:** 1.47x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 111.48s

```
Throughput: 47.68 tok/s
TTFT: 32246.50 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 52.70s

```
Throughput: 42.33 tok/s
TTFT: 468.39 ms
```

## Performance Delta
- Throughput Δ: -5.35 tok/s
- TTFT Δ: +31778.11 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.47x (sequential time / concurrent time)
- **Efficiency:** 73.6% (speedup / ideal 2x speedup)
- **Contention:** High
