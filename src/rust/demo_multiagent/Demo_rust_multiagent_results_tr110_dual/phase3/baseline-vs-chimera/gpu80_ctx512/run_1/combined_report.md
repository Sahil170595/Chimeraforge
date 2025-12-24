# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.25s
- Sequential Estimate: 19.86s
- Speedup: 1.77x
- Efficiency: 88.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 73.42 tok/s
- TTFT: 5544.83 ms
- Total Duration: 11246.59 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 81.03 tok/s
- TTFT: 290.58 ms
- Total Duration: 8613.68 ms

## Delta (B - A)
- Throughput Δ: +7.61 tok/s
- TTFT Δ: +5254.25 ms (positive = Agent B faster TTFT)
