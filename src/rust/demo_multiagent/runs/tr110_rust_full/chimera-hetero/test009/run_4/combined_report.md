# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.12s
- Sequential Estimate: 109.84s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.71 tok/s
- TTFT: 678.34 ms
- Total Duration: 54699.69 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 681.03 ms
- Total Duration: 55104.36 ms

## Delta (B - A)
- Throughput Δ: +0.48 tok/s
- TTFT Δ: -2.68 ms (positive = Agent B faster TTFT)
