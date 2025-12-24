# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.07s
- Sequential Estimate: 19.51s
- Speedup: 1.29x
- Efficiency: 64.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.89 tok/s
- TTFT: 179.05 ms
- Total Duration: 4435.28 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.57 tok/s
- TTFT: 8614.67 ms
- Total Duration: 15073.77 ms

## Delta (B - A)
- Throughput Δ: -1.33 tok/s
- TTFT Δ: -8435.62 ms (positive = Agent B faster TTFT)
