# Rust Multi-Agent Report – Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.61s
- Sequential Estimate: 112.93s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.53 tok/s
- TTFT: 511.41 ms
- Total Duration: 56317.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.70 tok/s
- TTFT: 413.44 ms
- Total Duration: 56608.72 ms

## Delta (B - A)
- Throughput Δ: +0.17 tok/s
- TTFT Δ: +97.97 ms (positive = Agent B faster TTFT)
