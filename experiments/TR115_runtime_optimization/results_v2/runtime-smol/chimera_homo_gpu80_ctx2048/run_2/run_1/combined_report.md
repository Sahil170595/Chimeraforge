# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.35s
- Sequential Estimate: 106.11s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.20 tok/s
- TTFT: 646.82 ms
- Total Duration: 53334.93 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.19 tok/s
- TTFT: 811.43 ms
- Total Duration: 52741.01 ms

## Delta (B - A)
- Throughput Δ: -1.00 tok/s
- TTFT Δ: -164.61 ms (positive = Agent B faster TTFT)
