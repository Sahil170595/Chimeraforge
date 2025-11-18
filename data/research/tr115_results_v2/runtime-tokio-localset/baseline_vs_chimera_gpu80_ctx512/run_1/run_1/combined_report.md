# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 62.94s
- Sequential Estimate: 122.52s
- Speedup: 1.95x
- Efficiency: 97.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 45.03 tok/s
- TTFT: 4430.42 ms
- Total Duration: 62894.42 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.93 tok/s
- TTFT: 4134.79 ms
- Total Duration: 59541.20 ms

## Delta (B - A)
- Throughput Δ: -4.11 tok/s
- TTFT Δ: +295.64 ms (positive = Agent B faster TTFT)
