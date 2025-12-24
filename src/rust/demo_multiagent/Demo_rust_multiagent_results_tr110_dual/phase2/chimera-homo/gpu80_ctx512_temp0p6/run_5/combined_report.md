# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.05s
- Sequential Estimate: 23.43s
- Speedup: 1.80x
- Efficiency: 89.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.07 tok/s
- TTFT: 263.26 ms
- Total Duration: 10375.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.01 tok/s
- TTFT: 301.86 ms
- Total Duration: 13049.32 ms

## Delta (B - A)
- Throughput Δ: +13.93 tok/s
- TTFT Δ: -38.60 ms (positive = Agent B faster TTFT)
