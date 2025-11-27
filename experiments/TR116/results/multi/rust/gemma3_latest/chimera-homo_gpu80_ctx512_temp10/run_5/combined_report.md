# Rust Multi-Agent Report – Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 51.26s
- Sequential Estimate: 100.74s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.93 tok/s
- TTFT: 609.75 ms
- Total Duration: 49475.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.20 tok/s
- TTFT: 334.78 ms
- Total Duration: 51264.26 ms

## Delta (B - A)
- Throughput Δ: +2.27 tok/s
- TTFT Δ: +274.96 ms (positive = Agent B faster TTFT)
