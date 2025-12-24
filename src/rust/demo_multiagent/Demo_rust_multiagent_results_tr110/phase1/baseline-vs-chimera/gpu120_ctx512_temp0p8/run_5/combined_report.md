# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 17.80s
- Sequential Estimate: 28.47s
- Speedup: 1.60x
- Efficiency: 80.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.91 tok/s
- TTFT: 14077.73 ms
- Total Duration: 17797.80 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.33 tok/s
- TTFT: 3464.56 ms
- Total Duration: 10674.16 ms

## Delta (B - A)
- Throughput Δ: -0.58 tok/s
- TTFT Δ: +10613.16 ms (positive = Agent B faster TTFT)
