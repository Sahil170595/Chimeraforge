# Multi-Agent Analysis - Run 3

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 110.97s
**Sequential Estimated Time:** 163.14s
**Concurrency Speedup:** 1.47x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 110.97s

```
Throughput: 55.81 tok/s
TTFT: 32083.07 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 1024, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 52.18s

```
Throughput: 42.26 tok/s
TTFT: 477.80 ms
```

## Performance Delta
- Throughput Δ: -13.55 tok/s
- TTFT Δ: +31605.27 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.47x (sequential time / concurrent time)
- **Efficiency:** 73.5% (speedup / ideal 2x speedup)
- **Contention:** High
