# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 124.58s
**Sequential Estimated Time:** 184.10s
**Concurrency Speedup:** 1.48x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 124.58s

```
Throughput: 45.46 tok/s
TTFT: 31824.45 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 59.53s

```
Throughput: 39.63 tok/s
TTFT: 2072.79 ms
```

## Performance Delta
- Throughput Δ: -5.83 tok/s
- TTFT Δ: +29751.65 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.48x (sequential time / concurrent time)
- **Efficiency:** 73.9% (speedup / ideal 2x speedup)
- **Contention:** High
