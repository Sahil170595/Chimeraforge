# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 57.73s
- Sequential Estimate: 114.90s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.64 tok/s
- TTFT: 653.47 ms
- Total Duration: 57710.72 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.92 tok/s
- TTFT: 662.00 ms
- Total Duration: 57148.18 ms

## Delta (B - A)
- Throughput Δ: -0.72 tok/s
- TTFT Δ: -8.52 ms (positive = Agent B faster TTFT)
