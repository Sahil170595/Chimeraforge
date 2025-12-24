# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.46s
- Sequential Estimate: 22.56s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.36 tok/s
- TTFT: 674.98 ms
- Total Duration: 10101.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.70 tok/s
- TTFT: 564.36 ms
- Total Duration: 12462.10 ms

## Delta (B - A)
- Throughput Δ: +15.34 tok/s
- TTFT Δ: +110.63 ms (positive = Agent B faster TTFT)
