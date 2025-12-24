# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.12s
- Sequential Estimate: 23.91s
- Speedup: 1.82x
- Efficiency: 91.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.50 tok/s
- TTFT: 674.06 ms
- Total Duration: 10795.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.53 tok/s
- TTFT: 593.94 ms
- Total Duration: 13119.78 ms

## Delta (B - A)
- Throughput Δ: +14.02 tok/s
- TTFT Δ: +80.12 ms (positive = Agent B faster TTFT)
