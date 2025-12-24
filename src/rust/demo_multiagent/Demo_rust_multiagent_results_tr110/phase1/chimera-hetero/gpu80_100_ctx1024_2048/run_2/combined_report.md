# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.66s
- Sequential Estimate: 25.25s
- Speedup: 1.43x
- Efficiency: 71.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.04 tok/s
- TTFT: 3347.15 ms
- Total Duration: 7589.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.59 tok/s
- TTFT: 10542.38 ms
- Total Duration: 17662.89 ms

## Delta (B - A)
- Throughput Δ: +0.54 tok/s
- TTFT Δ: -7195.24 ms (positive = Agent B faster TTFT)
