# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.14s
- Sequential Estimate: 21.49s
- Speedup: 1.77x
- Efficiency: 88.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.98 tok/s
- TTFT: 216.50 ms
- Total Duration: 9345.14 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.84 tok/s
- TTFT: 358.87 ms
- Total Duration: 12144.53 ms

## Delta (B - A)
- Throughput Δ: +14.86 tok/s
- TTFT Δ: -142.37 ms (positive = Agent B faster TTFT)
