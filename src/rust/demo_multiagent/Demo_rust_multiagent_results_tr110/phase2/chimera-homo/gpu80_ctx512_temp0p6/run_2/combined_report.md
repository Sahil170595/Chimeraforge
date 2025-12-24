# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.82s
- Sequential Estimate: 15.35s
- Speedup: 1.42x
- Efficiency: 70.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.92 tok/s
- TTFT: 227.93 ms
- Total Duration: 4530.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.75 tok/s
- TTFT: 4558.32 ms
- Total Duration: 10823.07 ms

## Delta (B - A)
- Throughput Δ: +0.82 tok/s
- TTFT Δ: -4330.39 ms (positive = Agent B faster TTFT)
