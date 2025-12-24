# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.32s
- Sequential Estimate: 18.32s
- Speedup: 1.28x
- Efficiency: 64.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 101.09 tok/s
- TTFT: 206.03 ms
- Total Duration: 4007.37 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.93 tok/s
- TTFT: 7402.15 ms
- Total Duration: 14314.64 ms

## Delta (B - A)
- Throughput Δ: -1.16 tok/s
- TTFT Δ: -7196.12 ms (positive = Agent B faster TTFT)
