# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.61s
- Sequential Estimate: 112.48s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.61 tok/s
- TTFT: 951.30 ms
- Total Duration: 55851.99 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.32 tok/s
- TTFT: 846.21 ms
- Total Duration: 56581.51 ms

## Delta (B - A)
- Throughput Δ: +0.72 tok/s
- TTFT Δ: +105.09 ms (positive = Agent B faster TTFT)
