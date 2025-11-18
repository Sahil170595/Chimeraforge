# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.49s
- Sequential Estimate: 108.55s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.64 tok/s
- TTFT: 779.69 ms
- Total Duration: 54460.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.02 tok/s
- TTFT: 813.93 ms
- Total Duration: 54022.85 ms

## Delta (B - A)
- Throughput Δ: -0.62 tok/s
- TTFT Δ: -34.24 ms (positive = Agent B faster TTFT)
