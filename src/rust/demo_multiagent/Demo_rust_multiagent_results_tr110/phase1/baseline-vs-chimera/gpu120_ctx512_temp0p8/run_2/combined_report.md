# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.80s
- Sequential Estimate: 17.90s
- Speedup: 1.30x
- Efficiency: 64.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.53 tok/s
- TTFT: 221.10 ms
- Total Duration: 4102.22 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.48 tok/s
- TTFT: 7453.86 ms
- Total Duration: 13796.37 ms

## Delta (B - A)
- Throughput Δ: -1.05 tok/s
- TTFT Δ: -7232.76 ms (positive = Agent B faster TTFT)
