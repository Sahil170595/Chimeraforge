# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 62.53s
**Sequential Estimated Time:** 123.86s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 61.60s

```
Throughput: 38.62 tok/s
TTFT: 1836.30 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 62.26s

```
Throughput: 39.56 tok/s
TTFT: 1935.42 ms
```

## Performance Delta
- Throughput Δ: +0.94 tok/s
- TTFT Δ: -99.12 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.0% (speedup / ideal 2x speedup)
- **Contention:** Low
