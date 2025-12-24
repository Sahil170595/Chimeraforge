# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.71s
- Sequential Estimate: 23.10s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.16 tok/s
- TTFT: 274.32 ms
- Total Duration: 10390.92 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.76 tok/s
- TTFT: 300.08 ms
- Total Duration: 12711.87 ms

## Delta (B - A)
- Throughput Δ: +12.60 tok/s
- TTFT Δ: -25.76 ms (positive = Agent B faster TTFT)
