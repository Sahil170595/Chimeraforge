# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.62s
- Sequential Estimate: 115.48s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.39 tok/s
- TTFT: 824.53 ms
- Total Duration: 58589.82 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.70 tok/s
- TTFT: 673.81 ms
- Total Duration: 56837.93 ms

## Delta (B - A)
- Throughput Δ: -1.69 tok/s
- TTFT Δ: +150.72 ms (positive = Agent B faster TTFT)
