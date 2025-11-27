# Rust Multi-Agent Report – Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 33.93s
- Sequential Estimate: 67.22s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 27.82 tok/s
- TTFT: 2210.51 ms
- Total Duration: 33286.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 27.11 tok/s
- TTFT: 2698.31 ms
- Total Duration: 33933.21 ms

## Delta (B - A)
- Throughput Δ: -0.71 tok/s
- TTFT Δ: -487.80 ms (positive = Agent B faster TTFT)
