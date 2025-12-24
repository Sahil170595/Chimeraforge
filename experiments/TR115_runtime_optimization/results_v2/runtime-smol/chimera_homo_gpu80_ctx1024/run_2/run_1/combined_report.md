# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.12s
- Sequential Estimate: 115.10s
- Speedup: 1.95x
- Efficiency: 97.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 45.13 tok/s
- TTFT: 667.44 ms
- Total Duration: 59100.79 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 811.37 ms
- Total Duration: 55963.27 ms

## Delta (B - A)
- Throughput Δ: -4.00 tok/s
- TTFT Δ: -143.93 ms (positive = Agent B faster TTFT)
