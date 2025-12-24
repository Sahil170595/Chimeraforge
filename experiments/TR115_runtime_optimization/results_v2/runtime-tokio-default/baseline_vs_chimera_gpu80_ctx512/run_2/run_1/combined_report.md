# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.43s
- Sequential Estimate: 117.12s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 39.88 tok/s
- TTFT: 891.95 ms
- Total Duration: 59401.05 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.70 tok/s
- TTFT: 873.84 ms
- Total Duration: 57668.42 ms

## Delta (B - A)
- Throughput Δ: -1.18 tok/s
- TTFT Δ: +18.11 ms (positive = Agent B faster TTFT)
