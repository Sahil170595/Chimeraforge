# Rust Multi-Agent Report – Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 26.48s
- Sequential Estimate: 51.65s
- Speedup: 1.95x
- Efficiency: 97.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 28.77 tok/s
- TTFT: 358.30 ms
- Total Duration: 26480.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 25.97 tok/s
- TTFT: 282.67 ms
- Total Duration: 25169.38 ms

## Delta (B - A)
- Throughput Δ: -2.79 tok/s
- TTFT Δ: +75.64 ms (positive = Agent B faster TTFT)
