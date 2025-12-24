# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.33s
- Sequential Estimate: 21.48s
- Speedup: 1.74x
- Efficiency: 87.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.13 tok/s
- TTFT: 308.73 ms
- Total Duration: 9147.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 59.31 tok/s
- TTFT: 308.84 ms
- Total Duration: 12332.34 ms

## Delta (B - A)
- Throughput Δ: +18.18 tok/s
- TTFT Δ: -0.10 ms (positive = Agent B faster TTFT)
