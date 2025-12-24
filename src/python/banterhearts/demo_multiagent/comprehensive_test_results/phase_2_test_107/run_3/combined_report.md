# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 59.11s
**Sequential Estimated Time:** 117.69s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 59.11s

```
Throughput: 38.88 tok/s
TTFT: 496.34 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 2048, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 58.58s

```
Throughput: 38.11 tok/s
TTFT: 523.08 ms
```

## Performance Delta
- Throughput Δ: -0.77 tok/s
- TTFT Δ: -26.75 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.6% (speedup / ideal 2x speedup)
- **Contention:** Low
