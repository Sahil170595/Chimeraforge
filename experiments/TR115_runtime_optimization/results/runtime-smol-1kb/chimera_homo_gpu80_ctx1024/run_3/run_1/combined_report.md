# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.96s
- Sequential Estimate: 21.38s
- Speedup: 1.79x
- Efficiency: 89.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.01 tok/s
- TTFT: 909.36 ms
- Total Duration: 9425.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 59.91 tok/s
- TTFT: 726.33 ms
- Total Duration: 11954.51 ms

## Delta (B - A)
- Throughput Δ: +16.90 tok/s
- TTFT Δ: +183.03 ms (positive = Agent B faster TTFT)
