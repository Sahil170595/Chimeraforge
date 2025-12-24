# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.93s
- Sequential Estimate: 21.43s
- Speedup: 1.80x
- Efficiency: 89.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.53 tok/s
- TTFT: 686.61 ms
- Total Duration: 9504.18 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 59.02 tok/s
- TTFT: 582.73 ms
- Total Duration: 11926.94 ms

## Delta (B - A)
- Throughput Δ: +16.49 tok/s
- TTFT Δ: +103.87 ms (positive = Agent B faster TTFT)
