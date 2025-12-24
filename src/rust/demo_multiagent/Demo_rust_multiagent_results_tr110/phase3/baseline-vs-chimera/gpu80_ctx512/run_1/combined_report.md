# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 16.26s
- Sequential Estimate: 23.23s
- Speedup: 1.43x
- Efficiency: 71.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.62 tok/s
- TTFT: 3463.53 ms
- Total Duration: 6964.73 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.89 tok/s
- TTFT: 10170.60 ms
- Total Duration: 16261.13 ms

## Delta (B - A)
- Throughput Δ: -0.72 tok/s
- TTFT Δ: -6707.07 ms (positive = Agent B faster TTFT)
