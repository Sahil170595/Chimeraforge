# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.53s
- Sequential Estimate: 20.67s
- Speedup: 1.79x
- Efficiency: 89.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.85 tok/s
- TTFT: 240.43 ms
- Total Duration: 9136.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.10 tok/s
- TTFT: 295.57 ms
- Total Duration: 11534.63 ms

## Delta (B - A)
- Throughput Δ: +14.25 tok/s
- TTFT Δ: -55.14 ms (positive = Agent B faster TTFT)
