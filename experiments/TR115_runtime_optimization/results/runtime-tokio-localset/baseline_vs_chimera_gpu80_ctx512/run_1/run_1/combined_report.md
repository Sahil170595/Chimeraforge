# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 20.18s
- Sequential Estimate: 38.04s
- Speedup: 1.88x
- Efficiency: 94.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.89 tok/s
- TTFT: 7690.60 ms
- Total Duration: 17855.93 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.66 tok/s
- TTFT: 7661.75 ms
- Total Duration: 20182.52 ms

## Delta (B - A)
- Throughput Δ: +12.77 tok/s
- TTFT Δ: +28.85 ms (positive = Agent B faster TTFT)
