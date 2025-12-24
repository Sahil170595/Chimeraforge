# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.16s
- Sequential Estimate: 24.48s
- Speedup: 1.86x
- Efficiency: 93.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.11 tok/s
- TTFT: 268.19 ms
- Total Duration: 11317.01 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 50.82 tok/s
- TTFT: 313.31 ms
- Total Duration: 13160.84 ms

## Delta (B - A)
- Throughput Δ: +9.71 tok/s
- TTFT Δ: -45.12 ms (positive = Agent B faster TTFT)
