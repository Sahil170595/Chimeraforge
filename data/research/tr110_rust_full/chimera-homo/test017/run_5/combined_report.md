# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.43s
- Sequential Estimate: 112.19s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.77 tok/s
- TTFT: 658.30 ms
- Total Duration: 56391.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.96 tok/s
- TTFT: 643.07 ms
- Total Duration: 55734.82 ms

## Delta (B - A)
- Throughput Δ: -0.82 tok/s
- TTFT Δ: +15.23 ms (positive = Agent B faster TTFT)
