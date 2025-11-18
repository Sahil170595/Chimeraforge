# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.51s
- Sequential Estimate: 114.83s
- Speedup: 1.96x
- Efficiency: 98.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 46.17 tok/s
- TTFT: 3775.97 ms
- Total Duration: 58475.85 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.71 tok/s
- TTFT: 3480.26 ms
- Total Duration: 56281.46 ms

## Delta (B - A)
- Throughput Δ: -2.46 tok/s
- TTFT Δ: +295.71 ms (positive = Agent B faster TTFT)
