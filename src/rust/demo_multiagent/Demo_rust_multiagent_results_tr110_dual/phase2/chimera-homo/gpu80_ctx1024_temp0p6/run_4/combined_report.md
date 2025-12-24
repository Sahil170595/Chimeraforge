# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.35s
- Sequential Estimate: 22.23s
- Speedup: 1.80x
- Efficiency: 90.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.01 tok/s
- TTFT: 303.06 ms
- Total Duration: 9881.13 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.83 tok/s
- TTFT: 307.66 ms
- Total Duration: 12350.05 ms

## Delta (B - A)
- Throughput Δ: +13.82 tok/s
- TTFT Δ: -4.59 ms (positive = Agent B faster TTFT)
