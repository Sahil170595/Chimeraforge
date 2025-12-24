# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.95s
- Sequential Estimate: 26.28s
- Speedup: 1.88x
- Efficiency: 94.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.05 tok/s
- TTFT: 787.90 ms
- Total Duration: 12327.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.08 tok/s
- TTFT: 591.19 ms
- Total Duration: 13953.11 ms

## Delta (B - A)
- Throughput Δ: +9.03 tok/s
- TTFT Δ: +196.71 ms (positive = Agent B faster TTFT)
