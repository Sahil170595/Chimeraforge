# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.85s
- Sequential Estimate: 118.52s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.92 tok/s
- TTFT: 862.45 ms
- Total Duration: 59776.50 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 661.31 ms
- Total Duration: 58592.93 ms

## Delta (B - A)
- Throughput Δ: -1.07 tok/s
- TTFT Δ: +201.13 ms (positive = Agent B faster TTFT)
