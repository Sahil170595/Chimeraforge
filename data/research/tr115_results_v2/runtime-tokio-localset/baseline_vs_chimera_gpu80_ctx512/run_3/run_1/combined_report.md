# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.64s
- Sequential Estimate: 108.83s
- Speedup: 1.96x
- Efficiency: 97.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.10 tok/s
- TTFT: 1005.30 ms
- Total Duration: 55606.64 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.93 tok/s
- TTFT: 662.01 ms
- Total Duration: 53165.70 ms

## Delta (B - A)
- Throughput Δ: -3.17 tok/s
- TTFT Δ: +343.29 ms (positive = Agent B faster TTFT)
