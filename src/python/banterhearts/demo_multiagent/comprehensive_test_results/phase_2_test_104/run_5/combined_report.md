# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 57.71s
**Sequential Estimated Time:** 114.98s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 57.51s

```
Throughput: 38.27 tok/s
TTFT: 308.48 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.47s

```
Throughput: 38.53 tok/s
TTFT: 503.53 ms
```

## Performance Delta
- Throughput Δ: +0.27 tok/s
- TTFT Δ: -195.05 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.6% (speedup / ideal 2x speedup)
- **Contention:** Low
