# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.61s
- Sequential Estimate: 109.58s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.09 tok/s
- TTFT: 671.85 ms
- Total Duration: 55523.42 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.07 tok/s
- TTFT: 658.42 ms
- Total Duration: 53889.42 ms

## Delta (B - A)
- Throughput Δ: -2.02 tok/s
- TTFT Δ: +13.43 ms (positive = Agent B faster TTFT)
