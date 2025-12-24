# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.73s
- Sequential Estimate: 17.30s
- Speedup: 1.36x
- Efficiency: 67.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.12 tok/s
- TTFT: 201.87 ms
- Total Duration: 4568.95 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.41 tok/s
- TTFT: 4598.00 ms
- Total Duration: 12731.17 ms

## Delta (B - A)
- Throughput Δ: -0.71 tok/s
- TTFT Δ: -4396.13 ms (positive = Agent B faster TTFT)
