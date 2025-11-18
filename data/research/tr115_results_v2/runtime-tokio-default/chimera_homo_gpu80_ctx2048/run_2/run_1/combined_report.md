# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.15s
- Sequential Estimate: 109.64s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.10 tok/s
- TTFT: 663.55 ms
- Total Duration: 54474.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.73 tok/s
- TTFT: 818.61 ms
- Total Duration: 55134.11 ms

## Delta (B - A)
- Throughput Δ: +0.63 tok/s
- TTFT Δ: -155.06 ms (positive = Agent B faster TTFT)
