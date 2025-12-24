# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.01s
**Sequential Estimated Time:** 114.98s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 58.01s

```
Throughput: 40.08 tok/s
TTFT: 504.76 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 56.97s

```
Throughput: 38.23 tok/s
TTFT: 549.43 ms
```

## Performance Delta
- Throughput Δ: -1.84 tok/s
- TTFT Δ: -44.67 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.1% (speedup / ideal 2x speedup)
- **Contention:** Low
