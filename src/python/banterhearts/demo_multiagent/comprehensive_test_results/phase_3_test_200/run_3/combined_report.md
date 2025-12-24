# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.08s
**Sequential Estimated Time:** 109.71s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.84s

```
Throughput: 38.14 tok/s
TTFT: 286.08 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 55.87s

```
Throughput: 40.85 tok/s
TTFT: 492.57 ms
```

## Performance Delta
- Throughput Δ: +2.72 tok/s
- TTFT Δ: -206.49 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 97.8% (speedup / ideal 2x speedup)
- **Contention:** Low
