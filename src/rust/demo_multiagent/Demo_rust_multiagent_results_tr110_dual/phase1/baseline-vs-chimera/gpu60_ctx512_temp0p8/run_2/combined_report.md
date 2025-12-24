# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.32s
- Sequential Estimate: 24.18s
- Speedup: 1.82x
- Efficiency: 90.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 40.78 tok/s
- TTFT: 294.59 ms
- Total Duration: 10860.16 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.90 tok/s
- TTFT: 320.96 ms
- Total Duration: 13321.25 ms

## Delta (B - A)
- Throughput Δ: +13.12 tok/s
- TTFT Δ: -26.37 ms (positive = Agent B faster TTFT)
