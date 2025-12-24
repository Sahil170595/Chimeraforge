# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.73s
- Sequential Estimate: 15.74s
- Speedup: 1.62x
- Efficiency: 80.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.63 tok/s
- TTFT: 6042.70 ms
- Total Duration: 9726.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.16 tok/s
- TTFT: 197.18 ms
- Total Duration: 6014.50 ms

## Delta (B - A)
- Throughput Δ: -0.46 tok/s
- TTFT Δ: +5845.51 ms (positive = Agent B faster TTFT)
