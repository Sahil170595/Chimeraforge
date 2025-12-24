# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.35s
- Sequential Estimate: 25.47s
- Speedup: 1.91x
- Efficiency: 95.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.70 tok/s
- TTFT: 718.22 ms
- Total Duration: 12115.42 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 47.66 tok/s
- TTFT: 603.77 ms
- Total Duration: 13351.39 ms

## Delta (B - A)
- Throughput Δ: +6.96 tok/s
- TTFT Δ: +114.45 ms (positive = Agent B faster TTFT)
