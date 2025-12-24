# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 22.34s
- Sequential Estimate: 32.78s
- Speedup: 1.47x
- Efficiency: 73.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 96.43 tok/s
- TTFT: 5966.90 ms
- Total Duration: 10442.15 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 97.76 tok/s
- TTFT: 15416.22 ms
- Total Duration: 22337.67 ms

## Delta (B - A)
- Throughput Δ: +1.32 tok/s
- TTFT Δ: -9449.32 ms (positive = Agent B faster TTFT)
