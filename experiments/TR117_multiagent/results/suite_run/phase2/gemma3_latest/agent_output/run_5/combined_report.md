# Rust Multi-Agent Report – Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.73s
- Sequential Estimate: 108.79s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.26 tok/s
- TTFT: 488.29 ms
- Total Duration: 54730.40 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.72 tok/s
- TTFT: 476.12 ms
- Total Duration: 54057.86 ms

## Delta (B - A)
- Throughput Δ: -0.54 tok/s
- TTFT Δ: +12.18 ms (positive = Agent B faster TTFT)
