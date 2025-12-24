# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 114.99s
**Sequential Estimated Time:** 198.75s
**Concurrency Speedup:** 1.73x
**Resource Contention Detected:** No

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 114.99s

```
Throughput: 44.11 tok/s
TTFT: 29122.40 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 120, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 83.76s

```
Throughput: 43.87 tok/s
TTFT: 16680.96 ms
```

## Performance Delta
- Throughput Δ: -0.23 tok/s
- TTFT Δ: +12441.44 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.73x (sequential time / concurrent time)
- **Efficiency:** 86.4% (speedup / ideal 2x speedup)
- **Contention:** Low
