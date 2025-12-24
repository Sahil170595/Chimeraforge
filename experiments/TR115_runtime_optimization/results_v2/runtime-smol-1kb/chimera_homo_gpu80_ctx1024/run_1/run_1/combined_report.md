# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 52.44s
- Sequential Estimate: 104.64s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.10 tok/s
- TTFT: 878.15 ms
- Total Duration: 52405.99 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 1056.34 ms
- Total Duration: 52179.46 ms

## Delta (B - A)
- Throughput Δ: -0.12 tok/s
- TTFT Δ: -178.19 ms (positive = Agent B faster TTFT)
