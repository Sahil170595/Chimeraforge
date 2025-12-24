# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.64s
- Sequential Estimate: 22.78s
- Speedup: 1.80x
- Efficiency: 90.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.14 tok/s
- TTFT: 330.98 ms
- Total Duration: 10138.58 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 54.79 tok/s
- TTFT: 303.83 ms
- Total Duration: 12636.89 ms

## Delta (B - A)
- Throughput Δ: +13.65 tok/s
- TTFT Δ: +27.15 ms (positive = Agent B faster TTFT)
