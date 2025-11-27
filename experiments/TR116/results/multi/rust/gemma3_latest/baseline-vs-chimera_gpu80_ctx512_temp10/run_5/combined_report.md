# Rust Multi-Agent Report – Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.28s
- Sequential Estimate: 109.14s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.74 tok/s
- TTFT: 587.17 ms
- Total Duration: 55274.49 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 427.24 ms
- Total Duration: 53860.33 ms

## Delta (B - A)
- Throughput Δ: -1.57 tok/s
- TTFT Δ: +159.93 ms (positive = Agent B faster TTFT)
