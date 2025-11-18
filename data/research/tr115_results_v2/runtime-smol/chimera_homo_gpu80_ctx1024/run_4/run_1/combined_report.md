# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.77s
- Sequential Estimate: 115.18s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.51 tok/s
- TTFT: 650.12 ms
- Total Duration: 57389.13 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.55 tok/s
- TTFT: 834.36 ms
- Total Duration: 57758.92 ms

## Delta (B - A)
- Throughput Δ: +0.04 tok/s
- TTFT Δ: -184.24 ms (positive = Agent B faster TTFT)
