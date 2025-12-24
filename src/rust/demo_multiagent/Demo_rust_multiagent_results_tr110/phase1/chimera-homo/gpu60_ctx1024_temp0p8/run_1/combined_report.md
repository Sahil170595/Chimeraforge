# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.12s
- Sequential Estimate: 16.19s
- Speedup: 1.60x
- Efficiency: 80.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.44 tok/s
- TTFT: 6098.44 ms
- Total Duration: 10122.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.28 tok/s
- TTFT: 231.64 ms
- Total Duration: 6069.90 ms

## Delta (B - A)
- Throughput Δ: -0.16 tok/s
- TTFT Δ: +5866.79 ms (positive = Agent B faster TTFT)
