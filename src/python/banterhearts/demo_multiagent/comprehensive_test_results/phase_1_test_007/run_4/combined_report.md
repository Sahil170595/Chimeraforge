# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.27s
**Sequential Estimated Time:** 156.36s
**Concurrency Speedup:** 1.47x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 50.32s

```
Throughput: 42.35 tok/s
TTFT: 454.86 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 106.04s

```
Throughput: 52.89 tok/s
TTFT: 31092.44 ms
```

## Performance Delta
- Throughput Δ: +10.54 tok/s
- TTFT Δ: -30637.58 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.47x (sequential time / concurrent time)
- **Efficiency:** 73.6% (speedup / ideal 2x speedup)
- **Contention:** High
