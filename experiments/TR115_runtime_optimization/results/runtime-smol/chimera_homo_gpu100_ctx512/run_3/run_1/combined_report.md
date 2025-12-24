# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.51s
- Sequential Estimate: 23.42s
- Speedup: 1.87x
- Efficiency: 93.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.49 tok/s
- TTFT: 685.61 ms
- Total Duration: 10915.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.81 tok/s
- TTFT: 579.54 ms
- Total Duration: 12509.06 ms

## Delta (B - A)
- Throughput Δ: +10.32 tok/s
- TTFT Δ: +106.07 ms (positive = Agent B faster TTFT)
