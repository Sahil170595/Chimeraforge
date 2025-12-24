# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 56.44s
**Sequential Estimated Time:** 111.75s
**Concurrency Speedup:** 1.98x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 55.58s

```
Throughput: 38.33 tok/s
TTFT: 276.04 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 56.17s

```
Throughput: 39.12 tok/s
TTFT: 482.46 ms
```

## Performance Delta
- Throughput Δ: +0.80 tok/s
- TTFT Δ: -206.42 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.98x (sequential time / concurrent time)
- **Efficiency:** 99.0% (speedup / ideal 2x speedup)
- **Contention:** Low
