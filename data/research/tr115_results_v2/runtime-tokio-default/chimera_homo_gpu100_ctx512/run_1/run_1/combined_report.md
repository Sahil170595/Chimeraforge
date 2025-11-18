# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 61.65s
- Sequential Estimate: 123.17s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.64 tok/s
- TTFT: 4489.96 ms
- Total Duration: 61623.13 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 4330.15 ms
- Total Duration: 61481.61 ms

## Delta (B - A)
- Throughput Δ: -0.47 tok/s
- TTFT Δ: +159.82 ms (positive = Agent B faster TTFT)
