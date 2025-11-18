# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.66s
- Sequential Estimate: 113.84s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.82 tok/s
- TTFT: 1084.42 ms
- Total Duration: 57627.29 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 1083.75 ms
- Total Duration: 56144.39 ms

## Delta (B - A)
- Throughput Δ: -1.69 tok/s
- TTFT Δ: +0.68 ms (positive = Agent B faster TTFT)
