# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.10s
- Sequential Estimate: 17.80s
- Speedup: 1.60x
- Efficiency: 80.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.33 tok/s
- TTFT: 6733.61 ms
- Total Duration: 11097.70 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.77 tok/s
- TTFT: 208.99 ms
- Total Duration: 6702.88 ms

## Delta (B - A)
- Throughput Δ: -0.56 tok/s
- TTFT Δ: +6524.62 ms (positive = Agent B faster TTFT)
