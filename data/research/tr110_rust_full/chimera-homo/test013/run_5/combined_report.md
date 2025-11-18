# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.96s
- Sequential Estimate: 115.33s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.68 tok/s
- TTFT: 663.51 ms
- Total Duration: 57928.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.71 tok/s
- TTFT: 503.07 ms
- Total Duration: 57340.21 ms

## Delta (B - A)
- Throughput Δ: -0.97 tok/s
- TTFT Δ: +160.43 ms (positive = Agent B faster TTFT)
