# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.92s
- Sequential Estimate: 13.93s
- Speedup: 1.40x
- Efficiency: 70.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.18 tok/s
- TTFT: 232.24 ms
- Total Duration: 4007.94 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.97 tok/s
- TTFT: 4038.74 ms
- Total Duration: 9918.74 ms

## Delta (B - A)
- Throughput Δ: -0.20 tok/s
- TTFT Δ: -3806.50 ms (positive = Agent B faster TTFT)
