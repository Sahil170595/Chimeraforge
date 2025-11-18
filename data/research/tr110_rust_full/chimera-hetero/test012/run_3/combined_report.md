# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.23s
- Sequential Estimate: 109.78s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 640.49 ms
- Total Duration: 54520.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.00 tok/s
- TTFT: 655.00 ms
- Total Duration: 55205.17 ms

## Delta (B - A)
- Throughput Δ: +0.87 tok/s
- TTFT Δ: -14.50 ms (positive = Agent B faster TTFT)
