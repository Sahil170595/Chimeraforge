# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.99s
- Sequential Estimate: 24.64s
- Speedup: 1.90x
- Efficiency: 94.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.14 tok/s
- TTFT: 299.93 ms
- Total Duration: 11646.69 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 48.12 tok/s
- TTFT: 295.80 ms
- Total Duration: 12989.32 ms

## Delta (B - A)
- Throughput Δ: +6.98 tok/s
- TTFT Δ: +4.13 ms (positive = Agent B faster TTFT)
