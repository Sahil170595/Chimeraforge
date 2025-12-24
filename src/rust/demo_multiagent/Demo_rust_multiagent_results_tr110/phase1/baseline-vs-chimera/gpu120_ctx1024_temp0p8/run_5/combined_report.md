# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.07s
- Sequential Estimate: 18.06s
- Speedup: 1.28x
- Efficiency: 64.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.68 tok/s
- TTFT: 187.14 ms
- Total Duration: 3994.70 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.75 tok/s
- TTFT: 7335.46 ms
- Total Duration: 14067.39 ms

## Delta (B - A)
- Throughput Δ: -0.94 tok/s
- TTFT Δ: -7148.32 ms (positive = Agent B faster TTFT)
