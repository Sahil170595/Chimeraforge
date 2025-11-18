# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.62s
- Sequential Estimate: 111.53s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.01 tok/s
- TTFT: 865.72 ms
- Total Duration: 56590.24 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.86 tok/s
- TTFT: 665.68 ms
- Total Duration: 54891.97 ms

## Delta (B - A)
- Throughput Δ: -2.15 tok/s
- TTFT Δ: +200.04 ms (positive = Agent B faster TTFT)
