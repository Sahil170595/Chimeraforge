# Rust Multi-Agent Report – Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 118.81s
- Sequential Estimate: 213.72s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.02 tok/s
- TTFT: 331.13 ms
- Total Duration: 118810.00 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 23.96 tok/s
- TTFT: 272.63 ms
- Total Duration: 94911.55 ms

## Delta (B - A)
- Throughput Δ: -16.06 tok/s
- TTFT Δ: +58.50 ms (positive = Agent B faster TTFT)
