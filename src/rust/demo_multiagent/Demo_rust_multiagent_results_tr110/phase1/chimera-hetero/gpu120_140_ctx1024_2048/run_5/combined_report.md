# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.50s
- Sequential Estimate: 19.71s
- Speedup: 1.46x
- Efficiency: 73.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.87 tok/s
- TTFT: 9564.45 ms
- Total Duration: 13499.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 102.26 tok/s
- TTFT: 202.34 ms
- Total Duration: 6211.99 ms

## Delta (B - A)
- Throughput Δ: +1.39 tok/s
- TTFT Δ: +9362.12 ms (positive = Agent B faster TTFT)
