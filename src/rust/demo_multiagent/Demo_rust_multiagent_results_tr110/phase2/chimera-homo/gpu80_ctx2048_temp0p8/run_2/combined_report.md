# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.68s
- Sequential Estimate: 16.99s
- Speedup: 1.59x
- Efficiency: 79.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.87 tok/s
- TTFT: 6338.45 ms
- Total Duration: 10682.84 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.60 tok/s
- TTFT: 202.00 ms
- Total Duration: 6311.48 ms

## Delta (B - A)
- Throughput Δ: -0.27 tok/s
- TTFT Δ: +6136.45 ms (positive = Agent B faster TTFT)
