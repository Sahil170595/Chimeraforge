# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.29s
- Sequential Estimate: 20.87s
- Speedup: 1.46x
- Efficiency: 73.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.16 tok/s
- TTFT: 10039.57 ms
- Total Duration: 14293.49 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.69 tok/s
- TTFT: 220.62 ms
- Total Duration: 6579.75 ms

## Delta (B - A)
- Throughput Δ: +1.53 tok/s
- TTFT Δ: +9818.95 ms (positive = Agent B faster TTFT)
