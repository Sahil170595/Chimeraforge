# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 5.15s
- Sequential Estimate: 9.47s
- Speedup: 1.84x
- Efficiency: 92.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.97 tok/s
- TTFT: 192.71 ms
- Total Duration: 4327.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.84 tok/s
- TTFT: 4357.68 ms
- Total Duration: 5145.48 ms

## Delta (B - A)
- Throughput Δ: +2.87 tok/s
- TTFT Δ: -4164.97 ms (positive = Agent B faster TTFT)
