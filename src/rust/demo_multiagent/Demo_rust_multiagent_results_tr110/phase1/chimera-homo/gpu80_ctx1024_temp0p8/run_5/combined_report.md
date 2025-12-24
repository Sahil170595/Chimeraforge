# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.14s
- Sequential Estimate: 15.10s
- Speedup: 1.36x
- Efficiency: 67.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.76 tok/s
- TTFT: 220.96 ms
- Total Duration: 3958.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.31 tok/s
- TTFT: 3987.13 ms
- Total Duration: 11139.75 ms

## Delta (B - A)
- Throughput Δ: -0.45 tok/s
- TTFT Δ: -3766.17 ms (positive = Agent B faster TTFT)
