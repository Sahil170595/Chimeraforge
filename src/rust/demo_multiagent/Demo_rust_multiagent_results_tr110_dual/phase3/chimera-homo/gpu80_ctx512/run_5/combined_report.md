# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.49s
- Sequential Estimate: 20.72s
- Speedup: 1.80x
- Efficiency: 90.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.17 tok/s
- TTFT: 279.73 ms
- Total Duration: 9234.29 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.13 tok/s
- TTFT: 305.73 ms
- Total Duration: 11489.75 ms

## Delta (B - A)
- Throughput Δ: +13.96 tok/s
- TTFT Δ: -26.00 ms (positive = Agent B faster TTFT)
