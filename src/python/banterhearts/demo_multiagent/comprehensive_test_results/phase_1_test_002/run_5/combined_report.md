# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 113.09s
**Sequential Estimated Time:** 165.56s
**Concurrency Speedup:** 1.46x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 113.09s

```
Throughput: 50.24 tok/s
TTFT: 33183.50 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 52.47s

```
Throughput: 42.74 tok/s
TTFT: 457.98 ms
```

## Performance Delta
- Throughput Δ: -7.50 tok/s
- TTFT Δ: +32725.52 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.46x (sequential time / concurrent time)
- **Efficiency:** 73.2% (speedup / ideal 2x speedup)
- **Contention:** High
