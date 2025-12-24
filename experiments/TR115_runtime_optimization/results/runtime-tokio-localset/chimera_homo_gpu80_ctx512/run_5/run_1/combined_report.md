# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.62s
- Sequential Estimate: 22.90s
- Speedup: 1.81x
- Efficiency: 90.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.92 tok/s
- TTFT: 693.03 ms
- Total Duration: 10283.01 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.49 tok/s
- TTFT: 599.17 ms
- Total Duration: 12620.18 ms

## Delta (B - A)
- Throughput Δ: +13.57 tok/s
- TTFT Δ: +93.86 ms (positive = Agent B faster TTFT)
