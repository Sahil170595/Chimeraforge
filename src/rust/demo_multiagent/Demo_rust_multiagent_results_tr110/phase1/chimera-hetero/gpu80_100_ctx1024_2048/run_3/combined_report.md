# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.45s
- Sequential Estimate: 19.98s
- Speedup: 1.49x
- Efficiency: 74.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.93 tok/s
- TTFT: 9749.32 ms
- Total Duration: 13449.03 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.81 tok/s
- TTFT: 195.52 ms
- Total Duration: 6534.91 ms

## Delta (B - A)
- Throughput Δ: +0.87 tok/s
- TTFT Δ: +9553.80 ms (positive = Agent B faster TTFT)
