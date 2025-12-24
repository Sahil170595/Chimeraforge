# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.49s
- Sequential Estimate: 14.75s
- Speedup: 1.41x
- Efficiency: 70.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.15 tok/s
- TTFT: 236.58 ms
- Total Duration: 4262.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.00 tok/s
- TTFT: 4292.45 ms
- Total Duration: 10487.07 ms

## Delta (B - A)
- Throughput Δ: -0.14 tok/s
- TTFT Δ: -4055.87 ms (positive = Agent B faster TTFT)
