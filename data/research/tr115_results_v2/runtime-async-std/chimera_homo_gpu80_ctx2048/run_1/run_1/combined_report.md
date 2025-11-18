# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 49.43s
- Sequential Estimate: 49.42s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.39 tok/s
- TTFT: 584.35 ms
- Total Duration: 25571.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.08 tok/s
- TTFT: 586.64 ms
- Total Duration: 23784.74 ms

## Delta (B - A)
- Throughput Δ: -0.31 tok/s
- TTFT Δ: -2.29 ms (positive = Agent B faster TTFT)
