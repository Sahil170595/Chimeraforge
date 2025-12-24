# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.12s
- Sequential Estimate: 24.99s
- Speedup: 1.91x
- Efficiency: 95.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.29 tok/s
- TTFT: 674.86 ms
- Total Duration: 11875.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.93 tok/s
- TTFT: 579.79 ms
- Total Duration: 13115.18 ms

## Delta (B - A)
- Throughput Δ: +7.64 tok/s
- TTFT Δ: +95.07 ms (positive = Agent B faster TTFT)
