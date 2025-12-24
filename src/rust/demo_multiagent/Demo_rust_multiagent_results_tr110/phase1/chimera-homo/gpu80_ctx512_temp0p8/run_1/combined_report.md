# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.07s
- Sequential Estimate: 24.60s
- Speedup: 1.75x
- Efficiency: 87.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.91 tok/s
- TTFT: 10552.85 ms
- Total Duration: 14071.80 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.94 tok/s
- TTFT: 3604.67 ms
- Total Duration: 10524.28 ms

## Delta (B - A)
- Throughput Δ: -1.98 tok/s
- TTFT Δ: +6948.18 ms (positive = Agent B faster TTFT)
