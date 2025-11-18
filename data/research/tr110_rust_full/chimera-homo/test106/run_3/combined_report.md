# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 52.75s
- Sequential Estimate: 104.08s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.88 tok/s
- TTFT: 650.80 ms
- Total Duration: 52710.93 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.04 tok/s
- TTFT: 658.81 ms
- Total Duration: 51299.83 ms

## Delta (B - A)
- Throughput Δ: -1.84 tok/s
- TTFT Δ: -8.01 ms (positive = Agent B faster TTFT)
