# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.52s
- Sequential Estimate: 115.47s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.93 tok/s
- TTFT: 627.23 ms
- Total Duration: 58493.24 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.73 tok/s
- TTFT: 654.14 ms
- Total Duration: 56913.37 ms

## Delta (B - A)
- Throughput Δ: -1.20 tok/s
- TTFT Δ: -26.91 ms (positive = Agent B faster TTFT)
