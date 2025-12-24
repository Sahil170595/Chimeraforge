# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.36s
- Sequential Estimate: 24.34s
- Speedup: 1.82x
- Efficiency: 91.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.93 tok/s
- TTFT: 884.07 ms
- Total Duration: 10986.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.06 tok/s
- TTFT: 664.48 ms
- Total Duration: 13356.93 ms

## Delta (B - A)
- Throughput Δ: +14.13 tok/s
- TTFT Δ: +219.59 ms (positive = Agent B faster TTFT)
