# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 18.36s
- Sequential Estimate: 34.15s
- Speedup: 1.86x
- Efficiency: 93.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.60 tok/s
- TTFT: 6307.88 ms
- Total Duration: 15796.47 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.43 tok/s
- TTFT: 6343.55 ms
- Total Duration: 18355.72 ms

## Delta (B - A)
- Throughput Δ: +15.83 tok/s
- TTFT Δ: -35.67 ms (positive = Agent B faster TTFT)
