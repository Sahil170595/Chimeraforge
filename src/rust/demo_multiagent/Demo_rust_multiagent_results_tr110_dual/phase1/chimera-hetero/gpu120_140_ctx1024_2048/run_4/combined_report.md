# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.12s
- Sequential Estimate: 22.10s
- Speedup: 1.82x
- Efficiency: 91.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.08 tok/s
- TTFT: 266.86 ms
- Total Duration: 9974.24 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 53.39 tok/s
- TTFT: 303.99 ms
- Total Duration: 12124.18 ms

## Delta (B - A)
- Throughput Δ: +12.31 tok/s
- TTFT Δ: -37.13 ms (positive = Agent B faster TTFT)
