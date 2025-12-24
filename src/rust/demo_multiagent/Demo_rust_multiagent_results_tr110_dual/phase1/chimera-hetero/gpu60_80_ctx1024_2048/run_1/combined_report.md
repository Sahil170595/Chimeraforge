# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.36s
- Sequential Estimate: 22.27s
- Speedup: 1.80x
- Efficiency: 90.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.24 tok/s
- TTFT: 283.10 ms
- Total Duration: 9917.87 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 54.98 tok/s
- TTFT: 305.16 ms
- Total Duration: 12356.32 ms

## Delta (B - A)
- Throughput Δ: +13.74 tok/s
- TTFT Δ: -22.06 ms (positive = Agent B faster TTFT)
