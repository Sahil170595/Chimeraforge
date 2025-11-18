# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.92s
- Sequential Estimate: 116.98s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.57 tok/s
- TTFT: 814.57 ms
- Total Duration: 58037.35 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.64 tok/s
- TTFT: 662.12 ms
- Total Duration: 58891.01 ms

## Delta (B - A)
- Throughput Δ: +1.07 tok/s
- TTFT Δ: +152.46 ms (positive = Agent B faster TTFT)
