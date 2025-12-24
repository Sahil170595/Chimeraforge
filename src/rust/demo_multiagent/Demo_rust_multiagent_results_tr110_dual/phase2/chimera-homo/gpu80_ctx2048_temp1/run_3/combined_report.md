# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.02s
- Sequential Estimate: 23.48s
- Speedup: 1.80x
- Efficiency: 90.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.91 tok/s
- TTFT: 210.24 ms
- Total Duration: 10457.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.62 tok/s
- TTFT: 368.11 ms
- Total Duration: 13022.32 ms

## Delta (B - A)
- Throughput Δ: +12.71 tok/s
- TTFT Δ: -157.86 ms (positive = Agent B faster TTFT)
