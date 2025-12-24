# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.74s
- Sequential Estimate: 15.81s
- Speedup: 1.62x
- Efficiency: 81.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.86 tok/s
- TTFT: 6093.55 ms
- Total Duration: 9744.55 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.56 tok/s
- TTFT: 183.35 ms
- Total Duration: 6064.95 ms

## Delta (B - A)
- Throughput Δ: +0.70 tok/s
- TTFT Δ: +5910.20 ms (positive = Agent B faster TTFT)
