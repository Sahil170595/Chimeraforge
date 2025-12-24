# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.51s
- Sequential Estimate: 15.67s
- Speedup: 1.36x
- Efficiency: 68.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.39 tok/s
- TTFT: 225.60 ms
- Total Duration: 4163.01 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.09 tok/s
- TTFT: 4192.93 ms
- Total Duration: 11507.95 ms

## Delta (B - A)
- Throughput Δ: -0.30 tok/s
- TTFT Δ: -3967.33 ms (positive = Agent B faster TTFT)
