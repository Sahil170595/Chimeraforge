# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.20s
- Sequential Estimate: 116.10s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.50 tok/s
- TTFT: 1033.23 ms
- Total Duration: 58160.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.09 tok/s
- TTFT: 1059.96 ms
- Total Duration: 57865.30 ms

## Delta (B - A)
- Throughput Δ: -0.41 tok/s
- TTFT Δ: -26.73 ms (positive = Agent B faster TTFT)
