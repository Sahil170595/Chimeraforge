# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.62s
- Sequential Estimate: 22.45s
- Speedup: 1.78x
- Efficiency: 88.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.16 tok/s
- TTFT: 298.01 ms
- Total Duration: 9828.26 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.58 tok/s
- TTFT: 329.00 ms
- Total Duration: 12622.35 ms

## Delta (B - A)
- Throughput Δ: +15.42 tok/s
- TTFT Δ: -30.99 ms (positive = Agent B faster TTFT)
