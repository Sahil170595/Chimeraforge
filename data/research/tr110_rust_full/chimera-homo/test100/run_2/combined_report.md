# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 109.12s
- Sequential Estimate: 165.33s
- Speedup: 1.52x
- Efficiency: 75.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.31 tok/s
- TTFT: 678.70 ms
- Total Duration: 56146.38 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 64.13 tok/s
- TTFT: 564.32 ms
- Total Duration: 109046.67 ms

## Delta (B - A)
- Throughput Δ: +22.83 tok/s
- TTFT Δ: +114.38 ms (positive = Agent B faster TTFT)
