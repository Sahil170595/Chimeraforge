# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.22s
- Sequential Estimate: 105.74s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.71 tok/s
- TTFT: 878.80 ms
- Total Duration: 53187.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.08 tok/s
- TTFT: 1051.24 ms
- Total Duration: 52489.70 ms

## Delta (B - A)
- Throughput Δ: -0.63 tok/s
- TTFT Δ: -172.43 ms (positive = Agent B faster TTFT)
