# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.42s
- Sequential Estimate: 17.05s
- Speedup: 1.64x
- Efficiency: 81.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.09 tok/s
- TTFT: 6661.81 ms
- Total Duration: 10420.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.49 tok/s
- TTFT: 215.61 ms
- Total Duration: 6633.48 ms

## Delta (B - A)
- Throughput Δ: -0.60 tok/s
- TTFT Δ: +6446.20 ms (positive = Agent B faster TTFT)
