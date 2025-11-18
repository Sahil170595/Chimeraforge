# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.55s
- Sequential Estimate: 115.26s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.85 tok/s
- TTFT: 1031.32 ms
- Total Duration: 58514.22 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 832.38 ms
- Total Duration: 56684.25 ms

## Delta (B - A)
- Throughput Δ: -1.72 tok/s
- TTFT Δ: +198.95 ms (positive = Agent B faster TTFT)
