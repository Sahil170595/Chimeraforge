# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.28s
- Sequential Estimate: 19.68s
- Speedup: 1.48x
- Efficiency: 74.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.74 tok/s
- TTFT: 9671.91 ms
- Total Duration: 13275.10 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 102.70 tok/s
- TTFT: 193.44 ms
- Total Duration: 6409.39 ms

## Delta (B - A)
- Throughput Δ: +1.96 tok/s
- TTFT Δ: +9478.48 ms (positive = Agent B faster TTFT)
