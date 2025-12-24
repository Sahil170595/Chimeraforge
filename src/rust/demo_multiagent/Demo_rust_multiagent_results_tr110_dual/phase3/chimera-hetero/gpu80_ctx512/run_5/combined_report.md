# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.31s
- Sequential Estimate: 21.69s
- Speedup: 1.76x
- Efficiency: 88.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.40 tok/s
- TTFT: 274.50 ms
- Total Duration: 9380.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 57.74 tok/s
- TTFT: 321.54 ms
- Total Duration: 12310.52 ms

## Delta (B - A)
- Throughput Δ: +16.34 tok/s
- TTFT Δ: -47.04 ms (positive = Agent B faster TTFT)
