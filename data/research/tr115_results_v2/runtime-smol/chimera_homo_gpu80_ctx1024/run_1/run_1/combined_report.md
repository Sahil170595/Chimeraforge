# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.60s
- Sequential Estimate: 113.65s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.85 tok/s
- TTFT: 517.48 ms
- Total Duration: 57581.66 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.07 tok/s
- TTFT: 814.47 ms
- Total Duration: 56026.56 ms

## Delta (B - A)
- Throughput Δ: -1.78 tok/s
- TTFT Δ: -296.99 ms (positive = Agent B faster TTFT)
