# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.79s
- Sequential Estimate: 115.41s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.04 tok/s
- TTFT: 870.52 ms
- Total Duration: 58756.34 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.60 tok/s
- TTFT: 658.84 ms
- Total Duration: 56586.95 ms

## Delta (B - A)
- Throughput Δ: -2.44 tok/s
- TTFT Δ: +211.68 ms (positive = Agent B faster TTFT)
