# Rust Multi-Agent Report – Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 52.43s
- Sequential Estimate: 104.43s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 24.48 tok/s
- TTFT: 283.98 ms
- Total Duration: 52433.54 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 24.13 tok/s
- TTFT: 266.32 ms
- Total Duration: 51995.55 ms

## Delta (B - A)
- Throughput Δ: -0.35 tok/s
- TTFT Δ: +17.66 ms (positive = Agent B faster TTFT)
