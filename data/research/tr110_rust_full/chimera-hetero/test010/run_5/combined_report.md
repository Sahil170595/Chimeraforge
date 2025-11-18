# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.91s
- Sequential Estimate: 109.51s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.86 tok/s
- TTFT: 647.61 ms
- Total Duration: 54583.00 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.26 tok/s
- TTFT: 661.21 ms
- Total Duration: 54876.99 ms

## Delta (B - A)
- Throughput Δ: +0.40 tok/s
- TTFT Δ: -13.60 ms (positive = Agent B faster TTFT)
