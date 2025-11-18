# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.65s
- Sequential Estimate: 118.68s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.02 tok/s
- TTFT: 864.19 ms
- Total Duration: 59611.70 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.43 tok/s
- TTFT: 661.20 ms
- Total Duration: 59002.45 ms

## Delta (B - A)
- Throughput Δ: -0.59 tok/s
- TTFT Δ: +202.98 ms (positive = Agent B faster TTFT)
