# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.12s
- Sequential Estimate: 23.73s
- Speedup: 1.81x
- Efficiency: 90.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.23 tok/s
- TTFT: 256.82 ms
- Total Duration: 10608.53 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.48 tok/s
- TTFT: 304.05 ms
- Total Duration: 13124.58 ms

## Delta (B - A)
- Throughput Δ: +13.25 tok/s
- TTFT Δ: -47.23 ms (positive = Agent B faster TTFT)
