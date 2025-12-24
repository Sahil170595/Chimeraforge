# Multi-Agent Analysis - Run 2

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 119.12s
**Sequential Estimated Time:** 172.56s
**Concurrency Speedup:** 1.45x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 119.12s

```
Throughput: 52.58 tok/s
TTFT: 32105.88 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 53.44s

```
Throughput: 41.33 tok/s
TTFT: 590.44 ms
```

## Performance Delta
- Throughput Δ: -11.25 tok/s
- TTFT Δ: +31515.44 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.45x (sequential time / concurrent time)
- **Efficiency:** 72.4% (speedup / ideal 2x speedup)
- **Contention:** High
