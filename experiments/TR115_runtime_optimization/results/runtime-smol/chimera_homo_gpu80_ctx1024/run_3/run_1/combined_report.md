# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.27s
- Sequential Estimate: 22.24s
- Speedup: 1.81x
- Efficiency: 90.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.68 tok/s
- TTFT: 714.51 ms
- Total Duration: 9978.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.74 tok/s
- TTFT: 576.91 ms
- Total Duration: 12265.79 ms

## Delta (B - A)
- Throughput Δ: +15.06 tok/s
- TTFT Δ: +137.60 ms (positive = Agent B faster TTFT)
