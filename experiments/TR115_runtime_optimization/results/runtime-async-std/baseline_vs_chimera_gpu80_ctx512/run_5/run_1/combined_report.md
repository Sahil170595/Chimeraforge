# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 10.51s
- Sequential Estimate: 10.51s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 122.71 tok/s
- TTFT: 637.98 ms
- Total Duration: 4292.33 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 120.95 tok/s
- TTFT: 563.08 ms
- Total Duration: 6221.65 ms

## Delta (B - A)
- Throughput Δ: -1.76 tok/s
- TTFT Δ: +74.90 ms (positive = Agent B faster TTFT)
