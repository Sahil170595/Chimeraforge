# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.82s
- Sequential Estimate: 115.46s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 845.74 ms
- Total Duration: 57609.81 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 847.84 ms
- Total Duration: 57779.99 ms

## Delta (B - A)
- Throughput Δ: +0.07 tok/s
- TTFT Δ: -2.10 ms (positive = Agent B faster TTFT)
