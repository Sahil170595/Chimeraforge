# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.62s
- Sequential Estimate: 22.66s
- Speedup: 1.80x
- Efficiency: 89.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 39.18 tok/s
- TTFT: 759.96 ms
- Total Duration: 10042.39 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.82 tok/s
- TTFT: 615.87 ms
- Total Duration: 12619.90 ms

## Delta (B - A)
- Throughput Δ: +15.65 tok/s
- TTFT Δ: +144.09 ms (positive = Agent B faster TTFT)
