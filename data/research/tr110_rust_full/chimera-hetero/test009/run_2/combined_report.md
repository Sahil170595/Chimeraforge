# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 57.46s
- Sequential Estimate: 114.09s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 646.08 ms
- Total Duration: 56547.58 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.06 tok/s
- TTFT: 677.01 ms
- Total Duration: 57378.16 ms

## Delta (B - A)
- Throughput Δ: +1.08 tok/s
- TTFT Δ: -30.93 ms (positive = Agent B faster TTFT)
