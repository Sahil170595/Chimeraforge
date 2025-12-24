# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.15s
- Sequential Estimate: 113.80s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.74 tok/s
- TTFT: 674.11 ms
- Total Duration: 57110.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.74 tok/s
- TTFT: 696.47 ms
- Total Duration: 56616.15 ms

## Delta (B - A)
- Throughput Δ: -1.00 tok/s
- TTFT Δ: -22.36 ms (positive = Agent B faster TTFT)
