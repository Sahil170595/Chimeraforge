# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.12s
- Sequential Estimate: 21.80s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.23 tok/s
- TTFT: 252.22 ms
- Total Duration: 9676.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 55.02 tok/s
- TTFT: 294.30 ms
- Total Duration: 12121.45 ms

## Delta (B - A)
- Throughput Δ: +13.79 tok/s
- TTFT Δ: -42.07 ms (positive = Agent B faster TTFT)
