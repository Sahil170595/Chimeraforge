# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.43s
- Sequential Estimate: 24.78s
- Speedup: 1.85x
- Efficiency: 92.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.28 tok/s
- TTFT: 279.34 ms
- Total Duration: 11354.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.80 tok/s
- TTFT: 304.71 ms
- Total Duration: 13428.78 ms

## Delta (B - A)
- Throughput Δ: +10.52 tok/s
- TTFT Δ: -25.38 ms (positive = Agent B faster TTFT)
