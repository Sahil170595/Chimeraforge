# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 112.07s
**Sequential Estimated Time:** 163.32s
**Concurrency Speedup:** 1.46x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 51.50s

```
Throughput: 43.01 tok/s
TTFT: 455.01 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 111.81s

```
Throughput: 57.08 tok/s
TTFT: 33953.33 ms
```

## Performance Delta
- Throughput Δ: +14.07 tok/s
- TTFT Δ: -33498.31 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.46x (sequential time / concurrent time)
- **Efficiency:** 72.9% (speedup / ideal 2x speedup)
- **Contention:** High
