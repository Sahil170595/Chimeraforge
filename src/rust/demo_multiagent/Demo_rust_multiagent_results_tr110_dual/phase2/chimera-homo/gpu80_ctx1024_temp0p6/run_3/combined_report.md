# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.64s
- Sequential Estimate: 23.62s
- Speedup: 1.87x
- Efficiency: 93.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.05 tok/s
- TTFT: 285.55 ms
- Total Duration: 10981.62 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 49.90 tok/s
- TTFT: 321.26 ms
- Total Duration: 12637.03 ms

## Delta (B - A)
- Throughput Δ: +8.85 tok/s
- TTFT Δ: -35.71 ms (positive = Agent B faster TTFT)
