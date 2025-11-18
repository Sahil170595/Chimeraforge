# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.66s
- Sequential Estimate: 110.93s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.16 tok/s
- TTFT: 868.14 ms
- Total Duration: 56624.08 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.44 tok/s
- TTFT: 696.34 ms
- Total Duration: 54247.42 ms

## Delta (B - A)
- Throughput Δ: -2.72 tok/s
- TTFT Δ: +171.79 ms (positive = Agent B faster TTFT)
