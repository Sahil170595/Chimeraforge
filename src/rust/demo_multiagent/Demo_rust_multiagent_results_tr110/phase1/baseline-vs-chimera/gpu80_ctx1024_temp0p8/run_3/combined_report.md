# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 7.85s
- Sequential Estimate: 11.78s
- Speedup: 1.50x
- Efficiency: 75.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.54 tok/s
- TTFT: 196.25 ms
- Total Duration: 3928.05 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 95.32 tok/s
- TTFT: 7264.32 ms
- Total Duration: 7848.46 ms

## Delta (B - A)
- Throughput Δ: -5.22 tok/s
- TTFT Δ: -7068.08 ms (positive = Agent B faster TTFT)
