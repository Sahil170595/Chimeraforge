# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 49.22s
- Sequential Estimate: 94.25s
- Speedup: 1.91x
- Efficiency: 95.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 47.97 tok/s
- TTFT: 654.43 ms
- Total Duration: 49188.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 661.87 ms
- Total Duration: 44993.85 ms

## Delta (B - A)
- Throughput Δ: -6.97 tok/s
- TTFT Δ: -7.44 ms (positive = Agent B faster TTFT)
