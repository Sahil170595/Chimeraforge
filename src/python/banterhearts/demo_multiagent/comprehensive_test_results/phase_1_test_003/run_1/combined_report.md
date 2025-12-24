# Multi-Agent Analysis - Run 1

## Execution Summary
**Scenario:** baseline_vs_chimera
**Concurrent Wall Time:** 116.36s
**Sequential Estimated Time:** 173.61s
**Concurrency Speedup:** 1.49x
**Resource Contention Detected:** Yes

## Agent 1 Summary (Baseline)
Model: gemma3:latest
Ollama URL: http://localhost:11434
Execution Time: 116.36s

```
Throughput: 40.01 tok/s
TTFT: 30375.57 ms
```

## Agent 2 Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8}
Ollama URL: http://localhost:11435
Execution Time: 57.25s

```
Throughput: 40.28 tok/s
TTFT: 1431.80 ms
```

## Performance Delta
- Throughput Δ: +0.27 tok/s
- TTFT Δ: +28943.77 ms (positive = Agent 2 faster)

## Concurrent Execution Analysis
- **Speedup:** 1.49x (sequential time / concurrent time)
- **Efficiency:** 74.6% (speedup / ideal 2x speedup)
- **Contention:** High
