# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.96s
- Sequential Estimate: 24.11s
- Speedup: 1.86x
- Efficiency: 93.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.80 tok/s
- TTFT: 207.69 ms
- Total Duration: 11147.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 50.74 tok/s
- TTFT: 344.28 ms
- Total Duration: 12957.95 ms

## Delta (B - A)
- Throughput Δ: +8.94 tok/s
- TTFT Δ: -136.59 ms (positive = Agent B faster TTFT)
