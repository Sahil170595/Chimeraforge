# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.29s
- Sequential Estimate: 20.66s
- Speedup: 1.83x
- Efficiency: 91.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.23 tok/s
- TTFT: 680.16 ms
- Total Duration: 9367.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.20 tok/s
- TTFT: 569.76 ms
- Total Duration: 11292.53 ms

## Delta (B - A)
- Throughput Δ: +13.96 tok/s
- TTFT Δ: +110.40 ms (positive = Agent B faster TTFT)
