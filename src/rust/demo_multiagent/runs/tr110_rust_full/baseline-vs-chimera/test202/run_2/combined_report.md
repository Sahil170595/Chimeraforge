# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 61.43s
- Sequential Estimate: 120.74s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.96 tok/s
- TTFT: 841.22 ms
- Total Duration: 61398.89 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.61 tok/s
- TTFT: 643.95 ms
- Total Duration: 59278.73 ms

## Delta (B - A)
- Throughput Δ: -2.34 tok/s
- TTFT Δ: +197.27 ms (positive = Agent B faster TTFT)
