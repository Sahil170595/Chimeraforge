# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 19.30s
- Sequential Estimate: 37.08s
- Speedup: 1.92x
- Efficiency: 96.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.61 tok/s
- TTFT: 7578.54 ms
- Total Duration: 17783.72 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 51.75 tok/s
- TTFT: 7760.98 ms
- Total Duration: 19299.01 ms

## Delta (B - A)
- Throughput Δ: +9.13 tok/s
- TTFT Δ: -182.44 ms (positive = Agent B faster TTFT)
