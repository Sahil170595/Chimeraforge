# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.55s
- Sequential Estimate: 22.13s
- Speedup: 1.76x
- Efficiency: 88.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.20 tok/s
- TTFT: 277.58 ms
- Total Duration: 9587.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 58.31 tok/s
- TTFT: 314.63 ms
- Total Duration: 12544.80 ms

## Delta (B - A)
- Throughput Δ: +17.11 tok/s
- TTFT Δ: -37.05 ms (positive = Agent B faster TTFT)
