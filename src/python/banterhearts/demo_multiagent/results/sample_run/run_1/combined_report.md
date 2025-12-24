# Multi-Agent Analysis - Run 1

## Data Collector Summary (Baseline)
Model: gemma3:latest
Execution Time: 26.29s

```
Throughput: 99.58 tok/s
TTFT: 1848.23 ms
```

## Insight Agent Summary (Chimera)
Model: gemma3:latest
Overrides: {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8}
Execution Time: 26.26s

```
Throughput: 99.42 tok/s
TTFT: 1663.85 ms
```

## Delta Overview
- Throughput Δ: -0.15 tok/s
- TTFT Δ: +184.38 ms (positive = Chimera faster)
