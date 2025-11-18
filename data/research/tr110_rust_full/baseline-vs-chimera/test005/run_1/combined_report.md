# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.93s
- Sequential Estimate: 110.98s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 49.01 tok/s
- TTFT: 808.03 ms
- Total Duration: 55889.28 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.82 tok/s
- TTFT: 2862.13 ms
- Total Duration: 55007.41 ms

## Delta (B - A)
- Throughput Δ: -8.19 tok/s
- TTFT Δ: -2054.09 ms (positive = Agent B faster TTFT)
