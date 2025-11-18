# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.09s
- Sequential Estimate: 111.96s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.57 tok/s
- TTFT: 498.31 ms
- Total Duration: 56059.37 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.74 tok/s
- TTFT: 668.31 ms
- Total Duration: 55839.03 ms

## Delta (B - A)
- Throughput Δ: +0.17 tok/s
- TTFT Δ: -170.00 ms (positive = Agent B faster TTFT)
