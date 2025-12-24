# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.36s
- Sequential Estimate: 22.12s
- Speedup: 1.79x
- Efficiency: 89.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.26 tok/s
- TTFT: 713.66 ms
- Total Duration: 9764.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.30 tok/s
- TTFT: 604.90 ms
- Total Duration: 12356.87 ms

## Delta (B - A)
- Throughput Δ: +15.04 tok/s
- TTFT Δ: +108.76 ms (positive = Agent B faster TTFT)
