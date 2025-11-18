# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 61.12s
- Sequential Estimate: 120.56s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.46 tok/s
- TTFT: 4041.51 ms
- Total Duration: 61077.99 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.52 tok/s
- TTFT: 3410.95 ms
- Total Duration: 59406.73 ms

## Delta (B - A)
- Throughput Δ: -0.94 tok/s
- TTFT Δ: +630.56 ms (positive = Agent B faster TTFT)
