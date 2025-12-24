# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 37.63s
**Sequential Estimated Time:** 64.16s
**Concurrency Speedup:** 1.70x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 37.63s

```
Throughput: 72.87 tok/s
TTFT: 377.08 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 1.0}
Ollama URL: http://localhost:11435
Execution Time: 26.53s

```
Throughput: 19.26 tok/s
TTFT: 107.97 ms
```

## Performance Delta
- Throughput Δ: -53.61 tok/s
- TTFT Δ: +269.11 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.70x (sequential time / concurrent time)
- **Efficiency:** 85.2% (speedup / ideal 2x speedup)
- **Contention:** Low
