# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.12s
- Sequential Estimate: 13.90s
- Speedup: 1.37x
- Efficiency: 68.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.22 tok/s
- TTFT: 204.97 ms
- Total Duration: 3773.09 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.83 tok/s
- TTFT: 3801.45 ms
- Total Duration: 10123.53 ms

## Delta (B - A)
- Throughput Δ: -0.39 tok/s
- TTFT Δ: -3596.48 ms (positive = Agent B faster TTFT)
