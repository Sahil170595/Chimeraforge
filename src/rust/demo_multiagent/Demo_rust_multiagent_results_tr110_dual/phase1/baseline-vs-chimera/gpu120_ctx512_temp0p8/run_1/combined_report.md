# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 5.38s
- Sequential Estimate: 9.37s
- Speedup: 1.74x
- Efficiency: 87.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 106.23 tok/s
- TTFT: 267.19 ms
- Total Duration: 3994.31 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 116.71 tok/s
- TTFT: 4862.52 ms
- Total Duration: 5379.19 ms

## Delta (B - A)
- Throughput Δ: +10.49 tok/s
- TTFT Δ: -4595.33 ms (positive = Agent B faster TTFT)
