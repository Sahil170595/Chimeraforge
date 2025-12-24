# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.57s
- Sequential Estimate: 20.43s
- Speedup: 1.51x
- Efficiency: 75.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.98 tok/s
- TTFT: 3403.44 ms
- Total Duration: 6862.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.31 tok/s
- TTFT: 6895.87 ms
- Total Duration: 13568.30 ms

## Delta (B - A)
- Throughput Δ: +0.33 tok/s
- TTFT Δ: -3492.42 ms (positive = Agent B faster TTFT)
