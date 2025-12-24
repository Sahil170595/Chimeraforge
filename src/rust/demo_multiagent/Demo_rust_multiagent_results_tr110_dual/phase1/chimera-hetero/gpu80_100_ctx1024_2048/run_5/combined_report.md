# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.73s
- Sequential Estimate: 21.08s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.31 tok/s
- TTFT: 274.21 ms
- Total Duration: 9355.86 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 55.63 tok/s
- TTFT: 323.09 ms
- Total Duration: 11725.70 ms

## Delta (B - A)
- Throughput Δ: +14.33 tok/s
- TTFT Δ: -48.87 ms (positive = Agent B faster TTFT)
