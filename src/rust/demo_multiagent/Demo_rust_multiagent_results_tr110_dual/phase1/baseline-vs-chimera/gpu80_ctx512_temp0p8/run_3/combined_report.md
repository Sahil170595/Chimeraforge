# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.44s
- Sequential Estimate: 20.14s
- Speedup: 1.76x
- Efficiency: 88.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 42.35 tok/s
- TTFT: 214.92 ms
- Total Duration: 8704.99 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.16 tok/s
- TTFT: 380.66 ms
- Total Duration: 11435.49 ms

## Delta (B - A)
- Throughput Δ: +15.81 tok/s
- TTFT Δ: -165.74 ms (positive = Agent B faster TTFT)
