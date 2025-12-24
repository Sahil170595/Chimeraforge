# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 62.01s
**Sequential Estimated Time:** 123.44s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 61.67s

```
Throughput: 37.72 tok/s
TTFT: 476.75 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 61.77s

```
Throughput: 37.53 tok/s
TTFT: 521.14 ms
```

## Performance Delta
- Throughput Δ: -0.19 tok/s
- TTFT Δ: -44.38 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.5% (speedup / ideal 2x speedup)
- **Contention:** Low
