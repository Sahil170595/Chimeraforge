# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 54.26s
**Sequential Estimated Time:** 104.95s
**Concurrency Speedup:** 1.93x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 50.98s

```
Throughput: 39.17 tok/s
TTFT: 447.09 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 53.97s

```
Throughput: 42.97 tok/s
TTFT: 497.20 ms
```

## Performance Delta
- Throughput Δ: +3.80 tok/s
- TTFT Δ: -50.11 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.93x (sequential time / concurrent time)
- **Efficiency:** 96.7% (speedup / ideal 2x speedup)
- **Contention:** Low
