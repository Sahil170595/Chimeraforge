# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.87s
- Sequential Estimate: 15.19s
- Speedup: 1.40x
- Efficiency: 69.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.86 tok/s
- TTFT: 203.27 ms
- Total Duration: 4327.93 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.71 tok/s
- TTFT: 4356.16 ms
- Total Duration: 10865.48 ms

## Delta (B - A)
- Throughput Δ: -1.15 tok/s
- TTFT Δ: -4152.90 ms (positive = Agent B faster TTFT)
