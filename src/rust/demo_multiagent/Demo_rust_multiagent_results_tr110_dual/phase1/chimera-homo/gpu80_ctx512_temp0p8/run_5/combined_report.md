# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.56s
- Sequential Estimate: 22.93s
- Speedup: 1.83x
- Efficiency: 91.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.42 tok/s
- TTFT: 267.92 ms
- Total Duration: 10367.41 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.55 tok/s
- TTFT: 312.74 ms
- Total Duration: 12564.52 ms

## Delta (B - A)
- Throughput Δ: +12.13 tok/s
- TTFT Δ: -44.82 ms (positive = Agent B faster TTFT)
