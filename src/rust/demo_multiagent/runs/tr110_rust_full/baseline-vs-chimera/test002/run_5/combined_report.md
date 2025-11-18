# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.65s
- Sequential Estimate: 116.84s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.06 tok/s
- TTFT: 831.58 ms
- Total Duration: 59616.87 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.25 tok/s
- TTFT: 682.86 ms
- Total Duration: 57170.52 ms

## Delta (B - A)
- Throughput Δ: -2.81 tok/s
- TTFT Δ: +148.71 ms (positive = Agent B faster TTFT)
