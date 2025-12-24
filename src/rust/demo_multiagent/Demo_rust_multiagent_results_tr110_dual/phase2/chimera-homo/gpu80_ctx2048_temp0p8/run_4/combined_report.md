# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.74s
- Sequential Estimate: 21.07s
- Speedup: 1.79x
- Efficiency: 89.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.93 tok/s
- TTFT: 215.84 ms
- Total Duration: 9328.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.49 tok/s
- TTFT: 364.09 ms
- Total Duration: 11738.43 ms

## Delta (B - A)
- Throughput Δ: +13.56 tok/s
- TTFT Δ: -148.25 ms (positive = Agent B faster TTFT)
