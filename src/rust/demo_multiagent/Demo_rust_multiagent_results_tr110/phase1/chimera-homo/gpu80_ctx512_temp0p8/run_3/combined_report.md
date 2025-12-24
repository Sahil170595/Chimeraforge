# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.36s
- Sequential Estimate: 14.25s
- Speedup: 1.38x
- Efficiency: 68.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.20 tok/s
- TTFT: 217.75 ms
- Total Duration: 3892.85 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.55 tok/s
- TTFT: 3925.01 ms
- Total Duration: 10361.92 ms

## Delta (B - A)
- Throughput Δ: -0.65 tok/s
- TTFT Δ: -3707.27 ms (positive = Agent B faster TTFT)
