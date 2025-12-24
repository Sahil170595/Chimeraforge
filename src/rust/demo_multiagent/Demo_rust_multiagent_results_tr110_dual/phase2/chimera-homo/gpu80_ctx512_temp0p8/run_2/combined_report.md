# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.72s
- Sequential Estimate: 24.62s
- Speedup: 1.79x
- Efficiency: 89.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.19 tok/s
- TTFT: 302.81 ms
- Total Duration: 10904.66 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.21 tok/s
- TTFT: 306.96 ms
- Total Duration: 13717.68 ms

## Delta (B - A)
- Throughput Δ: +14.02 tok/s
- TTFT Δ: -4.15 ms (positive = Agent B faster TTFT)
