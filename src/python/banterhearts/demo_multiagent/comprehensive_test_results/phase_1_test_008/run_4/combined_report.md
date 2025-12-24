# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 106.16s
**Sequential Estimated Time:** 152.16s
**Concurrency Speedup:** 1.43x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 46.27s

```
Throughput: 43.97 tok/s
TTFT: 345.23 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 105.88s

```
Throughput: 55.56 tok/s
TTFT: 32526.65 ms
```

## Performance Delta
- Throughput Δ: +11.60 tok/s
- TTFT Δ: -32181.42 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.43x (sequential time / concurrent time)
- **Efficiency:** 71.7% (speedup / ideal 2x speedup)
- **Contention:** High
