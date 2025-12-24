# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 58.84s
**Sequential Estimated Time:** 117.01s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 58.84s

```
Throughput: 38.92 tok/s
TTFT: 1056.22 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 58.18s

```
Throughput: 38.53 tok/s
TTFT: 835.52 ms
```

## Performance Delta
- Throughput Δ: -0.39 tok/s
- TTFT Δ: +220.70 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
