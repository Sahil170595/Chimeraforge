# Rust Multi-Agent Report – Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 184.98s
- Sequential Estimate: 356.56s
- Speedup: 1.93x
- Efficiency: 96.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 25.14 tok/s
- TTFT: 237.97 ms
- Total Duration: 184976.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 22.27 tok/s
- TTFT: 264.01 ms
- Total Duration: 171584.07 ms

## Delta (B - A)
- Throughput Δ: -2.88 tok/s
- TTFT Δ: -26.04 ms (positive = Agent B faster TTFT)
