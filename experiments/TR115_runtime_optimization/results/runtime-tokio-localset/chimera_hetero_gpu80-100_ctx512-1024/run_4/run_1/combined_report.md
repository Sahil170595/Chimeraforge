# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.22s
- Sequential Estimate: 22.21s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 739.29 ms
- Total Duration: 9994.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.82 tok/s
- TTFT: 580.54 ms
- Total Duration: 12219.17 ms

## Delta (B - A)
- Throughput Δ: +13.98 tok/s
- TTFT Δ: +158.74 ms (positive = Agent B faster TTFT)
