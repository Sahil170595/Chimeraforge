# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.70s
- Sequential Estimate: 22.50s
- Speedup: 1.77x
- Efficiency: 88.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.15 tok/s
- TTFT: 272.46 ms
- Total Duration: 9803.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 56.94 tok/s
- TTFT: 314.97 ms
- Total Duration: 12696.24 ms

## Delta (B - A)
- Throughput Δ: +15.79 tok/s
- TTFT Δ: -42.51 ms (positive = Agent B faster TTFT)
