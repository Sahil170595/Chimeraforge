# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 108.44s
**Sequential Estimated Time:** 161.49s
**Concurrency Speedup:** 1.49x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 108.44s

```
Throughput: 51.38 tok/s
TTFT: 31544.82 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 53.05s

```
Throughput: 42.27 tok/s
TTFT: 473.14 ms
```

## Performance Delta
- Throughput Δ: -9.12 tok/s
- TTFT Δ: +31071.68 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.49x (sequential time / concurrent time)
- **Efficiency:** 74.5% (speedup / ideal 2x speedup)
- **Contention:** High
