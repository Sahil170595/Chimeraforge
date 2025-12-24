# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.00s
- Sequential Estimate: 25.70s
- Speedup: 1.43x
- Efficiency: 71.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.08 tok/s
- TTFT: 3473.96 ms
- Total Duration: 7701.45 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.77 tok/s
- TTFT: 11028.88 ms
- Total Duration: 17994.87 ms

## Delta (B - A)
- Throughput Δ: -0.31 tok/s
- TTFT Δ: -7554.91 ms (positive = Agent B faster TTFT)
