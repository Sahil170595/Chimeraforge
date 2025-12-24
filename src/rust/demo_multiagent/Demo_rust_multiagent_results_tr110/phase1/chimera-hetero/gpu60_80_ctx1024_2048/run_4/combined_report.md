# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.87s
- Sequential Estimate: 17.80s
- Speedup: 1.64x
- Efficiency: 81.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.07 tok/s
- TTFT: 3360.44 ms
- Total Duration: 6928.86 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 96.90 tok/s
- TTFT: 10095.59 ms
- Total Duration: 10867.24 ms

## Delta (B - A)
- Throughput Δ: -4.17 tok/s
- TTFT Δ: -6735.15 ms (positive = Agent B faster TTFT)
