# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.11s
- Sequential Estimate: 26.21s
- Speedup: 1.86x
- Efficiency: 92.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.18 tok/s
- TTFT: 282.31 ms
- Total Duration: 12101.11 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 50.53 tok/s
- TTFT: 356.89 ms
- Total Duration: 14110.76 ms

## Delta (B - A)
- Throughput Δ: +9.36 tok/s
- TTFT Δ: -74.58 ms (positive = Agent B faster TTFT)
