# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 61.21s
- Sequential Estimate: 121.63s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.31 tok/s
- TTFT: 842.70 ms
- Total Duration: 61180.44 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.62 tok/s
- TTFT: 660.08 ms
- Total Duration: 60391.15 ms

## Delta (B - A)
- Throughput Δ: -0.69 tok/s
- TTFT Δ: +182.62 ms (positive = Agent B faster TTFT)
