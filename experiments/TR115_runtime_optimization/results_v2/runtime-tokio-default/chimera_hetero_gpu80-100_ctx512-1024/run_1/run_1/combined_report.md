# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 62.28s
- Sequential Estimate: 124.27s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.81 tok/s
- TTFT: 3374.98 ms
- Total Duration: 61969.43 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.71 tok/s
- TTFT: 3684.09 ms
- Total Duration: 62253.75 ms

## Delta (B - A)
- Throughput Δ: -0.09 tok/s
- TTFT Δ: -309.11 ms (positive = Agent B faster TTFT)
