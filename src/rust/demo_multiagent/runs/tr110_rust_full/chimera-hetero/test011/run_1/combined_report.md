# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 61.00s
- Sequential Estimate: 121.43s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.83 tok/s
- TTFT: 3523.13 ms
- Total Duration: 60962.42 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 3210.30 ms
- Total Duration: 60402.75 ms

## Delta (B - A)
- Throughput Δ: -0.92 tok/s
- TTFT Δ: +312.83 ms (positive = Agent B faster TTFT)
