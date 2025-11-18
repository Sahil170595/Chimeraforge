# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.59s
- Sequential Estimate: 110.46s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.96 tok/s
- TTFT: 653.43 ms
- Total Duration: 54842.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.89 tok/s
- TTFT: 657.74 ms
- Total Duration: 55563.54 ms

## Delta (B - A)
- Throughput Δ: +0.93 tok/s
- TTFT Δ: -4.31 ms (positive = Agent B faster TTFT)
