# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.11s
- Sequential Estimate: 111.41s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.12 tok/s
- TTFT: 1017.11 ms
- Total Duration: 56078.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.73 tok/s
- TTFT: 835.21 ms
- Total Duration: 55260.74 ms

## Delta (B - A)
- Throughput Δ: -1.39 tok/s
- TTFT Δ: +181.89 ms (positive = Agent B faster TTFT)
