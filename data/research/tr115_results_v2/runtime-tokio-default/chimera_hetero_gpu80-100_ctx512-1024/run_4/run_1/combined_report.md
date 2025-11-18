# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.21s
- Sequential Estimate: 109.79s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 648.50 ms
- Total Duration: 54568.90 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.23 tok/s
- TTFT: 800.03 ms
- Total Duration: 55189.20 ms

## Delta (B - A)
- Throughput Δ: +0.38 tok/s
- TTFT Δ: -151.53 ms (positive = Agent B faster TTFT)
