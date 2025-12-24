# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.20s
- Sequential Estimate: 23.89s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.27 tok/s
- TTFT: 901.63 ms
- Total Duration: 10697.39 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.31 tok/s
- TTFT: 730.89 ms
- Total Duration: 13196.84 ms

## Delta (B - A)
- Throughput Δ: +15.04 tok/s
- TTFT Δ: +170.74 ms (positive = Agent B faster TTFT)
