# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.97s
- Sequential Estimate: 23.96s
- Speedup: 1.41x
- Efficiency: 70.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.77 tok/s
- TTFT: 3382.24 ms
- Total Duration: 6985.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.41 tok/s
- TTFT: 10341.09 ms
- Total Duration: 16973.07 ms

## Delta (B - A)
- Throughput Δ: -0.36 tok/s
- TTFT Δ: -6958.85 ms (positive = Agent B faster TTFT)
