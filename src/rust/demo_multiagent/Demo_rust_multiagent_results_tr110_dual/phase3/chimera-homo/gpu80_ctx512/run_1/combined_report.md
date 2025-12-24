# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.77s
- Sequential Estimate: 22.65s
- Speedup: 1.77x
- Efficiency: 88.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.11 tok/s
- TTFT: 278.78 ms
- Total Duration: 9881.24 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.76 tok/s
- TTFT: 324.03 ms
- Total Duration: 12767.90 ms

## Delta (B - A)
- Throughput Δ: +15.65 tok/s
- TTFT Δ: -45.25 ms (positive = Agent B faster TTFT)
