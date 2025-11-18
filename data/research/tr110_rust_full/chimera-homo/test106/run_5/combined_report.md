# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.28s
- Sequential Estimate: 110.14s
- Speedup: 1.96x
- Efficiency: 97.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.62 tok/s
- TTFT: 520.38 ms
- Total Duration: 56251.95 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.92 tok/s
- TTFT: 663.78 ms
- Total Duration: 53835.69 ms

## Delta (B - A)
- Throughput Δ: -2.71 tok/s
- TTFT Δ: -143.40 ms (positive = Agent B faster TTFT)
