# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 66.92s
- Sequential Estimate: 133.43s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.69 tok/s
- TTFT: 5291.06 ms
- Total Duration: 66866.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.15 tok/s
- TTFT: 5304.39 ms
- Total Duration: 66452.45 ms

## Delta (B - A)
- Throughput Δ: -0.54 tok/s
- TTFT Δ: -13.32 ms (positive = Agent B faster TTFT)
