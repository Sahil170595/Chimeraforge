# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.63s
- Sequential Estimate: 22.90s
- Speedup: 1.81x
- Efficiency: 90.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.07 tok/s
- TTFT: 816.06 ms
- Total Duration: 10268.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.50 tok/s
- TTFT: 617.17 ms
- Total Duration: 12630.84 ms

## Delta (B - A)
- Throughput Δ: +14.43 tok/s
- TTFT Δ: +198.89 ms (positive = Agent B faster TTFT)
