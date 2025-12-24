# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.17s
- Sequential Estimate: 14.08s
- Speedup: 1.38x
- Efficiency: 69.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.38 tok/s
- TTFT: 191.05 ms
- Total Duration: 3912.18 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.66 tok/s
- TTFT: 3943.25 ms
- Total Duration: 10172.06 ms

## Delta (B - A)
- Throughput Δ: -0.72 tok/s
- TTFT Δ: -3752.20 ms (positive = Agent B faster TTFT)
