# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.41s
- Sequential Estimate: 21.03s
- Speedup: 1.46x
- Efficiency: 73.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.20 tok/s
- TTFT: 10181.61 ms
- Total Duration: 14414.39 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.82 tok/s
- TTFT: 209.65 ms
- Total Duration: 6616.49 ms

## Delta (B - A)
- Throughput Δ: +0.62 tok/s
- TTFT Δ: +9971.96 ms (positive = Agent B faster TTFT)
