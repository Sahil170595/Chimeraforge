# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.63s
- Sequential Estimate: 23.70s
- Speedup: 1.88x
- Efficiency: 93.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.15 tok/s
- TTFT: 233.61 ms
- Total Duration: 11063.48 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 49.75 tok/s
- TTFT: 288.56 ms
- Total Duration: 12631.99 ms

## Delta (B - A)
- Throughput Δ: +8.60 tok/s
- TTFT Δ: -54.94 ms (positive = Agent B faster TTFT)
