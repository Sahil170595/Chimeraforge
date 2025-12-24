# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.70s
- Sequential Estimate: 21.19s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.58 tok/s
- TTFT: 912.70 ms
- Total Duration: 9488.84 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.01 tok/s
- TTFT: 649.57 ms
- Total Duration: 11701.45 ms

## Delta (B - A)
- Throughput Δ: +15.42 tok/s
- TTFT Δ: +263.13 ms (positive = Agent B faster TTFT)
