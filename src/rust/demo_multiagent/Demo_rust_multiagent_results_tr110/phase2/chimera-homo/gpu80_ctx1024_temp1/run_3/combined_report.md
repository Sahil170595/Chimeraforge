# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.32s
- Sequential Estimate: 15.86s
- Speedup: 1.40x
- Efficiency: 70.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.62 tok/s
- TTFT: 206.89 ms
- Total Duration: 4538.18 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.13 tok/s
- TTFT: 4568.77 ms
- Total Duration: 11323.33 ms

## Delta (B - A)
- Throughput Δ: -1.49 tok/s
- TTFT Δ: -4361.88 ms (positive = Agent B faster TTFT)
