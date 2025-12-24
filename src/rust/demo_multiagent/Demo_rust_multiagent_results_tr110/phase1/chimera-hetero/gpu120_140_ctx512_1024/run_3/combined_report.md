# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.66s
- Sequential Estimate: 23.68s
- Speedup: 1.42x
- Efficiency: 71.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.90 tok/s
- TTFT: 3283.99 ms
- Total Duration: 7021.11 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.79 tok/s
- TTFT: 10114.51 ms
- Total Duration: 16661.15 ms

## Delta (B - A)
- Throughput Δ: -0.11 tok/s
- TTFT Δ: -6830.51 ms (positive = Agent B faster TTFT)
