# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.80s
- Sequential Estimate: 25.07s
- Speedup: 1.41x
- Efficiency: 70.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.01 tok/s
- TTFT: 3439.62 ms
- Total Duration: 7273.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.54 tok/s
- TTFT: 10586.94 ms
- Total Duration: 17794.68 ms

## Delta (B - A)
- Throughput Δ: +0.54 tok/s
- TTFT Δ: -7147.32 ms (positive = Agent B faster TTFT)
