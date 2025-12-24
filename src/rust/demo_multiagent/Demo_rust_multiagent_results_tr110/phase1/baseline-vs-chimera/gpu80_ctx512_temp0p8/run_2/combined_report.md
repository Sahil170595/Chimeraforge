# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.19s
- Sequential Estimate: 22.18s
- Speedup: 1.46x
- Efficiency: 73.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.40 tok/s
- TTFT: 10740.84 ms
- Total Duration: 15188.28 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.00 tok/s
- TTFT: 208.94 ms
- Total Duration: 6994.71 ms

## Delta (B - A)
- Throughput Δ: +1.61 tok/s
- TTFT Δ: +10531.90 ms (positive = Agent B faster TTFT)
