# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.66s
- Sequential Estimate: 114.82s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.17 tok/s
- TTFT: 807.90 ms
- Total Duration: 58623.05 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.85 tok/s
- TTFT: 730.83 ms
- Total Duration: 56133.81 ms

## Delta (B - A)
- Throughput Δ: -3.32 tok/s
- TTFT Δ: +77.07 ms (positive = Agent B faster TTFT)
