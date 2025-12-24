# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.69s
- Sequential Estimate: 22.90s
- Speedup: 1.80x
- Efficiency: 90.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.96 tok/s
- TTFT: 214.66 ms
- Total Duration: 10211.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.75 tok/s
- TTFT: 345.49 ms
- Total Duration: 12693.03 ms

## Delta (B - A)
- Throughput Δ: +12.79 tok/s
- TTFT Δ: -130.82 ms (positive = Agent B faster TTFT)
