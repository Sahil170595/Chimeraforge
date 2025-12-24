# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.14s
- Sequential Estimate: 6.03s
- Speedup: 1.17x
- Efficiency: 58.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.74 tok/s
- TTFT: 919.89 ms
- Total Duration: 5137.95 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 104.79 tok/s
- TTFT: 219.71 ms
- Total Duration: 888.12 ms

## Delta (B - A)
- Throughput Δ: +3.06 tok/s
- TTFT Δ: +700.18 ms (positive = Agent B faster TTFT)
