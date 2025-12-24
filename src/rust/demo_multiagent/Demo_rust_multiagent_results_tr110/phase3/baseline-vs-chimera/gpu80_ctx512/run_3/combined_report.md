# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 16.21s
- Sequential Estimate: 25.70s
- Speedup: 1.59x
- Efficiency: 79.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.61 tok/s
- TTFT: 12600.24 ms
- Total Duration: 16212.47 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.61 tok/s
- TTFT: 3372.52 ms
- Total Duration: 9485.88 ms

## Delta (B - A)
- Throughput Δ: +1.00 tok/s
- TTFT Δ: +9227.73 ms (positive = Agent B faster TTFT)
