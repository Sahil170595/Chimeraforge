# Multi-Agent Analysis - Run 4

## Execution Summary
**Scenario:** chimera_homo
**Concurrent Wall Time:** 59.02s
**Sequential Estimated Time:** 117.39s
**Concurrency Speedup:** 1.99x
**Resource Contention Detected:** No

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 59.02s

```
Throughput: 38.77 tok/s
TTFT: 258.63 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 58.36s

```
Throughput: 38.32 tok/s
TTFT: 484.27 ms
```

## Performance Delta
- Throughput Δ: -0.46 tok/s
- TTFT Δ: -225.64 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.99x (sequential time / concurrent time)
- **Efficiency:** 99.4% (speedup / ideal 2x speedup)
- **Contention:** Low
