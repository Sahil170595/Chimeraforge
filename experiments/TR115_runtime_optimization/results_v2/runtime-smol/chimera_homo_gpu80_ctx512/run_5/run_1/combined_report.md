# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.41s
- Sequential Estimate: 110.29s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.51 tok/s
- TTFT: 663.43 ms
- Total Duration: 54868.67 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.91 tok/s
- TTFT: 845.15 ms
- Total Duration: 55390.17 ms

## Delta (B - A)
- Throughput Δ: +0.39 tok/s
- TTFT Δ: -181.72 ms (positive = Agent B faster TTFT)
