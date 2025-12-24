# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.78s
- Sequential Estimate: 23.69s
- Speedup: 1.72x
- Efficiency: 85.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.20 tok/s
- TTFT: 248.15 ms
- Total Duration: 9904.75 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 60.63 tok/s
- TTFT: 298.16 ms
- Total Duration: 13781.16 ms

## Delta (B - A)
- Throughput Δ: +19.42 tok/s
- TTFT Δ: -50.01 ms (positive = Agent B faster TTFT)
