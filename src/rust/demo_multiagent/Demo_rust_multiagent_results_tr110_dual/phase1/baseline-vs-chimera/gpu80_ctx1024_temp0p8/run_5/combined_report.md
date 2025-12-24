# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.38s
- Sequential Estimate: 22.01s
- Speedup: 1.78x
- Efficiency: 88.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.24 tok/s
- TTFT: 253.29 ms
- Total Duration: 9632.77 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.77 tok/s
- TTFT: 291.72 ms
- Total Duration: 12379.57 ms

## Delta (B - A)
- Throughput Δ: +15.53 tok/s
- TTFT Δ: -38.43 ms (positive = Agent B faster TTFT)
