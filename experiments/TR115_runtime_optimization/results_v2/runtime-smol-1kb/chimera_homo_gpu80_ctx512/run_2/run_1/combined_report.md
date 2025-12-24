# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.44s
- Sequential Estimate: 105.40s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 1018.89 ms
- Total Duration: 51930.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.05 tok/s
- TTFT: 1061.60 ms
- Total Duration: 53402.84 ms

## Delta (B - A)
- Throughput Δ: +1.92 tok/s
- TTFT Δ: -42.71 ms (positive = Agent B faster TTFT)
