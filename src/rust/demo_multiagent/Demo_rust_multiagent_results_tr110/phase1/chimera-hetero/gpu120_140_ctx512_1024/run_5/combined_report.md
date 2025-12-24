# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.89s
- Sequential Estimate: 18.08s
- Speedup: 1.30x
- Efficiency: 65.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.54 tok/s
- TTFT: 209.24 ms
- Total Duration: 4191.41 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.08 tok/s
- TTFT: 7415.38 ms
- Total Duration: 13892.20 ms

## Delta (B - A)
- Throughput Δ: -0.45 tok/s
- TTFT Δ: -7206.14 ms (positive = Agent B faster TTFT)
