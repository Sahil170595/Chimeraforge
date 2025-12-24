# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.70s
- Sequential Estimate: 22.89s
- Speedup: 1.80x
- Efficiency: 90.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.15 tok/s
- TTFT: 269.69 ms
- Total Duration: 10184.60 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.01 tok/s
- TTFT: 300.04 ms
- Total Duration: 12701.02 ms

## Delta (B - A)
- Throughput Δ: +13.86 tok/s
- TTFT Δ: -30.36 ms (positive = Agent B faster TTFT)
