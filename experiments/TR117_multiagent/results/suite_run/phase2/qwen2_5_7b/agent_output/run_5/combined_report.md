# Rust Multi-Agent Report – Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 86.13s
- Sequential Estimate: 166.20s
- Speedup: 1.93x
- Efficiency: 96.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 24.99 tok/s
- TTFT: 299.13 ms
- Total Duration: 86126.43 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 21.99 tok/s
- TTFT: 283.39 ms
- Total Duration: 80071.35 ms

## Delta (B - A)
- Throughput Δ: -3.00 tok/s
- TTFT Δ: +15.75 ms (positive = Agent B faster TTFT)
