# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.25s
- Sequential Estimate: 108.06s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.94 tok/s
- TTFT: 822.25 ms
- Total Duration: 54207.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.38 tok/s
- TTFT: 808.98 ms
- Total Duration: 53779.69 ms

## Delta (B - A)
- Throughput Δ: -0.56 tok/s
- TTFT Δ: +13.27 ms (positive = Agent B faster TTFT)
