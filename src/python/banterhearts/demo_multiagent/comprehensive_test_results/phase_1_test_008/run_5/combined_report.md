# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 108.53s
**Sequential Estimated Time:** 159.98s
**Concurrency Speedup:** 1.47x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 51.68s

```
Throughput: 42.93 tok/s
TTFT: 457.13 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 108.30s

```
Throughput: 51.26 tok/s
TTFT: 32577.31 ms
```

## Performance Delta
- Throughput Δ: +8.33 tok/s
- TTFT Δ: -32120.18 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.47x (sequential time / concurrent time)
- **Efficiency:** 73.7% (speedup / ideal 2x speedup)
- **Contention:** High
