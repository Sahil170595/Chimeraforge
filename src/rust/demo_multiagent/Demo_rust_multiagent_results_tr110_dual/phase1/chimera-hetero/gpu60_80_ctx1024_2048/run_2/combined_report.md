# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.99s
- Sequential Estimate: 21.90s
- Speedup: 1.83x
- Efficiency: 91.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.07 tok/s
- TTFT: 275.56 ms
- Total Duration: 9912.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 53.13 tok/s
- TTFT: 305.00 ms
- Total Duration: 11991.47 ms

## Delta (B - A)
- Throughput Δ: +12.06 tok/s
- TTFT Δ: -29.44 ms (positive = Agent B faster TTFT)
