# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.13s
- Sequential Estimate: 21.96s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.23 tok/s
- TTFT: 274.74 ms
- Total Duration: 9827.46 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.24 tok/s
- TTFT: 314.58 ms
- Total Duration: 12129.32 ms

## Delta (B - A)
- Throughput Δ: +13.01 tok/s
- TTFT Δ: -39.84 ms (positive = Agent B faster TTFT)
