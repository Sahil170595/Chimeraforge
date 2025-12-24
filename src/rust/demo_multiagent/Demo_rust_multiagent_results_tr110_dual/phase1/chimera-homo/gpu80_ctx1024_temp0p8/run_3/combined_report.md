# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.38s
- Sequential Estimate: 22.26s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.63 tok/s
- TTFT: 301.79 ms
- Total Duration: 9878.58 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.56 tok/s
- TTFT: 328.06 ms
- Total Duration: 12378.13 ms

## Delta (B - A)
- Throughput Δ: +13.92 tok/s
- TTFT Δ: -26.27 ms (positive = Agent B faster TTFT)
