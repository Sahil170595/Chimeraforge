# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 17.66s
- Sequential Estimate: 27.48s
- Speedup: 1.56x
- Efficiency: 77.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.25 tok/s
- TTFT: 13291.46 ms
- Total Duration: 17661.59 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.75 tok/s
- TTFT: 3496.18 ms
- Total Duration: 9819.95 ms

## Delta (B - A)
- Throughput Δ: +0.50 tok/s
- TTFT Δ: +9795.28 ms (positive = Agent B faster TTFT)
