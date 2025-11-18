# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.81s
- Sequential Estimate: 118.93s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.84 tok/s
- TTFT: 771.76 ms
- Total Duration: 59781.17 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.89 tok/s
- TTFT: 832.88 ms
- Total Duration: 59094.59 ms

## Delta (B - A)
- Throughput Δ: -0.94 tok/s
- TTFT Δ: -61.12 ms (positive = Agent B faster TTFT)
