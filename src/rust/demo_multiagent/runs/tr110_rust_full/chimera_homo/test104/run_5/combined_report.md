# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.65s
- Sequential Estimate: 119.23s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.03 tok/s
- TTFT: 659.12 ms
- Total Duration: 59599.30 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.96 tok/s
- TTFT: 652.65 ms
- Total Duration: 59524.58 ms

## Delta (B - A)
- Throughput Δ: -0.07 tok/s
- TTFT Δ: +6.47 ms (positive = Agent B faster TTFT)
