# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.93s
- Sequential Estimate: 17.88s
- Speedup: 1.64x
- Efficiency: 81.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.58 tok/s
- TTFT: 6980.99 ms
- Total Duration: 10930.38 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.16 tok/s
- TTFT: 288.95 ms
- Total Duration: 6951.69 ms

## Delta (B - A)
- Throughput Δ: -0.41 tok/s
- TTFT Δ: +6692.03 ms (positive = Agent B faster TTFT)
