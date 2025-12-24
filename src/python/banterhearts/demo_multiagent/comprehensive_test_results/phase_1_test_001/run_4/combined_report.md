# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 114.23s
**Sequential Estimated Time:** 167.25s
**Concurrency Speedup:** 1.46x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 114.23s

```
Throughput: 47.59 tok/s
TTFT: 30221.01 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 53.02s

```
Throughput: 41.78 tok/s
TTFT: 472.32 ms
```

## Performance Delta
- Throughput Δ: -5.81 tok/s
- TTFT Δ: +29748.68 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.46x (sequential time / concurrent time)
- **Efficiency:** 73.2% (speedup / ideal 2x speedup)
- **Contention:** High
