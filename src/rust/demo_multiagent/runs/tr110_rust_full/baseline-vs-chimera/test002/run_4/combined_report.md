# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.05s
- Sequential Estimate: 106.26s
- Speedup: 1.93x
- Efficiency: 96.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 45.18 tok/s
- TTFT: 819.13 ms
- Total Duration: 55022.51 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.30 tok/s
- TTFT: 667.07 ms
- Total Duration: 51183.48 ms

## Delta (B - A)
- Throughput Δ: -4.88 tok/s
- TTFT Δ: +152.06 ms (positive = Agent B faster TTFT)
