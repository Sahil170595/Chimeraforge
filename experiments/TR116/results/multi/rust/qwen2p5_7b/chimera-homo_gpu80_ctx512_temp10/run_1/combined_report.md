# Rust Multi-Agent Report – Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 118.09s
- Sequential Estimate: 226.55s
- Speedup: 1.92x
- Efficiency: 95.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 27.83 tok/s
- TTFT: 1796.22 ms
- Total Duration: 118086.80 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 24.18 tok/s
- TTFT: 2264.46 ms
- Total Duration: 108455.67 ms

## Delta (B - A)
- Throughput Δ: -3.65 tok/s
- TTFT Δ: -468.24 ms (positive = Agent B faster TTFT)
