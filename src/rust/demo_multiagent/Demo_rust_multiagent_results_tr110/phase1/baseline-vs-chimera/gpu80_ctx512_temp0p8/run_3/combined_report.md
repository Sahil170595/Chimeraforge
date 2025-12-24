# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.25s
- Sequential Estimate: 19.53s
- Speedup: 1.28x
- Efficiency: 64.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.35 tok/s
- TTFT: 226.33 ms
- Total Duration: 4285.38 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.68 tok/s
- TTFT: 8131.99 ms
- Total Duration: 15249.08 ms

## Delta (B - A)
- Throughput Δ: -0.67 tok/s
- TTFT Δ: -7905.66 ms (positive = Agent B faster TTFT)
