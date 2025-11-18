# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.39s
- Sequential Estimate: 114.35s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.71 tok/s
- TTFT: 713.67 ms
- Total Duration: 56937.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.42 tok/s
- TTFT: 815.08 ms
- Total Duration: 57355.77 ms

## Delta (B - A)
- Throughput Δ: +0.71 tok/s
- TTFT Δ: -101.41 ms (positive = Agent B faster TTFT)
