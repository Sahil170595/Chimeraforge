# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.91s
- Sequential Estimate: 113.21s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.17 tok/s
- TTFT: 650.91 ms
- Total Duration: 56274.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.89 tok/s
- TTFT: 654.16 ms
- Total Duration: 56881.50 ms

## Delta (B - A)
- Throughput Δ: +0.72 tok/s
- TTFT Δ: -3.25 ms (positive = Agent B faster TTFT)
