# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.64s
- Sequential Estimate: 21.47s
- Speedup: 1.84x
- Efficiency: 92.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.50 tok/s
- TTFT: 681.47 ms
- Total Duration: 9830.12 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.34 tok/s
- TTFT: 560.04 ms
- Total Duration: 11643.46 ms

## Delta (B - A)
- Throughput Δ: +12.84 tok/s
- TTFT Δ: +121.44 ms (positive = Agent B faster TTFT)
