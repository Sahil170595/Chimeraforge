# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 57.54s
- Sequential Estimate: 112.98s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.09 tok/s
- TTFT: 951.99 ms
- Total Duration: 57502.56 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 804.32 ms
- Total Duration: 55399.10 ms

## Delta (B - A)
- Throughput Δ: -2.18 tok/s
- TTFT Δ: +147.67 ms (positive = Agent B faster TTFT)
