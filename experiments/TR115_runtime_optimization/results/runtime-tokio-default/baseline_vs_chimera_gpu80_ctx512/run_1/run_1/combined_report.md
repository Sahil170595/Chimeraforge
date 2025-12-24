# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 21.90s
- Sequential Estimate: 41.31s
- Speedup: 1.89x
- Efficiency: 94.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 39.74 tok/s
- TTFT: 8503.91 ms
- Total Duration: 19415.62 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.24 tok/s
- TTFT: 8669.24 ms
- Total Duration: 21898.59 ms

## Delta (B - A)
- Throughput Δ: +12.50 tok/s
- TTFT Δ: -165.33 ms (positive = Agent B faster TTFT)
