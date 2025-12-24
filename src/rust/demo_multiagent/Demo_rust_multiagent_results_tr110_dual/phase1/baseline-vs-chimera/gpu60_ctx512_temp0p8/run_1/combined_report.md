# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.62s
- Sequential Estimate: 34.61s
- Speedup: 1.86x
- Efficiency: 92.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 40.82 tok/s
- TTFT: 6461.68 ms
- Total Duration: 15997.83 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.89 tok/s
- TTFT: 6271.13 ms
- Total Duration: 18617.15 ms

## Delta (B - A)
- Throughput Δ: +15.08 tok/s
- TTFT Δ: +190.55 ms (positive = Agent B faster TTFT)
