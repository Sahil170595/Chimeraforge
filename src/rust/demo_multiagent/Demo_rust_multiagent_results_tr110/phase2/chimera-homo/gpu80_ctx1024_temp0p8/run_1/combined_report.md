# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.33s
- Sequential Estimate: 16.96s
- Speedup: 1.64x
- Efficiency: 82.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.97 tok/s
- TTFT: 6662.94 ms
- Total Duration: 10327.07 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.29 tok/s
- TTFT: 256.13 ms
- Total Duration: 6629.98 ms

## Delta (B - A)
- Throughput Δ: +0.32 tok/s
- TTFT Δ: +6406.81 ms (positive = Agent B faster TTFT)
