# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 53.05s
**Sequential Estimated Time:** 103.99s
**Concurrency Speedup:** 1.96x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 51.17s

```
Throughput: 39.19 tok/s
TTFT: 405.96 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 52.82s

```
Throughput: 40.98 tok/s
TTFT: 497.80 ms
```

## Performance Delta
- Throughput Δ: +1.79 tok/s
- TTFT Δ: -91.84 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.96x (sequential time / concurrent time)
- **Efficiency:** 98.0% (speedup / ideal 2x speedup)
- **Contention:** Low
