# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.71s
- Sequential Estimate: 22.74s
- Speedup: 1.79x
- Efficiency: 89.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.27 tok/s
- TTFT: 282.20 ms
- Total Duration: 10026.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.81 tok/s
- TTFT: 319.92 ms
- Total Duration: 12710.54 ms

## Delta (B - A)
- Throughput Δ: +14.54 tok/s
- TTFT Δ: -37.72 ms (positive = Agent B faster TTFT)
