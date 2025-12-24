# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.45s
- Sequential Estimate: 22.38s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.71 tok/s
- TTFT: 629.40 ms
- Total Duration: 9930.67 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.50 tok/s
- TTFT: 567.91 ms
- Total Duration: 12451.26 ms

## Delta (B - A)
- Throughput Δ: +15.78 tok/s
- TTFT Δ: +61.50 ms (positive = Agent B faster TTFT)
