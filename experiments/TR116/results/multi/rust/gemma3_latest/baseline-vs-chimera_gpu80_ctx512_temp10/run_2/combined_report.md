# Rust Multi-Agent Report – Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.50s
- Sequential Estimate: 117.15s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.92 tok/s
- TTFT: 664.76 ms
- Total Duration: 57649.38 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.14 tok/s
- TTFT: 519.50 ms
- Total Duration: 59496.26 ms

## Delta (B - A)
- Throughput Δ: +2.22 tok/s
- TTFT Δ: +145.26 ms (positive = Agent B faster TTFT)
