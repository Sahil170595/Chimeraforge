# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.52s
- Sequential Estimate: 17.91s
- Speedup: 1.32x
- Efficiency: 66.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.27 tok/s
- TTFT: 201.66 ms
- Total Duration: 4389.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.46 tok/s
- TTFT: 7557.59 ms
- Total Duration: 13517.11 ms

## Delta (B - A)
- Throughput Δ: -1.81 tok/s
- TTFT Δ: -7355.93 ms (positive = Agent B faster TTFT)
