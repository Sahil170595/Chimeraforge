# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.13s
- Sequential Estimate: 25.59s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.16 tok/s
- TTFT: 261.85 ms
- Total Duration: 11459.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.31 tok/s
- TTFT: 306.27 ms
- Total Duration: 14132.17 ms

## Delta (B - A)
- Throughput Δ: +13.15 tok/s
- TTFT Δ: -44.42 ms (positive = Agent B faster TTFT)
