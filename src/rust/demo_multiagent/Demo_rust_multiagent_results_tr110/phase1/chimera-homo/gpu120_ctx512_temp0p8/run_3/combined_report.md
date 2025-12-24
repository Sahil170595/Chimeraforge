# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.44s
- Sequential Estimate: 18.78s
- Speedup: 1.64x
- Efficiency: 82.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.65 tok/s
- TTFT: 7372.27 ms
- Total Duration: 11438.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.68 tok/s
- TTFT: 207.08 ms
- Total Duration: 7343.72 ms

## Delta (B - A)
- Throughput Δ: +0.03 tok/s
- TTFT Δ: +7165.19 ms (positive = Agent B faster TTFT)
