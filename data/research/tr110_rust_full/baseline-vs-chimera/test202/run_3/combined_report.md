# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.52s
- Sequential Estimate: 117.62s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.11 tok/s
- TTFT: 832.71 ms
- Total Duration: 59494.26 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.72 tok/s
- TTFT: 667.64 ms
- Total Duration: 58072.69 ms

## Delta (B - A)
- Throughput Δ: -1.39 tok/s
- TTFT Δ: +165.08 ms (positive = Agent B faster TTFT)
