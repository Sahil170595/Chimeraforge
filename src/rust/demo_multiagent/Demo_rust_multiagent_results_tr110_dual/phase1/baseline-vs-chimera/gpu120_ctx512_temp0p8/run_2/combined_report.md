# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.40s
- Sequential Estimate: 22.43s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.17 tok/s
- TTFT: 278.38 ms
- Total Duration: 10031.14 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.51 tok/s
- TTFT: 325.52 ms
- Total Duration: 12398.37 ms

## Delta (B - A)
- Throughput Δ: +13.35 tok/s
- TTFT Δ: -47.13 ms (positive = Agent B faster TTFT)
