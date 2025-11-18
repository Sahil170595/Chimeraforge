# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.63s
- Sequential Estimate: 115.39s
- Speedup: 1.93x
- Efficiency: 96.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.48 tok/s
- TTFT: 880.13 ms
- Total Duration: 59605.75 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.17 tok/s
- TTFT: 633.10 ms
- Total Duration: 55721.93 ms

## Delta (B - A)
- Throughput Δ: -4.32 tok/s
- TTFT Δ: +247.03 ms (positive = Agent B faster TTFT)
