# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.14s
- Sequential Estimate: 22.02s
- Speedup: 1.81x
- Efficiency: 90.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 40.99 tok/s
- TTFT: 293.72 ms
- Total Duration: 9879.92 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.95 tok/s
- TTFT: 264.90 ms
- Total Duration: 12135.29 ms

## Delta (B - A)
- Throughput Δ: +12.96 tok/s
- TTFT Δ: +28.82 ms (positive = Agent B faster TTFT)
