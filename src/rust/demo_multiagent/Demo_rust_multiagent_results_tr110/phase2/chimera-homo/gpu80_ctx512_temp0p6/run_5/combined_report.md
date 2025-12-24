# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.34s
- Sequential Estimate: 16.86s
- Speedup: 1.63x
- Efficiency: 81.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.70 tok/s
- TTFT: 6541.30 ms
- Total Duration: 10341.84 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.31 tok/s
- TTFT: 191.63 ms
- Total Duration: 6513.69 ms

## Delta (B - A)
- Throughput Δ: -1.40 tok/s
- TTFT Δ: +6349.67 ms (positive = Agent B faster TTFT)
