# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.23s
- Sequential Estimate: 16.92s
- Speedup: 1.65x
- Efficiency: 82.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.92 tok/s
- TTFT: 6708.49 ms
- Total Duration: 10232.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.99 tok/s
- TTFT: 200.74 ms
- Total Duration: 6682.23 ms

## Delta (B - A)
- Throughput Δ: -0.93 tok/s
- TTFT Δ: +6507.74 ms (positive = Agent B faster TTFT)
