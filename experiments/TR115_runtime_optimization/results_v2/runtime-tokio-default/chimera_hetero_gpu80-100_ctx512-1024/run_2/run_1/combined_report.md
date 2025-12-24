# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 62.51s
- Sequential Estimate: 124.43s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.39 tok/s
- TTFT: 760.41 ms
- Total Duration: 61876.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.53 tok/s
- TTFT: 911.33 ms
- Total Duration: 62462.12 ms

## Delta (B - A)
- Throughput Δ: +0.15 tok/s
- TTFT Δ: -150.92 ms (positive = Agent B faster TTFT)
