# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.01s
- Sequential Estimate: 108.86s
- Speedup: 1.94x
- Efficiency: 97.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.81 tok/s
- TTFT: 813.33 ms
- Total Duration: 55982.81 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.90 tok/s
- TTFT: 610.02 ms
- Total Duration: 52815.50 ms

## Delta (B - A)
- Throughput Δ: -3.91 tok/s
- TTFT Δ: +203.31 ms (positive = Agent B faster TTFT)
