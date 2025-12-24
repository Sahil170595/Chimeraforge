# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 14.40s
- Sequential Estimate: 21.10s
- Speedup: 1.47x
- Efficiency: 73.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.76 tok/s
- TTFT: 10032.33 ms
- Total Duration: 14399.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.12 tok/s
- TTFT: 228.13 ms
- Total Duration: 6700.44 ms

## Delta (B - A)
- Throughput Δ: +0.36 tok/s
- TTFT Δ: +9804.19 ms (positive = Agent B faster TTFT)
