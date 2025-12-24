# Multi-Agent Analysis - Run 5

## Execution Summary
**Scenario:** chimera_hetero
**Concurrent Wall Time:** 113.44s
**Sequential Estimated Time:** 167.04s
**Concurrency Speedup:** 1.47x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Chimera Config 1)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 53.81s

```
Throughput: 42.85 tok/s
TTFT: 458.72 ms
```

## Agent 2 Summary (Chimera Config 2)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 1024, "temperature": 0.6}
Ollama URL: http://localhost:11435
Execution Time: 113.23s

```
Throughput: 54.84 tok/s
TTFT: 33455.22 ms
```

## Performance Delta
- Throughput Δ: +11.99 tok/s
- TTFT Δ: -32996.49 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.47x (sequential time / concurrent time)
- **Efficiency:** 73.6% (speedup / ideal 2x speedup)
- **Contention:** High
