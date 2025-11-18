# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.59s
- Sequential Estimate: 116.36s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.15 tok/s
- TTFT: 827.77 ms
- Total Duration: 58572.28 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.92 tok/s
- TTFT: 488.91 ms
- Total Duration: 57740.30 ms

## Delta (B - A)
- Throughput Δ: -1.23 tok/s
- TTFT Δ: +338.85 ms (positive = Agent B faster TTFT)
