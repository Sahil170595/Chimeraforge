# Rust Multi-Agent Report – Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 35.10s
- Sequential Estimate: 69.67s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 25.86 tok/s
- TTFT: 422.76 ms
- Total Duration: 34564.10 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 26.67 tok/s
- TTFT: 282.16 ms
- Total Duration: 35102.31 ms

## Delta (B - A)
- Throughput Δ: +0.81 tok/s
- TTFT Δ: +140.60 ms (positive = Agent B faster TTFT)
