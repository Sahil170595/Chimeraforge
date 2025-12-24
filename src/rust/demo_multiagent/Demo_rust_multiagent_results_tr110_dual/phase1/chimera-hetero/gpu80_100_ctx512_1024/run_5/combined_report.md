# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.39s
- Sequential Estimate: 21.99s
- Speedup: 1.77x
- Efficiency: 88.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.24 tok/s
- TTFT: 278.22 ms
- Total Duration: 9596.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 57.09 tok/s
- TTFT: 336.09 ms
- Total Duration: 12391.49 ms

## Delta (B - A)
- Throughput Δ: +15.85 tok/s
- TTFT Δ: -57.87 ms (positive = Agent B faster TTFT)
