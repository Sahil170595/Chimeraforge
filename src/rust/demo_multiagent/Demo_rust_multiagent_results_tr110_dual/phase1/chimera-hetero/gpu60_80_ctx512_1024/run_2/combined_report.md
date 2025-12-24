# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.28s
- Sequential Estimate: 22.11s
- Speedup: 1.80x
- Efficiency: 90.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.27 tok/s
- TTFT: 280.09 ms
- Total Duration: 9831.13 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 55.11 tok/s
- TTFT: 327.92 ms
- Total Duration: 12277.84 ms

## Delta (B - A)
- Throughput Δ: +13.85 tok/s
- TTFT Δ: -47.83 ms (positive = Agent B faster TTFT)
