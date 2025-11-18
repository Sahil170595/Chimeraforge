# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.02s
- Sequential Estimate: 113.77s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.19 tok/s
- TTFT: 845.00 ms
- Total Duration: 57934.07 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.58 tok/s
- TTFT: 658.84 ms
- Total Duration: 55671.02 ms

## Delta (B - A)
- Throughput Δ: -2.61 tok/s
- TTFT Δ: +186.16 ms (positive = Agent B faster TTFT)
