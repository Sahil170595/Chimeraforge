# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.62s
- Sequential Estimate: 15.67s
- Speedup: 1.35x
- Efficiency: 67.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.17 tok/s
- TTFT: 7258.14 ms
- Total Duration: 11620.99 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.74 tok/s
- TTFT: 3322.77 ms
- Total Duration: 4052.63 ms

## Delta (B - A)
- Throughput Δ: -1.42 tok/s
- TTFT Δ: +3935.37 ms (positive = Agent B faster TTFT)
