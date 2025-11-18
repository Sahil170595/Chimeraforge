# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 57.67s
- Sequential Estimate: 113.86s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.37 tok/s
- TTFT: 3488.56 ms
- Total Duration: 56136.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.44 tok/s
- TTFT: 3474.77 ms
- Total Duration: 57623.46 ms

## Delta (B - A)
- Throughput Δ: +2.07 tok/s
- TTFT Δ: +13.79 ms (positive = Agent B faster TTFT)
