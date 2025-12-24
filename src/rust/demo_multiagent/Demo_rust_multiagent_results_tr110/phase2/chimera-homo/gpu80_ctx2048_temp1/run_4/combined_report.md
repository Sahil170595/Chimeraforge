# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 4.89s
- Sequential Estimate: 9.03s
- Speedup: 1.85x
- Efficiency: 92.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.64 tok/s
- TTFT: 164.46 ms
- Total Duration: 4141.20 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 104.85 tok/s
- TTFT: 4170.32 ms
- Total Duration: 4887.15 ms

## Delta (B - A)
- Throughput Δ: +3.21 tok/s
- TTFT Δ: -4005.86 ms (positive = Agent B faster TTFT)
