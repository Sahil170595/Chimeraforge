# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.22s
- Sequential Estimate: 21.78s
- Speedup: 1.78x
- Efficiency: 89.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.19 tok/s
- TTFT: 279.18 ms
- Total Duration: 9564.07 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.71 tok/s
- TTFT: 309.52 ms
- Total Duration: 12217.67 ms

## Delta (B - A)
- Throughput Δ: +15.52 tok/s
- TTFT Δ: -30.34 ms (positive = Agent B faster TTFT)
