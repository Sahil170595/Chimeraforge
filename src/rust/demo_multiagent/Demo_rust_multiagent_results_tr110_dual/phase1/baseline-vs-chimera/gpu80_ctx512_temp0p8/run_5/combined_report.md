# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.13s
- Sequential Estimate: 23.67s
- Speedup: 1.80x
- Efficiency: 90.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.19 tok/s
- TTFT: 278.98 ms
- Total Duration: 10538.23 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.66 tok/s
- TTFT: 328.67 ms
- Total Duration: 13127.82 ms

## Delta (B - A)
- Throughput Δ: +13.47 tok/s
- TTFT Δ: -49.70 ms (positive = Agent B faster TTFT)
