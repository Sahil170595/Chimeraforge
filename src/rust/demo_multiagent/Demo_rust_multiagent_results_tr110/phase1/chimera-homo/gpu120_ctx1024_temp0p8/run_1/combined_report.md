# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.21s
- Sequential Estimate: 17.92s
- Speedup: 1.60x
- Efficiency: 79.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.09 tok/s
- TTFT: 6735.44 ms
- Total Duration: 11212.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.62 tok/s
- TTFT: 227.51 ms
- Total Duration: 6708.65 ms

## Delta (B - A)
- Throughput Δ: -0.47 tok/s
- TTFT Δ: +6507.94 ms (positive = Agent B faster TTFT)
