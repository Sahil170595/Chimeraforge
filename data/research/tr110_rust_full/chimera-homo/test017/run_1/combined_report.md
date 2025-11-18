# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 63.00s
- Sequential Estimate: 125.29s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.86 tok/s
- TTFT: 3381.62 ms
- Total Duration: 62265.33 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.13 tok/s
- TTFT: 3389.28 ms
- Total Duration: 62959.15 ms

## Delta (B - A)
- Throughput Δ: +1.27 tok/s
- TTFT Δ: -7.65 ms (positive = Agent B faster TTFT)
