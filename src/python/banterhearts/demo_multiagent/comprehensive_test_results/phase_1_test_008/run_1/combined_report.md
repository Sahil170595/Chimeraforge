# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.45s
**Sequential Estimated Time:** 155.44s
**Concurrency Speedup:** 1.46x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 49.31s

```
Throughput: 42.88 tok/s
TTFT: 477.57 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 106.13s

```
Throughput: 63.17 tok/s
TTFT: 32953.23 ms
```

## Performance Delta
- Throughput Δ: +20.29 tok/s
- TTFT Δ: -32475.66 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.46x (sequential time / concurrent time)
- **Efficiency:** 73.0% (speedup / ideal 2x speedup)
- **Contention:** High
