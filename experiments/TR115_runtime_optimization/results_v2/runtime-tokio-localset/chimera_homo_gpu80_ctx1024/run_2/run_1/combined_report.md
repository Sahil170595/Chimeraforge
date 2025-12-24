# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.95s
- Sequential Estimate: 108.06s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.65 tok/s
- TTFT: 775.91 ms
- Total Duration: 54929.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 798.08 ms
- Total Duration: 53082.26 ms

## Delta (B - A)
- Throughput Δ: -2.47 tok/s
- TTFT Δ: -22.17 ms (positive = Agent B faster TTFT)
