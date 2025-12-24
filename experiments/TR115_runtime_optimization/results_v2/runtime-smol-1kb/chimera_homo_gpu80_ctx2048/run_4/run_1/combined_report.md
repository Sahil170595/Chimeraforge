# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.96s
- Sequential Estimate: 112.06s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.00 tok/s
- TTFT: 1068.63 ms
- Total Duration: 55066.11 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.36 tok/s
- TTFT: 1067.74 ms
- Total Duration: 56919.71 ms

## Delta (B - A)
- Throughput Δ: +2.36 tok/s
- TTFT Δ: +0.89 ms (positive = Agent B faster TTFT)
