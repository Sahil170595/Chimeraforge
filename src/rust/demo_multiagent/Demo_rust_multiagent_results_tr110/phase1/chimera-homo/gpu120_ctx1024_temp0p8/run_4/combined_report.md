# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.96s
- Sequential Estimate: 15.58s
- Speedup: 1.42x
- Efficiency: 71.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.32 tok/s
- TTFT: 225.71 ms
- Total Duration: 4615.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.73 tok/s
- TTFT: 4645.58 ms
- Total Duration: 10959.99 ms

## Delta (B - A)
- Throughput Δ: -0.58 tok/s
- TTFT Δ: -4419.87 ms (positive = Agent B faster TTFT)
